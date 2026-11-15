import os

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from affiche import shops
from affiche.db import write_tx
from affiche.posters.auth import PASSWORDS, identifier_key
from test_db import engine  # noqa: F401

HASH = PASSWORDS.hash(os.urandom(12).hex())


@pytest.mark.parametrize("typed, key", [
    ("originalphone", "originalphone"), ("Original Phone", "originalphone"), ("ORIGINAL-PHONE", "originalphone"),
    ("  original.phone ! ", "originalphone"), ("Óriginal Phöne", "originalphone"), ("ｏｒｉｇｉｎａｌｐｈｏｎｅ", "originalphone"),
    # A phone number in the written form the operator chose; another form is another identifier.
    ("034 12 345 67", "0341234567"), ("+261 34 12 345 67", "261341234567"),
    ("---", ""), ("", ""), ("ß", ""), ("a" * 70, "a" * 64)])
def test_case_accents_spaces_and_punctuation_do_not_count_in_an_identifier(typed, key):
    assert identifier_key(typed) == key


def test_a_shop_is_created_inside_the_callers_transaction_with_its_identifier_normalised(engine):
    with write_tx(engine) as conn:
        shop = shops.create_shop(conn, "Boutique Deux", " Boutique Deux ", HASH)
        assert tuple(conn.exec_driver_sql(
            "SELECT identifier, name, state, password_hash, revision, created_at = updated_at FROM shop_profile WHERE id=?",
            (shop,)).one()) == ("boutiquedeux", "Boutique Deux", "active", HASH, 1, 1)
    assert shop == 2
    for taken in ("boutique deux", "BOUTIQUE-DEUX", "Boutiqué Deux", "originalphone"):
        with pytest.raises(IntegrityError), write_tx(engine) as conn:
            shops.create_shop(conn, taken, None, HASH)
    for bad in ("ab", "x" * 33, "- -"):
        with pytest.raises(ValueError, match="3 to 32"), write_tx(engine) as conn:
            shops.create_shop(conn, bad, None, HASH)
    with pytest.raises(ValidationError), write_tx(engine) as conn:  # the profile form's own rule
        shops.create_shop(conn, "troisieme", "x" * 161, HASH)
    with pytest.raises(IntegrityError), write_tx(engine) as conn:  # never a password in plain text
        shops.create_shop(conn, "troisieme", None, "not-a-hash")
    with pytest.raises(RuntimeError), write_tx(engine) as conn:  # the caller's rollback undoes it
        shops.create_shop(conn, "troisieme", None, HASH)
        raise RuntimeError
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT id, identifier FROM shop_profile ORDER BY id").all() == [
            (1, "originalphone"), (2, "boutiquedeux")]
