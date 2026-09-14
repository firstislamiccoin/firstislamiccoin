# firstislamiccoin-web-wallet

Phase 7 deliverable. A static, browser-based FirstIslamicCoin wallet -- no
build step, no bundler, no Node.js toolchain. Talks to
`../firstislamiccoin-staking-service/` using the exact same REST contract
(`../firstislamiccoin-mobile/docs/mobile-api.md`) as the mobile app
(`../firstislamiccoin-mobile/`). Forked from CodexaCoin's `web-wallet/` --
see `../docs/CHANGELOG-FIC.md`'s Phase 7 section for every deviation from
that source.

## Status

Not deployed anywhere -- no server, no DNS record (`docs/dns.md` lists
`wallet.firstislamiccoin.com` as planned but not live). Verified in a real
browser against a real regtest gateway+node stack -- see "Verification"
below.

## Files

- `index.html` / `style.css` -- markup and styling, no framework. Colors
  are the real brand tokens from `../firstislamiccoin-brand/tokens/theme.css`,
  not a generic reskin of CAC's palette.
- `app.js` -- all UI logic and event wiring.
- `crypto.js` -- address encoding, transaction signing, N-of-M multisig
  primitives (mirrors `../firstislamiccoin-mobile/lib/crypto/*.dart`).
- `gateway.js` -- REST client for the staking-service gateway.
- `qr.js` -- QR code generation (receive) and camera-based scanning
  (send). Needed no changes at all -- nothing in it was CAC-specific.
- `storage.js` -- optional PIN-based encryption for the recovery phrase
  at rest (PBKDF2 + AES-GCM via the browser's Web Crypto API).
- `sw.js` -- service worker, Web Push display only.

## What's different from CodexaCoin's `web-wallet/`

- **Chain parameters**: `crypto.js`'s `NETWORKS` now carries FIC's real
  values (mainnet P2PKH `36`/P2SH `28`/WIF `164`, bech32 HRP `fic`;
  testnet P2PKH `111`/P2SH `196`/WIF `239`, bech32 HRP `tfic`; BIP44 coin
  type `9770` on **both** networks, unlike CAC's testnet-uses-1
  convention) -- matching `firstislamiccoin-core`'s actual chainparams,
  not CAC's. Message-signing magic updated to
  `"FirstIslamicCoin Signed Message:\n"`, matching `message.cpp` exactly.
- **No wrapped-token/DEX integration, anywhere.** CAC's web wallet had a
  "Buy / Sell CAC (PancakeSwap)" button on Home and fetched a real (if
  thin) FIC/USD-equivalent price from that DEX pool plus a Stellar order
  book (`price.js`, dropped entirely) for the Home and Send screens' fiat
  estimate and the price-alerts "current price" display. FirstIslamicCoin
  has no wrapped token on any chain (`docs/CHANGELOG-FIC.md`'s
  Decision 3) -- the button is gone and both fiat-estimate spots are
  permanently empty rather than showing a fabricated number. The
  price-alerts feature itself is unchanged: it already asks the gateway's
  `/v1/price`, which now honestly answers `503` (see
  `firstislamiccoin-staking-service/price_alerts.py`) -- the existing
  `catch` block already showed "unavailable" for that case, so this
  needed no new code, just the removal of the client-side DEX fetch that
  used to race it.
- **P2CS cold-staking**: does not exist in `firstislamiccoin-core`'s
  consensus layer at all -- `crypto.js`'s multisig comment section notes
  this explicitly where CAC's referenced its own not-yet-built
  cold-staking feature.
- **Package/storage identity**: every `localStorage`/`sessionStorage` key
  renamed from `cac_*` to `fic_*` (`fic_mnemonic`, `fic_network`,
  `fic_address_book`, etc.) -- a fresh key namespace, not a migration,
  since this is a new deployment with no existing users to carry state
  forward for.
- **Explorer/legal links**: point at `explorer.firstislamiccoin.com` and
  `firstislamiccoin.com/legal/{terms,privacy}.html` (matching what
  Phases 8/9 actually built) instead of CAC's domain. No AML/KYC Policy
  page exists on the FIC website (CAC's linked one), so that link was
  dropped rather than pointed at a 404.
- **Brand colors**: `style.css`'s palette now uses
  `firstislamiccoin-brand/tokens/theme.css`'s real tokens (warm
  off-white/deep-green light palette, dark-green/gold dark palette)
  instead of CAC's dark-purple/gold scheme.

## Why no bundler

Unchanged from CAC: `crypto.js` hand-implements address encoding and
transaction signing on the `@noble`/`@scure` crypto libraries loaded
directly as ES modules from jsDelivr's `+esm` CDN endpoint --
dependency-free, browser-native, no bundler required. **This means the
page needs network access to jsDelivr to load.**

## Security note (also shown in-app, on the onboarding screen)

Unchanged from CAC: this web wallet keeps the recovery phrase in the
browser's `localStorage`, weaker than the mobile app's OS Keychain/
Keystore. Best suited for testnet/small amounts or as a reference
implementation. Setting a PIN (Settings tab) encrypts it at rest with a
PBKDF2-derived AES-GCM key -- real protection against someone reading
storage directly, not a UI-only lock, but only as strong as the PIN
itself.

## Running locally

Needs to be served over HTTP (ES module imports fail over `file://`):

```bash
python3 -m http.server 8090
```

Then open `http://127.0.0.1:8090`, with
`../firstislamiccoin-staking-service/` running and reachable (CORS must
be enabled there -- see its `GATEWAY_CORS_ORIGINS` env var, default `*`
-- for the browser to be allowed to call it from a different origin). By
default this page's `Gateway` points at its own origin; override via
`localStorage.setItem("fic_gateway_url_mainnet", "http://127.0.0.1:8080")`
(or `_testnet`) in the browser console for local dev against a gateway on
a different port.

## Verification (Phase 7)

Tested in a real browser (not just read for correctness), against a real
regtest `firstislamiccoind` node and a real `firstislamiccoin-staking-service`
instance -- the same stack Phase 6's own verification used:

- Wallet creation: real BIP39 mnemonic + BIP32 derivation via the
  CDN-loaded `@noble`/`@scure` libraries, producing a real,
  correctly-prefixed address (`m`/`n`-class on regtest, matching the
  P2PKH version byte 111 shared with testnet).
- Balance display against the live gateway after funding the address
  from the regtest genesis premine.
- A real send: built, signed, and broadcast through the gateway's own
  `/v1/tx/broadcast`, confirmed on-chain.
- Staking pool signup/login and the deposit flow: received a real
  deposit address from the pool wallet.
- Price alerts screen: confirmed `/v1/price`'s honest `503` renders as
  "Current price: unavailable right now", not an error or a stale
  number -- the one behavior this phase's Decision-3 changes needed to
  prove out end-to-end, not just read for correctness.

Full command-by-command account in `../docs/CHANGELOG-FIC.md`'s Phase 7
section.

## Deployment

Static files -- serve `index.html`/`app.js`/`crypto.js`/`gateway.js`/
`qr.js`/`storage.js`/`style.css`/`sw.js` from any static host or CDN. An
example nginx config serving this alongside a reverse-proxied gateway is
in `../firstislamiccoin-infra/provisioning/staking-service/` (adapt the
explorer's `nginx-example.conf` pattern -- not written separately here
since it would be near-identical).
