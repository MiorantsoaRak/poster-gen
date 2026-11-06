from typing import get_args

import pytest
from pydantic import ValidationError

from affiche.visuals.prompts import (BACKGROUND_SENTENCES, REASON_CODES, SCENE_SENTENCES, Direction, Intent, Mood,
                                     SceneSubject, build_background_prompt, build_scene_prompt,
                                     find_commercial_terms)

FIXTURE = {"name": "iPhone 15", "variant": "Noir", "price": "1 200 000 Ar", "warranty": "Garantie 6 mois",
           "promo": "-20 %"}
SUBJECT = SceneSubject(name=FIXTURE["name"], variant=FIXTURE["variant"])
DESIGN_CODES = {"coloris", "logo", "cameras", "boutons", "forme", "extra", "texte", "cadrage", "integration"}
STUDIO = "studio, soft even light"
NOTE = "le logo est flou"
SHA = "ab" * 32
# Spelled out here, not read from the production tables, so a changed instruction fails a test.
# Scene `cameras` and background `extra` and `integration` are D-PV-002's verbatim sentences.
SCENE_RULES = ["Keep it exactly as photographed", "every marking printed on it",
               "Do not add any text, numbers, prices, badges, logos or watermarks", "One product only",
               "Vertical 9:16"]
BACKGROUND_RULES = ["No product", "no people", "nothing written"]
SCENE_MEANING = {
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
BACKGROUND_MEANING = {  # every other code is ignored
    "extra": "Remove all objects from the surface.",
    "texte": "Remove all text, numbers, logos and watermarks.",
    "integration": "Match a neutral, soft front light and an eye-level camera angle.",
}


def scene(direction=Direction(), corrections=None, note=None):
    return build_scene_prompt(SUBJECT, direction, corrections, note)


def background(direction=Direction(), corrections=None, note=None):
    return build_background_prompt(direction, corrections, note)


BUILDERS = pytest.mark.parametrize("build", [scene, background])


@BUILDERS
def test_catalogue_price_warranty_and_promo_never_reach_a_prompt(build):
    direction = Direction(mood="neon", intent="promotion", description="fond bleu nuit", style_ref=SHA)
    prompt = build(direction, list(REASON_CODES), NOTE)
    assert not [FIXTURE[key] for key in ("price", "warranty", "promo") if FIXTURE[key] in prompt]


def test_scene_prompt_names_the_subject():
    assert "Product: iPhone 15 (Noir)." in scene()


@pytest.mark.parametrize(("build", "rules"), [(scene, SCENE_RULES), (background, BACKGROUND_RULES)])
def test_fixed_block_keeps_the_essential_rules(build, rules):
    prompt = build()
    assert [rule for rule in rules if rule not in prompt] == []


def test_the_subject_has_no_field_for_commercial_facts():
    with pytest.raises(ValidationError, match="price"):
        SceneSubject(**FIXTURE)
    with pytest.raises(ValidationError, match="price"):
        Direction(price="1 200 000 Ar")
    with pytest.raises(ValidationError, match="frozen"):
        SUBJECT.name = "iPhone 16"


def test_every_reason_code_has_a_sentence_or_is_explicitly_ignored():
    assert set(REASON_CODES) == set(SCENE_SENTENCES) == set(BACKGROUND_SENTENCES) == DESIGN_CODES
    assert all(isinstance(sentence, str) and sentence for sentence in SCENE_SENTENCES.values())
    assert {code for code, sentence in BACKGROUND_SENTENCES.items() if sentence is None} == (
        DESIGN_CODES - set(BACKGROUND_MEANING))
    assert all(isinstance(BACKGROUND_SENTENCES[code], str) for code in BACKGROUND_MEANING)


@pytest.mark.parametrize(("build", "meaning"), [(scene, SCENE_MEANING), (background, BACKGROUND_MEANING)])
@pytest.mark.parametrize("code", REASON_CODES)
def test_each_code_adds_its_meaning_or_nothing(build, meaning, code):
    initial, revised = build(), build(corrections=[code])
    assert revised.startswith(initial)
    added = revised.removeprefix(initial)
    if code in meaning:
        assert meaning[code] in added
    else:
        assert added == ""


@BUILDERS
def test_corrections_follow_the_canonical_order_not_the_callers(build):
    codes = list(REASON_CODES)
    assert build(corrections=codes[::-1]) == build(corrections=codes) == build(corrections=codes + codes)


@BUILDERS
def test_unknown_code_is_a_programming_error(build):
    with pytest.raises(ValueError):
        build(corrections=["prix"])


@BUILDERS
def test_arm_b_revision_is_the_initial_prompt(build):
    initial = build()
    assert build(corrections=None, note=None) == build(corrections=[], note="  ") == initial
    assert "correction" not in initial.lower()
    assert not [s for s in [*SCENE_SENTENCES.values(), *BACKGROUND_SENTENCES.values()] if s and s in initial]


@BUILDERS
def test_note_is_added_with_its_prefix(build):
    assert build(note=f"  {NOTE} ").endswith(f"\nShop's correction note (French): {NOTE}")


@BUILDERS
@pytest.mark.parametrize(("direction", "is_default", "present", "absent"), [
    (Direction(), True, [STUDIO], ["Atmosphere:", "Shop's direction", "style reference"]),
    (Direction(intent="promotion"), True, [STUDIO, "Atmosphere:"], []),
    (Direction(mood="studio"), False, [STUDIO], []),
    (Direction(mood="neon"), False, ["Mood: neon"], [STUDIO]),
    (Direction(description="  fond bleu nuit "), False, ["Shop's direction (French): fond bleu nuit"],
     ["nuit ", STUDIO]),
    (Direction(style_ref=SHA), False, ["image is a style reference only"], [STUDIO]),
])
def test_direction(build, direction, is_default, present, absent):
    prompt = build(direction)
    assert direction.is_default is is_default
    assert all(text in prompt for text in present) and not any(text in prompt for text in absent)


def test_style_reference_position_per_prompt_type():
    assert "The last image is a style reference" in scene(Direction(style_ref=SHA))
    assert "The attached image is a style reference" in background(Direction(style_ref=SHA))


@BUILDERS
def test_every_mood_and_intent_has_its_own_phrase(build):
    assert len({build(Direction(mood=mood)) for mood in get_args(Mood)}) == len(get_args(Mood))
    assert len({build(Direction(intent=intent)) for intent in get_args(Intent)}) == len(get_args(Intent))


def test_description_limits():
    assert Direction(description="x" * 500).description == "x" * 500
    with pytest.raises(ValidationError, match="500"):
        Direction(description="x" * 501)
    assert Direction(description=" \n ").description is None and Direction(description=" \n ").is_default


def test_product_height_ratio():
    assert "about 40% of the image height" in scene()
    assert "about 35% of the image height" in build_scene_prompt(SUBJECT, Direction(), None, None,
                                                                 product_height_ratio=0.35)


@pytest.mark.parametrize("text", [
    "1 200 000 Ar", "-20 %", "500 euros", "livré demain", "Garantie 6 mois",
    "GARANTIE", "Réduction", "reduction", "CRÉDIT", "1.200.000", "1,200,000", "1 200 000",
    "1\xa0200\xa0000", "1  200  000", "1200000", "afficher 49,99 en grand", "ajouter 129.90 en bas",
    "10 €", "15 $", "MGA", "soldes", "prix cassé", "paiement en 3 fois",
])
def test_screen_matches(text):
    assert find_commercial_terms(text)


@pytest.mark.parametrize("text", [
    "iPhone 15", "128 Go", "5G", "lumière pastel", "3 caméras", "iPhone 15, 128 Go", "2,5 GHz", "6,1 pouces",
    "arrière-plan sombre", "carte", "table en bois", "effet radar", "art déco", "accréditation", "",
])
def test_screen_does_not_match(text):
    assert find_commercial_terms(text) == []


@pytest.mark.parametrize(("text", "matches"), [
    ("livré demain", ["livré"]),
    ("Fond rouge, 1 200 000 Ar, CRÉDIT possible", ["1 200 000", "Ar", "CRÉDIT"]),
    ("afficher 49,99 en grand, 1  200  000", ["49,99", "1  200  000"]),
    ("réduction", ["réduction"]),  # decomposed accent, as some keyboards send it
])
def test_screen_returns_the_substrings_in_text_order(text, matches):
    assert find_commercial_terms(text) == matches
