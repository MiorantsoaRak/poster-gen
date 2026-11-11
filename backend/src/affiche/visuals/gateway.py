"""Image provider gateway (D-PRODUCT-VISUALS-003): provider inputs, the OpenAI adapter and its error mapping,
usage-based cost, and the stub. The only module that reads the API key. It never retries: the one retry
belongs to the caller, inside a budget transaction (T-PV-007)."""

import asyncio
import base64
import hashlib
import io
import itertools
import json
import logging
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, get_args

import httpx2
import openai
from openai.types import ImagesResponse
from PIL import Image, ImageCms, ImageOps
from pydantic import SecretStr

from affiche.config import ProviderErrorKind, Settings

log = logging.getLogger(__name__)

Purpose = Literal["scene", "background"]
OUTPUT_SIZE = (1088, 1920)
POSTER_SIZES = {"feed": "1088x1360", "square": "1088x1088", "story": "1152x2048"}
IMAGE_SIZES = {"1088x1920", "1024x1024", *POSTER_SIZES.values()}
PROVIDER_INPUT_LONG_EDGE = 1536
CLIENT_TIMEOUT_S = 180
MAX_DETAIL_CHARS = 500

ERROR_KINDS: tuple[ProviderErrorKind, ...] = get_args(ProviderErrorKind)
RETRYABLE_KINDS = frozenset({"rate_limited", "provider_error"})  # 429 rate limit, 5xx, connection error
# error.code values (OpenAI error-codes guide, read 2026-11-06). That page gives `insufficient_quota` as
# error.type only; it is kept as a code too, as the design names it.
QUOTA_CODES = frozenset({"insufficient_quota", "credit_balance_exhausted", "organization_spend_limit_exceeded",
                         "project_spend_limit_exceeded", "organization_usage_limit_exceeded"})
_API_KEY = re.compile(r"\bsk-[\w*.\-]+")  # a 401 message echoes the (masked) key


@dataclass(frozen=True)
class Rates:
    """Micro-USD per token, which equals USD per 1M tokens."""

    text_input: Decimal
    image_input: Decimal
    image_output: Decimal


# OpenAI pricing page, standard tier, read 2026-11-06. Snapshot ids (gpt-image-2-2026-04-21, …) are not listed there.
_GPT_IMAGE_2_RATES = Rates(text_input=Decimal(5), image_input=Decimal(8), image_output=Decimal(30))
RATES: dict[str, Rates] = {
    "gpt-image-2": _GPT_IMAGE_2_RATES,
    "gpt-image-2.5-sunburst": _GPT_IMAGE_2_RATES,
    "gpt-image-2.5-flare": _GPT_IMAGE_2_RATES,
}


class ProviderError(Exception):
    """A failed provider call. `retryable` follows from the kind; `detail` is redacted and truncated."""

    def __init__(self, kind: ProviderErrorKind, detail: str) -> None:
        if kind not in ERROR_KINDS:
            raise ValueError(f"unknown provider error kind: {kind!r}")
        self.kind = kind
        self.retryable = kind in RETRYABLE_KINDS
        self.detail = _API_KEY.sub("<redacted key>", detail)[:MAX_DETAIL_CHARS]
        super().__init__(f"{kind}: {self.detail}")


@dataclass(frozen=True)
class ProviderResult:
    image: bytes = field(repr=False)
    mime: str
    usage: dict[str, object] | None
    cost_micros: int | None  # None: no usable usage, so the caller keeps the reserved estimate


# --- Images -----------------------------------------------------------------------------------------------------

_SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
SRGB_GAMMA = 1 / 2.2  # PNG gAMA of an sRGB image (0.45455)
# PNG cHRM of sRGB, in Pillow's order: white x, y, then red, green and blue x, y (D65 white).
SRGB_CHROMATICITY = (0.3127, 0.3290, 0.64, 0.33, 0.30, 0.60, 0.15, 0.06)


def prepare_provider_input(data: bytes) -> bytes:
    """The copy sent to the provider: upright, sRGB, flattened onto white, long edge <= 1536, PNG without metadata.

    Raises ValueError for an ICC profile that cannot be read or applied, or for non-sRGB colour metadata without one,
    and Pillow's errors for an undecodable image.
    """
    with Image.open(io.BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source)
    icc_profile = image.info.get("icc_profile")
    refuse_undeclared_colours(image.info)
    if image.mode == "1":
        image = image.convert("L")
    if "transparency" in image.info and image.mode in ("L", "RGB"):  # a tRNS colour: alpha, same colour channels
        image = image.convert(image.mode + "A")
    if image.mode not in ("L", "LA", "RGB", "RGBA", "CMYK"):  # P, PA, I;16, La, RGBa…
        image = image.convert("RGBA" if image.has_transparency_data else "RGB")
    alpha = image.getchannel("A") if image.mode in ("LA", "RGBA") else None
    colour = image.convert(image.mode[:-1]) if alpha is not None else image  # the ICC profile describes these only
    image = _to_srgb(colour, icc_profile) if icc_profile else colour.convert("RGB")
    if alpha is not None:
        flat = Image.new("RGB", image.size, "white")
        flat.paste(image, mask=alpha)
        image = flat
    image.thumbnail((PROVIDER_INPUT_LONG_EDGE, PROVIDER_INPUT_LONG_EDGE), Image.Resampling.LANCZOS)
    image.info.clear()  # PNG save writes icc_profile and transparency from info
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def refuse_undeclared_colours(info: Mapping[str, object]) -> None:
    # Without an ICC profile the pixels are read as sRGB, so PNG gAMA/cHRM saying otherwise would shift the colours.
    # An ICC profile or an sRGB chunk is authoritative. Converting gAMA/cHRM is not worth it for phone photos.
    if info.get("icc_profile") or "srgb" in info:
        return
    gamma, chromaticity = info.get("gamma"), info.get("chromaticity")
    if (gamma is not None and abs(gamma - SRGB_GAMMA) > 0.01) or (chromaticity is not None and any(
            abs(value - srgb) > 0.01 for value, srgb in zip(chromaticity, SRGB_CHROMATICITY, strict=True))):
        raise ValueError("the photo declares non-sRGB colours (PNG gamma or primaries) and no ICC profile: "
                         "re-export it as sRGB")


def _to_srgb(image: Image.Image, icc_profile: bytes) -> Image.Image:
    # Without this, a Display-P3 phone photo would be read as sRGB and its colours shift (the `coloris` risk).
    try:
        profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
        # Relative colorimetric keeps in-gamut colours exact; perceptual may shift them.
        return ImageCms.profileToProfile(image, profile, _SRGB, outputMode="RGB",
                                         renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC)
    except (OSError, ImageCms.PyCMSError) as error:
        raise ValueError(f"the photo's ICC colour profile cannot be read or applied: {error}") from error


def image_dimensions(size: str) -> tuple[int, int]:
    if size not in IMAGE_SIZES:
        raise ValueError("unsupported image size")
    width, height = size.split("x")
    return int(width), int(height)


def validate_image(b64: str | None, *, size: str = "1088x1920") -> tuple[bytes, str]:
    """Bytes and mime of a provider image. Anything but a complete PNG or WebP of the requested size is
    `invalid_response`."""
    expected = image_dimensions(size)
    if not isinstance(b64, str):
        raise ProviderError("invalid_response", "no b64_json image in the response")
    try:
        data = base64.b64decode(b64, validate=True)
        with Image.open(io.BytesIO(data)) as image:
            image.load()  # a full decode, so that truncated data fails here
            image_format, dimensions = image.format, image.size
    except (ValueError, OSError, SyntaxError, Image.DecompressionBombError) as error:
        undecodable = str(error)
    else:
        undecodable = None
    if undecodable is not None:  # raised outside the handler: no raw error travels as __context__
        raise ProviderError("invalid_response", f"undecodable image: {undecodable}")
    if image_format not in ("PNG", "WEBP"):
        raise ProviderError("invalid_response", f"format {image_format}, expected PNG or WEBP")
    # ponytail: strict size; accept-and-crop larger outputs if the evaluation shows mismatches.
    if dimensions != expected:
        raise ProviderError("invalid_response", f"size {dimensions[0]}x{dimensions[1]}, expected {size}")
    return data, Image.MIME[image_format]


# --- Money --------------------------------------------------------------------------------------------------------

def usd_to_micros(usd: Decimal) -> int:
    """Rounded up, so the ledger never under-counts."""
    return math.ceil(usd * 1_000_000)


def parse_usage(raw: object) -> dict[str, object] | None:
    """The allowlisted token counts of a usage (an SDK model or a mapping), or None when they are missing or
    inconsistent, so that a malformed usage can never replace the reservation with an undercount.

    Usable: every count present is an int >= 0 (not a bool), input_tokens is present, output_tokens > 0,
    total_tokens (if present) == input + output, and the split counts supplied (text, image or both) sum to at most
    input_tokens.
    """
    counts = _present(raw, ("input_tokens", "output_tokens", "total_tokens"))
    split = _present(_field(raw, "input_tokens_details"), ("text_tokens", "image_tokens"))
    if not all(type(count) is int and count >= 0 for count in [*counts.values(), *split.values()]):
        return None
    input_tokens, output_tokens = counts.get("input_tokens"), counts.get("output_tokens", 0)
    if (input_tokens is None or output_tokens == 0
            or counts.get("total_tokens", input_tokens + output_tokens) != input_tokens + output_tokens
            or sum(split.values()) > input_tokens):
        return None
    return counts | ({"input_tokens_details": split} if split else {})


def _present(source: object, names: tuple[str, ...]) -> dict[str, object]:
    return {name: value for name in names if (value := _field(source, name)) is not None}


def _field(source: object, name: str) -> object:
    # Attributes, not to_dict(): serialisation turns a bool into 1 or 0, which would then pass as a count.
    return source.get(name) if isinstance(source, Mapping) else getattr(source, name, None)


def cost_micros(model: str, usage: object) -> int | None:
    """ceil(sum of tokens x rate), in micro-USD. None when `parse_usage` finds no usable usage.

    When the split is unknown the higher rate is charged: input tokens not reported as text are charged at the
    image-input rate, and every output token at the image-output rate.
    """
    if (parsed := parse_usage(usage)) is None:
        return None
    input_tokens, output_tokens = parsed["input_tokens"], parsed["output_tokens"]
    text_tokens = parsed.get("input_tokens_details", {}).get("text_tokens", 0)
    rates = RATES[model]
    return math.ceil(text_tokens * rates.text_input + (input_tokens - text_tokens) * rates.image_input
                     + output_tokens * rates.image_output)


# --- Providers ----------------------------------------------------------------------------------------------------

def _check_request(purpose: Purpose, model: str, images: list[bytes]) -> None:
    """Programming and configuration errors, refused before anything is sent or paid."""
    if model not in RATES:
        raise ValueError(f"no token rates for model {model!r}: add them to RATES before using it")
    if not (purpose == "scene" and images or purpose == "background" and len(images) <= 1):
        raise ValueError(f"{purpose!r} with {len(images)} image(s): a scene needs at least one photo, "
                         "a background takes only the style reference")


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: SecretStr, *, http_client: httpx2.AsyncClient | None = None) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key.get_secret_value(), timeout=CLIENT_TIMEOUT_S,
                                          max_retries=0, http_client=http_client)
        for name in ("openai", "httpx2", "httpcore2"):  # their debug logs carry request details
            logging.getLogger(name).setLevel(logging.WARNING)

    async def generate(self, *, purpose: Purpose, model: str, quality: str, prompt: str,
                       images: list[bytes], size: str = "1088x1920") -> ProviderResult:
        """`images` are provider_input copies: the variant's photos then the style reference, in that order."""
        _check_request(purpose, model, images)
        image_dimensions(size)
        try:
            response = await self._send(model, quality, prompt, images, size)
        except (openai.APIError, json.JSONDecodeError, UnicodeDecodeError) as error:  # the last two: a bad 200 body
            failure = _classify(error)
        else:
            return _result(model, response, size=size)
        # Raised outside the handler: the SDK error, whose message may echo a key, must not travel as __context__.
        raise failure

    async def _send(self, model: str, quality: str, prompt: str, images: list[bytes], size: str) -> object:
        common = {"model": model, "prompt": prompt, "n": 1, "size": size, "quality": quality, "output_format": "png"}
        if not images:
            return await self._client.images.generate(**common)
        # Never input_fidelity: the docs say to omit it for gpt-image-2. A list goes as `image[]` parts, in order.
        files = [(f"image-{number}.png", data, "image/png") for number, data in enumerate(images, 1)]
        return await self._client.images.edit(image=files, **common)

    async def close(self):
        await self._client.close()


def _classify(error: openai.APIError | ValueError) -> ProviderError:
    if isinstance(error, openai.APITimeoutError):  # a subclass of APIConnectionError: test it first
        return ProviderError("timeout", str(error))
    if isinstance(error, openai.APIConnectionError):
        return ProviderError("provider_error", f"{error} ({error.__cause__!r})")
    if isinstance(error, openai.APIStatusError):
        return ProviderError(_status_kind(error), f"{error} [code={error.code}, request_id={error.request_id}]")
    return ProviderError("invalid_response", f"unreadable response body: {error}")  # bad JSON or UTF-8, schema


def _status_kind(error: openai.APIStatusError) -> ProviderErrorKind:
    if error.code in QUOTA_CODES or error.type == "insufficient_quota":
        return "quota"
    # moderation_blocked is an error.code, image_generation_user_error an error.type (image-generation guide).
    if error.code == "moderation_blocked" or "image_generation_user_error" in (error.code, error.type):
        return "refused"
    if error.status_code in (401, 403):
        return "auth"
    if error.status_code == 429:
        return "rate_limited"  # rate_limit_exceeded, slow_down, or no code
    if error.status_code >= 500:
        return "provider_error"
    return "invalid_request"


def _result(model: str, response: object, *, size: str = "1088x1920") -> ProviderResult:
    items = response.data if isinstance(response, ImagesResponse) else None
    if not isinstance(items, list) or not items:
        raise ProviderError("invalid_response", f"no image in the response ({type(response).__name__})")
    image, mime = validate_image(getattr(items[0], "b64_json", None), size=size)
    usage = parse_usage(response.usage)
    if usage is None:  # no values logged: the raw usage is unvalidated provider data
        log.warning("%s usage from %s: the reserved estimate stays as the cost",
                    "no" if response.usage is None else "unusable", model)
    return ProviderResult(image, mime, usage, cost_micros(model, usage))


class StubProvider:
    """Offline and free. Each call fails with the next of `fail_kinds` while any remain, else returns a
    deterministic image after `delay` seconds."""

    name = "stub"

    def __init__(self, fail_kinds: Iterable[ProviderErrorKind] = (), delay: float = 1.0) -> None:
        self._fail_kinds = iter(fail_kinds)
        self.delay = delay

    async def generate(self, *, purpose: Purpose, model: str, quality: str, prompt: str,
                       images: list[bytes], size: str = "1088x1920") -> ProviderResult:
        _check_request(purpose, model, images)
        dimensions = image_dimensions(size)
        if (kind := next(self._fail_kinds, None)) is not None:
            raise ProviderError(kind, "stub failure")
        await asyncio.sleep(self.delay)
        digest = hashlib.sha256(prompt.encode())
        for data in images:
            digest.update(hashlib.sha256(data).digest())
        buffer = io.BytesIO()
        Image.new("RGB", dimensions, tuple(digest.digest()[:3])).save(buffer, format="PNG")
        return ProviderResult(buffer.getvalue(), "image/png", usage=None, cost_micros=0)


def make_provider(settings: Settings) -> OpenAIProvider | StubProvider:
    if settings.image_provider == "openai":
        return OpenAIProvider(settings.openai_api_key)
    # STUB_FAIL fails every call (D-PV-003). Tests pass a finite list to model "fail once, then succeed".
    return StubProvider(itertools.repeat(settings.stub_fail) if settings.stub_fail else ())
