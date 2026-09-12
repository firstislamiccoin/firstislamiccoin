# FirstIslamicCoin (FIC) — Brand Kit

Everything here is generated from `generate.py` (vector-first, all text converted to outlines, so no fonts are required to render the SVGs). Re-run the script to regenerate every asset after changing a colour or the emblem geometry.

## Emblem

A gold crescent with an eight-point accent star, set inside a Rub el Hizb–style eight-point star (two overlapping squares) on Islamic green. No people, animals, or calligraphy are depicted, so the mark is safe to use across all markets and app stores. Minimum display size: 24 px (use `fic-icon-*` variants; below 24 px the accent star may be dropped).

## Files

| Folder | Contents |
|---|---|
| `svg/` | Master vectors: `fic-icon` (transparent), `fic-icon-square` (app-icon style), `fic-icon-circle`, mono variants (white / black / green), `fic-coin-full` (512 coin with FIC wordmark), `fic-wordmark` (+ on-dark), `fic-lockup-horizontal` (+ dark), `fic-lockup-vertical`, `og-image` |
| `png/` | Icon, square icon and full coin at 16–1024 px; @2x exports of wordmarks and lockups |
| `android/` | `mipmap-*` launcher icons (legacy + round) and adaptive `ic_launcher_foreground/background`, `mipmap-anydpi-v26/*.xml`, `playstore-icon-512.png` |
| `ios/AppIcon.appiconset/` | Complete Xcode asset catalog (iPhone, iPad, App Store 1024) with `Contents.json` — drop into `Assets.xcassets` |
| `favicon/` | `favicon.ico` (16/32/48), `favicon.svg`, PNGs 16–512, `apple-touch-icon.png`, `site.webmanifest` |
| `splash/` | Light + dark splash screens: phone 1080×1920, 1242×2688, tablet 1536×2048, square 1024 |
| `social/` | `og-image-1200x630.png`, profile 400×400, header 1500×500 |
| `tokens/` | `palette.json`, `theme.css` (CSS variables, light/dark), `flutter_theme.dart` (Material 3 themes) |

## Colours

| Token | Hex | Use |
|---|---|---|
| Green | `#0B6E4F` | Primary, buttons, app-icon field |
| Green deep | `#08523B` | Pressed states, gradients |
| Gold | `#D4AF37` | Accent, emblem, highlights, "Islamic" in the wordmark |
| Gold deep | `#B8962E` | Gradient shadow side |
| Gold light | `#E9CC6A` | Gradient highlight side, dark-mode accent |
| Dark | `#0A1F17` | Dark-mode background |
| Light | `#F7F5EE` | Light-mode background (warm off-white) |

Contrast: white on Green = 6.9:1 (AA/AAA for text); Dark on Gold = 9.4:1; Gold on Dark = 9.4:1. Avoid gold text on the light background for body copy (2.3:1) — use it for large display text or on green/dark only.

## Typography

Display and wordmark: **Poppins** (Medium for "First"/"Coin", Bold for "Islamic"). Body: Inter or system-ui. Arabic/Urdu UI: Noto Naskh Arabic or Amiri. Mono (addresses, tx ids): JetBrains Mono.

## Clear space & don'ts

Keep clear space equal to the height of the accent star around the emblem. Don't recolour the emblem outside the mono variants, don't rotate the star, don't place the gold emblem on gold, don't add drop shadows, and don't stretch the wordmark.

## Placing into the repos (matches the Claude Code prompt)

- `firstislamiccoin-core/src/qt/res/icons/` ← `png/fic-icon-square-*.png` (rename to `bitcoin.png` equivalents as CAC does), `splash/splash-square-*.png` for the Qt splash.
- `firstislamiccoin-mobile/android/app/src/main/res/` ← `android/mipmap-*`.
- `firstislamiccoin-mobile/ios/Runner/Assets.xcassets/` ← `ios/AppIcon.appiconset`.
- `firstislamiccoin-web-wallet/public/` and `firstislamiccoin-website/public/` ← `favicon/*`, `social/og-image-1200x630.png`.
- Every front-end ← `tokens/theme.css`; Flutter ← `tokens/flutter_theme.dart`.
