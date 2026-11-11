"""The gateway, with the real SDK driven through httpx2.MockTransport: no network, no key from the environment."""

import asyncio
import base64
import io
import json
import logging
import re
import struct
from decimal import Decimal

import httpx2
import pytest
from PIL import ExifTags, Image, ImageCms, PngImagePlugin
from pydantic import SecretStr

from affiche.config import load_settings
from affiche.visuals import gateway
from affiche.visuals.gateway import (
    ERROR_KINDS, OUTPUT_SIZE, OpenAIProvider, ProviderError, Rates, StubProvider, cost_micros, make_provider,
    prepare_provider_input, usd_to_micros, validate_image,
)
from test_config import env  # noqa: F401  (fixture: a clean environment with a valid cap)

KEY = "sk-test-gateway-key-never-sent-anywhere"
PHOTO, PHOTO_2, STYLE = b"photo-1", b"photo-2", b"style-ref"
USAGE = {"input_tokens": 1000, "input_tokens_details": {"text_tokens": 200, "image_tokens": 800},
         "output_tokens": 5000, "total_tokens": 6000}
USAGE_COST = 200 * 5 + 800 * 8 + 5000 * 30  # micro-USD at the gpt-image-2 rates


def encode(image: Image.Image, image_format: str = "PNG", **options) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=image_format, **options)
    return buffer.getvalue()


def picture(size=OUTPUT_SIZE, image_format="PNG", color="red") -> bytes:
    return encode(Image.new("RGB", size, color), image_format)


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def image_reply(data: bytes | None = None, usage: dict | None = None) -> httpx2.Response:
    body = {"created": 1, "data": [{"b64_json": b64(data or picture())}]}
    return httpx2.Response(200, json=body | ({"usage": usage} if usage else {}))


def error_reply(status: int, code: str | None = None, error_type: str | None = None,
                message: str = "provider says no") -> httpx2.Response:
    return httpx2.Response(status, json={"error": {"message": message, "type": error_type, "param": None,
                                                   "code": code}})


class FakeApi:
    """MockTransport handler: records each request and answers with the next reply (a response or an exception)."""

    def __init__(self, *replies: httpx2.Response | Exception) -> None:
        self.replies = list(replies)
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def provider(self) -> OpenAIProvider:
        return OpenAIProvider(SecretStr(KEY), http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(self)))


def generate(provider, purpose="scene", images=(PHOTO,), model="gpt-image-2", prompt="a prompt", size="1088x1920"):
    return asyncio.run(provider.generate(purpose=purpose, model=model, quality="medium", prompt=prompt,
                                         images=list(images), size=size))


def form_parts(request: httpx2.Request) -> list[tuple[str, str | None, bytes]]:
    """(name, filename, body) of each multipart part, in order."""
    boundary = request.headers["content-type"].split("boundary=")[1].encode()
    parts = []
    for chunk in request.content.split(b"--" + boundary)[1:-1]:
        head, _, body = chunk.partition(b"\r\n\r\n")
        filename = re.search(rb'filename="([^"]*)"', head)
        parts.append((re.search(rb' name="([^"]*)"', head).group(1).decode(),
                      filename and filename.group(1).decode(), body.removesuffix(b"\r\n")))
    return parts


# --- Error mapping (design table, D-PV-003) -----------------------------------------------------------------------

@pytest.mark.parametrize("size", ["1088x1360", "1088x1088", "1152x2048", "1024x1024"])
def test_explicit_poster_and_texture_sizes(size):
    dimensions = gateway.image_dimensions(size)
    api = FakeApi(image_reply(picture(size=dimensions)))
    result = generate(api.provider(), size=size)
    assert Image.open(io.BytesIO(result.image)).size == dimensions
    assert ("size", None, size.encode()) in form_parts(api.requests[0])
    stub = generate(StubProvider(), size=size)
    assert Image.open(io.BytesIO(stub.image)).size == dimensions
    with pytest.raises(ProviderError, match="expected " + size):
        generate(FakeApi(image_reply()).provider(), size=size)


def test_invalid_size_refused_before_dispatch():
    api = FakeApi()
    with pytest.raises(ValueError, match="unsupported image size"):
        generate(api.provider(), size="1080x1350")
    assert api.requests == []

MAPPING = [
    (httpx2.ReadTimeout("slow"), "timeout", False),
    (httpx2.ConnectError("down"), "provider_error", True),
    (error_reply(500), "provider_error", True),
    (httpx2.Response(502, text="<html>Bad gateway</html>"), "provider_error", True),
    (error_reply(503, "server_is_overloaded", "service_unavailable_error"), "provider_error", True),
    (error_reply(429, "rate_limit_exceeded", "requests"), "rate_limited", True),
    (error_reply(429, "slow_down", "rate_limit_error"), "rate_limited", True),
    (error_reply(429), "rate_limited", True),
    (error_reply(429, "insufficient_quota", "insufficient_quota"), "quota", False),
    (error_reply(429, None, "insufficient_quota"), "quota", False),
    (error_reply(429, "credit_balance_exhausted"), "quota", False),
    (error_reply(429, "organization_spend_limit_exceeded"), "quota", False),
    (error_reply(429, "project_spend_limit_exceeded"), "quota", False),
    (error_reply(429, "organization_usage_limit_exceeded"), "quota", False),
    (error_reply(400, "moderation_blocked", "image_generation_user_error"), "refused", False),
    (error_reply(400, "moderation_blocked", "invalid_request_error"), "refused", False),
    (error_reply(400, None, "image_generation_user_error"), "refused", False),
    (error_reply(400, "image_generation_user_error"), "refused", False),
    (error_reply(400, "invalid_value", "invalid_request_error"), "invalid_request", False),
    (error_reply(401, "invalid_api_key", "invalid_request_error"), "auth", False),
    (error_reply(403), "auth", False),
    (error_reply(404), "invalid_request", False),
    (error_reply(422), "invalid_request", False),
]


@pytest.mark.parametrize(("reply", "kind", "retryable"), MAPPING)
def test_error_mapping(reply, kind, retryable):
    api = FakeApi(reply)
    with pytest.raises(ProviderError) as caught:
        generate(api.provider())
    assert (caught.value.kind, caught.value.retryable) == (kind, retryable)
    assert len(api.requests) == 1  # the SDK never retries; the one retry is the caller's
    assert caught.value.__context__ is None and caught.value.__cause__ is None


def test_api_key_never_appears_in_errors():
    echoed = "Incorrect API key provided: sk-proj-abc...xyz. You can find your API key at https://platform.openai.com."
    with pytest.raises(ProviderError) as caught:
        generate(FakeApi(error_reply(401, "invalid_api_key", message=echoed)).provider())
    error = caught.value
    assert error.kind == "auth" and "<redacted key>" in error.detail
    for text in (error.detail, str(error), repr(error)):
        assert "sk-" not in text and KEY not in text


def test_detail_is_truncated():
    assert len(ProviderError("provider_error", "x" * 2000).detail) == 500


def test_unknown_kind_is_a_programming_error():
    with pytest.raises(ValueError, match="unknown provider error kind"):
        ProviderError("budget_exhausted", "the cap is the caller's, not the provider's")


# --- Requests sent ------------------------------------------------------------------------------------------------

def test_client_settings():
    provider = FakeApi().provider()
    assert provider._client.timeout == 180 and provider._client.max_retries == 0
    assert all(logging.getLogger(name).level == logging.WARNING for name in ("openai", "httpx2", "httpcore2"))


def test_scene_request_goes_to_edit_with_images_in_order():
    api = FakeApi(image_reply())
    generate(api.provider(), "scene", [PHOTO, PHOTO_2, STYLE])
    request, = api.requests
    assert request.url.path.endswith("/images/edits")
    parts = form_parts(request)
    fields = {name: body.decode() for name, filename, body in parts if filename is None}
    assert fields == {"prompt": "a prompt", "model": "gpt-image-2", "n": "1", "quality": "medium",
                      "size": "1088x1920", "output_format": "png"}  # no input_fidelity
    files = [(name, body) for name, filename, body in parts if filename is not None]
    assert files == [("image[]", PHOTO), ("image[]", PHOTO_2), ("image[]", STYLE)]


def test_background_without_images_goes_to_generate():
    api = FakeApi(image_reply())
    generate(api.provider(), "background", [])
    request, = api.requests
    assert request.url.path.endswith("/images/generations")
    assert json.loads(request.content) == {"prompt": "a prompt", "model": "gpt-image-2", "n": 1,
                                           "quality": "medium", "size": "1088x1920", "output_format": "png"}


def test_background_with_style_reference_goes_to_edit_with_one_image():
    api = FakeApi(image_reply())
    generate(api.provider(), "background", [STYLE])
    request, = api.requests
    assert request.url.path.endswith("/images/edits")
    assert [(name, body) for name, filename, body in form_parts(request) if filename] == [("image[]", STYLE)]


@pytest.mark.parametrize(("purpose", "images", "model", "match"), [
    ("scene", [PHOTO], "gpt-image-9", "no token rates"),
    ("scene", [], "gpt-image-2", "a scene needs at least one photo"),
    ("background", [STYLE, STYLE], "gpt-image-2", "a background takes only the style reference"),
])
def test_bad_request_is_refused_before_any_call(purpose, images, model, match):
    api = FakeApi()
    with pytest.raises(ValueError, match=match):
        generate(api.provider(), purpose, images, model)
    assert api.requests == []


# --- Responses ----------------------------------------------------------------------------------------------------

def test_success_with_usage():
    image = picture()
    result = generate(FakeApi(image_reply(image, USAGE)).provider())
    assert (result.image, result.mime, result.usage, result.cost_micros) == (image, "image/png", USAGE, USAGE_COST)


def test_success_without_usage_keeps_the_estimate():
    result = generate(FakeApi(image_reply(picture(image_format="WEBP"))).provider())
    assert (result.mime, result.usage, result.cost_micros) == ("image/webp", None, None)


def test_usage_keeps_only_allowlisted_counts():
    raw = USAGE | {"note": "sk-proj-leak", "output_tokens_details": {"image_tokens": 5000, "text_tokens": 0},
                   "input_tokens_details": USAGE["input_tokens_details"] | {"cached_tokens": 3}}
    result = generate(FakeApi(image_reply(picture(), raw)).provider())
    assert (result.usage, result.cost_micros) == (USAGE, USAGE_COST)


@pytest.mark.parametrize("usage", [
    {"input_tokens": True, "output_tokens": False, "total_tokens": 6000},  # the SDK would serialise them as 1 and 0
    {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    {"input_tokens": 1000, "output_tokens": 5000, "total_tokens": 600},
    {"input_tokens": 10, "input_tokens_details": {"text_tokens": True}, "output_tokens": 2},
    {"input_tokens": 10, "input_tokens_details": {"text_tokens": 10, "image_tokens": 10}, "output_tokens": 2},
    {"input_tokens": 10, "input_tokens_details": {"image_tokens": 11}, "output_tokens": 2},
])
def test_malformed_usage_keeps_the_estimate(caplog, usage):
    with caplog.at_level(logging.WARNING, logger="affiche.visuals.gateway"):
        result = generate(FakeApi(image_reply(picture(), usage)).provider())
    assert (result.usage, result.cost_micros) == (None, None)
    assert caplog.messages == ["unusable usage from gpt-image-2: the reserved estimate stays as the cost"]


@pytest.mark.parametrize("reply", [
    image_reply(picture(size=(1024, 1536))),
    image_reply(picture(size=(1088, 1921))),
    image_reply(b"not an image"),
    image_reply(picture(image_format="JPEG")),
    image_reply(encode(Image.effect_noise(OUTPUT_SIZE, 64).convert("RGB"))[:100_000]),  # truncated
    httpx2.Response(200, json={"created": 1, "data": [{"b64_json": "%%% not base64 %%%"}]}),
    httpx2.Response(200, json={"created": 1, "data": [{}]}),
    httpx2.Response(200, json={"created": 1, "data": []}),
    httpx2.Response(200, json={"created": 1}),
    httpx2.Response(200, text="<html>not json</html>", headers={"content-type": "text/html"}),
    httpx2.Response(200, content=b"{not json", headers={"content-type": "application/json"}),
    httpx2.Response(200, content=b'{"created": 1, "data": [\xff]}', headers={"content-type": "application/json"}),
])
def test_unusable_response_is_invalid_response(reply):
    with pytest.raises(ProviderError) as caught:
        generate(FakeApi(reply).provider())
    assert (caught.value.kind, caught.value.retryable) == ("invalid_response", False)
    assert caught.value.__context__ is None and caught.value.__cause__ is None


def test_validate_image_returns_bytes_and_mime():
    image = picture()
    assert validate_image(b64(image)) == (image, "image/png")


def test_validate_image_error_carries_no_raw_error():
    with pytest.raises(ProviderError, match="undecodable image") as caught:
        validate_image(b64(b"not an image"))
    assert caught.value.__context__ is None and caught.value.__cause__ is None


# --- Money --------------------------------------------------------------------------------------------------------

def test_cost_from_usage():
    assert cost_micros("gpt-image-2", USAGE) == USAGE_COST


@pytest.mark.parametrize(("output_rate", "expected"), [
    ("0.7", 4),  # 3 x 0.1 + 7 x 0.3 + 1 x 0.7 = 3.1 micro-USD, rounded up
    ("0.6", 3),  # exactly 3.0: not rounded further
])
def test_cost_is_rounded_up(monkeypatch, output_rate, expected):
    monkeypatch.setitem(gateway.RATES, "test-model", Rates(Decimal("0.1"), Decimal("0.3"), Decimal(output_rate)))
    usage = {"input_tokens": 10, "input_tokens_details": {"text_tokens": 3, "image_tokens": 7}, "output_tokens": 1}
    assert cost_micros("test-model", usage) == expected


@pytest.mark.parametrize("usage", [
    {"input_tokens": 10, "output_tokens": 2},
    {"input_tokens": 10, "input_tokens_details": {"image_tokens": 4}, "output_tokens": 2},
    {"input_tokens": 10, "input_tokens_details": None, "output_tokens": 2},
])
def test_cost_without_text_split_charges_the_image_rate(usage):
    assert cost_micros("gpt-image-2", usage) == 10 * 8 + 2 * 30


@pytest.mark.parametrize("usage", [
    None, {}, {"total_tokens": 12}, {"input_tokens": "10", "output_tokens": 2},
    {"input_tokens": True, "output_tokens": 2}, {"input_tokens": -1, "output_tokens": 2},
    {"input_tokens": 10, "output_tokens": 0},
    {"input_tokens": 10, "output_tokens": 2, "total_tokens": 13},
    {"input_tokens": 10, "input_tokens_details": {"text_tokens": 11}, "output_tokens": 2},
    {"input_tokens": 10, "input_tokens_details": {"image_tokens": -1}, "output_tokens": 2},
])
def test_cost_without_usable_usage_is_none(usage):
    assert gateway.parse_usage(usage) is None and cost_micros("gpt-image-2", usage) is None


@pytest.mark.parametrize(("usd", "micros"), [
    ("0.0000001", 1), ("0.40", 400_000), ("1.0000001", 1_000_001), ("0.000001", 1), ("0", 0),
])
def test_usd_to_micros_rounds_up(usd, micros):
    assert usd_to_micros(Decimal(usd)) == micros


# --- Provider input -----------------------------------------------------------------------------------------------

def open_png(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    assert image.format == "PNG"
    return image


def test_exif_orientation_is_applied():
    stored = Image.new("RGB", (400, 200), "blue")
    stored.paste((255, 0, 0), (0, 0, 200, 200))  # left half red
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = 6  # shown rotated 90° clockwise
    result = open_png(prepare_provider_input(encode(stored, "JPEG", exif=exif)))
    assert result.size == (200, 400)
    top, bottom = result.getpixel((100, 50)), result.getpixel((100, 350))
    assert top[0] > 200 and top[2] < 60 and bottom[2] > 200 and bottom[0] < 60  # the red half is now on top


def gps_jpeg() -> bytes:
    exif = Image.Exif()
    exif[ExifTags.Base.Make] = "PhoneMaker"
    exif[ExifTags.Base.Model] = "Phone 1"
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef] = "S"
    gps[ExifTags.GPS.GPSLatitude] = (18.0, 55.0, 0.0)
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    data = encode(Image.new("RGB", (64, 48), "green"), "JPEG", exif=exif, icc_profile=icc)
    assert Image.open(io.BytesIO(data)).getexif().get_ifd(ExifTags.IFD.GPSInfo)  # the fixture really has GPS
    return data


def text_png() -> bytes:
    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", "shot at the shop")
    info.add_itxt("Description", "Antananarivo", zip=True)
    exif = Image.Exif()
    exif[ExifTags.Base.Make] = "PhoneMaker"
    data = encode(Image.new("RGB", (64, 48), "green"), pnginfo=info, exif=exif)
    assert Image.open(io.BytesIO(data)).text  # the fixture really has text chunks
    return data


@pytest.mark.parametrize("source", [gps_jpeg, text_png])
def test_provider_input_has_no_metadata(source):
    result = open_png(prepare_provider_input(source()))
    result.load()
    assert result.info == {} and result.text == {} and not result.getexif()


@pytest.mark.parametrize(("size", "expected"), [((4000, 3000), (1536, 1152)), ((3000, 4000), (1152, 1536)),
                                                ((300, 200), (300, 200))])
def test_provider_input_is_only_downscaled(size, expected):
    assert open_png(prepare_provider_input(picture(size, "JPEG"))).size == expected


def test_transparency_is_flattened_onto_white():
    image = Image.new("RGBA", (20, 10), (0, 0, 0, 0))
    image.paste((255, 0, 0, 255), (10, 0, 20, 10))  # right half opaque red
    result = open_png(prepare_provider_input(encode(image)))
    assert result.mode == "RGB"
    assert result.getpixel((2, 5)) == (255, 255, 255) and result.getpixel((15, 5)) == (255, 0, 0)


def linear_gray_profile() -> bytes:
    """A minimal ICC v2 gray display profile with gamma 1.0. Pillow can only create sRGB, LAB and XYZ profiles."""
    d50 = b"".join(struct.pack(">i", round(value * 65536)) for value in (0.9642, 1.0, 0.8249))
    tags = [(b"wtpt", b"XYZ " + bytes(4) + d50), (b"kTRC", b"curv" + bytes(4) + struct.pack(">IH", 1, 256) + bytes(2))]
    offset, table, data = 128 + 4 + 12 * len(tags), b"", b""
    for signature, tag in tags:
        table += signature + struct.pack(">II", offset + len(data), len(tag))
        data += tag
    header = (struct.pack(">I", offset + len(data)) + bytes(4) + struct.pack(">I", 0x02100000) + b"mntrGRAYXYZ "
              + bytes(12) + b"acsp" + bytes(28) + d50 + bytes(48))
    return header + struct.pack(">I", len(tags)) + table + data


def test_icc_profile_is_converted_to_srgb():
    # Linear gray 128 is 50 % light, which sRGB encodes as 188: the pixels change only if the profile is applied.
    result = open_png(prepare_provider_input(encode(Image.new("L", (8, 8), 128), icc_profile=linear_gray_profile())))
    assert all(abs(channel - 188) <= 2 for channel in result.getpixel((4, 4)))
    assert result.mode == "RGB" and "icc_profile" not in result.info


def test_gray_with_alpha_and_icc_profile_is_converted_then_flattened():
    image = Image.new("LA", (20, 10), (0, 0))
    image.paste((128, 255), (10, 0, 20, 10))  # right half opaque linear gray 128
    result = open_png(prepare_provider_input(encode(image, icc_profile=linear_gray_profile())))
    assert result.getpixel((2, 5)) == (255, 255, 255)
    assert all(abs(channel - 188) <= 2 for channel in result.getpixel((15, 5)))


def test_gray_with_trns_and_icc_profile_stays_gray_for_the_profile():
    image = Image.new("L", (20, 10), 0)
    image.paste(128, (10, 0, 20, 10))  # left half gray 0, transparent through tRNS
    result = open_png(prepare_provider_input(encode(image, transparency=0, icc_profile=linear_gray_profile())))
    assert result.getpixel((2, 5)) == (255, 255, 255)
    assert all(abs(channel - 188) <= 2 for channel in result.getpixel((15, 5)))


def test_bilevel_with_gray_profile_is_converted():
    image = Image.new("1", (8, 8), 1)
    result = open_png(prepare_provider_input(encode(image, icc_profile=linear_gray_profile())))
    assert result.getpixel((4, 4)) == (255, 255, 255)


SRGB_XY = (0.3127, 0.3290, 0.64, 0.33, 0.30, 0.60, 0.15, 0.06)
P3_XY = (0.3127, 0.3290, 0.680, 0.320, 0.265, 0.690, 0.150, 0.060)


def gama(value: float) -> tuple[bytes, bytes]:
    return b"gAMA", struct.pack(">I", round(value * 100000))


def chrm(xy: tuple[float, ...]) -> tuple[bytes, bytes]:
    return b"cHRM", struct.pack(">8I", *(round(value * 100000) for value in xy))


def png_with(*chunks: tuple[bytes, bytes]) -> bytes:
    info = PngImagePlugin.PngInfo()
    for chunk_type, chunk_data in chunks:
        info.add(chunk_type, chunk_data)
    return encode(Image.new("RGB", (8, 8), "red"), pnginfo=info)


@pytest.mark.parametrize("chunks", [
    [gama(0.45455)],
    [gama(0.45455), chrm(SRGB_XY)],
    [(b"sRGB", b"\0"), gama(1.0), chrm(P3_XY)],  # the sRGB chunk is authoritative
])
def test_srgb_colour_metadata_is_accepted(chunks):
    assert open_png(prepare_provider_input(png_with(*chunks))).getpixel((4, 4)) == (255, 0, 0)


@pytest.mark.parametrize("chunks", [[gama(1.0)], [gama(0.45455), chrm(P3_XY)], [chrm(P3_XY)]])
def test_non_srgb_colour_metadata_without_profile_is_refused(chunks):
    with pytest.raises(ValueError, match="non-sRGB colours"):
        prepare_provider_input(png_with(*chunks))


def test_unreadable_icc_profile_is_refused():
    with pytest.raises(ValueError, match="ICC colour profile"):
        prepare_provider_input(encode(Image.new("RGB", (8, 8), "red"), icc_profile=b"not an ICC profile"))


# --- Stub ---------------------------------------------------------------------------------------------------------

def test_stub_is_deterministic_and_valid():
    stub = StubProvider(delay=0)
    first = generate(stub)
    assert generate(stub).image == first.image
    assert generate(stub, prompt="another prompt").image != first.image
    assert generate(stub, images=(PHOTO_2,)).image != first.image
    assert validate_image(b64(first.image)) == (first.image, "image/png")
    assert (first.mime, first.usage, first.cost_micros, StubProvider.name) == ("image/png", None, 0, "stub")


def test_stub_fails_in_order_then_succeeds():
    stub = StubProvider(["provider_error", "timeout"], delay=0)
    for kind, retryable in [("provider_error", True), ("timeout", False)]:
        with pytest.raises(ProviderError) as caught:
            generate(stub)
        assert (caught.value.kind, caught.value.retryable) == (kind, retryable)
    assert generate(stub).cost_micros == 0


def test_stub_retryable_flags_match_the_real_mapping():
    real = {kind: retryable for _, kind, retryable in MAPPING} | {"invalid_response": False}
    assert real.keys() == set(ERROR_KINDS)
    for kind, retryable in real.items():
        with pytest.raises(ProviderError) as caught:
            generate(StubProvider([kind], delay=0))
        assert caught.value.retryable is retryable


def test_make_provider_with_stub_fail_fails_every_call(env):  # noqa: F811
    env.setenv("STUB_FAIL", "quota")
    stub = make_provider(load_settings(env_file=None))
    for _ in range(3):
        with pytest.raises(ProviderError, match="quota"):
            generate(stub)


def test_make_provider_without_stub_fail_succeeds(env):  # noqa: F811
    stub = make_provider(load_settings(env_file=None))
    stub.delay = 0
    assert isinstance(stub, StubProvider) and generate(stub).cost_micros == 0


def test_make_provider_for_openai(env):  # noqa: F811
    env.setenv("IMAGE_PROVIDER", "openai")
    env.setenv("OPENAI_API_KEY", KEY)
    assert isinstance(make_provider(load_settings(env_file=None)), OpenAIProvider)
