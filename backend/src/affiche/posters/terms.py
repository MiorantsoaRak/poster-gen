"""The conditions of use (D-TERMS-001, D-TERMS-002, D-TERMS-003): the French text, its version, a shop's acceptance, and
the gate that refuses a new AI request without it. The text is held here, not in the database (a restore could pair an
older text with a newer version) nor in the bundle (the page shows the server's words of now). A word changed needs a
new VERSION: tests/test_terms.py pins the text's hash to it. The contact is not part of the
version: changing it asks nobody again."""
from sqlalchemy import text

from affiche.db import utc_now, write_tx
from . import auth
from .store import Refused

VERSION = "2026-11-21"  # the text's date, ISO, at most one a day; a new one asks every shop again
# Drafts waiting for the owner's reading (designs/service-terms.md, "French texts"); a jurist has read none of this.
PARAGRAPHS_FR = (
    "Ce service fabrique vos affiches avec une intelligence artificielle (IA). L'IA peut se tromper : un mot mal écrit, "
    "un prix déformé, un détail du produit inexact, une caractéristique que le produit n'a pas, un logo de marque mal "
    "dessiné.",
    "Avant d'utiliser une affiche, vous vérifiez chaque mot, chaque prix, chaque caractéristique et chaque logo ou "
    "marque. Si vous demandez des caractéristiques sans les écrire, l'IA les choisit, et elles peuvent être fausses. Ce "
    "que vous publiez reste sous votre responsabilité.",
    "Les crédits se paient à l'avance. Un crédit sert à une image : une nouvelle version de l'affiche, un ajustement de "
    "la scène ou la matière d'un texte. Si l'image n'a pas pu être faite, le crédit vous est rendu. Une image faite "
    "n'est pas remboursée, même si elle ne vous convient pas.",
    "Ces conditions valent pour la boutique. Toute personne qui se connecte avec l'identifiant et le mot de passe de la "
    "boutique agit en son nom : ne les confiez qu'à des personnes de confiance.",
    "Ce que le service garde de vos photos et de vos messages, et ce qu'il envoie à d'autres services, est expliqué sur "
    "la page « Vos données ».",
    # 2026-11-21: publishing on a Facebook Page (designs/facebook-publishing.md, answer 1 of the owner); amended before its
    # release for a post of one or several posters (designs/facebook-post-page.md, D-FB-POST-006, T-FB-011).
    "Si vous connectez une Page Facebook, le service garde son nom, son identifiant et l'accès que Facebook a donné "
    "pour cette Page. Cet accès reste sur le serveur : il n'est jamais affiché ni envoyé au navigateur. Pour chaque "
    "publication demandée, une fois la demande prise en compte et même si elle n'aboutit pas, le service garde sa "
    "date, la Page, les affiches qu'elle contient et leur ordre, sa description, son résultat, votre réponse si vous "
    "dites qu'elle est ou n'est pas sur votre Page, et ce qu'il a retenu de la réponse de Facebook (les identifiants "
    "des images reçues, puis le lien de la publication ou un code d'erreur). Les images envoyées sont les fichiers "
    "finaux des affiches confirmées. Une image reçue par Facebook pour une publication qui n'aboutit pas y reste, "
    "invisible sur votre Page ; le service ne la supprime pas. Le service "
    "ne lit pas le contenu de votre Page ; à la connexion, il reçoit le nom et l'identifiant des Pages que vous "
    "autorisez. « Déconnecter », dans « Mon compte », efface aussitôt cet accès ici ; les copies de secours peuvent "
    "encore le contenir, et l'autorisation donnée sur Facebook se retire sur Facebook. La page « Vos données » donne "
    "le détail. Les publications faites restent sur votre Page jusqu'à ce que vous les supprimiez sur "
    "Facebook ; chaque affiche garde la liste des publications où elle figure. C'est vous qui publiez : avant "
    "« Publier », vous vérifiez les images et la description. Une publication faite est sur votre Page, sous votre "
    "responsabilité.",
    "Si ces conditions changent, la nouvelle version vous sera montrée ; il faudra l'accepter avant de demander quoi "
    "que ce soit de nouveau à l'IA.",
    "Une question, un problème, une demande sur vos données : contactez {contact}.",
)
NO_CONTACT_FR = "l'opérateur qui vous a remis votre identifiant"


def paragraphs(settings) -> list[str]:
    """SUPPORT_CONTACT_FR, else the fallback, in place of {contact}: replace, never format, so braces in it stay."""
    contact = settings.support_contact_fr or NO_CONTACT_FR
    return [paragraph.replace("{contact}", contact) for paragraph in PARAGRAPHS_FR]


def view(conn, settings, shop: int) -> dict:
    """GET /api/terms. accepted_at: of the current version, else None; changed: an earlier version was accepted."""
    accepted, at = conn.execute(text("SELECT terms_version, terms_accepted_at FROM shop_profile WHERE id=:shop"),
                                {"shop": shop}).one()
    return {"version": VERSION, "paragraphs_fr": paragraphs(settings), "accepted_at": at if accepted == VERSION else None,
            "changed": accepted is not None and accepted != VERSION}


def require(conn, shop: int) -> None:
    """The gate (D-TERMS-003), the one comparison with the current version: in the caller's admission transaction, after
    replay and ownership and before the limits and the credit, so a refusal writes, takes and sends nothing. Callers:
    jobs.enqueue (a kind with a provider call), reads._admit (a new read) and jobs.blocked (GET /api/balance)."""
    if conn.execute(text("SELECT terms_version FROM shop_profile WHERE id=:shop"), {"shop": shop}).scalar() != VERSION:
        raise Refused("terms_required", 403)


def accept(engine, token: str, shop: int, version: str) -> dict:
    """POST /api/terms. The session was read before this transaction: it is checked again once the write lock is held,
    so a session ended or a shop suspended meanwhile writes nothing (401). Sent twice, or by two devices at once, it
    writes once and answers the first date."""
    with write_tx(engine) as conn:
        if auth.live_shop(conn, token) != shop:
            raise Refused("unauthenticated", 401)
        if version != VERSION:
            raise Refused("terms_outdated", 409)
        conn.execute(text("UPDATE shop_profile SET terms_version=:version, terms_accepted_at=:now "
                          "WHERE id=:shop AND terms_version IS NOT :version"),
                     {"version": version, "now": utc_now(), "shop": shop})
        return {"version": version, "accepted_at": conn.execute(
            text("SELECT terms_accepted_at FROM shop_profile WHERE id=:shop"), {"shop": shop}).scalar_one()}
