"""Trusted shared canvas in an offline browser; original files are never rewritten."""
import asyncio
import base64
import hashlib
import io
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageOps
from playwright.async_api import Error as BrowserError, async_playwright

from affiche.config import BACKEND_DIR
from affiche.visuals.gateway import _to_srgb, refuse_undeclared_colours
from .models import Document, FORMATS, canonical
from .store import Refused

BUILD_DIR = BACKEND_DIR.parent / "frontend" / "dist"
ORIGIN = "https://affiche-render.invalid"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def data_url(data, mime="image/png"):
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def canvas_image(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > 40_000_000 or getattr(source, "n_frames", 1) != 1:
            raise ValueError("invalid_canvas_image")
        image = ImageOps.exif_transpose(source)
        image.load()
    refuse_undeclared_colours(image.info)
    profile = image.info.get("icc_profile")
    alpha = image.convert("RGBA").getchannel("A") if image.has_transparency_data else None
    colour = image.convert("L" if image.mode in {"1", "L", "LA"} else "CMYK" if image.mode == "CMYK" else "RGB")
    image = _to_srgb(colour, profile) if profile else colour.convert("RGB")
    if alpha is not None:
        image.putalpha(alpha)
    # Generated scenes already fit this bound; logo/reference images need no larger working surface.
    image.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
    image.info.clear()
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def bundle(build_dir=BUILD_DIR):
    try:
        files = {"/" + path.relative_to(build_dir).as_posix(): path.read_bytes()
                 for path in build_dir.rglob("*") if path.is_file() and not path.is_symlink()
                 and path.resolve().is_relative_to(build_dir.resolve())}
        if "/render.html" not in files:
            raise ValueError("build_missing")
        manifest = json.loads(files["/font-manifest.json"])
        fonts = {}
        for font in manifest["fonts"]:
            data = files["/fonts/" + font["file"]]
            if sha(data) != font["sha256"]:
                raise ValueError("font_corrupt")
            fonts[font["file"]] = data_url(data, "font/ttf")
    except (OSError, ValueError, KeyError, TypeError):
        raise Refused("renderer_unavailable", 503) from None
    return {"files": files, "fonts": fonts, "manifest": manifest,
            "font_manifest_hash": sha(files["/font-manifest.json"]),
            "build_hash": sha(canonical({path: sha(data) for path, data in files.items()}).encode())}


def png_bytes(result, format):
    try:
        if not result.startswith("data:image/png;base64,"):
            raise ValueError("invalid_png")
        data = base64.b64decode(result.split(",", 1)[1], validate=True)
        if len(data) > 30 * 1024 * 1024 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("invalid_png")
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "PNG" or image.size != FORMATS[format]:
                raise ValueError("invalid_dimensions")
            image.load()
        return data
    except (ValueError, OSError, KeyError, AttributeError):
        raise Refused("render_invalid", 503) from None


async def render(document: dict, format: str, sources: dict, build: dict):
    Document.model_validate(document)
    async def execute():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                context = await browser.new_context(viewport={"width": 1080, "height": 1920}, device_scale_factor=1,
                                                    service_workers="block", reduced_motion="reduce")
                async def route(request):
                    url = urlsplit(request.request.url)
                    if f"{url.scheme}://{url.netloc}" == ORIGIN and url.path in build["files"]:
                        await request.fulfill(status=200, body=build["files"][url.path],
                                              content_type=mimetypes.guess_type(url.path)[0] or "application/octet-stream")
                    else:
                        await request.abort()
                await context.route("**/*", route)
                page = await context.new_page()
                await page.goto(ORIGIN + "/render.html")
                await page.wait_for_function("typeof window.renderPoster === 'function'")
                result = await page.evaluate("payload => window.renderPoster(payload)", {
                    "document": document, "format": format, "sources": sources, "fonts": build["fonts"]})
                if any(issue["blocking"] for issue in result["issues"]):
                    raise Refused("layout_invalid")
                return {"png": result["png"], "warnings": result["issues"]}
            finally:
                await browser.close()
    try:
        async with asyncio.timeout(30):
            result = await execute()
    except (BrowserError, TimeoutError):
        raise Refused("render_unavailable", 503) from None
    png_bytes(result["png"], format)
    return result
