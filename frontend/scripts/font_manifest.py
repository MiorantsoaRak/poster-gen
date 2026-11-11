"""Rebuild the checked font manifest from bundled, unmodified OFL files. Run using backend's uv environment."""
import hashlib
import json
from pathlib import Path

from fontTools.ttLib import TTFont

root = Path(__file__).resolve().parents[1]
entries = []
for id, family, basename, variants in (
    ("noto-sans", "Affiche Noto Sans", "NotoSans", ((400, "Regular"), (700, "Bold"))),
    ("noto-serif", "Affiche Noto Serif", "NotoSerif", ((400, "Regular"), (700, "Bold"))),
    ("montserrat-black-italic", "Affiche Montserrat Black Italic", "Montserrat", ((900, "BlackItalic"),)),
):
    for weight, suffix in variants:
        italic = suffix.endswith("Italic")
        filename = f"{basename}-{suffix}.ttf"
        path = root / "public" / "fonts" / filename
        with TTFont(path) as font:
            points = sorted(font.getBestCmap())
            required = "\u00c9\u00e9\u00e0\u00e7\u00f9\u0153AR0123456789" + ("\u00a0" if italic else "\u202f")
            assert set(map(ord, required)) <= set(points), filename
            assert font["OS/2"].usWeightClass == weight, filename
            assert bool(font["OS/2"].fsSelection & 1) == italic, filename
        ranges = []
        for point in points:
            if ranges and point == ranges[-1][1]+1:
                ranges[-1][1] = point
            else:
                ranges.append([point, point])
        entry = {"id": id, "family": family, "weight": weight, "style": "italic" if italic else "normal", "file": filename}
        if basename == "Montserrat":
            entry.update(license="Montserrat-OFL.txt",
                         source="https://github.com/JulietaUla/Montserrat/blob/master/fonts/ttf/Montserrat-BlackItalic.ttf")
        entry.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), ranges=ranges)
        entries.append(entry)
manifest = {"version": 1, "license": "OFL.txt", "source": "https://github.com/notofonts/noto-fonts", "fonts": entries}
(root / "src" / "font-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
(root / "public" / "font-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(f"Verified {len(entries)} fonts, French glyphs, weights and SHA-256 hashes.")
