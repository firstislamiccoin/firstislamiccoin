#!/usr/bin/env python3
"""Phase 0 acceptance check.

Verifies the brand kit and Phase 0 documents against the FIC prompt's checklist:
all SVGs valid, PNG sets complete, app-icon catalogues intact, docs present.

Run from the project root:  python docs/verify-phase0.py
"""
import glob
import json
import os
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND = os.path.join(ROOT, "firstislamiccoin-brand")

REQUIRED_PNG_SIZES = [16, 32, 64, 128, 256, 512, 1024]
PNG_SETS = ["fic-coin-full", "fic-icon", "fic-icon-square"]
REQUIRED_SVGS = ["fic-coin-full", "fic-icon", "fic-wordmark"]
PALETTE = {
    "green": "#0B6E4F", "greenDeep": "#08523B", "gold": "#D4AF37",
    "goldDeep": "#B8962E", "goldLight": "#E9CC6A",
}
DOCS = [
    "docs/cac-audit.md", "docs/repo-map.md", "docs/CHANGELOG-FIC.md",
    "docs/rebrand-manifest.txt", "firstislamiccoin-brand/docs/brand.md",
]

results = []


def check(name, ok, detail=""):
    # ASCII only: this runs on a Windows console with a legacy code page.
    results.append((ok, name, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if detail and not ok else ""))
    return ok


def png_size(path):
    """(width, height) read straight from the IHDR chunk."""
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">II", head[16:24])


# --- SVGs parse, and carry no font dependency -------------------------------
svgs = sorted(glob.glob(os.path.join(BRAND, "svg", "*.svg")))
svgs.append(os.path.join(BRAND, "favicon", "favicon.svg"))
bad, fonty = [], []
for p in svgs:
    rel = os.path.relpath(p, BRAND)
    try:
        root = ET.parse(p).getroot()
        if not root.get("viewBox"):
            bad.append(f"{rel} (no viewBox)")
    except ET.ParseError as exc:
        bad.append(f"{rel} ({exc})")
        continue
    body = open(p, encoding="utf-8").read()
    if "font-family" in body or "<text" in body:
        fonty.append(rel)

check(f"{len(svgs)} SVGs parse with a viewBox", not bad, "; ".join(bad))
check("SVG text is outlined (no font dependency)", not fonty, "; ".join(fonty))
check(
    "prompt-required SVG names present",
    all(os.path.exists(os.path.join(BRAND, "svg", f"{n}.svg")) for n in REQUIRED_SVGS),
    "expected in svg/ (prompt says logo/ — see CHANGELOG-FIC.md)",
)

# --- PNG sets complete and correctly dimensioned ---------------------------
missing, wrong = [], []
for base in PNG_SETS:
    for size in REQUIRED_PNG_SIZES:
        p = os.path.join(BRAND, "png", f"{base}-{size}.png")
        if not os.path.exists(p):
            missing.append(f"{base}-{size}")
            continue
        got = png_size(p)
        if got != (size, size):
            wrong.append(f"{base}-{size} is {got[0]}x{got[1]}")

check(
    f"PNG sets complete ({len(PNG_SETS)} sets x {len(REQUIRED_PNG_SIZES)} sizes)",
    not missing, "missing: " + ", ".join(missing),
)
check("PNG dimensions match filenames", not wrong, "; ".join(wrong))

# --- favicon.ico really is multi-size --------------------------------------
ico = os.path.join(BRAND, "favicon", "favicon.ico")
data = open(ico, "rb").read()
count = struct.unpack("<HHH", data[:6])[2]
sizes = sorted((data[6 + i * 16] or 256) for i in range(count))
check("favicon.ico holds 16/32/48", sizes == [16, 32, 48], f"got {sizes}")

# --- iOS catalogue -------------------------------------------------------
cat = os.path.join(BRAND, "ios", "AppIcon.appiconset")
meta = json.load(open(os.path.join(cat, "Contents.json")))
absent = [i["filename"] for i in meta["images"]
          if not os.path.exists(os.path.join(cat, i["filename"]))]
has_marketing = any(i.get("idiom") == "ios-marketing" for i in meta["images"])
alpha = []
for entry in {i["filename"] for i in meta["images"]}:
    with open(os.path.join(cat, entry), "rb") as fh:
        if fh.read(26)[25] == 6:  # colour-type 6 == RGBA
            alpha.append(entry)

check(f"iOS catalogue: {len(meta['images'])} entries, files present", not absent,
      "; ".join(absent))
check("iOS catalogue has ios-marketing 1024", has_marketing)
check("iOS icons have no alpha channel", not alpha, "; ".join(alpha))

# --- Android launcher set ------------------------------------------------
dens = ["mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"]
need = ["ic_launcher.png", "ic_launcher_round.png",
        "ic_launcher_foreground.png", "ic_launcher_background.png"]
gone = [f"mipmap-{d}/{f}" for d in dens for f in need
        if not os.path.exists(os.path.join(BRAND, "android", f"mipmap-{d}", f))]
check(f"Android launcher icons ({len(dens)} densities)", not gone, "; ".join(gone))
check("Android adaptive-icon XML present", all(os.path.exists(
    os.path.join(BRAND, "android", "mipmap-anydpi-v26", f))
    for f in ["ic_launcher.xml", "ic_launcher_round.xml"]))

# --- Splash screens ------------------------------------------------------
splash = [f"splash-{v}-{t}.png"
          for v in ["phone-portrait", "phone-portrait-3x", "tablet", "square"]
          for t in ["light", "dark"]]
lost = [f for f in splash
        if not os.path.exists(os.path.join(BRAND, "splash", f))]
check("splash screens, light + dark", not lost, "; ".join(lost))

# --- Palette agreement ---------------------------------------------------
pal = json.load(open(os.path.join(BRAND, "tokens", "palette.json")))
drift = [f"{k}: {pal['brand'].get(k)} != {v}"
         for k, v in PALETTE.items() if pal["brand"].get(k) != v]
check("palette.json matches the prompt's constants", not drift, "; ".join(drift))

css = open(os.path.join(BRAND, "tokens", "theme.css"), encoding="utf-8").read()
check("theme.css defines light and dark",
      "prefers-color-scheme: dark" in css and 'data-theme="dark"' in css)

# --- Phase 0 documents ---------------------------------------------------
nodoc = [d for d in DOCS if not os.path.exists(os.path.join(ROOT, d))]
check("Phase 0 documents exist", not nodoc, "; ".join(nodoc))

# --- Summary -------------------------------------------------------------
failed = [r for r in results if not r[0]]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
if failed:
    print("\nPhase 0 acceptance NOT met:")
    for _, name, detail in failed:
        print(f"  - {name} {detail}")
print("\nNot covered here: fresh SVG rasterization needs cairosvg or "
      "rsvg-convert on a Linux host (see CHANGELOG-FIC.md).")
sys.exit(1 if failed else 0)
