"""Validated application documents, never serialised canvas-library objects."""
import json
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

MAX_PRICE = 9_007_199_254_740_991
Id = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]
Sha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Colour = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
Format = Literal["feed", "square", "story"]
FORMATS = {"feed": (1080, 1350), "square": (1080, 1080), "story": (1080, 1920)}


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False, hide_input_in_errors=True)


def canonical(value: Model | dict | list) -> str:
    if isinstance(value, Model):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def parse_price(value: str) -> int:
    """Only integer Ariary and groups of three; never silently round or strip punctuation."""
    if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+)", value):
        raise ValueError("invalid_price")
    digits = re.sub(r"[ \u00a0\u202f]", "", value).lstrip("0") or "0"
    if len(digits) > 16 or int(digits) > MAX_PRICE:
        raise ValueError("invalid_price")
    return int(digits)


def format_price(value: int) -> str:
    if type(value) is not int or not 0 <= value <= MAX_PRICE:
        raise ValueError("invalid_price")
    return f"{value:,}".replace(",", "\u202f") + " Ar"


class Offer(Model):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
    price_ar: int = Field(ge=0, le=MAX_PRICE)
    currency: Literal["MGA"] = "MGA"


class ProductInput(Model):
    product_ref: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")] | None = None
    name: Name
    variant: Name
    photo_assets: list[Sha] = Field(min_length=1, max_length=3)
    facts: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = Field(default_factory=list, max_length=10)
    supersedes_id: Id | None = None

    @field_validator("photo_assets")
    @classmethod
    def distinct_photos(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("duplicate_photo")
        return value


class Profile(Model):
    name: Name | None = None
    contact: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] | None = None
    logo_asset: Sha | None = None

    @field_validator("contact")
    @classmethod
    def contact_lines(cls, value):
        if value is not None and len(value.splitlines()) > 6:
            raise ValueError("too_many_contact_lines")
        return value


class BrandSnapshot(Profile):
    profile_revision: int = Field(ge=1)


class Inclusion(Model):
    logo: bool
    shop_name: bool
    contact: bool


class NewCreation(Model):
    input_id: Id
    offer: Offer
    brand_selection: Inclusion
    primary_format: Format = "feed"


class Crop(Model):
    x: float = Field(ge=0, le=40000)
    y: float = Field(ge=0, le=40000)
    w: float = Field(gt=0, le=40000)
    h: float = Field(gt=0, le=40000)


class Scene(Model):
    visual_id: Id | None = None
    crop: Crop | None = None

    @model_validator(mode="after")
    def paired(self):
        if (self.visual_id is None) != (self.crop is None):
            raise ValueError("visual_and_crop_required_together")
        return self


class Outline(Model):
    colour: Colour
    width: float = Field(ge=0, le=24)


class Shadow(Model):
    colour: Colour
    blur: float = Field(ge=0, le=40)
    offset_x: float = Field(ge=-40, le=40)
    offset_y: float = Field(ge=-40, le=40)
    opacity: float = Field(ge=0, le=1)


class Layer(Model):
    id: Id
    x: float = Field(ge=-4000, le=4000)
    y: float = Field(ge=-4000, le=4000)
    width: float = Field(gt=0, le=4000)
    height: float = Field(gt=0, le=4000)
    visible: bool = True
    z: int = Field(ge=0, le=100)


class PriceBadge(Model):
    fill: Colour = "#FFFFFF"
    border_start: Colour = "#009FE3"
    border_end: Colour = "#1853BD"


class TextLayer(Layer):
    kind: Literal["text"] = "text"
    role: Literal["title", "price", "shop_name", "contact"]
    font_id: Literal["noto-sans", "noto-serif", "montserrat-black-italic"] = "noto-sans"
    font_size: float = Field(64.0, ge=24, le=240)
    weight: Literal[400, 700, 900] = 700
    fill: Colour = "#FFFFFF"
    align: Literal["left", "center", "right"] = "left"
    line_height: float = Field(1.2, ge=0.8, le=2)
    outline: Outline | None = None
    shadow: Shadow | None = None
    texture_effect_id: Id | None = None
    # Omit the new default so old draft/request/style hashes remain replayable.
    price_badge: PriceBadge | None = Field(None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def supported_typography(self):
        if (self.font_id == "montserrat-black-italic") != (self.weight == 900):
            raise ValueError("unsupported_font")
        if self.price_badge is not None and self.role != "price":
            raise ValueError("price_badge_requires_price")
        return self


class ImageLayer(Layer):
    kind: Literal["logo", "product_cutout"]
    role: Literal["logo", "product"]
    asset: Sha
    keep_aspect: Literal[True] = True

    @field_validator("keep_aspect", mode="before")
    @classmethod
    def boolean_aspect(cls, value):
        if value is not True:
            raise ValueError("keep_aspect_required")
        return value

    @model_validator(mode="after")
    def matching_role(self):
        if (self.kind == "logo") != (self.role == "logo"):
            raise ValueError("invalid_image_role")
        return self


class Layout(Model):
    scene: Scene = Field(default_factory=Scene)
    layers: list[Annotated[TextLayer | ImageLayer, Field(discriminator="kind")]] = Field(min_length=2, max_length=20)


class Document(Model):
    schema_version: Literal[1] = 1
    input_id: Id
    offer: Offer
    brand_snapshot: BrandSnapshot
    include: Inclusion
    primary_format: Format
    formats: dict[Format, Layout] = Field(min_length=1, max_length=3)

    @field_validator("schema_version", mode="before")
    @classmethod
    def version_number(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("document_version_unsupported")
        return value

    @model_validator(mode="after")
    def consistent_layers(self):
        if self.primary_format not in self.formats:
            raise ValueError("missing_primary_format")
        source = {"logo": self.brand_snapshot.logo_asset, "shop_name": self.brand_snapshot.name,
                  "contact": self.brand_snapshot.contact}
        enabled = self.include.model_dump()
        if any(enabled[role] and not value for role, value in source.items()):
            raise ValueError("missing_brand_field")
        for layout in self.formats.values():
            ids, roles = [layer.id for layer in layout.layers], [layer.role for layer in layout.layers]
            if len(set(ids)) != len(ids) or len(set(roles)) != len(roles):
                raise ValueError("duplicate_layer")
            if not {"title", "price"}.issubset(roles):
                raise ValueError("missing_offer_layer")
            for role, include in enabled.items():
                if include and role not in roles:
                    raise ValueError("missing_brand_layer")
            for layer in layout.layers:
                # An included shop name/contact may be hidden when the scene itself carries it (export checks that).
                if layer.role in enabled and layer.visible and not enabled[layer.role] or (
                        layer.role == "logo" and layer.visible != enabled["logo"]):
                    raise ValueError("inconsistent_visibility")
                # Title and price may be hidden: export then requires a scene that drew exactly the current ones.
                if layer.role == "logo" and layer.asset != self.brand_snapshot.logo_asset:
                    raise ValueError("wrong_logo")
        return self


class CopyCreation(Model):
    source_revision: int = Field(ge=1)
    new_input_id: Id | None = None
    reason: Literal["price_update", "new_campaign", "replace_input", "save_conflict"]
    unsaved_document: Document | None = None

    @model_validator(mode="after")
    def explicit_conflict(self):
        if self.unsaved_document is not None and self.reason != "save_conflict":
            raise ValueError("unsaved_document_requires_save_conflict")
        if (self.new_input_id is not None) != (self.reason == "replace_input"):
            raise ValueError("replacement_requires_new_input")
        return self
