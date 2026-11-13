"""Authenticated HTTP boundary for the pilot. Run with python -m affiche.api."""
import hashlib
import io
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated, Literal
from uuid import uuid4

from PIL import Image
from fastapi import APIRouter, Depends, FastAPI, Header, Path, Query, Request
from fastapi.security import APIKeyCookie
from fastapi.exceptions import RequestValidationError
from pydantic import Field, SecretStr
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response
from starlette.staticfiles import StaticFiles

from affiche import assets
from affiche.config import Settings, load_settings
from affiche.posters import auth, exports, jobs, looks, rendering, store, typography, visuals
from affiche.posters.service import PosterService
from affiche.posters.models import CopyCreation, Document, Id, Model, NewCreation, ProductInput, Profile, Sha
from affiche.runtime import start
from affiche.visuals.admission import spent_micros
from affiche.visuals.gateway import usd_to_micros

log = logging.getLogger(__name__)


# What the owner reads when the server refuses something. Every refusal he can cause has a sentence that says what
# to do; tests/test_api.py fails when a new refusal code has neither a sentence here nor a place in its list of
# codes that only a programming error can produce.
MESSAGES = {
        "title_too_long": "Le titre dépasse 60 caractères : l’IA ne peut pas le dessiner dans l’image. Raccourcissez le titre.",
        "title_unsupported": "Le titre contient un guillemet droit (\") ou un retour à la ligne : l’IA ne peut pas le dessiner. Écrivez par exemple « 32 pouces ».",
        "title_commercial_text": "Le titre contient un mot de prix, de promotion ou de garantie (par exemple « promo », « gratuit », « % », « Ar »). Le prix a son propre champ : retirez ce mot du titre.",
        "contact_unsupported": "Le contact est trop long ou contient un guillemet : l’IA ne peut pas le dessiner. Raccourcissez-le, ou décochez « Dessiner aussi le contact dans l’image ».",
        "invalid_headline": "Ces réglages de texte ne peuvent pas être dessinés ensemble dans l’image. Rechargez la page, puis générez de nouveau.",
        "validation_error": "Une valeur saisie n’est pas acceptée. Marque et sous-titre : 60 caractères au plus, sans guillemet droit, sans mot de prix, de promotion ni de garantie.",
        "invalid_image": "Ce fichier n’est pas une image lisible. Choisissez une photo JPEG, PNG ou WebP.",
        "animated_image": "Les images animées ne sont pas acceptées. Choisissez une photo fixe (JPEG, PNG ou WebP).",
        "unsupported_colour": "Les couleurs de cette image ne sont pas prises en charge (profil d’impression). Enregistrez-la en JPEG ou PNG standard, puis réessayez.",
        "invalid_crop": "Ce cadrage sort de la photo. Ajustez-le et réessayez.",
        "plan_stale": "L’affiche a changé depuis la préparation de cette génération. Relancez « Générer l’affiche ».",
        "headline_stale": "Le titre, le prix ou le contact a changé depuis cette version : ils sont dessinés dans l’image. Générez une nouvelle version.",
        "title_missing": "Le titre dessiné dans l’image ne correspond plus au titre de l’affiche. Générez une nouvelle version, ou remettez le titre d’origine.",
        "price_stale": "Le prix dessiné dans l’image ne correspond plus au prix de l’affiche. Générez une nouvelle version, ou remettez le prix d’origine.",
        "signature_missing": "Le contact dessiné dans l’image ne correspond plus à celui de la boutique. Générez une nouvelle version.",
        "creation_abandoned": "Cette affiche a été retirée de la liste : elle ne peut plus être modifiée. Remettez-la dans la liste depuis « Mes affiches », ou dupliquez-la.",
        "base_not_selected": "Choisissez d’abord la version à ajuster.",
        "review_decided": "Cette version a déjà été approuvée ou refusée. Rechargez la page pour voir son état.",
        "proposal_decided": "Cette proposition a déjà été appliquée ou refusée. Rechargez la page.",
        "effect_decided": "Cet effet a déjà été appliqué ou refusé. Rechargez la page.",
        "unsupported_visual": "Cette version ne peut pas servir à cette action. Choisissez une autre version.",
        "unsupported_font": "Cette police n’est pas disponible pour le fichier final. Choisissez une autre police dans les réglages avancés.",
        "render_invalid": "Le fichier final n’a pas pu être produit correctement. Relancez « Vérifier l’aperçu final ».",
        "render_inputs_changed": "L’affiche a changé pendant la préparation du fichier final. Relancez « Vérifier l’aperçu final ».",
        "layout_not_plannable": "Les éléments choisis ne tiennent pas ensemble sur l’affiche. Décochez un élément de la boutique (logo, nom ou contact) ou raccourcissez le titre.",
        "invalid_plan": "Cette composition n’est pas valable (un élément sort de l’affiche ou en recouvre un autre). Annulez le dernier déplacement et réessayez.",
        "invalid_reference": "L’image de référence choisie n’est plus utilisable. Choisissez-en une autre.",
        "input_changed": "Le produit de cette affiche a changé pendant la génération. Relancez la génération.",
        "provider_unavailable": "Le service d’images n’est pas disponible pour le moment. Réessayez dans quelques minutes.",
        "format_unavailable": "Ce format n’est pas encore disponible : seul le format publication (1080 × 1350) peut être exporté.",
        "unauthenticated": "Connectez-vous pour continuer.", "forbidden_origin": "Origine de la demande refusée.",
        "revision_conflict": "Une version plus récente existe. Vos modifications restent à récupérer.",
        "idempotency_reused": "Cette référence de demande a déjà été utilisée avec un autre contenu.",
        "precondition_required": "La version du document est requise.", "not_found": "Élément introuvable.",
        "too_large": "Fichier trop volumineux. Limite : 10 Mo et 40 millions de pixels.",
        "unsupported_type": "Utilisez une image JPEG, PNG ou WebP fixe.",
        "rate_limited": "Trop de tentatives. Réessayez dans 15 minutes.",
        "storage_unavailable": "Enregistrement indisponible. Conservez vos modifications et réessayez.",
        "scene_unapproved": "Vérifiez et approuvez la fidélité de la scène avant l’export.",
        "layout_invalid": "Un texte ou un élément est coupé. Corrigez les avertissements avant l’export.",
        "preview_stale": "L’affiche a changé. Créez un nouvel aperçu avant de confirmer.",
        "logo_disc_uncovered": "L’image contient un disque prévu pour le logo : replacez le logo dessus ou générez une nouvelle version.",
        "confirmation_incomplete": "Vérifiez tous les points et les avertissements avant de confirmer.",
        "renderer_unavailable": "Le rendu est indisponible. Vérifiez la compilation de l’éditeur et les polices.",
        "render_unavailable": "Le rendu a échoué. Le brouillon et les exports précédents sont conservés.",
        "export_missing": "Ce fichier confirmé est absent ou endommagé. Restaurez-le depuis sa sauvegarde.",
        "unsupported_target": "Sélectionnez le titre ou le prix pour ajuster sa typographie.",
        "stale_proposal": "Le brouillon a changé depuis cette proposition. Demandez un nouvel ajustement.",
        "stale_effect": "Le texte a changé depuis cet effet. Demandez un nouvel effet.",
        "acknowledgement_required": "La photo du produit est petite (moins de 800 px) : l’affiche peut manquer de netteté. Acceptez la qualité réduite pour continuer, ou choisissez une photo plus grande.",
        "content_acknowledgement_required": "Vérifiez et acceptez explicitement le nouveau titre ou prix.",
        "effect_unapproved": "Cet effet doit être approuvé avant de l’utiliser.",
        "unsupported_effect": "Cet effet ne peut pas être représenté. Utilisez les réglages de police, couleur, contour ou ombre.",
        "missing_brand_field": "Complétez les informations de la boutique sélectionnées.",
        "asset_missing": "Une image est introuvable. Restaurez le fichier original.",
        "asset_corrupt": "Une image est endommagée. Restaurez le fichier original.",
        "internal_error": "Une erreur est survenue. Conservez vos modifications.",
        "budget_exhausted": "Le budget d’images de la boutique est atteint. Vous pouvez encore modifier et télécharger vos affiches. Pour créer de nouvelles images, contactez l’administrateur.",
        "image_job_running": "Une image est déjà en cours de préparation pour cette création.",
        "already_started": "Cette tâche a déjà démarré et ne peut plus être annulée.",
        "fidelity_incomplete": "Relisez et cochez aussi chaque texte dessiné dans l’image avant d’approuver.",
        "look_limit": "Vous avez déjà enregistré le nombre maximal de styles.",
        "look_name_taken": "Un autre style porte déjà ce nom. Choisissez-en un autre.",
        "look_removed": "Ce style a été retiré.",
        "invalid_brief": "Le style n’a pas pu être décrit à partir de cette affiche. Essayez une autre image.",
        "attempt_limit": "Douze scènes ont déjà été demandées pour cette affiche. Conservez une version ou créez une copie pour continuer.",
        "planner_unavailable": "La préparation par Claude n’est pas disponible. La composition simple reste disponible.",
}


def error_response(request: Request, error: store.Refused):
    # A refusal without a sentence is a programming error, not something the owner typed: say so, with the code.
    fallback = f"Cette action a été refusée (code : {error.code}). Rechargez la page et réessayez ; si cela se répète, donnez ce code à l’administrateur."
    body = {"code": error.code, "message_fr": MESSAGES.get(error.code, fallback),
            "retryable": error.status in (429, 503)}
    if error.field:
        body["field"] = error.field
    if error.current_revision is not None:
        body["current_revision"] = error.current_revision
    response = JSONResponse({"error": body, "request_id": request.state.request_id}, status_code=error.status)
    if error.code == "rate_limited":
        response.headers["Retry-After"] = "900"
    return response


class AccessBoundary:
    def __init__(self, app, settings, owner):
        self.app, self.settings, self.owner = app, settings, owner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        request.state.request_id = str(uuid4())
        api_path = scope["path"].startswith("/api/")
        started = False

        async def headers(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                # Shop data is never cached. The built frontend is public: hashed files for a year, the rest revalidated.
                caching = (b"no-store" if api_path else b"public, max-age=31536000, immutable"
                           if scope["path"].startswith("/assets/") and message["status"] == 200 else b"no-cache")
                message["headers"] = [pair for pair in message["headers"] if pair[0] != b"cache-control"] + [
                    (b"cache-control", caching), (b"x-content-type-options", b"nosniff"),
                    (b"x-request-id", request.state.request_id.encode("ascii"))]
            await send(message)

        limit = store.MAX_UPLOAD_BYTES+65536 if scope["path"] == "/api/assets" else 128*1024
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise store.Refused("too_large", 413)
            return message

        try:
            if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("origin") != self.settings.app_origin:
                raise store.Refused("forbidden_origin", 403)
            # Everything under /api/ needs a session; the built frontend (SERVE_FRONTEND) is public and holds no data.
            # The Origin check above and the size limits below stay on every path.
            request.state.shop = await run_in_threadpool(auth.session_shop, self.owner.state.engine,
                                                         request.cookies.get(auth.COOKIE)) if api_path else None
            if api_path and scope["path"] != "/api/session" and request.state.shop is None:
                raise store.Refused("unauthenticated", 401)
            length = request.headers.get("content-length", "0")
            if not length.isascii() or not length.isdigit():
                raise store.Refused("validation_error", 400)
            if len(length) > 20 or int(length) > limit:
                raise store.Refused("too_large", 413)
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                body = bytearray()
                while True:
                    part = await bounded_receive()
                    if part["type"] == "http.disconnect":
                        raise store.Refused("validation_error", 400)
                    body.extend(part.get("body", b""))
                    if not part.get("more_body", False):
                        break
                body_sent = False

                async def buffered_receive():
                    nonlocal body_sent
                    if not body_sent:
                        body_sent = True
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await receive()

                # Enforce limits before framework JSON/form parsing can turn an overflow into a generic 400.
                await self.app(scope, buffered_receive, headers)
            else:
                await self.app(scope, bounded_receive, headers)
        except store.Refused as error:
            if started:
                raise
            await error_response(request, error)(scope, receive, headers)
        except Exception as error:
            if started:
                raise
            code = "storage_unavailable" if isinstance(error, (OSError, SQLAlchemyError)) else "internal_error"
            log.warning("request=%s error=%s", request.state.request_id, type(error).__name__)
            await error_response(request, store.Refused(code, 503 if code == "storage_unavailable" else 500))(scope, receive, headers)


class Login(Model):
    password: SecretStr = Field(min_length=1, max_length=1024)


class ProfileView(Profile):
    revision: int


class CreationView(Model):
    id: Id
    revision: int
    status: Literal["active", "abandoned"]
    parent_creation_id: Id | None
    document: Document


class ErrorDetail(Model):
    code: str
    message_fr: str
    retryable: bool
    field: str | None = None
    current_revision: int | None = None


class ErrorView(Model):
    error: ErrorDetail
    request_id: Id


Key = Annotated[str, Header(alias="Idempotency-Key", pattern=r"^[0-9a-f-]{36}$")]
Version = Annotated[str | None, Header(alias="If-Match")]


def expected_revision(value: str | None) -> int | None:
    if value is None:
        return None
    if not re.fullmatch(r'"[1-9][0-9]{0,15}"', value):
        raise store.Refused("invalid_revision")
    return int(value[1:-1])


def result_response(result):
    status, body = result
    return JSONResponse(body, status_code=status, headers={"ETag": f'"{body["revision"]}"'} if "revision" in body else {})


@lru_cache(maxsize=256)
def _thumbnail(path: str) -> bytes:
    """A small JPEG of a stored image. Files are content-addressed, so a path always means the same bytes."""
    with Image.open(path) as image:
        small = image.convert("RGB")
        small.thumbnail((192, 240))
        out = io.BytesIO()
        small.save(out, "JPEG", quality=82)
        return out.getvalue()


def _backup_state(folder) -> dict | None:
    """The last backup as its marker file tells it, with its age; None when there is none to read."""
    if folder is None:
        return None
    try:
        finished = json.loads((folder / "last-backup.json").read_text(encoding="utf-8"))["finished_at"]
        age = (datetime.now(UTC) - datetime.fromisoformat(finished)).total_seconds() / 3600
    except (OSError, ValueError, KeyError, TypeError) as error:
        log.warning("last-backup.json is missing or unreadable: %s", type(error).__name__)
        return None
    return {"finished_at": finished, "age_hours": round(age, 1), "late": age > 48}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app):
        auth.validate_config(settings)
        runtime = start(settings, "api")
        app.state.engine = runtime.engine
        app.state.started_at = datetime.now(UTC).isoformat(timespec="seconds")
        service = None
        try:
            auth.end_sessions_on_new_password(runtime.engine, settings)
            app.state.pending_finalisations = jobs.recover(runtime.engine, settings.data_dir)
            service = PosterService(runtime.engine, settings)
            app.state.poster_service = service
            service.start()
            yield
        finally:
            try:
                if service is not None:
                    await service.close()
            finally:
                runtime.engine.dispose()
                runtime.lock_file.close()

    app = FastAPI(title="Affiche IA — pilote", version="0.2.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url="/api/openapi.json",
                  responses={code: {"model": ErrorView} for code in (400, 401, 403, 404, 409, 413, 415, 422, 428, 429, 500, 503)})
    app.add_middleware(AccessBoundary, settings=settings, owner=app)
    protected = APIRouter(dependencies=[Depends(APIKeyCookie(name=auth.COOKIE, auto_error=False))])

    @protected.get("/api/jobs/{id}")
    def job_status(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            return jobs.get_job(conn, request.state.shop, id)

    @protected.post("/api/jobs/{id}/cancel")
    def cancel_job(id: Id, request: Request, key: Key, body: Model | None = None):
        return result_response(jobs.cancel(app.state.engine, request.state.shop, key, id))

    @protected.get("/api/usage")
    def usage(request: Request):
        with app.state.engine.connect() as conn:
            return {"recorded_micros": spent_micros(conn, settings),
                    "cap_micros": usd_to_micros(settings.spend_cap_usd), "since": settings.spend_cap_since.isoformat()}

    @protected.get("/api/status")
    def status():
        """For the administrator: which code runs, the last backup, the spend, recent failures. No provider call."""
        since = (datetime.now(UTC) - timedelta(hours=24)).isoformat(timespec="microseconds")
        with app.state.engine.connect() as conn:
            return {"commit": os.environ.get("REVISION") or "dev",
                    "migration": conn.execute(text("SELECT version_num FROM alembic_version")).scalar(),
                    "started_at": app.state.started_at,
                    "backup": _backup_state(settings.backup_dir),
                    "spend": {"recorded_micros": spent_micros(conn, settings),
                              "cap_micros": usd_to_micros(settings.spend_cap_usd), "since": settings.spend_cap_since.isoformat()},
                    "failed_jobs_24h": conn.execute(text(
                        "SELECT count(*) FROM poster_jobs WHERE status IN ('failed','interrupted') AND finished_at>:since"),
                        {"since": since}).scalar_one()}

    @protected.get("/api/capabilities")
    def capabilities():
        return {"image_mode": settings.image_provider, "planner_mode": settings.planner_provider,
                "planner_available": settings.planner_provider == "stub" or (settings.planner_provider == "claude" and settings.anthropic_api_key is not None),
                "scene_estimate_micros": 0 if settings.image_provider == "stub" else usd_to_micros(settings.estimate_scene_usd),
                "plan_estimate_micros": 0 if settings.planner_provider == "stub" else usd_to_micros(settings.estimate_plan_usd),
                "texture_estimate_micros": 0 if settings.image_provider == "stub" else usd_to_micros(settings.estimate_texture_usd)}

    @protected.get("/api/creations/{id}/jobs")
    def creation_jobs(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            store.get_creation(conn, request.state.shop, id)
            ids = conn.execute(text("SELECT id FROM poster_jobs WHERE creation_id=:id ORDER BY "
                                    "CASE WHEN status IN ('queued','running') THEN 0 ELSE 1 END,created_at DESC LIMIT 50"), {"id": id}).scalars().all()
            return {"items": [jobs.get_job(conn, request.state.shop, item) for item in ids]}

    @protected.post("/api/creations/{id}/plans")
    def new_plan(id: Id, body: visuals.PlanRequest, request: Request, key: Key, version: Version = None):
        return result_response(visuals.create_plan(app.state.engine, settings, request.state.shop, key, id, expected_revision(version), body))

    @protected.post("/api/creations/{id}/looks", status_code=202)
    def new_look(id: Id, body: looks.LookRequest, request: Request, key: Key, version: Version = None):
        return result_response(looks.request_look(app.state.engine, settings, request.state.shop, key, id, expected_revision(version), body))

    @protected.get("/api/looks")
    def saved_looks(request: Request):
        with app.state.engine.connect() as conn:
            return {"items": looks.list_looks(conn, request.state.shop)}

    @protected.get("/api/looks/{id}")
    def saved_look(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            return looks.get_look(conn, request.state.shop, id)

    @protected.put("/api/looks/{id}")
    def rename_look(id: Id, body: looks.Rename, request: Request, key: Key):
        return result_response(looks.rename_look(app.state.engine, request.state.shop, key, id, body))

    @protected.delete("/api/looks/{id}")
    def remove_look(id: Id, request: Request, key: Key):
        return result_response(looks.remove_look(app.state.engine, request.state.shop, key, id))

    @protected.get("/api/plans/{id}")
    def plan(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            return visuals.get_plan(conn, request.state.shop, id)

    @protected.post("/api/plans/{id}/revisions")
    def revise_plan(id: Id, body: visuals.PlanRevision, request: Request, key: Key, version: Version = None):
        return result_response(visuals.revise_plan(app.state.engine, settings, request.state.shop, key, id, expected_revision(version), body))

    @protected.post("/api/creations/{id}/scenes", status_code=202)
    def new_scene(id: Id, body: visuals.SceneRequest, request: Request, key: Key, version: Version = None):
        return result_response(visuals.request_scene(app.state.engine, settings, request.state.shop, key, id, expected_revision(version), body))

    @protected.post("/api/creations/{id}/refinements", status_code=202)
    def refine(id: Id, body: visuals.RefinementRequest, request: Request, key: Key, version: Version = None):
        return result_response(visuals.request_refinement(app.state.engine, settings, request.state.shop, key, id, expected_revision(version), body))

    @protected.get("/api/visuals/{id}")
    def visual(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            return visuals.get_visual(conn, request.state.shop, id)

    @protected.get("/api/creations/{id}/visuals")
    def creation_visuals(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            creation = store.get_creation(conn, request.state.shop, id)
            ids = conn.execute(text("SELECT id FROM poster_visuals WHERE shop_id=:shop AND input_id=:input ORDER BY created_at DESC"),
                               {"shop": request.state.shop, "input": creation["document"]["input_id"]}).scalars().all()
            return {"items": [visuals.get_visual(conn, request.state.shop, item) for item in ids]}

    @protected.post("/api/visuals/{id}/decision")
    def visual_decision(id: Id, body: visuals.Decision, request: Request, key: Key):
        return result_response(visuals.decide(app.state.engine, request.state.shop, key, id, body))

    @protected.post("/api/creations/{id}/text-proposals")
    def new_text_proposal(id: Id, body: typography.ProposalRequest, request: Request, key: Key, version: Version = None):
        return result_response(typography.request_proposal(app.state.engine, settings, request.state.shop, key, id, expected_revision(version), body))

    @protected.get("/api/text-proposals/{id}")
    def text_proposal(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            return typography.get_proposal(conn, request.state.shop, id)

    @protected.post("/api/text-proposals/{id}/apply")
    def apply_text_proposal(id: Id, body: typography.ApplyRequest, request: Request, key: Key, version: Version = None):
        return result_response(typography.decide_proposal(app.state.engine, settings, request.state.shop, key, id,
            expected_revision(version), "apply", body))

    @protected.post("/api/text-proposals/{id}/reject")
    def reject_text_proposal(id: Id, request: Request, key: Key):
        return result_response(typography.decide_proposal(app.state.engine, settings, request.state.shop, key, id,
            None, "reject", typography.ApplyRequest()))

    @protected.post("/api/creations/{id}/text-effects")
    def new_text_effect(id: Id, body: typography.EffectRequest, request: Request, key: Key, version: Version = None):
        return result_response(typography.request_effect(app.state.engine, settings, request.state.shop, key, id, expected_revision(version), body))

    @protected.get("/api/text-effects/{id}")
    def text_effect(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            return typography.get_effect(conn, request.state.shop, id)

    @protected.post("/api/text-effects/{id}/apply")
    def apply_text_effect(id: Id, request: Request, key: Key, version: Version = None):
        return result_response(typography.decide_effect(app.state.engine, settings, request.state.shop, key, id, expected_revision(version), "apply"))

    @protected.post("/api/text-effects/{id}/reject")
    def reject_text_effect(id: Id, request: Request, key: Key):
        return result_response(typography.decide_effect(app.state.engine, settings, request.state.shop, key, id, None, "reject"))

    @protected.post("/api/creations/{id}/renders")
    def new_render(id: Id, body: exports.RenderRequest, request: Request, key: Key, version: Version = None):
        return result_response(exports.request_render(app.state.engine, settings, request.state.shop, key, id, expected_revision(version), body))

    @protected.get("/api/renders/{id}")
    def render_metadata(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            return exports.get_render(conn, request.state.shop, id)

    @protected.get("/api/renders/{id}/preview")
    def render_preview(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            row = exports.render_row(conn, request.state.shop, id)
            return Response(exports.read_png(settings, row), media_type="image/png", headers={"ETag": f'"{row["png_sha256"]}"'})

    @protected.post("/api/creations/{id}/confirmations")
    def new_confirmation(id: Id, body: exports.ConfirmRequest, request: Request, key: Key, version: Version = None):
        return result_response(exports.confirm(app.state.engine, settings, request.state.shop, key, id, expected_revision(version), body))

    @protected.get("/api/confirmations/{id}/download")
    def download(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            row, data = exports.download(conn, settings, request.state.shop, id)
        return Response(data, media_type="image/png", headers={"ETag": f'"{row["png_sha256"]}"',
            "Content-Disposition": f'attachment; filename="affiche-{row["format"]}-{id[:8]}.png"'})

    @app.exception_handler(store.Refused)
    async def refusal(request, error):
        return error_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def validation(request, error):
        # Pydantic errors contain raw inputs (passwords/documents); never serialise or log them.
        field = ".".join(map(str, error.errors()[0]["loc"])) if error.errors() else None
        return error_response(request, store.Refused("validation_error", field=field))

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return error_response(request, store.Refused("not_found" if error.status_code == 404 else "validation_error", error.status_code))

    @app.get("/api/session", openapi_extra={"security": []})
    def session(request: Request):
        return {"authenticated": request.state.shop is not None}

    @app.post("/api/session", openapi_extra={"security": []})
    def login(body: Login, request: Request):
        token = auth.login(app.state.engine, settings, body.password.get_secret_value(),
                           request.client.host if request.client else "unknown", request.cookies.get(auth.COOKIE))
        response = JSONResponse({"authenticated": True})
        response.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_SECONDS, httponly=True,
                            secure=settings.app_origin.startswith("https://"), samesite="strict", path="/")
        return response

    @app.delete("/api/session", openapi_extra={"security": []})
    def logout(request: Request):
        auth.logout(app.state.engine, request.cookies.get(auth.COOKIE))
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(auth.COOKIE, httponly=True, secure=settings.app_origin.startswith("https://"), samesite="strict")
        return response

    @protected.post("/api/assets", status_code=201, openapi_extra={"requestBody": {"required": True, "content": {
        "multipart/form-data": {"schema": {"type": "object", "required": ["file", "role"], "additionalProperties": False,
        "properties": {"file": {"type": "string", "format": "binary"},
                       "role": {"type": "string", "enum": ["original", "logo", "style"]}}}}}}})
    async def upload(request: Request):
        await request.body()  # Bounded before opening multipart spool files, including chunked requests.
        async with request.form(max_files=1, max_fields=1, max_part_size=1024) as form:
            if len(form.multi_items()) != 2 or set(form) != {"file", "role"} or not isinstance(form["file"], UploadFile):
                raise store.Refused("validation_error")
            data = await form["file"].read(store.MAX_UPLOAD_BYTES+1)
            return await run_in_threadpool(store.upload, app.state.engine, settings.data_dir, request.state.shop,
                                           data, form["role"], min_short_edge=settings.min_source_short_edge)

    @protected.get("/api/thumbnails/{sha}")
    def thumbnail(sha: Sha, request: Request):
        # Only this shop's final previews and scenes have thumbnails.
        with app.state.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT 'image/png' FROM poster_renders r JOIN creations c ON c.id=r.creation_id "
                "WHERE r.png_sha256=:sha AND c.shop_id=:shop UNION ALL "
                "SELECT a.mime FROM poster_visuals v JOIN assets a ON a.sha256=v.image_asset "
                "WHERE v.image_asset=:sha AND v.shop_id=:shop LIMIT 1"), {"sha": sha, "shop": request.state.shop}).first()
        if row is None:
            raise store.Refused("not_found", 404)
        try:
            data = _thumbnail(str(assets.path(settings.data_dir, sha, assets.extension(row[0]))))
        except (OSError, ValueError):  # missing, unreadable or not an image: the list falls back to its icon
            raise store.Refused("not_found", 404) from None
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=31536000, immutable"})

    @protected.get("/api/assets/{sha}")
    def asset(sha: Sha, request: Request, prepared: bool = False):
        with app.state.engine.connect() as conn:
            row = conn.execute(text("SELECT a.mime FROM assets a WHERE a.sha256=:sha AND ("
                                    "EXISTS (SELECT 1 FROM asset_access r WHERE r.asset_sha=a.sha256 AND r.shop_id=:shop) OR "
                                    "EXISTS (SELECT 1 FROM poster_visuals v WHERE v.image_asset=a.sha256 AND v.shop_id=:shop) OR "
                                    "EXISTS (SELECT 1 FROM text_effects e WHERE e.texture_asset=a.sha256 AND e.shop_id=:shop))"),
                               {"sha": sha, "shop": request.state.shop}).first()
            if row is None:
                raise store.Refused("not_found", 404)
            try:
                data = assets.load(conn, settings.data_dir, sha)
            except FileNotFoundError:
                raise store.Refused("not_found", 404) from None
        if hashlib.sha256(data).hexdigest() != sha:
            raise store.Refused("asset_corrupt", 409)
        if prepared:
            try:
                return Response(rendering.canvas_image(data), media_type="image/png")
            except (ValueError, OSError):
                raise store.Refused("invalid_image") from None
        return Response(data, media_type=row.mime)

    @protected.post("/api/product-inputs", status_code=201)
    def new_input(body: ProductInput, request: Request, key: Key):
        return result_response(store.create_input(app.state.engine, settings.data_dir, request.state.shop, key, body))

    @protected.get("/api/product-inputs/{id}")
    def product(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            result = store.get_input(conn, request.state.shop, id)
        return result | {"photo_urls": [f"/api/assets/{sha}" for sha in result["photo_assets"]]}

    @protected.get("/api/shop-profile", response_model=ProfileView)
    def profile(request: Request):
        with app.state.engine.connect() as conn:
            return result_response((200, store.get_profile(conn, request.state.shop)))

    @protected.put("/api/shop-profile", response_model=ProfileView)
    def save_profile(body: Profile, request: Request, key: Key, version: Version = None):
        return result_response(store.save_profile(app.state.engine, settings.data_dir, request.state.shop,
                                                  key, body, expected_revision(version)))

    @protected.post("/api/creations", status_code=201, response_model=CreationView)
    def new_creation(body: NewCreation, request: Request, key: Key):
        return result_response(store.create_creation(app.state.engine, settings.data_dir, request.state.shop, key, body))

    @protected.get("/api/creations")
    def creations(request: Request, limit: Annotated[int, Query(ge=1, le=50)] = 20,
                  before: Annotated[str | None, Query(max_length=100)] = None,
                  status: Literal["active", "abandoned"] = "active"):
        cursor = ("9999", "")
        if before:
            try:
                stamp, id = before.split("|", 1)
                if not re.fullmatch(r"[0-9T:+.\-]{20,40}", stamp) or not re.fullmatch(r"[0-9a-f-]{36}", id):
                    raise ValueError()
                cursor = stamp, id
            except ValueError:
                raise store.Refused("invalid_cursor") from None
        with app.state.engine.connect() as conn:
            # Thumbnail: the last final preview of the poster, else its current scene. Feed only until T-POSTER-009.
            rows = conn.execute(text("SELECT c.*,v.document_json,p.name,p.variant,"
                "(SELECT r.png_sha256 FROM poster_renders r WHERE r.creation_id=c.id ORDER BY r.created_at DESC,r.id DESC LIMIT 1) AS render_sha,"
                "(SELECT s.image_asset FROM poster_visuals s WHERE s.shop_id=c.shop_id AND "
                "s.id=json_extract(v.document_json,'$.formats.feed.scene.visual_id')) AS scene_asset,"
                "(SELECT s.status FROM poster_visuals s WHERE s.shop_id=c.shop_id AND "
                "s.id=json_extract(v.document_json,'$.formats.feed.scene.visual_id')) AS scene_status,"
                # A later version waits outside the document until it is chosen: look at the creation's own jobs too.
                "EXISTS(SELECT 1 FROM poster_visuals w JOIN poster_jobs j ON j.id=w.job_id "
                "WHERE j.creation_id=c.id AND w.status='pending_review') AS waiting,"
                "EXISTS(SELECT 1 FROM confirmations k WHERE k.creation_id=c.id "
                "AND k.confirmed_revision=c.current_revision) AS confirmed "
                "FROM creations c JOIN creation_versions v "
                "ON v.creation_id=c.id AND v.revision=c.current_revision JOIN product_inputs p "
                "ON p.id=json_extract(v.document_json,'$.input_id') WHERE c.shop_id=:shop AND c.status=:status "
                "AND (c.created_at,c.id)<(:stamp,:id) ORDER BY c.created_at DESC,c.id DESC LIMIT :limit"),
                {"shop": request.state.shop, "status": status, "stamp": cursor[0], "id": cursor[1], "limit": limit+1}).mappings().all()
            total = conn.execute(text("SELECT COUNT(*) FROM creations WHERE shop_id=:shop AND status=:status"),
                                 {"shop": request.state.shop, "status": status}).scalar_one()
        items = [{"id": r["id"], "revision": r["current_revision"], "status": r["status"], "created_at": r["created_at"],
                  "name": r["name"], "variant": r["variant"],
                  # The one state that asks the owner to act comes first; "confirmed" means the file is this revision.
                  "state": "to_review" if r["waiting"] or r["scene_status"] == "pending_review" else
                           "confirmed" if r["confirmed"] else "approved" if r["scene_status"] == "approved" else "draft",
                  "thumbnail_url": f'/api/thumbnails/{r["render_sha"] or r["scene_asset"]}'
                  if r["render_sha"] or r["scene_asset"] else None,
                  **{key: json.loads(r["document_json"])["offer"][key] for key in ("title", "price_ar")}} for r in rows[:limit]]
        return {"items": items, "total": total, "next_cursor": f'{rows[limit-1]["created_at"]}|{rows[limit-1]["id"]}' if len(rows)>limit else None}

    @protected.get("/api/creations/{id}", response_model=CreationView)
    def creation(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            return result_response((200, store.get_creation(conn, request.state.shop, id)))

    @protected.put("/api/creations/{id}", response_model=CreationView)
    def save_creation(id: Id, body: Document, request: Request, key: Key, version: Version = None):
        return result_response(store.save_creation(app.state.engine, settings.data_dir, request.state.shop,
                                                   key, id, body, expected_revision(version)))

    @protected.get("/api/creations/{id}/versions")
    def versions(id: Id, request: Request, before: Annotated[int | None, Query(ge=1)] = None,
                 limit: Annotated[int, Query(ge=1, le=50)] = 20):
        with app.state.engine.connect() as conn:
            store.get_creation(conn, request.state.shop, id)
            rows = conn.execute(text("SELECT revision,created_at FROM creation_versions WHERE creation_id=:id "
                "AND revision<:before ORDER BY revision DESC LIMIT :limit"),
                {"id": id, "before": before or 9_007_199_254_740_991, "limit": limit+1}).mappings().all()
        return {"items": [dict(r) for r in rows[:limit]], "next_cursor": rows[limit-1]["revision"] if len(rows)>limit else None}

    @protected.get("/api/creations/{id}/versions/{revision}", response_model=CreationView)
    def version(id: Id, revision: Annotated[int, Path(ge=1)], request: Request):
        with app.state.engine.connect() as conn:
            return result_response((200, store.get_creation(conn, request.state.shop, id, revision)))

    @protected.post("/api/creations/{id}/copies", status_code=201, response_model=CreationView)
    def copy_creation(id: Id, body: CopyCreation, request: Request, key: Key):
        return result_response(store.copy_creation(app.state.engine, settings.data_dir, request.state.shop, key, id, body))

    @protected.post("/api/creations/{id}/abandon", response_model=CreationView)
    def abandon_creation(id: Id, request: Request, key: Key, version: Version = None, body: Model | None = None):
        return result_response(store.abandon_creation(app.state.engine, request.state.shop, key, id, expected_revision(version)))

    @protected.post("/api/creations/{id}/restore", response_model=CreationView)
    def restore_creation(id: Id, request: Request, key: Key, version: Version = None, body: Model | None = None):
        return result_response(store.restore_creation(app.state.engine, request.state.shop, key, id, expected_revision(version)))

    app.include_router(protected)
    if settings.serve_frontend:
        # After every route: a mount at / matches all paths, so it must be the last thing the router tries.
        app.mount("/", StaticFiles(directory=rendering.BUILD_DIR, html=True), name="frontend")
    return app


# Loopback by default. One front process (Vite, a tunnel client, or Caddy on the container network) is the only
# door, and only its forwarding headers are believed, so the login limit counts the real client and not the front process.
UVICORN = {"host": "127.0.0.1", "port": 8000, "proxy_headers": True, "forwarded_allow_ips": "127.0.0.1", "access_log": False}



def uvicorn_options(settings: Settings) -> dict:
    """In a container, API_HOST and FORWARDED_ALLOW_IPS replace the loopback defaults (config.py)."""
    return {**UVICORN, "host": settings.api_host, "forwarded_allow_ips": settings.forwarded_allow_ips}


if __name__ == "__main__":
    import uvicorn
    configured = load_settings()
    uvicorn.run(create_app(configured), **uvicorn_options(configured))
