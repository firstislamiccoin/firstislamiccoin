# FirstIslamicCoin — brand and identity constants

Source of truth for every brand, naming and identity value in the FIC project.
Consensus and chain parameters live in [`../../docs/cac-audit.md`](../../docs/cac-audit.md)
and (once Phase 1 lands) `firstislamiccoin-core/PARAMETERS-FIC.md` — not here.

For asset usage, clear space, don'ts and the file inventory, see the kit's
[`../README.md`](../README.md).

## Identity

| Key | Value |
|---|---|
| Full name | FirstIslamicCoin |
| Short name | FIC |
| Ticker | FIC |
| Sub-unit | fils (1 FIC = 10⁸ fils) |
| Website | https://FirstIslamicCoin.com |
| Explorer | https://explorer.FirstIslamicCoin.com |
| Web wallet | https://wallet.FirstIslamicCoin.com |
| Electrum servers | electrum1.FirstIslamicCoin.com, electrum2.FirstIslamicCoin.com |
| DNS seeds | seed1.FirstIslamicCoin.com, seed2.FirstIslamicCoin.com, seed3.FirstIslamicCoin.com |
| GitHub org | `FirstIslamicCoin` |
| Mobile app display name | FIC Wallet |

## Palette

| Token | Hex | Use |
|---|---|---|
| Green (primary) | `#0B6E4F` | Primary, buttons, app-icon field |
| Green deep | `#08523B` | Pressed states, gradients |
| Gold (accent) | `#D4AF37` | Accent, emblem, "Islamic" in the wordmark |
| Gold deep | `#B8962E` | Gradient shadow side |
| Gold light | `#E9CC6A` | Gradient highlight, dark-mode accent |
| Dark background | `#0A1F17` | Dark-mode background |
| Light background | `#F7F5EE` | Light-mode background (warm off-white) |
| Text on green | `#FFFFFF` | — |

Contrast: white on green 6.9:1 (AA/AAA body text); dark on gold and gold on dark
both 9.4:1. **Gold on the light background is 2.3:1** — display sizes only, never
body copy. Machine-readable values in [`../tokens/palette.json`](../tokens/palette.json).

## Logo

Crescent + eight-point Islamic geometric star (Rub el Hizb-inspired: two
overlapping squares), gold on Islamic green. **No depictions of people or
animals**, and no calligraphy — so the mark is safe across all markets and app
stores.

Minimum display size 24 px; below that use the `fic-icon-*` variants, where the
accent star may be dropped.

## Typography

| Role | Face |
|---|---|
| Display / wordmark | Poppins (Medium for "First"/"Coin", Bold for "Islamic") |
| Body | Inter, system-ui |
| Arabic / Urdu UI | Noto Naskh Arabic, Amiri |
| Mono (addresses, tx ids) | JetBrains Mono |

Kit SVGs carry all text as outlines, so none of these fonts are needed to render
them.

## Platform naming

| Key | Value |
|---|---|
| Daemon | `firstislamiccoind` |
| CLI | `firstislamiccoin-cli` |
| Tx tool | `firstislamiccoin-tx` |
| GUI | `firstislamiccoin-qt` |
| Config file | `firstislamiccoin.conf` |
| URI scheme | `firstislamiccoin:` |
| Android package | `com.firstislamiccoin.wallet` |
| iOS bundle | `com.firstislamiccoin.wallet` |
| Release artifacts | `firstislamiccoin-<version>-<platform>.<ext>` |

### Data directory

| OS | Path |
|---|---|
| Linux | `~/.firstislamiccoin/` |
| Windows | `%APPDATA%\FirstIslamicCoin\` |
| macOS | `~/Library/Application Support/FirstIslamicCoin/` |

## Localization

English (default), Arabic (RTL), Urdu (RTL), Bahasa Indonesia, Malay, Turkish.
Flutter `intl` ARB files, English fallback for every string.

Keep "Bismillah" and comparable religious terms **untranslated** where used, and
do not machine-translate religious terminology.

## Asset placement

| Destination | Source |
|---|---|
| `firstislamiccoin-core/src/qt/res/icons/` | `png/fic-icon-square-*.png` (renamed to match CAC's `bitcoin.png` equivalents) |
| `firstislamiccoin-core/src/qt/res/images/` | `splash/splash-square-*.png` |
| `firstislamiccoin-mobile/android/app/src/main/res/` | `android/mipmap-*` |
| `firstislamiccoin-mobile/ios/Runner/Assets.xcassets/` | `ios/AppIcon.appiconset` |
| `firstislamiccoin-web-wallet/public/`, `firstislamiccoin-website/public/` | `favicon/*`, `social/og-image-1200x630.png` |
| every front-end | `tokens/theme.css` |
| Flutter | `tokens/flutter_theme.dart` |

## Honesty constraints

These are brand rules, not just legal hygiene, and they apply to every asset,
page and store listing produced under this identity:

- No fabricated endorsements, scholar names, fatwas, certifications or audits.
- No claimed partnerships or exchange listings that do not exist.
- No price or return claims.
- The Shariah-compliance document is **not a fatwa** and must say so wherever it
  is surfaced. Review by a qualified advisory board is still pending —
  `TODO-HUMAN`.
