"""Image-model prompts and screening of the shop's free text (D-PRODUCT-VISUALS-002). Pure: no I/O."""

import re
import unicodedata
from collections.abc import Mapping
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

Mood = Literal["neon", "pastel", "studio", "lifestyle", "minimal"]
Intent = Literal["promotion", "nouveaute", "benefice"]
ReasonCode = Literal["coloris", "logo", "cameras", "boutons", "forme", "extra", "texte", "cadrage", "integration"]
REASON_CODES: tuple[ReasonCode, ...] = get_args(ReasonCode)  # canonical order: the review checklist's


class SceneSubject(BaseModel):
    """All the model learns about the product. Price, warranty and promo have no field to travel in (R-003 c.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    variant: str


class Direction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mood: Mood | None = None
    intent: Intent | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    style_ref: str | None = None  # asset sha256

    @field_validator("description")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value or None

    @property
    def is_default(self) -> bool:
        # Intent does not count: it sets an atmosphere, not the look.
        return self.mood is None and self.description is None and self.style_ref is None


_MOOD_PHRASES: dict[Mood, str] = {
    "neon": "neon, a dark background with vivid neon colour accents and glowing reflections",
    "pastel": "pastel, soft pastel colours and gentle diffuse light",
    "studio": "studio, soft even light",
    "lifestyle": "lifestyle, a real everyday setting with natural daylight and a softly blurred background",
    "minimal": "minimal, a plain single-colour background with plenty of empty space",
}
_INTENT_PHRASES: dict[Intent, str] = {
    "promotion": "energetic and eye-catching, with bold contrast and dynamic light",
    "nouveaute": "fresh and premium, like a product launch, with a spotlight on the product",
    "benefice": "calm and trustworthy, with warm light that brings out the product's quality",
}

SCENE_SENTENCES: dict[ReasonCode, str] = {
    "coloris": "The product colour must match image 1 exactly.",
    "logo": "The manufacturer logo must match image 1 exactly: same logo, same place, nothing added or removed.",
    "cameras": "The camera layout must match image 1 exactly.",
    "boutons": "The buttons and ports must match image 1 exactly: same number, same places.",
    "forme": "The product shape and proportions must match image 1 exactly; do not stretch or distort it.",
    "extra": "Show only this one product: remove every other device and accessory.",
    "texte": "Remove all text, numbers, badges and logos that are not printed on the product itself.",
    "cadrage": "Keep the whole product inside the central square of the image, with clear space on every side.",
    "integration": "Light, shadows and perspective on the product must match the scene, so it looks placed in it.",
}
# None: the code has no meaning for an empty background (it is about the product), so it adds nothing.
BACKGROUND_SENTENCES: dict[ReasonCode, str | None] = {
    "coloris": None,
    "logo": None,
    "cameras": None,
    "boutons": None,
    "forme": None,
    "extra": "Remove all objects from the surface.",
    "texte": "Remove all text, numbers, logos and watermarks.",
    "cadrage": None,
    "integration": "Match a neutral, soft front light and an eye-level camera angle.",
}


def build_scene_prompt(subject: SceneSubject, direction: Direction, corrections: list[ReasonCode] | None,
                       note: str | None, *, product_height_ratio: float = 0.40) -> str:
    """Images sent: the variant's photos first, then the style reference if any (D-PV-003)."""
    return "\n".join([
        f"Advertising scene for a shop poster. Product: {subject.name} ({subject.variant}).",
        "Rules (they override everything below):",
        "1. Image 1 is the product; any further product photos show the same product from other angles. "
        "Keep it exactly as photographed: shape, colour, camera layout, buttons, ports, and every marking "
        "printed on it (brand logo, labels, camera-module text).",
        "2. Do not add any text, numbers, prices, badges, logos or watermarks to the scene. "
        "Only markings already printed on the product may appear.",
        "3. One product only; no added devices or accessories.",
        f"4. Vertical 9:16; the product centred, fully visible, about {product_height_ratio:.0%} of the image "
        "height, with clear space above and below.",
        *_direction_lines(direction, "The last image"),
        *_correction_lines(corrections, note, SCENE_SENTENCES),
    ])


def build_background_prompt(direction: Direction, corrections: list[ReasonCode] | None, note: str | None) -> str:
    """Image sent: the style reference alone, or none (D-PV-003)."""
    return "\n".join([
        "Empty background for a shop poster.",
        "Rules (they override everything below):",
        "1. An empty product-photography scene, vertical 9:16, with a surface in the lower-middle area.",
        "2. No product, no people, nothing written: no text, numbers, logos or watermarks.",
        *_direction_lines(direction, "The attached image"),
        *_correction_lines(corrections, note, BACKGROUND_SENTENCES),
    ])


def _direction_lines(direction: Direction, style_ref_image: str) -> list[str]:
    lines = []
    mood = "studio" if direction.is_default else direction.mood
    if mood:
        lines.append(f"Mood: {_MOOD_PHRASES[mood]}.")
    if direction.intent:
        lines.append(f"Atmosphere: {_INTENT_PHRASES[direction.intent]}. Show it only through light, colour and "
                     "composition, never with words, numbers or badges.")
    if direction.description:
        lines.append(f"Shop's direction (French): {direction.description}")
    if direction.style_ref:
        lines.append(f"{style_ref_image} is a style reference only: take only its mood, colours and lighting, "
                     "never its objects, text or logos.")
    return lines


def _correction_lines(corrections: list[ReasonCode] | None, note: str | None,
                      sentences: Mapping[ReasonCode, str | None]) -> list[str]:
    # Canonical order, never the caller's: the same input always gives the same prompt.
    # An unknown code raises (ValueError from .index): a programming error, not input to drop.
    codes = sorted(set(corrections or ()), key=REASON_CODES.index)
    lines = [f"- {sentence}" for code in codes if (sentence := sentences[code])]
    if note and note.strip():
        lines.append(f"Shop's correction note (French): {note.strip()}")
    return ["Corrections to the previous attempt:", *lines] if lines else []


# ponytail: best-effort blocklist (R-003 c.1, ADR-011); it cannot be complete, and it also blocks a few innocent
# texts: two numbers apart by a space ("Galaxy S24 128 Go"), a 4-digit year, "5000 mAh". The real guards are
# rule 2 of the scene prompt and the review checklist.
_COMMERCIAL_TERMS = re.compile(
    r"\b(?:ar|ariary|mga|euros?|dollars?)\b"
    r"|[€$%]"
    r"|\d(?:(?:[.,]|\s+)?\d){3,}"  # >= 4 digits; between two digits, one dot or comma, or spaces (not a mix)
    r"|\b(?:garanti|livr|remise|reduc|sold|promo|offert|gratuit|prix|credit|paiement|cadeau)\w*",
    re.IGNORECASE,
)


def find_commercial_terms(text: str) -> list[str]:
    """Commercial-looking substrings of the text, NFC-normalised with accents kept (for the UI), in text order."""
    text = unicodedata.normalize("NFC", text)  # else a decomposed "é" splits "réduction" in two
    # One character in, one character out, so match positions index the text itself.
    # NFKD also turns U+00A0 and U+202F (French thousands separators) into plain spaces.
    folded = "".join(unicodedata.normalize("NFKD", char)[0] for char in text)
    return [text[match.start():match.end()] for match in _COMMERCIAL_TERMS.finditer(folded)]
