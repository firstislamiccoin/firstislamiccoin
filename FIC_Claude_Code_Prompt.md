# Claude Code Master Prompt — FirstIslamicCoin (FIC)

> Copy everything below the line into Claude Code. Run it phase by phase (`Phase 0` first). Each phase ends with an explicit acceptance checklist; do not advance until every item passes.

---

## ROLE AND CONTEXT

You are the lead engineer for **FirstIslamicCoin (FIC)**, a new Proof-of-Stake Layer-1 cryptocurrency. FIC is a fork of **CodexaCoin (CAC)**, which is itself a fork of **Blackcoin More** (Bitcoin Core lineage, PoS v3 consensus, C++). The CodexaCoin repository is the starting point; everything CodexaCoin already has (rebranded core, testnet, desktop wallet CI, ElectrumX backend, Flutter mobile wallets, VPS staking service, web wallet, block explorer) must be carried over, rebranded, and then modified according to the FIC-specific changes below.

Official website: **https://FirstIslamicCoin.com**
Project name: **FirstIslamicCoin**
Ticker: **FIC**
Smallest unit name: **fils** (1 FIC = 100,000,000 fils)

Work methodically. Before changing any file, read it. Prefer minimal, surgical diffs over rewrites. Never delete tests; update them. Commit after every logical step with clear messages. Keep a running `docs/CHANGELOG-FIC.md` documenting every deviation from CodexaCoin.

---

## GLOBAL BRAND & IDENTITY CONSTANTS

Use these values everywhere (source of truth: `docs/brand.md`, which you will create in Phase 0):

| Key | Value |
|---|---|
| Full name | FirstIslamicCoin |
| Short name | FIC |
| Ticker | FIC |
| Sub-unit | fils (1 FIC = 10^8 fils) |
| Website | https://FirstIslamicCoin.com |
| Explorer | https://explorer.FirstIslamicCoin.com |
| Web wallet | https://wallet.FirstIslamicCoin.com |
| Electrum servers | electrum1.FirstIslamicCoin.com, electrum2.FirstIslamicCoin.com |
| DNS seeds | seed1.FirstIslamicCoin.com, seed2.FirstIslamicCoin.com, seed3.FirstIslamicCoin.com |
| GitHub org | `FirstIslamicCoin` |
| Primary color (Islamic green) | `#0B6E4F` |
| Accent color (gold) | `#D4AF37` |
| Dark background | `#0A1F17` |
| Light background | `#F7F5EE` |
| Text on green | `#FFFFFF` |
| Logo motif | Crescent + eight-point Islamic geometric star (Rub el Hizb-inspired), no depictions of people or animals |
| Data directory | `~/.firstislamiccoin/` (Linux), `%APPDATA%\FirstIslamicCoin\` (Windows), `~/Library/Application Support/FirstIslamicCoin/` (macOS) |
| Config file | `firstislamiccoin.conf` |
| Daemon / CLI / GUI binaries | `firstislamiccoind`, `firstislamiccoin-cli`, `firstislamiccoin-tx`, `firstislamiccoin-qt` |
| URI scheme | `firstislamiccoin:` |

---

## CHAIN PARAMETERS

| Parameter | Mainnet | Testnet | Regtest |
|---|---|---|---|
| Ticker | FIC | tFIC | rFIC |
| Premine (genesis output) | **14,000,000,000 FIC** (same as CAC) | 14,000,000,000 tFIC | 14,000,000,000 rFIC |
| Target block spacing | 64 seconds | 64 seconds | 1 second |
| Consensus | PoS v3 (Blackcoin kernel), no PoW after genesis | same | same |
| **PoS reward model** | **Fixed per-block reward** (see below) | same | same |
| Initial block reward | **10 FIC + tx fees** | 10 tFIC + fees | 10 rFIC + fees |
| Minimum stake age | 8 hours | 1 hour | 0 |
| Maximum stake age | none (coin age has NO effect on reward or weight) | same | same |
| Stake weight | proportional to coin amount only | same | same |
| Coinbase/coinstake maturity | 500 blocks | 50 | 10 |
| P2P port | 19770 | 29770 | 39770 |
| RPC port | 19771 | 29771 | 39771 |
| Message start bytes (magic) | `0xF1 0x1C 0x51 0xA3` | `0xF1 0x1C 0x54 0xB3` | `0xF1 0x1C 0x52 0xC3` |
| P2PKH address prefix (base58) | 36 → addresses start with **`F`** | 111 (`m`/`n`) | 111 |
| P2SH address prefix | 28 → addresses start with **`C`** | 196 | 196 |
| WIF secret prefix | 164 | 239 | 239 |
| Bech32 HRP | `fic` | `tfic` | `rfic` |
| BIP44 coin type | 9770 (register at SLIP-0044 via PR; use as-is until merged) | 1 | 1 |
| Extended key prefixes (xpub/xprv) | `0x0488B21E` / `0x0488ADE4` (standard) | tpub/tprv | tpub/tprv |
| Genesis timestamp string | `"FirstIslamicCoin 12/Sep/2026 — Bismillah, the first Shariah-conscious Proof-of-Stake network"` | same | same |
| Genesis time | 1789171200 (2026-09-12 00:00:00 UTC) | 1789171200 | 1789171200 |

**Reward model — mandatory implementation details**

1. `GetProofOfStakeReward(...)` (or CAC's equivalent, wherever the 1.14%/month coin-age formula lives — search for it in `src/pos.cpp`, `src/validation.cpp`, `src/kernel.cpp` and `src/consensus/`) must be replaced so that it returns `consensusParams.nFixedStakeReward + nFees`. Remove the coin-age-proportional computation, the 60-day age cap, and the 128-bit overflow handling associated with it. Document the removal in `docs/CHANGELOG-FIC.md`.
2. Kernel stake weight (`CheckStakeKernelHash` / `GetKernelStakeModifier` path) must use **coin amount only**. If CAC's kernel multiplies weight by age, remove the age factor. Keep the minimum stake age as an anti-grinding measure only.
3. Add `nFixedStakeReward` to `Consensus::Params` and set it in `chainparams.cpp` for all three networks.
4. Add an **optional** halving schedule field `nRewardHalvingInterval` (default 0 = disabled). Implement the code path so it can be enabled later by a single parameter change; leave it disabled at launch.
5. Emission calculation (write it into `docs/tokenomics.md`): 31,536,000 s / 64 s ≈ 492,750 blocks/year × 10 FIC = ~4,927,500 FIC/year ≈ 0.035% annual inflation against the 14B premine.
6. Write unit tests (`src/test/fic_reward_tests.cpp`) proving: reward is constant regardless of input amount; reward is constant regardless of coin age; reward equals fixed amount + fees; halving path works when enabled on regtest.
7. Write `docs/shariah-compliance.md` (plain English, non-legal) explaining: rewards are compensation for validation work (block production), not a percentage return on principal; the amount does not scale with the depositor's balance per block; the frequency of winning is stake-weighted (proportional participation, like a mudarabah-style profit share in a joint venture); rewards are uncertain and not guaranteed. State clearly that this document is not a fatwa and that the project will seek review from a qualified Shariah advisory board. Do **not** invent any endorsements, scholar names, or certification claims.

---

## REPOSITORY LAYOUT (target)

```
FirstIslamicCoin/
├── firstislamiccoin-core/        # C++ node, forked from codexacoin-core
├── firstislamiccoin-electrumx/   # ElectrumX fork with FIC coin definition
├── firstislamiccoin-mobile/      # Flutter app (Android + iOS), single codebase
├── firstislamiccoin-web-wallet/  # Web wallet (React + TypeScript)
├── firstislamiccoin-explorer/    # Block explorer
├── firstislamiccoin-staking-service/  # VPS staking service (custodial + P2CS non-custodial)
├── firstislamiccoin-website/     # FirstIslamicCoin.com marketing site
├── firstislamiccoin-brand/       # Logos, palette, typography, icon sets
└── firstislamiccoin-infra/       # Docker Compose, Ansible/Terraform, seed nodes, CI
```

If CodexaCoin's repositories are structured differently, mirror CAC's structure and record the mapping in `docs/repo-map.md`.

---

## PHASE 0 — Discovery and Brand Kit

1. Clone every CodexaCoin repository. Run `git log --oneline | head -50` and `tree -L 3` on each; write a summary of what exists, what builds, and what is incomplete to `docs/cac-audit.md`.
2. Locate every occurrence of the CAC brand and parameters: `grep -rniE "codexa|codexacoin|\bCAC\b|0B2A45|F0C24E" --exclude-dir=.git`. Save the file list to `docs/rebrand-manifest.txt`.
3. Create `firstislamiccoin-brand/` containing:
   - `docs/brand.md` with the constants table above.
   - `logo/fic-coin-full.svg` — round coin, green field, gold rim, crescent + eight-point star, "FIC" wordmark beneath the emblem.
   - `logo/fic-icon.svg` — simplified emblem only (crescent + star), for app icons and favicons.
   - `logo/fic-wordmark.svg` — "FirstIslamicCoin" wordmark, geometric sans-serif.
   - Generated raster exports: 16, 32, 64, 128, 256, 512, 1024 px PNGs; Android adaptive icon set; iOS AppIcon set (all required sizes); favicon.ico; splash screens (light/dark).
   - `palette.json` and `theme.css` (CSS custom properties) with light and dark themes.
4. Acceptance: all SVGs render (verify by rasterizing with `rsvg-convert` or `cairosvg`), PNG sets are complete, and `docs/cac-audit.md` exists.

---

## PHASE 1 — Core Node Rebrand and Chain Parameters

1. Fork `codexacoin-core` → `firstislamiccoin-core`. Perform a **case-preserving** global rename: `CodexaCoin`→`FirstIslamicCoin`, `codexacoin`→`firstislamiccoin`, `CODEXACOIN`→`FIRSTISLAMICCOIN`, `CAC`→`FIC` (ticker contexts only — check each hit manually; do not rename unrelated identifiers). Rename files, directories, binaries, `.desktop` entries, `Info.plist`, Windows `.rc` and NSIS installer strings, `configure.ac`, `Makefile.am`, `contrib/`, `share/`, `doc/`.
2. Replace all CAC artwork under `src/qt/res/` with the FIC brand kit. Update the Qt splash screen and `bitcoin.qrc`/equivalent.
3. Apply every chain parameter from the table above in `src/chainparams.cpp`, `src/chainparamsbase.cpp`, `src/consensus/params.h`, `src/kernel/chainparams.cpp` (wherever CAC keeps them). Update `src/util/system.cpp` / `src/common/args.cpp` data-dir names.
4. Regenerate genesis blocks for mainnet/testnet/regtest: write a `contrib/genesis/generate_genesis.py` script that mines the genesis nonce for the given timestamp string, time, and nBits, and prints hash + merkle root. Insert the results and add asserts in `CChainParams`. Record all values in `docs/genesis.md`.
5. Implement the **fixed per-block reward model** exactly as specified in "Reward model — mandatory implementation details". Add tests.
6. Clear CAC checkpoints and `chainTxData`; leave `assumevalid` null until launch.
7. Set `nDefaultPort`, `vSeeds` (the three DNS seeds), and empty `vFixedSeeds` for now (populate in Phase 3).
8. Update `README.md`, `doc/build-*.md`, `COPYING` (keep upstream MIT + Blackcoin/CodexaCoin attributions; add FIC copyright line).
9. Build on Linux with `depends/` and native; run `make check` and `test/functional/test_runner.py`. All tests must pass, including the new reward tests.
10. Acceptance: `firstislamiccoind -regtest` starts, produces staking blocks, `getblockchaininfo` reports the new genesis hash, `getstakinginfo` works, and `grep -rni codexa` returns zero hits outside `docs/CHANGELOG-FIC.md` and `COPYING`.

---

## PHASE 2 — Testnet Validation

1. Provision (via `firstislamiccoin-infra/docker-compose.testnet.yml`) three testnet nodes on one host plus a fourth on a separate network namespace.
2. Distribute the premine from the genesis key across 5 wallets; start staking on all; run ≥ 2,000 testnet blocks. Verify: reward per block is exactly 10 tFIC + fees at every height; block spacing average within ±10% of 64 s; no forks longer than 2 blocks; reorg handling works (`invalidateblock`/`reconsiderblock`).
3. Stress-test: 10,000 transactions via `sendmany` batches, mempool eviction, restart-with-reindex, `-prune=2000`, `-txindex=1`.
4. Write a `test/functional/feature_fic_fixed_reward.py` functional test and add it to the runner.
5. Acceptance: `docs/testnet-report.md` with the metrics above and all functional tests green.

---

## PHASE 3 — Desktop Wallets, CI and Release Pipeline

1. GitHub Actions matrix: Linux x86_64 (deb + tar.gz), Windows x86_64 (NSIS installer + zip), macOS universal (dmg, notarization step templated with secrets), all built through `depends/` for reproducibility. Use Guix if CAC already uses it.
2. Artifacts named `firstislamiccoin-<version>-<platform>.<ext>`; attach SHA256SUMS and a detached GPG signature step.
3. Add release drafter and semantic version tags starting at `v1.0.0-rc1`.
4. Qt wallet: theme with the FIC palette (light + dark), FIC coin control, staking status tab, "Cold Staking (P2CS)" delegation dialog reused from CAC, and an "About FirstIslamicCoin" dialog linking to the website and the Shariah-compliance doc.
5. Populate `vFixedSeeds` from the first mainnet seed nodes once Phase 6 provisions them.
6. Acceptance: green CI on all three platforms; installers open and sync testnet.

---

## PHASE 4 — ElectrumX Light-Wallet Backend

1. Fork `codexacoin-electrumx` → `firstislamiccoin-electrumx`. Add `class FirstIslamicCoin(Coin)` and `FirstIslamicCoinTestnet` to `electrumx/lib/coins.py` with: `NAME`, `SHORTNAME="FIC"`, `NET`, `P2PKH_VERBYTE=bytes.fromhex("24")`, `P2SH_VERBYTES`, `WIF_BYTE`, `GENESIS_HASH`, `XPUB_VERBYTES`/`XPRV_VERBYTES`, `TX_COUNT`, `TX_COUNT_HEIGHT`, `TX_PER_BLOCK`, `RPC_PORT`, `PEERS`, and the PoS block header deserializer CAC uses (Blackcoin-style headers with `nFlags`/signature — reuse CAC's `DeserializerBlackcoin` equivalent).
2. Docker image `firstislamiccoin/electrumx` with TLS termination (Caddy/Traefik), ports 50001 (TCP) / 50002 (SSL) / 50004 (WSS — required by the web wallet).
3. Acceptance: server syncs full testnet, responds to `server.version`, `blockchain.scripthash.get_balance`, `blockchain.transaction.broadcast`; WSS endpoint reachable from a browser.

---

## PHASE 5 — Mobile Wallets (Android + iOS, Flutter)

1. Fork `codexacoin-mobile` → `firstislamiccoin-mobile`. Rename package IDs: Android `com.firstislamiccoin.wallet`, iOS bundle `com.firstislamiccoin.wallet`. Replace app icons, splash screens, and theme with the FIC brand kit (Material 3 color scheme seeded from `#0B6E4F`, gold accents, full dark-mode support). App display name: **FIC Wallet**.
2. Wallet core (reuse CAC's, change constants): BIP39 mnemonic (12/24 words, with Arabic and Urdu wordlists offered in addition to English if the BIP39 library supports them — otherwise English only, never invent wordlists), BIP32/BIP44 derivation `m/44'/9770'/0'`, secp256k1 signing, P2PKH + bech32 (`fic1...`) address support, Electrum protocol client over WSS/TCP with server list from `https://FirstIslamicCoin.com/servers.json` plus hard-coded fallback.
3. Features: send/receive (QR generation and scanning, `firstislamiccoin:` URI parsing), transaction history with confirmation status, fee selection, address book, biometric unlock (Face ID / fingerprint), PIN, encrypted secure storage (Keychain / Android Keystore), backup + restore, multi-wallet, watch-only (xpub) wallets, fiat display (USD/EUR/PKR/SAR/AED/MYR/IDR/TRY via a price API abstraction with a stub until FIC is listed), push-notification hooks for incoming transactions (Firebase, optional), and a **"Cold Staking" screen** that constructs P2CS delegation transactions to a chosen staking-service address — **no on-device staking** (same policy as CAC).
4. Localization: English (default), Arabic (RTL, fully mirrored layout), Urdu (RTL), Bahasa Indonesia, Malay, Turkish. Use Flutter `intl` ARB files; leave all strings translatable with English fallback — do not machine-translate religious terms carelessly; keep "Bismillah" and similar untranslated where used.
5. Add an "About" section with links to the website, explorer, Shariah-compliance doc, and privacy policy.
6. CI: GitHub Actions building a signed Android AAB/APK (keystore via secrets) and an iOS IPA via Fastlane match (templated); TestFlight and Play internal-track upload lanes.
7. Store metadata: write `store/android/` and `store/ios/` listing text, screenshots checklist, privacy policy (`docs/privacy-policy.md`), and a compliance note that the app is a non-custodial wallet and does not custody funds.
8. Acceptance: app runs on an Android emulator and iOS simulator, restores a testnet wallet from mnemonic, shows balance from ElectrumX, sends a testnet transaction, and passes `flutter test` + `flutter analyze` with zero errors.

---

## PHASE 6 — VPS Staking Service (Custodial + Non-Custodial P2CS)

1. Fork `codexacoin-staking-service` → `firstislamiccoin-staking-service`. Rebrand and point at the FIC node RPC.
2. Non-custodial P2CS (Cold Staking) mode: publish the service's staking address(es); users delegate from desktop/mobile/web wallets; the service stakes on their behalf but cannot spend. Reward accounting: the fixed 10 FIC block reward is paid into the coinstake as usual; the service takes a configurable fee percentage from the **reward only** (never from principal), and the remainder is credited to the delegator — implement this in the coinstake output construction. Document in `docs/p2cs.md`.
3. Custodial mode (opt-in, KYC-gated hook available but disabled by default): pooled hot wallet, proportional reward distribution by stake-weighted share per block, daily payout job, withdrawal queue, full audit log. Implement hot/cold wallet separation with a cold-storage sweep threshold.
4. API (FastAPI or Node — match CAC): `/v1/staking/address`, `/v1/staking/stats`, `/v1/delegations/{address}`, `/v1/rewards/{address}`, health and Prometheus metrics.
5. Security: RPC over localhost only, wallet encryption with passphrase from a secrets manager, rate limiting, 2FA for the admin panel, nightly encrypted wallet backups to object storage.
6. Deployment: Ansible playbook + `docker-compose.prod.yml` for a single VPS, and a hardening checklist (`docs/vps-hardening.md`: ufw, fail2ban, unattended-upgrades, SSH keys only).
7. Also provision **three mainnet seed nodes** and DNS-seeder (`sipa/bitcoin-seeder` fork) here; feed their IPs back into Phase 3 `vFixedSeeds`.
8. Acceptance: on testnet, a delegated P2CS UTXO earns rewards; service fee is deducted only from rewards; custodial pool distributes correctly across three test accounts; all endpoints documented with OpenAPI.

---

## PHASE 7 — Web Wallet

1. Fork `codexacoin-web-wallet` → `firstislamiccoin-web-wallet` (React + TypeScript + Vite, or match CAC's stack). Fully client-side: keys never leave the browser; talks to ElectrumX over WSS.
2. Features: create/restore BIP39 wallet, encrypted local vault (WebCrypto AES-GCM, PBKDF2/Argon2), send/receive with QR, history, address book, watch-only mode, P2CS delegation UI, hardware-wallet abstraction stub, PWA install support, RTL layouts for Arabic/Urdu, light/dark FIC theme.
3. Security: strict CSP, no third-party scripts, Subresource Integrity, clear "self-custody" warnings, optional passphrase (25th word).
4. Deploy: static build to `wallet.FirstIslamicCoin.com` via GitHub Pages/Cloudflare Pages with CI; `servers.json` published from the website repo.
5. Acceptance: Lighthouse PWA score ≥ 90, restores a testnet wallet, sends a transaction, delegates to the staking service address, no console errors, passes `npm test`.

---

## PHASE 8 — Block Explorer

1. Fork `codexacoin-explorer` → `firstislamiccoin-explorer` (reuse CAC's stack; if starting fresh, use `janoside/btc-rpc-explorer` fork with PoS field support).
2. Rebrand, add: staking statistics page (blocks/day, active stake weight estimate, current block reward — always 10 FIC — and annual emission), rich list, P2CS delegation stats, API endpoints (`/api/supply`, `/api/circulating`, `/api/blockreward`) needed by CoinMarketCap/CoinGecko listing forms.
3. Deploy at `explorer.FirstIslamicCoin.com` with Docker Compose alongside a full `-txindex=1` node.
4. Acceptance: explorer indexes full testnet, all pages render, API returns correct supply.

---

## PHASE 9 — Website (FirstIslamicCoin.com)

1. Static site (Astro or Next.js static export) with the FIC brand: hero, "How FIC works" (PoS with fixed per-block reward, explained simply), tokenomics page generated from `docs/tokenomics.md`, Shariah-compliance page generated from `docs/shariah-compliance.md` (with the disclaimer preserved verbatim), downloads page (auto-pulls latest GitHub release assets + checksums), wallets page (Web / Android / iOS / Desktop links), staking page (how to delegate; staking-service address), roadmap, FAQ, community links, `servers.json`, privacy policy, and terms.
2. Arabic + Urdu localized versions with RTL; SEO metadata; OpenGraph images from the brand kit.
3. No fabricated partnerships, listings, scholar endorsements, or price claims anywhere on the site.
4. Deploy with CI to Cloudflare Pages; configure the DNS records for all subdomains listed in the constants table and document them in `docs/dns.md`.
5. Acceptance: site builds, Lighthouse ≥ 90 on all categories, all links resolve.

---

## PHASE 10 — Mainnet Launch Checklist and Handover

1. Freeze parameters; regenerate mainnet genesis with the final timestamp; set `assumevalid` and initial checkpoints after the first 1,000 mainnet blocks; tag `v1.0.0`.
2. Security review pass: run `clang-tidy`, `cppcheck`, ASan/UBSan builds on core; `npm audit` / `flutter pub outdated` on apps; document findings in `docs/security-review.md`.
3. Produce `docs/LAUNCH-RUNBOOK.md`: genesis key ceremony (premine held in a multisig 3-of-5 cold wallet — write the exact commands), seed node bring-up order, ElectrumX sync, explorer, staking service, wallet releases, announcement copy.
4. Produce `docs/OPERATIONS.md` covering backups, upgrades, incident response, and how to enable the halving schedule via a scheduled consensus-height activation if the community later votes for it.
5. Final deliverable: a top-level `README.md` in the `FirstIslamicCoin` org describing every repository, how they fit together, and the status of each phase.

---

## GENERAL RULES FOR EVERY PHASE

- Read before you write; never guess file contents.
- Run the existing test suite before and after each change.
- Keep the fixed-reward invariant sacred: **every block pays exactly `nFixedStakeReward` + fees, independent of stake amount or age.** If any code path violates this, stop and fix it before continuing.
- Never introduce hidden premine outputs, developer taxes, or backdoors. Every consensus-affecting constant must be documented in `docs/tokenomics.md`.
- Do not fabricate endorsements, audits, certifications, listings, or Shariah rulings. Use placeholders labelled `TODO-HUMAN` where a human decision or external review is required.
- At the end of each phase, print a summary: files changed, tests added, open `TODO-HUMAN` items, and the exact commands to verify the acceptance checklist.
