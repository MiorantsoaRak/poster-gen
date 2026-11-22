"""Authenticated HTTP boundary for the pilot. Run with python -m affiche.api."""
import hashlib
import io
import ipaddress
import json
import logging
import os
import re
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path as FilePath
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from PIL import Image
from fastapi import APIRouter, Depends, FastAPI, Header, Path, Query, Request
from fastapi.security import APIKeyCookie
from fastapi.exceptions import RequestValidationError
from pydantic import Field, SecretStr
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response
from starlette.staticfiles import StaticFiles

from affiche import admin, assets
from affiche.config import ENV_FILE, Settings, load_settings
from affiche.db import utc_now
from affiche.posters import (auth, credits, exports, facebook, facebook_connect, facebook_posts, jobs, looks, reads,
                             rendering, store, terms, typography, visuals)
from affiche.posters.service import PosterService
from affiche.posters.models import CopyCreation, Document, Format, Id, Model, NewCreation, ProductInput, Profile, Sha
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
        "adjustments_limit": "Cette version porte trop d’ajustements de scène pour être refaite avec eux. Créez une nouvelle version dans Pas à pas.",
        "adjustment_refused": "Un ajustement de scène demandé plus tôt n’est plus accepté. Créez une nouvelle version dans Pas à pas.",
        "input_changed": "Le produit de cette affiche a changé pendant la génération. Relancez la génération.",
        "provider_unavailable": "Le service d’images n’est pas disponible pour le moment. Réessayez dans quelques minutes.",
        "format_unavailable": "Ce format d’affiche n’est pas encore disponible. Faites l’affiche au format Publication (4:5).",
        "format_locked": "Le format ne change plus après la première version : le titre, le prix et le contact sont dessinés dans une image à cette taille.",
        "scene_format_mismatch": "Cette version a été faite pour un autre format d’affiche. Choisissez une version de ce format, ou générez-en une nouvelle.",
        "unauthenticated": "Connectez-vous pour continuer.", "forbidden_origin": "Origine de la demande refusée.",
        "wrong_credentials": "Identifiant ou mot de passe incorrect.",
        "operator_not_set": "Aucun mot de passe d’opérateur n’est défini : lancez python -m affiche.shops operator-password sur le serveur.",
        "operator_refused": "Refusé : rien n’a été écrit.",  # the operator's; its detail says why
        "already_recorded": "Déjà enregistré : rien n’a été écrit de plus.",  # the operator's; existing is the line
        "shop_suspended": "Cette boutique est suspendue. Contactez l’administrateur.",
        "shop_changed": "Une autre boutique est connectée dans ce navigateur. Connectez-vous pour continuer.",
        "wrong_password": "Le mot de passe actuel n’est pas le bon.",
        "password_too_short": "Le nouveau mot de passe doit avoir au moins 10 caractères.",
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
        "logo_placement_stale": "Le logo ou le cadrage ne correspond plus à l’espace réservé : rétablissez sa position et le cadrage, ou générez une nouvelle version.",
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
        # The operator's pause and the service's cap (D-BALANCE-003): both stop images, styles, text proposals and reads.
        "budget_exhausted": "Le service est en pause : l’IA ne prépare rien de nouveau pour le moment (images, styles, textes, lecture des messages). Vous pouvez encore modifier et télécharger vos affiches. Réessayez plus tard.",
        "shop_daily_limit": "La boutique a atteint sa limite d’images pour aujourd’hui. Vous pouvez encore modifier et télécharger vos affiches. Réessayez demain.",
        "no_credit": "Il ne vous reste plus de crédit : rien n’a été envoyé, et vos affiches restent disponibles.",
        "image_job_running": "Une image est déjà en cours de préparation pour cette création.",
        "already_started": "Cette tâche a déjà démarré et ne peut plus être annulée.",
        "fidelity_incomplete": "Relisez et cochez aussi chaque texte dessiné dans l’image avant d’approuver.",
        "look_limit": "Vous avez déjà enregistré le nombre maximal de styles.",
        "look_name_taken": "Un autre style porte déjà ce nom. Choisissez-en un autre.",
        "look_removed": "Ce style a été retiré.",
        "invalid_brief": "Le style n’a pas pu être décrit à partir de cette affiche. Essayez une autre image.",
        "attempt_limit": "Douze scènes ont déjà été demandées pour cette affiche. Conservez une version ou créez une copie pour continuer.",
        "planner_unavailable": "La préparation par Claude n’est pas disponible. La composition simple reste disponible.",
        "chat_unavailable": "La création par message n’est pas disponible pour le moment. Continuez dans Pas à pas.",
        "read_failed": "Je n’ai pas pu lire votre message. Réessayez, ou passez par Pas à pas.",
        "read_running": "Votre message est encore en cours de lecture. Patientez quelques secondes.",
        "read_limit": "Limite de messages atteinte pour aujourd’hui. Continuez dans Pas à pas.",
        "reads_busy": "Deux messages de la boutique sont déjà en cours de lecture. Patientez quelques secondes, puis renvoyez le vôtre.",
        # The conditions of use (D-TERMS-002): the version the page showed is no longer the current one.
        "terms_outdated": "Les conditions viennent de changer : lisez la nouvelle version avant de l'accepter.",
        # The gate (D-TERMS-003): the current version not accepted; refused before anything is written, sent or taken.
        "terms_required": "Acceptez d'abord les conditions d'utilisation : rien n'a été envoyé, et aucun crédit n'a été pris.",
        # The chat's cards (posters/reads.py): the one place for their French sentences. {} is filled by the server.
        "card_ask_product": "Quel est le produit ? Marque et modèle.",
        "card_ask_price": "Quel est le prix ? Écrivez-le en chiffres, par exemple 700 000 Ar.",
        "card_ask_photo": "Il me faut une photo du produit.",
        "card_recap": "Voici l’affiche que je vais créer.",
        "card_refused": "Je ne peux pas demander ce changement à l’image : retirez les mots de prix, de promotion ou de garantie. Le prix se change à part, par message.",
        "card_unclear": "Écrivez le produit et son prix.",
        "card_unclear_poster": "Dites ce qu’il faut changer : {}. Le reste se change dans Pas à pas.",  # the field table's labels
        "card_same": "L’affiche a déjà ces textes.",
        "card_steps": "Cette affiche n’a pas de textes dessinés dans l’image : la marque et le sous-titre se règlent dans Pas à pas.",
        "card_title_without_brand": "Écrivez le titre sans la marque.",
        "card_title_too_long": "Le titre dépasse 240 caractères. Raccourcissez le titre.",
        "card_word_unknown": "Je ne peux pas écrire « {} » : ce mot n’est ni dans votre message ni sur l’affiche.",
        "card_words_first": "Demandez ensuite le changement de scène : il partira de la nouvelle version.",
        "card_accent_removed": "Le mot en couleur est retiré.",
        "card_format": "Un autre format est une nouvelle affiche : dans Pas à pas, « Style », « Refaire en … ».",
        "card_identity": "Le logo et le contact de la boutique se règlent dans Pas à pas, « Boutique ».",
        "card_steps_style": "Cette affiche n’a pas de textes dessinés dans l’image : le style se change dans Pas à pas.",
        "card_model_dropped": "L’affiche modèle n’est plus suivie.",
        "card_adjustments_dropped": "Les ajustements de scène demandés avant ne sont pas repris.",
        "reload_required": "Rechargez la page pour continuer.",
        # An older bundle in an open tab (BUNDLE): nothing it sends is saved, and a reload loses what it holds unsaved.
        "bundle_outdated": "Cette page est une ancienne version de l’application : rien n’est enregistré depuis sa mise à jour. Notez vos dernières modifications, puis rechargez la page.",
        # Connecting the shop's Facebook Page (D-FB-PUBLISH-002); the card of « Mon compte » shows the return page's.
        "facebook_state": "Recommencez la connexion.",
        "facebook_no_page": "Aucune des Pages lues ne vous permet de publier. Recommencez la connexion et autorisez votre Page. Au-delà de cent Pages autorisées, seules les cent premières sont lues.",
        "facebook_failed": "La connexion à Facebook n’a pas abouti. Réessayez.",
        "facebook_cancelled": "Connexion annulée.",
        "facebook_dialog_failed": "La connexion n’a pas abouti.",
        # Publishing on it (D-FB-POST-003): the refusals of the admission and of the owner's word, written nothing.
        "facebook_too_large": "Ce fichier dépasse 10 Mo, la limite de Facebook. Téléchargez-le, puis publiez-le depuis Facebook.",
        "facebook_not_connected": "Aucune Page Facebook n’est connectée. Connectez votre Page dans « Mon compte ».",
        "facebook_reconnect": "Reconnectez votre Page dans « Mon compte ».",
        "facebook_stale": "L’affiche, la Page connectée ou ses publications ont changé. Vérifiez, puis publiez.",
        "facebook_pending": "Une publication de cette affiche sur cette Page attend encore son résultat.",
        "facebook_running": "La publication est en cours. Patientez quelques secondes.",
        "facebook_settled": "Cette publication a déjà son résultat. Rechargez la page.",
        "caption_invalid": "La légende dépasse 2 000 caractères ou contient un caractère invisible non accepté. Corrigez-la, puis publiez.",
        # A post of one or several posters (D-FB-POST-003): the admission's own refusal ({} is the shop's limit), then a
        # post's line (facebook_posts.said), the design's table of sentences; {n}, {count}, {code}, {said} are filled there.
        "facebook_too_many": "Votre boutique peut mettre {} images au plus dans une publication.",
        "facebook_items": "Choisissez au moins une affiche, et chacune une seule fois.",
        "post_uploading": "Envoi de l’image {n} sur {count}…",
        "post_uploaded": "Images envoyées. Publication…",
        "post_posting": "Publication en cours…",
        "post_published": "Publié sur {}.",
        "post_confirmed": "Présence confirmée par vous",
        "post_unknown": "Je ne sais pas si la publication est sur votre Page. Ouvrez votre Page et dites-le-moi.",
        "post_image_refused": "L’image {n} n’a pas pu être envoyée (code {code}). Rien n’a été publié. Retirez l’image {n} ou remplacez-la, puis réessayez.",
        "post_poster_changed": "L’affiche {n} a changé avant l’envoi. Rien n’a été publié. Vérifiez-la à nouveau.",
        "post_export_missing": "Le fichier de l’image {n} est introuvable ou abîmé. Rien n’a été publié. Vérifiez cette affiche à nouveau.",
        "post_not_sent": "La publication n’est pas partie. Rien n’a été publié. Réessayez.",
        "post_stopped": "Envoi arrêté. Rien n’a été publié.",
        "post_page_changed": "Votre Page a changé pendant l’envoi. Rien n’a été publié.",
        "post_limit_lowered": "Le nombre d’images permis a changé pendant l’envoi. Rien n’a été publié.",
        "post_refused": "Facebook a refusé la publication (code {code}). Rien n’a été publié.",
        "post_reconnect": "Reconnectez votre Page. Rien n’a été publié.",
        "post_permission": "Facebook a refusé la publication (code {code}) : l’autorisation manque. Rien n’a été publié. Reconnectez votre Page en l’autorisant ; si cela se répète, contactez l’opérateur.",
        "post_limited": "Facebook limite les publications pour le moment. Rien n’a été publié. Réessayez plus tard.",
        "post_at_image": "Image {n} : {said}",  # (r3) a failure at an upload names its image first
        "post_not_published": "Vous avez dit qu’elle n’est pas sur votre Page.",
        # Not in the design's table: an upload unanswered twice, and an upload whose answer names a post (the photo is
        # public) or something else (facebook.Upload): the post stops there.
        "post_no_answer": "Facebook n’a pas confirmé l’envoi de l’image {n}. La publication n’a pas été envoyée. Réessayez.",
        "post_photo_public": "Facebook a publié l’image {n} seule sur votre Page au lieu de la garder pour la publication. L’envoi s’est arrêté. Vérifiez votre Page.",
        "post_unexpected": "Facebook a répondu autrement que prévu à l’envoi de l’image {n}. L’envoi s’est arrêté. Vérifiez votre Page.",
}


# GET /api/balance: what blocks a charged operation whatever the shop's credits (D-BALANCE-003). Buying would not help.
BLOCKED = {"budget_exhausted": "service", "provider_unavailable": "service", "shop_daily_limit": "day",
           "terms_required": "terms"}


def sentence(code: str) -> str:
    # A refusal without a sentence is a programming error, not something the owner typed: say so, with the code.
    return MESSAGES.get(code, f"Cette action a été refusée (code : {code}). Rechargez la page et réessayez ; si cela se répète, donnez ce code à l’administrateur.")


def error_response(request: Request, error: store.Refused, message: str | None = None):
    body = {"code": error.code, "message_fr": message or sentence(error.code),
            "retryable": error.status in (429, 503)}
    if error.field:
        body["field"] = error.field
    if error.current_revision is not None:
        body["current_revision"] = error.current_revision
    if error.detail is not None:
        body["detail"] = error.detail
    if error.existing is not None:
        body["existing"] = error.existing
    response = JSONResponse({"error": body, "request_id": request.state.request_id}, status_code=error.status)
    if error.code == "rate_limited":
        response.headers["Retry-After"] = "900"
    return response


# The frontend bundle a state-changing request must come from (its header X-Affiche-Bundle, frontend/src/api.ts BUNDLE).
# Raise both together when a change makes an older open tab unsafe (ADR-103): here a tab from before the shops'
# identifiers signs in with no identifier, and keeps what it stores on the device for every shop (D-MULTI-SHOP-007).
BUNDLE = 3


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
                # Shop data is never cached, except images whose address is their own SHA-256 (ADR-087): their route
                # says so on a 200 only. The built frontend is public: hashed files for a year, the rest revalidated.
                own = dict(message["headers"]).get(b"cache-control")
                caching = ((own if own == IMMUTABLE and message["status"] == 200 else b"no-store") if api_path
                           else b"public, max-age=31536000, immutable"
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
            # The operator's view answers anyone else as a route that does not exist, before any rule below could
            # answer otherwise (D-MULTI-SHOP-004). The operator has no session: the session rule lets it through.
            if scope["path"] == "/api/status" and not operator(request):
                raise store.Refused("not_found", 404)
            if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("origin") != self.settings.app_origin:
                raise store.Refused("forbidden_origin", 403)
            # The operator's paths take their own branch before any shop rule (D-ADMIN-001): a shop's cookie is never
            # read there and the operator's is read nowhere else, so neither session can stand for the other.
            operator_path = scope["path"].startswith("/api/admin/")
            request.state.operator = await run_in_threadpool(auth.operator_session, self.owner.state.engine,
                                                             request.cookies.get(auth.OPERATOR_COOKIE)) if operator_path else None
            if operator_path and scope["path"] != "/api/admin/session" and request.state.operator is None:
                raise store.Refused("unauthenticated", 401)
            # Everything under /api/ needs a session; the built frontend (SERVE_FRONTEND) is public and holds no data.
            # The Origin check above and the size limits below stay on every path.
            shop_path = api_path and not operator_path
            request.state.shop = await run_in_threadpool(auth.session_shop, self.owner.state.engine,
                                                         request.cookies.get(auth.COOKIE)) if shop_path else None
            if shop_path and scope["path"] not in ("/api/session", "/api/status") and request.state.shop is None:
                raise store.Refused("unauthenticated", 401)  # /api/status: only the operator reaches this line
            # A stale-tab guard, not authentication (D-MULTI-SHOP-002): a page bound to another shop than the cookie's
            # session reads and changes nothing, and an old tab of one shop cannot sign another out. A forged value only
            # gets the request refused; an absent one passes (images loaded by <img>, bundles that do not send it).
            claimed = request.headers.get("x-affiche-shop")
            if (shop_path and claimed is not None and not (scope["path"] == "/api/session" and request.method in ("GET", "POST"))
                    and (request.state.shop is None or claimed != str(request.state.shop))):
                raise store.Refused("shop_changed", 409)
            # An older open tab changes nothing and pays nothing: refused here, before any handler. It can still read
            # and sign out; its sign-in, which has no identifier, gets this sentence too, so a reload always works.
            bundle = request.headers.get("x-affiche-bundle", "")
            if (api_path and (scope["path"], request.method) not in (("/api/session", "DELETE"), ("/api/admin/session", "DELETE"))
                    and request.method not in ("GET", "HEAD", "OPTIONS")
                    and not (bundle.isascii() and bundle.isdigit() and len(bundle) < 10 and int(bundle) >= BUNDLE)):
                raise store.Refused("bundle_outdated", 409)
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
    identifier: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=1024)


class PasswordChange(Model):
    current_password: SecretStr = Field(min_length=1, max_length=1024)
    new_password: SecretStr = Field(min_length=1, max_length=1024)  # under 10 characters: password_too_short


class Acceptance(Model):
    version: str = Field(min_length=1, max_length=32)  # the version the page showed (terms.VERSION)


class ProfileView(Profile):
    revision: int


class CurrentConfirmation(Model):
    id: Id
    render_id: Id
    format: Format
    download_url: str


class CreationView(Model):
    id: Id
    revision: int
    status: Literal["active", "abandoned"]
    parent_creation_id: Id | None
    document: Document
    confirmation: CurrentConfirmation | None = None  # GET /api/creations/{id} only (D-SHARE-001): never a mutation's answer


class ErrorDetail(Model):
    code: str
    message_fr: str
    retryable: bool
    field: str | None = None
    current_revision: int | None = None
    detail: str | None = None  # the operator's refusals only (admin.py): the module's own sentence, in English
    existing: dict | None = None  # already_recorded: the line that holds the request's place, and moved_to


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


def creation_cursor(before: str | None) -> tuple[str, str]:
    """A cursor of the posters' pages, `created_at|id` (GET /api/creations, GET /api/facebook/posts/candidates)."""
    if not before:
        return "9999", ""
    try:
        stamp, id = before.split("|", 1)
        if not re.fullmatch(r"[0-9T:+.\-]{20,40}", stamp) or not re.fullmatch(r"[0-9a-f-]{36}", id):
            raise ValueError()
        return stamp, id
    except ValueError:
        raise store.Refused("invalid_cursor") from None


# Images made by code are kept by the browser for a year (ADR-087): their address carries the encoder's version
# (`v`), so bump the constant whenever its output changes. A request with another version gets the current encoding,
# never cached. The frontend builds the same addresses (frontend/src/api.ts, IMAGE_VERSIONS).
THUMBNAIL_VERSION = "1"
DISPLAY_VERSION = "1"  # also bump with rendering.CANVAS_IMAGE_VERSION: the display copy is made from that image


@lru_cache(maxsize=256)
def _thumbnail(path: str) -> bytes:
    """A small JPEG of a stored image, at least 3x for a 104 px wide version tile in every format (a Story is 9:16).
    Files are content-addressed, so a path always means the same bytes."""
    with Image.open(path) as image:
        small = image.convert("RGB")
        small.thumbnail((320, 568))
        out = io.BytesIO()
        small.save(out, "JPEG", quality=82)
        return out.getvalue()


IMMUTABLE = b"private, max-age=31536000, immutable"


# The editor's copy of a scene (D-POSTER-EDITOR-007 6c): a prepared PNG of 1.4 to 2.4 MB re-encoded on every request
# made opening a poster slow on a phone. Exports and the server's previews read the stored bytes, never this copy.
def _display_path(data_dir, sha: str, ext: str):
    return data_dir / "display" / f"v{DISPLAY_VERSION}" / sha[:2] / f"{sha}.{ext}"


def _cached_display(data_dir, sha: str) -> tuple[bytes, str] | None:
    for ext in ("jpeg", "png"):
        try:
            return _display_path(data_dir, sha, ext).read_bytes(), f"image/{ext}"
        except FileNotFoundError:
            continue
        except OSError:  # unreadable: made again below
            log.warning("display copy of %s could not be read; it is encoded again", sha, exc_info=True)
            return None
    return None


def _display_copy(png: bytes) -> tuple[bytes, str]:
    """A JPEG of an opaque prepared image. An image with any transparent pixel stays PNG, and so does a flat one whose
    PNG is already the smaller (the stub's scenes)."""
    with Image.open(io.BytesIO(png)) as image:
        if image.mode in ("RGBA", "LA") and image.getchannel("A").getextrema()[0] < 255:
            return png, "png"
        out = io.BytesIO()
        image.convert("L" if image.mode in ("L", "LA") else "RGB").save(out, "JPEG", quality=85)
        return (out.getvalue(), "jpeg") if out.tell() < len(png) else (png, "png")


def _display(data_dir, sha: str, png: bytes) -> tuple[bytes, str]:
    """Encoded once per SHA and kept on disk (derived, not backed up). Failing to encode sends the prepared PNG;
    failing to keep it sends the copy and encodes again next time. Both are logged."""
    try:
        data, ext = _display_copy(png)
    except (OSError, ValueError):
        log.warning("display copy of %s could not be encoded; the prepared PNG is sent", sha, exc_info=True)
        return png, "image/png"
    target = _display_path(data_dir, sha, ext)
    tmp = target.with_name(f"{target.name}.{uuid4().hex}.tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        os.replace(tmp, target)
    except OSError:
        log.warning("display copy of %s could not be kept", sha, exc_info=True)
        with suppress(OSError):  # already logged; a leftover temporary file is only disk space
            tmp.unlink(missing_ok=True)
    return data, f"image/{ext}"


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def operator(request: Request) -> bool:
    """The operator, until the administration has its own sign-in (D-MULTI-SHOP-004): a caller on the machine that runs
    the API, by both its address (after the forwarding headers believed from the front process) and the Host it names.
    Through Caddy a phone has neither; in development the developer's own browser through Vite has both, on purpose."""
    try:
        peer = request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
        host = urlsplit("//" + request.headers.get("host", "")).hostname
    except ValueError:  # a client name that is no address, or a Host that is no host
        return False
    return peer and host in LOCAL_HOSTS


def _kept(current: bool) -> dict:
    return {"Cache-Control": IMMUTABLE.decode()} if current else {}


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


def status_view(conn, settings: Settings, started_at: str) -> dict:
    """Which code runs, the last backup, the service's spend, recent failures: /api/status's answer, and the head of the
    dashboard's Service screen (D-ADMIN-004). No provider call."""
    since = (datetime.now(UTC) - timedelta(hours=24)).isoformat(timespec="microseconds")
    return {"commit": os.environ.get("REVISION") or "dev",
            "migration": conn.execute(text("SELECT version_num FROM alembic_version")).scalar(),
            "started_at": started_at,
            "backup": _backup_state(settings.backup_dir),
            "spend": {"recorded_micros": spent_micros(conn, settings),
                      "cap_micros": usd_to_micros(settings.spend_cap_usd), "since": settings.spend_cap_since.isoformat()},
            "failed_jobs_24h": conn.execute(text(
                "SELECT count(*) FROM poster_jobs WHERE status IN ('failed','interrupted') AND finished_at>:since"),
                {"since": since}).scalar_one()}


# The library's « À vérifier » (c: a creation, v: its current version), counted by the shop's dashboard too
# (D-SHOP-DASH-001): the scene its primary format shows waits for review, or a later version waits outside the document
# until it is chosen. Every join keeps to the creation's shop. The shown scene is one lookup by id; the posters with a
# waiting version are found once per query, not once per poster: :shop is the caller's, whose c.shop_id it is.
SCENE = ("s.shop_id=c.shop_id AND s.id=json_extract(v.document_json,'$.formats.'"
         "||json_extract(v.document_json,'$.primary_format')||'.scene.visual_id')")
TO_REVIEW = (f"(EXISTS(SELECT 1 FROM poster_visuals s WHERE {SCENE} AND s.status='pending_review') OR"
             " c.id IN (SELECT j.creation_id FROM poster_visuals w JOIN poster_jobs j ON j.id=w.job_id"
             " WHERE w.shop_id=:shop AND j.shop_id=:shop AND w.status='pending_review'))")
IMAGE_KINDS_SQL = ",".join(f"'{kind}'" for kind in sorted(jobs.IMAGE_KINDS))
# The poster's latest image generation (by admission, then id) ended without an image. Any later one supersedes it, a
# cancelled one included, and a cancelled one is no failure (D-SHOP-DASH-001). One pass over the shop's image jobs
# (:shop is attention's), not one per poster: no index orders a poster's finished jobs.
FAILED = ("c.id IN (SELECT creation_id FROM (SELECT creation_id,status,ROW_NUMBER() OVER (PARTITION BY creation_id"
          f" ORDER BY created_at DESC,id DESC) AS n FROM poster_jobs WHERE shop_id=:shop AND kind IN ({IMAGE_KINDS_SQL}))"
          " WHERE n=1 AND status IN ('failed','interrupted'))")
# [since, as_of) (D-SHOP-DASH-002): posters by creation, whatever became of them; images and credits by completion, a
# success from before credits included in images, credits gross of any repayment (its own line in the history).
USAGE = text(
    "SELECT (SELECT COUNT(*) FROM creations WHERE shop_id=:shop AND created_at>=:since AND created_at<:as_of) AS posters_created,"
    f" (SELECT COUNT(*) FROM poster_jobs WHERE shop_id=:shop AND status='succeeded' AND kind IN ({IMAGE_KINDS_SQL})"
    " AND finished_at>=:since AND finished_at<:as_of) AS images_generated,"
    " (SELECT COUNT(*) FROM poster_jobs WHERE shop_id=:shop AND status='succeeded' AND takes_credit=1"
    " AND finished_at>=:since AND finished_at<:as_of) AS credits_spent")


def attention(conn, shop: int, predicate: str) -> dict:
    """How many of the shop's active posters match, and the newest of them by created_at then id (None: none)."""
    row = conn.execute(text(
        "SELECT c.id,json_extract(v.document_json,'$.offer.title') AS title,COUNT(*) OVER () AS total"
        " FROM creations c JOIN creation_versions v ON v.creation_id=c.id"
        f" AND v.revision=c.current_revision WHERE c.shop_id=:shop AND c.status='active' AND {predicate}"
        " ORDER BY c.created_at DESC,c.id DESC LIMIT 1"), {"shop": shop}).first()
    title = row.title.strip() if row and isinstance(row.title, str) else None
    return {"total": row.total if row else 0, "first_creation_id": row.id if row else None, "first_creation_title": title or None}


def create_app(settings: Settings | None = None, prepare: Callable[[Engine], None] | None = None) -> FastAPI:
    """`prepare(engine)` runs once at start, under the API's lock and after the migrations, before anything else
    (deploy/phone_session.py sets its one-off password there): a folder another process holds is left untouched."""
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app):
        auth.validate_config(settings)
        runtime = start(settings, "api")
        app.state.engine = runtime.engine
        app.state.started_at = datetime.now(UTC).isoformat(timespec="seconds")
        service = None
        try:
            if prepare is not None:
                prepare(runtime.engine)
            auth.adopt_password_setting(runtime.engine, settings)
            jobs.recover(runtime.engine, settings.data_dir)  # the service's sweep finalises the spooled jobs it leaves running
            reads.recover(runtime.engine)
            facebook_connect.recover(runtime.engine)
            facebook_posts.recover(runtime.engine)  # whatever the provider now: a post in flight's task is gone
            service = PosterService(runtime.engine, settings)
            app.state.poster_service = service
            service.start()
            yield
        finally:
            try:
                # Before the lock goes: no send outlives its process's hold on the data.
                await facebook_posts.drain()
                if service is not None:
                    await service.close()
            finally:
                runtime.engine.dispose()
                runtime.lock_file.close()

    app = FastAPI(title="Affiche IA — pilote", version="0.2.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url="/api/openapi.json",
                  responses={code: {"model": ErrorView} for code in (400, 401, 402, 403, 404, 409, 413, 415, 422, 428, 429, 500, 503)})
    app.add_middleware(AccessBoundary, settings=settings, owner=app)
    protected = APIRouter(dependencies=[Depends(APIKeyCookie(name=auth.COOKIE, auto_error=False))])

    @protected.get("/api/jobs/{id}")
    def job_status(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            return jobs.get_job(conn, request.state.shop, id)

    @protected.post("/api/jobs/{id}/cancel")
    def cancel_job(id: Id, request: Request, key: Key, body: Model | None = None):
        return result_response(jobs.cancel(app.state.engine, request.state.shop, key, id))

    @protected.get("/api/balance")
    def balance(request: Request):
        """The session's shop's credits (D-BALANCE-004), and per charged operation what would refuse it now whatever its
        credits, so that the owner is told before the tap. No dollar figure, and no id: always the session's shop."""
        shop = request.state.shop
        with app.state.engine.connect() as conn:
            blocked = {}
            for kind in jobs.CHARGED:
                refused = jobs.blocked(conn, settings, shop, kind)
                if refused is not None and refused.code not in BLOCKED:
                    raise refused  # shop_suspended: suspended since its session was read; told as any request is
                blocked[kind] = None if refused is None else {"reason": BLOCKED[refused.code],
                                                              "message_fr": MESSAGES[refused.code]}
            return credits.balance(conn, shop) | {"purchase_fr": credits.purchase_text(conn, settings), "blocked": blocked}

    @protected.get("/api/shop-credit-history")
    def shop_credit_history(request: Request, limit: Annotated[int, Query(ge=1, le=50)] = 20,
                            before: Annotated[str | None, Query(max_length=100)] = None):
        with app.state.engine.connect() as conn:
            items, cursor = credits.shop_history(conn, request.state.shop, limit=limit, before=before)
        return {"items": items, "next_cursor": cursor}

    @protected.get("/api/shop-dashboard")
    def shop_dashboard(request: Request):
        """What needs the owner, and the last 30 × 24 hours (D-SHOP-DASH-001, 002). as_of is taken before any read, so
        whatever was written before it is counted. One connection, one deferred BEGIN (db._on_begin): one snapshot."""
        as_of, shop = utc_now(), request.state.shop
        since = (datetime.fromisoformat(as_of) - timedelta(days=30)).isoformat(timespec="microseconds")
        with app.state.engine.connect() as conn:
            return {"as_of": as_of, "review": attention(conn, shop, TO_REVIEW), "failed": attention(conn, shop, FAILED),
                    "usage": dict(conn.execute(USAGE, {"shop": shop, "since": since, "as_of": as_of}).mappings().one())}

    @protected.get("/api/terms")
    def conditions(request: Request):
        """The conditions of use and the session's shop's acceptance of this version (D-TERMS-002). No id."""
        with app.state.engine.connect() as conn:
            return terms.view(conn, settings, request.state.shop)

    # No Idempotency-Key: accepting again writes nothing and answers the first date.
    @protected.post("/api/terms")
    def accept_conditions(body: Acceptance, request: Request):
        return terms.accept(app.state.engine, request.cookies.get(auth.COOKIE), request.state.shop, body.version)

    @protected.get("/api/status")
    def status():
        """For the operator only (AccessBoundary answers 404 to any other caller, signed in or not: operator())."""
        with app.state.engine.connect() as conn:
            return status_view(conn, settings, app.state.started_at)

    @protected.get("/api/capabilities")
    def capabilities():
        return {"image_mode": settings.image_provider, "planner_mode": settings.planner_provider,
                "planner_available": settings.planner_provider == "stub" or (settings.planner_provider == "claude" and settings.anthropic_api_key is not None),
                "formats_enabled": list(settings.formats_enabled), "chat_available": reads.available(settings),
                "facebook": settings.facebook_provider != "off"}

    # The shop's Facebook Page (D-FB-PUBLISH-002). With FACEBOOK_PROVIDER=off the routes do not exist: not_found whatever
    # the request holds, before any body is read. No Idempotency-Key and not through store.mutate: the single-use `state`
    # guards these (facebook_connect).
    if settings.facebook_provider != "off":
        said = {}  # a return page's refusal, for the card it opens next (facebook_connect.remember)

        @protected.get("/api/facebook")
        def facebook_card(request: Request):
            facebook.make_graph(settings)
            token = request.cookies.get(auth.COOKIE)
            answer = facebook_connect.read(app.state.engine, request.state.shop, token)
            code = facebook_connect.recall(said, token)  # after the read: until the next successful one
            return answer | {"last_error": None if code is None else {"code": code, "message_fr": sentence(code)}}

        @protected.post("/api/facebook/connect")
        def connect_facebook(request: Request):
            return facebook_connect.connect(app.state.engine, settings, facebook.make_graph(settings), request.state.shop,
                                            request.cookies.get(auth.COOKIE))

        @protected.post("/api/facebook/code")
        async def facebook_code(body: facebook_connect.CodeRequest, request: Request):
            graph, token = facebook.make_graph(settings), request.cookies.get(auth.COOKIE)
            try:
                return await facebook_connect.code(app.state.engine, settings, graph, request.state.shop, token, body)
            except Exception as error:  # the return page goes on to the card, which reads the sentence from here
                facebook_connect.remember(said, token, error.code if isinstance(error, store.Refused) else "facebook_failed")
                raise

        @protected.post("/api/facebook/page")
        def choose_facebook_page(body: facebook_connect.Choice, request: Request):
            facebook.make_graph(settings)
            return facebook_connect.choose(app.state.engine, request.state.shop, request.cookies.get(auth.COOKIE), body.page_id)

        @protected.delete("/api/facebook/page")
        def disconnect_facebook(request: Request):
            facebook.make_graph(settings)
            return facebook_connect.disconnect(app.state.engine, request.state.shop, request.cookies.get(auth.COOKIE))

        # Publishing on it: a post of one or several posters (D-FB-POST-003), the one way (ADR-129). The key in the post's
        # own column, not store.mutate, so that no lock is held during the calls; the owner's word on an unknown outcome
        # makes no call: store.mutate. Candidates before {id}.
        @protected.get("/api/facebook/posts/candidates")
        def post_candidates(request: Request, limit: Annotated[int, Query(ge=1, le=50)] = 20,
                            before: Annotated[str | None, Query(max_length=100)] = None,
                            ids: Annotated[str | None, Query(max_length=8000)] = None):
            return facebook_posts.candidates(app.state.engine, request.state.shop, limit, creation_cursor(before), ids)

        @protected.get("/api/facebook/posts/excluded")
        def excluded_posters(request: Request, limit: Annotated[int, Query(ge=1, le=50)] = 20,
                            before: Annotated[str | None, Query(max_length=100)] = None):
            return facebook_posts.excluded(app.state.engine, request.state.shop, limit, creation_cursor(before))

        @protected.get("/api/facebook/posts")
        def facebook_posts_list(request: Request, limit: Annotated[int, Query(ge=1, le=50)] = 20, before: Id | None = None,
                                creation: Id | None = None):
            return facebook_posts.listed(app.state.engine, request.state.shop, limit, before, creation, MESSAGES)

        @protected.post("/api/facebook/posts", status_code=202)
        async def new_facebook_post(body: facebook_posts.PostRequest, request: Request, key: Key):
            return await facebook_posts.publish(app.state.engine, settings, facebook.make_graph(settings), request.state.shop,
                                                request.cookies.get(auth.COOKIE), key, body, MESSAGES)

        @protected.get("/api/facebook/posts/{id}")
        def facebook_post(id: Id, request: Request):
            return facebook_posts.read(app.state.engine, request.state.shop, id, MESSAGES)

        @protected.post("/api/facebook/posts/{id}/stop")
        def stop_facebook_post(id: Id, request: Request):
            return facebook_posts.stop(app.state.engine, request.state.shop, request.cookies.get(auth.COOKIE), id, MESSAGES)

        @protected.post("/api/facebook/posts/{id}/outcome")
        def facebook_post_outcome(id: Id, body: facebook_posts.OutcomeRequest, request: Request, key: Key):
            return result_response(facebook_posts.outcome(app.state.engine, request.state.shop, request.cookies.get(auth.COOKIE),
                                                          key, id, body, MESSAGES))

    @protected.post("/api/reads", status_code=201)
    async def new_read(body: reads.ReadRequest, request: Request, key: Key):
        return await reads.read(app.state.engine, settings, request.state.shop, key, body, MESSAGES)

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
            ids = visuals.listed_visuals(conn, request.state.shop, creation["document"])
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

    def with_purchase_text():
        with app.state.engine.connect() as conn:
            return f'{MESSAGES["no_credit"]} {credits.purchase_text(conn, settings)}'

    @app.exception_handler(store.Refused)
    async def refusal(request, error):
        message = None
        if error.code == "no_credit":  # how to get credits (D-BALANCE-004), read apart: the admission rolled back
            try:
                message = await run_in_threadpool(with_purchase_text)
            except (OSError, SQLAlchemyError) as failure:  # the refusal still goes out, with its sentence alone
                log.warning("request=%s purchase text unreadable: %s", request.state.request_id, type(failure).__name__)
        elif error.code == "facebook_too_many":  # the shop's limit, which the refusal carries (facebook_posts._admit)
            message = MESSAGES["facebook_too_many"].format(error.limit)
        return error_response(request, error, message)

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
        # Whom to call for a forgotten password is public text, given with every answer: a sign-in form shown because
        # another shop is signed in on the device needs it too (T-MULTI-SHOP-006 review r1).
        support = {"support_fr": settings.support_contact_fr} if settings.support_contact_fr else {}
        if request.state.shop is not None:
            return {"authenticated": True, "shop_id": request.state.shop} | support
        return {"authenticated": False} | support

    @app.post("/api/session", openapi_extra={"security": []})
    def login(body: Login, request: Request):
        token, shop = auth.login(app.state.engine, body.identifier, body.password.get_secret_value(),
                                 request.client.host if request.client else "unknown", request.cookies.get(auth.COOKIE))
        response = JSONResponse({"authenticated": True, "shop_id": shop})
        response.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_SECONDS, httponly=True,
                            secure=settings.app_origin.startswith("https://"), samesite="strict", path="/")
        return response

    @app.delete("/api/session", openapi_extra={"security": []})
    def logout(request: Request):
        auth.logout(app.state.engine, request.cookies.get(auth.COOKIE))
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(auth.COOKIE, httponly=True, secure=settings.app_origin.startswith("https://"), samesite="strict")
        return response

    # No Idempotency-Key: its stored payload hash would be an unsalted SHA-256 of both passwords. The session's token is
    # kept, so no cookie changes. 403, not 401, for a wrong current password: the editor ends the session on any 401.
    @protected.post("/api/session/password")
    def change_password(body: PasswordChange, request: Request):
        auth.change_password(app.state.engine, request.state.shop, request.cookies.get(auth.COOKIE),
                             body.current_password.get_secret_value(), body.new_password.get_secret_value(),
                             request.client.host if request.client else "unknown")
        return {"changed": True}

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
    def thumbnail(sha: Sha, request: Request, v: str | None = None):
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
        return Response(data, media_type="image/jpeg", headers=_kept(v == THUMBNAIL_VERSION))

    @protected.get("/api/assets/{sha}")
    def asset(sha: Sha, request: Request, prepared: bool = False, display: bool = False, v: str | None = None):
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
        # The stored file is its own address; a prepared or display image is kept only at its encoder's version.
        cached = _kept(not prepared or v == (DISPLAY_VERSION if display else rendering.CANVAS_IMAGE_VERSION))
        if prepared and display:
            shown = _cached_display(settings.data_dir, sha)
            if shown:
                return Response(shown[0], media_type=shown[1], headers=cached)
        if prepared:
            try:
                png = rendering.canvas_image(data)
            except (ValueError, OSError):
                raise store.Refused("invalid_image") from None
            if display:
                shown = _display(settings.data_dir, sha, png)
                return Response(shown[0], media_type=shown[1], headers=cached)
            return Response(png, media_type="image/png", headers=cached)
        return Response(data, media_type=row.mime, headers=cached)

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
        return result_response(store.create_creation(app.state.engine, settings.data_dir, request.state.shop, key, body,
                                                     formats_enabled=settings.formats_enabled))

    @protected.get("/api/creations")
    def creations(request: Request, limit: Annotated[int, Query(ge=1, le=50)] = 20,
                  before: Annotated[str | None, Query(max_length=100)] = None,
                  status: Literal["active", "abandoned"] = "active"):
        cursor = creation_cursor(before)
        with app.state.engine.connect() as conn:
            # Thumbnail: the last final preview of the poster, else the current scene of its format.
            rows = conn.execute(text("SELECT c.*,v.document_json,p.name,p.variant,"
                "(SELECT r.png_sha256 FROM poster_renders r WHERE r.creation_id=c.id ORDER BY r.created_at DESC,r.id DESC LIMIT 1) AS render_sha,"
                f"(SELECT s.image_asset FROM poster_visuals s WHERE {SCENE}) AS scene_asset,"
                f"(SELECT s.status FROM poster_visuals s WHERE {SCENE}) AS scene_status,"
                f"{TO_REVIEW} AS to_review,"
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
                  "name": r["name"], "variant": r["variant"], "has_current_file": bool(r["confirmed"]),
                  # The one state that asks the owner to act comes first; "confirmed" means the file is this revision.
                  "state": "to_review" if r["to_review"] else
                           "confirmed" if r["confirmed"] else "approved" if r["scene_status"] == "approved" else "draft",
                  "thumbnail_url": f'/api/thumbnails/{r["render_sha"] or r["scene_asset"]}?v={THUMBNAIL_VERSION}'
                  if r["render_sha"] or r["scene_asset"] else None,
                  **{key: json.loads(r["document_json"])["offer"][key] for key in ("title", "price_ar")}} for r in rows[:limit]]
        return {"items": items, "total": total, "next_cursor": f'{rows[limit-1]["created_at"]}|{rows[limit-1]["id"]}' if len(rows)>limit else None}

    @protected.get("/api/creations/{id}", response_model=CreationView)
    def creation(id: Id, request: Request):
        with app.state.engine.connect() as conn:
            # Computed here only: store.get_creation's answer is also what the mutation routes return and replay.
            found = store.get_creation(conn, request.state.shop, id)
            found["confirmation"] = exports.current_confirmation(conn, request.state.shop, id, found["document"]["primary_format"])
            return result_response((200, found))

    @protected.put("/api/creations/{id}", response_model=CreationView)
    def save_creation(id: Id, body: Document, request: Request, key: Key, version: Version = None):
        return result_response(store.save_creation(app.state.engine, settings.data_dir, request.state.shop,
                                                   key, id, body, expected_revision(version),
                                                   formats_enabled=settings.formats_enabled))

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
        return result_response(store.copy_creation(app.state.engine, settings.data_dir, request.state.shop, key, id, body,
                                                   formats_enabled=settings.formats_enabled))

    @protected.post("/api/creations/{id}/abandon", response_model=CreationView)
    def abandon_creation(id: Id, request: Request, key: Key, version: Version = None, body: Model | None = None):
        return result_response(store.abandon_creation(app.state.engine, request.state.shop, key, id, expected_revision(version)))

    @protected.post("/api/creations/{id}/restore", response_model=CreationView)
    def restore_creation(id: Id, request: Request, key: Key, version: Version = None, body: Model | None = None):
        return result_response(store.restore_creation(app.state.engine, request.state.shop, key, id, expected_revision(version)))

    app.include_router(protected)
    app.include_router(admin.router(settings))
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


def serve(env_file: FilePath | None = ENV_FILE):
    """The container's command (python -m affiche.api). Uvicorn configures its own loggers only and leaves ours alone
    (disable_existing_loggers false in its 0.54 LOGGING_CONFIG): without this handler the affiche loggers would drop INFO,
    the operator's journal lines (D-ADMIN-002), and print warnings through Python's last resort only."""
    import uvicorn
    configured = load_settings(env_file)
    handler = logging.StreamHandler()  # stderr, which the journald driver keeps
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    own = logging.getLogger("affiche")
    own.addHandler(handler)
    own.setLevel(logging.INFO)
    uvicorn.run(create_app(configured), **uvicorn_options(configured))


if __name__ == "__main__":
    serve()
