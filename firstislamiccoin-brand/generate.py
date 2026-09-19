#!/usr/bin/env python3
"""Generate the FirstIslamicCoin (FIC) brand kit: SVG logos, PNG exports, app icons, favicon, splash, OG, palette/theme."""
import os, json, math, shutil
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
import cairosvg
from PIL import Image

# FirstIslamicCoin: these three paths were hardcoded to one specific machine
# (the environment this script was first written in), making it unrunnable
# anywhere else without editing the source. Overridable via env vars now,
# defaulting to the original values so behavior there is unchanged.
OUT = os.environ.get("FIC_BRAND_OUT", "/home/claude/fic-brand")
GREEN = "#0B6E4F"; GREEN_DEEP = "#08523B"; GOLD = "#D4AF37"; GOLD_DEEP = "#B8962E"; GOLD_LIGHT = "#E9CC6A"
DARK = "#0A1F17"; LIGHT = "#F7F5EE"; WHITE = "#FFFFFF"
FONT_BOLD = os.environ.get("FIC_FONT_BOLD", "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf")
FONT_MED = os.environ.get("FIC_FONT_MED", "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf")

for d in ["svg", "png", "android", "ios/AppIcon.appiconset", "favicon", "splash", "social", "tokens"]:
    os.makedirs(f"{OUT}/{d}", exist_ok=True)

# ---------- text -> path ----------
_fonts = {}
def font(path):
    if path not in _fonts:
        _fonts[path] = TTFont(path)
    return _fonts[path]

def text_path(text, fontfile, size, x, y, fill, anchor="middle", tracking=0):
    """Return an SVG <path> for text baseline at (x,y). anchor: start|middle|end."""
    f = font(fontfile); gs = f.getGlyphSet(); cmap = f.getBestCmap(); upm = f["head"].unitsPerEm
    scale = size / upm
    # measure
    total = 0
    glyphs = []
    for ch in text:
        gname = cmap.get(ord(ch), ".notdef"); g = gs[gname]
        glyphs.append((gname, g.width)); total += g.width * scale + tracking
    total -= tracking
    if anchor == "middle": cx = x - total / 2
    elif anchor == "end": cx = x - total
    else: cx = x
    d = []
    pen_x = cx
    for gname, w in glyphs:
        pen = SVGPathPen(gs)
        tpen = TransformPen(pen, (scale, 0, 0, -scale, pen_x, y))
        gs[gname].draw(tpen)
        p = pen.getCommands()
        if p: d.append(p)
        pen_x += w * scale + tracking
    return f'<path fill="{fill}" d="{" ".join(d)}"/>', total

# ---------- emblem ----------
def octagram_points(cx, cy, R, r, rot=0):
    pts = []
    for i in range(16):
        ang = math.radians(rot + i * 22.5)
        rad = R if i % 2 == 0 else r
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return " ".join(f"{px:.2f},{py:.2f}" for px, py in pts)

def octagon_points(cx, cy, r, rot=22.5):
    return " ".join(f"{cx + r*math.cos(math.radians(rot+i*45)):.2f},{cy + r*math.sin(math.radians(rot+i*45)):.2f}" for i in range(8))

def crescent_path(x1, y1, r1, x2, y2, r2):
    """Path of circle1 minus circle2 (crescent), circles must intersect."""
    d = math.hypot(x2 - x1, y2 - y1)
    a = (r1*r1 - r2*r2 + d*d) / (2*d)
    h = math.sqrt(r1*r1 - a*a)
    mx, my = x1 + a*(x2 - x1)/d, y1 + a*(y2 - y1)/d
    px1, py1 = mx + h*(y2 - y1)/d, my - h*(x2 - x1)/d
    px2, py2 = mx - h*(y2 - y1)/d, my + h*(x2 - x1)/d
    # from P1 along big circle (large arc, away from c2) to P2, then back along small circle
    return (f"M{px1:.2f},{py1:.2f} A{r1:.2f},{r1:.2f} 0 1 0 {px2:.2f},{py2:.2f} "
            f"A{r2:.2f},{r2:.2f} 0 0 1 {px1:.2f},{py1:.2f} Z")

def emblem(cx=100, cy=100, s=1.0, star=GOLD, field=GREEN, crescent=GOLD, uid="e", gradient=True):
    """Crescent + eight-point star (Rub el Hizb-inspired) emblem, ~170 units wide at s=1."""
    R = 84.85 * s; r = 64.94 * s
    grad = ""
    starfill = star
    if gradient and star == GOLD:
        grad = f'''<defs><linearGradient id="g{uid}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{GOLD_LIGHT}"/><stop offset="0.55" stop-color="{GOLD}"/><stop offset="1" stop-color="{GOLD_DEEP}"/></linearGradient></defs>'''
        starfill = f"url(#g{uid})"
    inner = octagon_points(cx, cy, r)
    cr = 34 * s; cut_r = 29 * s; cut_dx = 13 * s; cut_dy = -9 * s
    cres = crescent_path(cx, cy, cr, cx + cut_dx, cy + cut_dy, cut_r)
    sx, sy = cx + 16 * s, cy - 12 * s
    accent = octagram_points(sx, sy, 10 * s, 4.5 * s, rot=22.5)
    return f'''<g id="emblem-{uid}">{grad}
    <path d="M{octagram_points(cx, cy, R, r).replace(' ', ' L')} Z M{inner.replace(' ', ' L')} Z" fill="{starfill}" fill-rule="evenodd"/>
    {'' if field == 'none' else f'<polygon points="{inner}" fill="{field}"/>'}
    <path d="{cres}" fill="{crescent}"/>
    <polygon points="{accent}" fill="{crescent}"/>
  </g>'''

def svg(w, h, body, bg=None):
    bgrect = f'<rect width="{w}" height="{h}" fill="{bg}"/>' if bg else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{bgrect}{body}</svg>'

def write(path, content):
    with open(path, "w") as f: f.write(content)

files = {}

# 1. Icon (emblem only, transparent)
files["fic-icon.svg"] = svg(200, 200, emblem(uid="i"))
# 1b. Icon on green rounded square (app-icon style)
files["fic-icon-square.svg"] = svg(200, 200, f'<rect width="200" height="200" rx="44" fill="{GREEN}"/>' + emblem(uid="sq"))
files["fic-icon-circle.svg"] = svg(200, 200, f'<circle cx="100" cy="100" r="100" fill="{GREEN}"/>' + emblem(uid="ci"))
# 1c. Monochrome variants
files["fic-icon-mono-white.svg"] = svg(200, 200, emblem(uid="mw", star=WHITE, field="none", crescent=WHITE, gradient=False))
files["fic-icon-mono-black.svg"] = svg(200, 200, emblem(uid="mb", star="#111111", field="none", crescent="#111111", gradient=False))
files["fic-icon-mono-green.svg"] = svg(200, 200, emblem(uid="mg", star=GREEN, field="none", crescent=GREEN, gradient=False))

# 2. Full coin
fic_txt, _ = text_path("FIC", FONT_BOLD, 88, 256, 415, GOLD, tracking=6)
sub_txt, _ = text_path("FIRSTISLAMICCOIN", FONT_MED, 21, 256, 452, GOLD_LIGHT, tracking=3.2)
coin_body = f'''<defs>
  <radialGradient id="coinField" cx="0.4" cy="0.35" r="0.8"><stop offset="0" stop-color="#127A5A"/><stop offset="1" stop-color="{GREEN_DEEP}"/></radialGradient>
  <linearGradient id="rim" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{GOLD_LIGHT}"/><stop offset="0.5" stop-color="{GOLD}"/><stop offset="1" stop-color="{GOLD_DEEP}"/></linearGradient>
</defs>
<circle cx="256" cy="256" r="252" fill="url(#rim)"/>
<circle cx="256" cy="256" r="234" fill="url(#coinField)"/>
<circle cx="256" cy="256" r="220" fill="none" stroke="{GOLD}" stroke-width="2.5" opacity="0.9"/>
<circle cx="256" cy="256" r="212" fill="none" stroke="{GOLD}" stroke-width="1" opacity="0.5"/>
{emblem(cx=256, cy=228, s=1.18, uid="c")}
{fic_txt}
{sub_txt}'''
files["fic-coin-full.svg"] = svg(512, 512, coin_body)

# 3. Wordmarks
def wordmark(dark_bg=False, uid="w"):
    color_first = WHITE if dark_bg else GREEN
    color_islamic = GOLD
    color_coin = WHITE if dark_bg else GREEN
    p1, w1 = text_path("First", FONT_MED, 64, 0, 62, color_first, anchor="start")
    p2, w2 = text_path("Islamic", FONT_BOLD, 64, w1 + 2, 62, color_islamic, anchor="start")
    p3, w3 = text_path("Coin", FONT_MED, 64, w1 + 2 + w2 + 2, 62, color_coin, anchor="start")
    total = w1 + w2 + w3 + 4
    return p1 + p2 + p3, total
wm, wm_w = wordmark()
files["fic-wordmark.svg"] = svg(round(wm_w) + 8, 84, f'<g transform="translate(4,0)">{wm}</g>')
wm_d, _ = wordmark(dark_bg=True, uid="wd")
files["fic-wordmark-on-dark.svg"] = svg(round(wm_w) + 8, 84, f'<g transform="translate(4,0)">{wm_d}</g>')

# 4. Horizontal lockup: icon + wordmark (+ ticker)
def lockup(dark_bg=False):
    wmp, w = wordmark(dark_bg, uid="l")
    tick, _ = text_path("FIC  ·  Shariah-conscious Proof-of-Stake", FONT_MED, 20, 0, 92, GOLD if dark_bg else GREEN_DEEP, anchor="start", tracking=1)
    body = f'<g transform="translate(6,8)">{emblem(cx=50, cy=50, s=0.58, uid="lk"+("d" if dark_bg else "l"), field=(DARK if dark_bg else WHITE) if False else GREEN)}</g>'
    body += f'<g transform="translate(130,10)">{wmp}{tick}</g>'
    return svg(round(w) + 150, 120, body, bg=(DARK if dark_bg else None))
files["fic-lockup-horizontal.svg"] = lockup(False)
files["fic-lockup-horizontal-dark.svg"] = lockup(True)

# 5. Vertical lockup
wmv, wmv_w = wordmark()
VW = round(wmv_w) + 80
files["fic-lockup-vertical.svg"] = svg(VW, 330, f'''
<g transform="translate({VW/2 - 100},0)">{emblem(uid="v")}</g>
<g transform="translate({VW/2 - wmv_w/2},230)">{wmv}</g>''')

for name, content in files.items():
    write(f"{OUT}/svg/{name}", content)

# ---------- PNG exports ----------
def render(svg_name, png_path, w, h=None):
    cairosvg.svg2png(url=f"{OUT}/svg/{svg_name}", write_to=png_path, output_width=w, output_height=h or w)

for size in [16, 32, 48, 64, 128, 256, 512, 1024]:
    render("fic-icon.svg", f"{OUT}/png/fic-icon-{size}.png", size)
    render("fic-coin-full.svg", f"{OUT}/png/fic-coin-full-{size}.png", size)
    render("fic-icon-square.svg", f"{OUT}/png/fic-icon-square-{size}.png", size)
for name in ["fic-wordmark", "fic-wordmark-on-dark", "fic-lockup-horizontal", "fic-lockup-horizontal-dark", "fic-lockup-vertical", "fic-icon-mono-white", "fic-icon-mono-black", "fic-icon-mono-green"]:
    cairosvg.svg2png(url=f"{OUT}/svg/{name}.svg", write_to=f"{OUT}/png/{name}@2x.png", scale=2)

# ---------- Android adaptive icons ----------
android = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
for dpi, px in android.items():
    d = f"{OUT}/android/mipmap-{dpi}"; os.makedirs(d, exist_ok=True)
    render("fic-icon-square.svg", f"{d}/ic_launcher.png", px)
    render("fic-icon-circle.svg", f"{d}/ic_launcher_round.png", px)
    # adaptive foreground: emblem inside 108dp canvas with safe zone (66dp centre)
    fg = svg(108, 108, f'<g transform="translate(54,54) scale(0.34) translate(-100,-100)">{emblem(uid="af")}</g>')
    write("/tmp/fg.svg", fg)
    cairosvg.svg2png(url="/tmp/fg.svg", write_to=f"{d}/ic_launcher_foreground.png", output_width=px*108//48, output_height=px*108//48)
    bg = svg(108, 108, "", bg=GREEN); write("/tmp/bg.svg", bg)
    cairosvg.svg2png(url="/tmp/bg.svg", write_to=f"{d}/ic_launcher_background.png", output_width=px*108//48, output_height=px*108//48)
os.makedirs(f"{OUT}/android/mipmap-anydpi-v26", exist_ok=True)
write(f"{OUT}/android/mipmap-anydpi-v26/ic_launcher.xml", '''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@mipmap/ic_launcher_background"/>
    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
</adaptive-icon>''')
shutil.copy(f"{OUT}/android/mipmap-anydpi-v26/ic_launcher.xml", f"{OUT}/android/mipmap-anydpi-v26/ic_launcher_round.xml")
render("fic-icon-square.svg", f"{OUT}/android/playstore-icon-512.png", 512)

# ---------- iOS AppIcon set ----------
ios_sizes = [("iphone", "20x20", "2x", 40), ("iphone", "20x20", "3x", 60), ("iphone", "29x29", "2x", 58), ("iphone", "29x29", "3x", 87),
             ("iphone", "40x40", "2x", 80), ("iphone", "40x40", "3x", 120), ("iphone", "60x60", "2x", 120), ("iphone", "60x60", "3x", 180),
             ("ipad", "20x20", "1x", 20), ("ipad", "20x20", "2x", 40), ("ipad", "29x29", "1x", 29), ("ipad", "29x29", "2x", 58),
             ("ipad", "40x40", "1x", 40), ("ipad", "40x40", "2x", 80), ("ipad", "76x76", "1x", 76), ("ipad", "76x76", "2x", 152),
             ("ipad", "83.5x83.5", "2x", 167), ("ios-marketing", "1024x1024", "1x", 1024)]
# iOS icons must have no transparency and no rounded corners (iOS masks them)
ios_src = svg(200, 200, f'<rect width="200" height="200" fill="{GREEN}"/>' + emblem(uid="ios"))
write(f"{OUT}/svg/fic-icon-ios-source.svg", ios_src)
images = []
for idiom, size, scale, px in ios_sizes:
    fn = f"icon-{size}@{scale}.png".replace("x1x", "x@1x")
    fn = f"icon-{size.replace('.', '_')}-{scale}.png"
    cairosvg.svg2png(url=f"{OUT}/svg/fic-icon-ios-source.svg", write_to=f"{OUT}/ios/AppIcon.appiconset/{fn}", output_width=px, output_height=px)
    images.append({"idiom": idiom, "size": size, "scale": scale, "filename": fn})
write(f"{OUT}/ios/AppIcon.appiconset/Contents.json", json.dumps({"images": images, "info": {"version": 1, "author": "xcode"}}, indent=2))

# ---------- favicon ----------
for s in [16, 32, 48, 180, 192, 512]:
    render("fic-icon-square.svg", f"{OUT}/favicon/favicon-{s}.png", s)
imgs = [Image.open(f"{OUT}/favicon/favicon-{s}.png") for s in [16, 32, 48]]
imgs[0].save(f"{OUT}/favicon/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=imgs[1:])
shutil.copy(f"{OUT}/favicon/favicon-180.png", f"{OUT}/favicon/apple-touch-icon.png")
shutil.copy(f"{OUT}/svg/fic-icon-square.svg", f"{OUT}/favicon/favicon.svg")
write(f"{OUT}/favicon/site.webmanifest", json.dumps({"name": "FirstIslamicCoin", "short_name": "FIC", "icons": [
    {"src": "favicon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "favicon-512.png", "sizes": "512x512", "type": "image/png"}],
    "theme_color": GREEN, "background_color": LIGHT, "display": "standalone"}, indent=2))

# ---------- splash screens ----------
def splash(w, h, dark):
    bg = DARK if dark else LIGHT
    wmp, ww = wordmark(dark_bg=dark, uid="sp")
    es = min(w, h) * 0.0022
    body = f'<g transform="translate({w/2 - 100*es},{h/2 - 100*es - 60}) scale({es})">{emblem(uid="spl")}</g>'
    ws = (w * 0.62) / ww
    body += f'<g transform="translate({w/2 - ww*ws/2},{h/2 + 100*es + 20}) scale({ws:.3f})">{wmp}</g>'
    return svg(w, h, body, bg=bg)
for label, (w, h) in {"phone-portrait": (1080, 1920), "phone-portrait-3x": (1242, 2688), "tablet": (1536, 2048), "square": (1024, 1024)}.items():
    for dark in (False, True):
        n = f"splash-{label}-{'dark' if dark else 'light'}"
        write(f"/tmp/{n}.svg", splash(w, h, dark)); cairosvg.svg2png(url=f"/tmp/{n}.svg", write_to=f"{OUT}/splash/{n}.png")

# ---------- social / OG ----------
wmp, ww = wordmark(dark_bg=True, uid="og")
tag, tw = text_path("Shariah-conscious Proof-of-Stake  ·  FirstIslamicCoin.com", FONT_MED, 30, 600, 470, GOLD, tracking=1)
og = svg(1200, 630, f'''<defs><radialGradient id="ogbg" cx="0.3" cy="0.3" r="1"><stop offset="0" stop-color="#0F3A2C"/><stop offset="1" stop-color="{DARK}"/></radialGradient></defs>
<rect width="1200" height="630" fill="url(#ogbg)"/>
<g opacity="0.06" transform="translate(900,120) scale(3)">{emblem(uid="ogbgpat", star=GOLD, field="none", crescent=GOLD, gradient=False)}</g>
<g transform="translate(120,145) scale(1.7)">{emblem(uid="ogem")}</g>
<g transform="translate(510,180) scale(1.15)">{wmp}</g>
<rect x="510" y="270" width="120" height="4" fill="{GOLD}"/>
{text_path("FIC", FONT_BOLD, 96, 510, 400, GOLD, anchor="start", tracking=8)[0]}
{tag}''')
write("/tmp/og.svg", og); cairosvg.svg2png(url="/tmp/og.svg", write_to=f"{OUT}/social/og-image-1200x630.png")
write(f"{OUT}/svg/og-image.svg", og)
# Twitter/X header & profile
render("fic-icon-circle.svg", f"{OUT}/social/profile-400.png", 400)
hdr = svg(1500, 500, f'''<rect width="1500" height="500" fill="{DARK}"/>
<g opacity="0.07" transform="translate(1250,-40) scale(3.2)">{emblem(uid="hbg", star=GOLD, field="none", crescent=GOLD, gradient=False)}</g>
<g transform="translate(80,130) scale(1.2)">{emblem(uid="hem")}</g>
<g transform="translate(360,190) scale(1.25)">{wordmark(True, "hw")[0]}</g>
{text_path("FirstIslamicCoin.com", FONT_MED, 32, 360, 320, GOLD, anchor="start", tracking=1)[0]}''')
write("/tmp/hdr.svg", hdr); cairosvg.svg2png(url="/tmp/hdr.svg", write_to=f"{OUT}/social/header-1500x500.png")

# ---------- tokens ----------
palette = {
    "brand": {"green": GREEN, "greenDeep": GREEN_DEEP, "gold": GOLD, "goldDeep": GOLD_DEEP, "goldLight": GOLD_LIGHT},
    "neutral": {"dark": DARK, "light": LIGHT, "white": WHITE, "ink": "#14201B", "muted": "#5E6B65", "line": "#D9D6CB"},
    "semantic": {"success": "#1E9E6A", "warning": "#D89B2B", "error": "#C2413B", "info": "#2F6F9F"},
    "typography": {"display": "Poppins", "body": "Inter, system-ui, sans-serif", "arabic": "Noto Naskh Arabic, Amiri, serif", "mono": "JetBrains Mono, monospace"},
    "radius": {"sm": 6, "md": 12, "lg": 20, "pill": 999},
}
write(f"{OUT}/tokens/palette.json", json.dumps(palette, indent=2))
write(f"{OUT}/tokens/theme.css", f""":root {{
  --fic-green: {GREEN}; --fic-green-deep: {GREEN_DEEP}; --fic-gold: {GOLD}; --fic-gold-deep: {GOLD_DEEP}; --fic-gold-light: {GOLD_LIGHT};
  --fic-bg: {LIGHT}; --fic-surface: {WHITE}; --fic-ink: #14201B; --fic-muted: #5E6B65; --fic-line: #D9D6CB;
  --fic-primary: var(--fic-green); --fic-on-primary: {WHITE}; --fic-accent: var(--fic-gold); --fic-on-accent: {DARK};
  --fic-success: #1E9E6A; --fic-warning: #D89B2B; --fic-error: #C2413B; --fic-info: #2F6F9F;
  --fic-font-display: "Poppins", system-ui, sans-serif; --fic-font-body: "Inter", system-ui, sans-serif; --fic-font-arabic: "Noto Naskh Arabic", "Amiri", serif;
  --fic-radius-sm: 6px; --fic-radius-md: 12px; --fic-radius-lg: 20px;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --fic-bg: {DARK}; --fic-surface: #10291F; --fic-ink: #EEF2EE; --fic-muted: #9DB0A6; --fic-line: #23483A;
  --fic-primary: #1B9A6E; --fic-accent: {GOLD_LIGHT};
}} }}
:root[data-theme="dark"] {{
  --fic-bg: {DARK}; --fic-surface: #10291F; --fic-ink: #EEF2EE; --fic-muted: #9DB0A6; --fic-line: #23483A;
  --fic-primary: #1B9A6E; --fic-accent: {GOLD_LIGHT};
}}
""")
write(f"{OUT}/tokens/flutter_theme.dart", f"""import 'package:flutter/material.dart';

/// FirstIslamicCoin (FIC) brand colors and Material 3 themes.
class FicColors {{
  static const green = Color(0xFF{GREEN[1:]});
  static const greenDeep = Color(0xFF{GREEN_DEEP[1:]});
  static const gold = Color(0xFF{GOLD[1:]});
  static const goldDeep = Color(0xFF{GOLD_DEEP[1:]});
  static const goldLight = Color(0xFF{GOLD_LIGHT[1:]});
  static const dark = Color(0xFF{DARK[1:]});
  static const light = Color(0xFF{LIGHT[1:]});
}}

ThemeData ficLightTheme() => ThemeData(
  useMaterial3: true,
  colorScheme: ColorScheme.fromSeed(seedColor: FicColors.green, primary: FicColors.green, secondary: FicColors.gold, brightness: Brightness.light, surface: FicColors.light),
  scaffoldBackgroundColor: FicColors.light,
  fontFamily: 'Poppins',
);

ThemeData ficDarkTheme() => ThemeData(
  useMaterial3: true,
  colorScheme: ColorScheme.fromSeed(seedColor: FicColors.green, primary: const Color(0xFF1B9A6E), secondary: FicColors.goldLight, brightness: Brightness.dark, surface: const Color(0xFF10291F)),
  scaffoldBackgroundColor: FicColors.dark,
  fontFamily: 'Poppins',
);
""")

print("done")
