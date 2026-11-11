import copy
import hashlib
import io
import itertools
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from alembic import command
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import exc

from affiche import assets
from affiche.db import make_engine, migrate, write_tx
from affiche.posters import store
from affiche.posters.models import (
    MAX_PRICE, CopyCreation, Document, NewCreation, Offer, ProductInput, Profile, format_price, parse_price,
)
from test_db import engine  # noqa: F401


def key():
    return str(uuid4())


def photo(fmt="PNG", colour="navy"):
    out = io.BytesIO()
    Image.new("RGBA" if fmt == "PNG" else "RGB", (40, 80), colour).save(out, fmt)
    return out.getvalue()


@pytest.fixture
def input_id(engine, tmp_path):
    uploaded = store.upload(engine, tmp_path, 1, photo(), "original")
    return store.create_input(engine, tmp_path, 1, key(), ProductInput(
        name="JBL", variant="Conforme à la photo", photo_assets=[uploaded["asset"]]))[1]["id"]


def draft(engine, tmp_path, input_id, include=None):
    request = NewCreation(input_id=input_id, offer=Offer(title="Une enceinte", price_ar=899000),
                          brand_selection=include or {"logo": False, "shop_name": False, "contact": False})
    return store.create_creation(engine, tmp_path, 1, key(), request)[1]


def latest(engine, id, revision=None):
    with engine.connect() as conn:
        return store.get_creation(conn, 1, id, revision)


@pytest.mark.parametrize("value,expected", [("0", 0), ("899000", 899000), ("899 000", 899000),
    ("9\u00a0007\u202f199\u202f254\u202f740\u202f991", MAX_PRICE)])
def test_integer_price(value, expected):
    assert parse_price(value) == expected
    assert parse_price(format_price(expected).removesuffix(" Ar")) == expected
    assert format_price(0) == "0 Ar"


@pytest.mark.parametrize("value", [True, 10.0, -1, "1.5", "1e3", "899,000", "89 90", " 12", "12 Ar", "", "١٢", str(MAX_PRICE+1)])
def test_price_parser_refuses_ambiguous_input(value):
    with pytest.raises(ValueError):
        parse_price(value)


@pytest.mark.parametrize("value", [True, 1.0, -1, "1", MAX_PRICE+1])
def test_offer_price_is_strict(value):
    with pytest.raises(ValidationError):
        Offer(title="JBL", price_ar=value)


def test_intake_preserves_original_alpha_hash_and_access(engine, tmp_path):
    data = photo(colour=(10, 20, 30, 50))
    first = store.upload(engine, tmp_path, 1, data, "logo")
    original = store.upload(engine, tmp_path, 1, data, "original")
    assert first["asset"] == hashlib.sha256(data).hexdigest() == original["asset"]
    assert first["warnings"] == [] and original["warnings"] == ["low_resolution"]
    with engine.connect() as conn:
        assert assets.load(conn, tmp_path, first["asset"]) == data
        assert conn.exec_driver_sql("SELECT count(*) FROM assets").scalar_one() == 1
        assert conn.exec_driver_sql("SELECT count(*) FROM asset_access").scalar_one() == 2


def test_invalid_uploads_record_nothing(engine, tmp_path, monkeypatch):
    for data in (b"not an image", photo("GIF"), photo()[:50]):
        with pytest.raises(store.Refused):
            store.upload(engine, tmp_path, 1, data, "original")
    monkeypatch.setattr(store, "MAX_UPLOAD_PIXELS", 100)
    with pytest.raises(store.Refused, match="too_large"):
        store.upload(engine, tmp_path, 1, photo(), "original")
    monkeypatch.setattr(store, "MAX_UPLOAD_BYTES", 1)
    with pytest.raises(store.Refused, match="too_large"):
        store.upload(engine, tmp_path, 1, photo(), "original")
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM assets").scalar_one() == 0


def test_animated_png_rejected(engine, tmp_path):
    out = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(out, "PNG", save_all=True,
        append_images=[Image.new("RGB", (10, 10), "blue")], duration=100)
    with pytest.raises(store.Refused, match="animated_image"):
        store.upload(engine, tmp_path, 1, out.getvalue(), "original")


def test_product_access_and_replacement_are_immutable(engine, tmp_path, input_id):
    with engine.connect() as conn:
        original = store.get_input(conn, 1, input_id)
    request = ProductInput(name="JBL nouvelle photo", variant="Noir", photo_assets=original["photo_assets"],
                           supersedes_id=input_id)
    op = key()
    replacement = store.create_input(engine, tmp_path, 1, op, request)
    assert store.create_input(engine, tmp_path, 1, op, request) == replacement
    assert replacement[1]["product_ref"] == original["product_ref"]
    assert replacement[1]["id"] != input_id
    with engine.connect() as conn:
        assert store.get_input(conn, 1, input_id) == original
    request.photo_assets = ["f" * 64]
    with pytest.raises(store.Refused, match="unknown_asset"):
        store.create_input(engine, tmp_path, 1, key(), request)


@pytest.mark.parametrize("flags", list(itertools.product([False, True], repeat=3)))
def test_every_identity_combination_is_snapshotted(engine, tmp_path, input_id, flags):
    logo = store.upload(engine, tmp_path, 1, photo(), "logo")["asset"]
    store.save_profile(engine, tmp_path, 1, key(), Profile(name="Original Phone Mada", contact="034 00 000 00", logo_asset=logo), 1)
    include = dict(zip(("logo", "shop_name", "contact"), flags, strict=True))
    first = draft(engine, tmp_path, input_id, include)
    store.save_profile(engine, tmp_path, 1, key(), Profile(name="Nouveau nom"), 2)
    saved = latest(engine, first["id"])
    assert saved == first
    assert saved["document"]["brand_snapshot"]["name"] == "Original Phone Mada"
    assert saved["document"]["include"] == include
    roles = {layer["role"] for layer in saved["document"]["formats"]["feed"]["layers"]}
    assert roles == {"title", "price"} | {role for role, enabled in include.items() if enabled}


def test_missing_identity_is_explicit_and_atomic(engine, tmp_path, input_id):
    with pytest.raises(store.Refused, match="missing_brand_field"):
        draft(engine, tmp_path, input_id, {"logo": True, "shop_name": False, "contact": False})
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM creations").scalar_one() == 0


def test_revision_conflict_replay_and_noop(engine, tmp_path, input_id):
    first = draft(engine, tmp_path, input_id)
    document = Document.model_validate(first["document"])
    assert store.save_creation(engine, tmp_path, 1, key(), first["id"], document, 1)[1] == first
    document.offer.price_ar = 799000
    op = key()
    changed = store.save_creation(engine, tmp_path, 1, op, first["id"], document, 1)
    assert changed[1]["revision"] == 2
    assert store.save_creation(engine, tmp_path, 1, op, first["id"], document, 1) == changed
    with pytest.raises(store.Refused, match="revision_conflict") as error:
        store.save_creation(engine, tmp_path, 1, key(), first["id"], document, 1)
    assert error.value.current_revision == 2
    document.offer.price_ar = 1
    with pytest.raises(store.Refused, match="idempotency_reused"):
        store.save_creation(engine, tmp_path, 1, op, first["id"], document, 1)
    assert latest(engine, first["id"], 1)["document"]["offer"]["price_ar"] == 899000
    assert latest(engine, first["id"])["document"]["offer"]["price_ar"] == 799000


def test_concurrent_save_has_exactly_one_winner(engine, tmp_path, input_id):
    first = draft(engine, tmp_path, input_id)
    def save(price):
        document = Document.model_validate(first["document"])
        document.offer.price_ar = price
        try:
            return store.save_creation(engine, tmp_path, 1, key(), first["id"], document, 1)[0]
        except store.Refused as error:
            return error.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, [100, 200])) == [200, 409]
    assert latest(engine, first["id"])["revision"] == 2


def test_failed_save_rolls_back_version_pointer_and_key(engine, tmp_path, input_id, monkeypatch):
    first = draft(engine, tmp_path, input_id)
    document = Document.model_validate(first["document"])
    document.offer.price_ar = 1
    real_insert = store._insert_version
    def fail(*args):
        real_insert(*args)
        raise OSError("disk full")
    op = key()
    with monkeypatch.context() as patch:
        patch.setattr(store, "_insert_version", fail)
        with pytest.raises(OSError):
            store.save_creation(engine, tmp_path, 1, op, first["id"], document, 1)
    assert latest(engine, first["id"]) == first
    assert store.save_creation(engine, tmp_path, 1, op, first["id"], document, 1)[1]["revision"] == 2


def test_copy_and_input_replacement_leave_source_untouched(engine, tmp_path, input_id):
    first = draft(engine, tmp_path, input_id)
    copy_request = CopyCreation(source_revision=1, reason="price_update")
    second = store.copy_creation(engine, tmp_path, 1, key(), first["id"], copy_request)[1]
    assert second["parent_creation_id"] == first["id"] and second["revision"] == 1
    assert second["document"] == first["document"]
    new_photo = store.upload(engine, tmp_path, 1, photo(colour="red"), "original")
    new_input = store.create_input(engine, tmp_path, 1, key(), ProductInput(name="Soundcore", variant="Rouge",
        photo_assets=[new_photo["asset"]]))[1]["id"]
    changed = Document.model_validate(second["document"])
    changed.input_id = new_input
    with pytest.raises(store.Refused, match="input_immutable"):
        store.save_creation(engine, tmp_path, 1, key(), second["id"], changed, 1)
    replaced = store.copy_creation(engine, tmp_path, 1, key(), first["id"],
        CopyCreation(source_revision=1, reason="replace_input", new_input_id=new_input))[1]
    assert replaced["document"]["input_id"] == new_input
    assert latest(engine, first["id"]) == first


@pytest.mark.parametrize("bad", ["extra", "nan", "duplicate", "price_text", "missing_title", "font_url", "boolean_version"])
def test_untrusted_document_properties_rejected(engine, tmp_path, input_id, bad):
    document = copy.deepcopy(draft(engine, tmp_path, input_id)["document"])
    layers = document["formats"]["feed"]["layers"]
    if bad == "extra": document["script"] = "alert(1)"
    if bad == "nan": layers[0]["x"] = float("nan")
    if bad == "duplicate": layers.append(copy.deepcopy(layers[0]))
    if bad == "price_text": layers[1]["text"] = "gratuit"
    if bad == "missing_title": layers.pop(0)
    if bad == "font_url": layers[0]["font_id"] = "https://example.com/font"
    if bad == "boolean_version": document["schema_version"] = True
    with pytest.raises(ValidationError):
        Document.model_validate(document)


def test_new_migration_preserves_legacy_tables(tmp_path, monkeypatch):
    engine = make_engine(tmp_path)
    upgrade = command.upgrade
    try:
        with monkeypatch.context() as patch:
            patch.setattr(command, "upgrade", lambda config, _revision: upgrade(config, "0003"))
            migrate(engine)
        with write_tx(engine) as conn:
            conn.exec_driver_sql("INSERT INTO runs VALUES ('old','gpt-image-2','high','1088x1920',3,'on','now')")
            conn.exec_driver_sql("INSERT INTO run_products VALUES ('old','P1','A','row','JBL','Black','[\"photo\"]')")
            conn.exec_driver_sql("INSERT INTO generation_requests (id,payload_hash,purpose,variant_ref,cycle_no,run_label,"
                "request_json,corrections_applied,owner,status,created_at) VALUES ('req','h','scene','P1',1,'old','{}',0,'cli','succeeded','now')")
            conn.exec_driver_sql("INSERT INTO provider_calls (id,request_id,call_no,provider,model,status,cost_micros,"
                "cost_is_estimate,started_at) VALUES ('paid','req',1,'openai','gpt-image-2','succeeded',512881,0,'now')")
            names = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name!='alembic_version'").scalars().all()
            before = {name: conn.exec_driver_sql(f"SELECT * FROM {name}").all() for name in names}
        migrate(engine)
        migrate(engine)
        with engine.connect() as conn:
            assert {name: conn.exec_driver_sql(f"SELECT * FROM {name}").all() for name in names} == before
            assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
            assert conn.exec_driver_sql("SELECT revision FROM shop_profile").scalar_one() == 1
        with pytest.raises(exc.IntegrityError), write_tx(engine) as conn:
            conn.exec_driver_sql("DELETE FROM shop_profile")
    finally:
        engine.dispose()
