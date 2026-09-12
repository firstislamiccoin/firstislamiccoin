# CHANGELOG-FIC

Every deviation of FirstIslamicCoin from CodexaCoin, in the order decided.

Upstream baseline: `github.com/fakharnaqvi5313/codexacoin` @ `50b1dce`. CAC's own
parameter record and changelogs are archived unmodified in [`upstream/`](upstream/).

---

## Phase 0 — Discovery and brand kit

*2026-09-12*

### Delivered

- [`cac-audit.md`](cac-audit.md) — audit of the CAC tree: what exists, what
  builds, what is incomplete, and every place the FIC prompt's assumptions
  diverge from the code.
- [`repo-map.md`](repo-map.md) — CAC monorepo → FIC directory mapping. FIC mirrors
  the monorepo shape rather than splitting into nine repositories.
- [`rebrand-manifest.txt`](rebrand-manifest.txt) — 375 unique files needing brand
  edits, by pattern.
- `firstislamiccoin-brand/` — brand kit reconciled into the target layout.

### Brand kit deviations from the prompt

The kit was supplied pre-built (`FIC_Brand_Kit/fic-brand/`) rather than generated
during this phase. Verified rather than assumed: all 15 SVGs parse as well-formed
XML with valid `viewBox` and intrinsic dimensions, all text is converted to
outlines (zero `font-family` / `<text>` references, so CI needs no fonts
installed), every PNG's dimensions were read from its header, and all seven
palette values match the prompt's constants table exactly.

| Prompt says | Kit has | Resolution |
|---|---|---|
| `firstislamiccoin-brand/logo/*.svg` | `svg/*.svg` | **Kept `svg/`.** It is the layout `generate.py` writes and the kit README documents; renaming would desync both for no gain |
| `docs/brand.md` | `README.md` | Added `docs/brand.md` as the prompt's constants table; kit `README.md` retained as the usage guide |
| `favicon.ico` at 16/32/48 | **16 only** — kit README overstated it | **Fixed.** Rebuilt from `favicon-512.png` via Pillow; now genuinely 16/32/48 |

Also added `firstislamiccoin-brand/render-check.html` — a self-contained contact
sheet with every SVG inlined, for re-verifying renders after any
`generate.py` change.

`generate.py` hardcodes `OUT = "/home/claude/fic-brand"` and Linux
Google-Fonts paths, so it needs pathing work before it will run on another host.
Not blocking — every asset it produces is already committed. `TODO-HUMAN`.

**Acceptance note:** the prompt asks that SVGs be verified by rasterizing with
`rsvg-convert` or `cairosvg`. Neither is usable on this Windows host — `cairosvg`
installs but cannot load `libcairo-2.dll`, and `convert` on `PATH` is Windows'
FAT→NTFS tool, not ImageMagick. Renders were instead verified by XML validity,
by the committed PNG exports (which `generate.py` produced from these same SVGs
via cairosvg), and by visual inspection of the preview sheet.

---

## Decisions

Three scope decisions taken before Phase 1, after the audit showed the prompt's
assumptions about CAC were wrong in each case.

### Decision 1 — Premine becomes a true genesis output

**Decided:** carry the premine in the genesis coinbase as spendable outputs.
Drop CAC's 500-block proof-of-work premine window.

**What CAC does:** mints the 14,000,000,000 premine through blocks 1–500 of
proof of work at a flat 28,000,000 per block, then rejects PoW forever. Its
genesis coinbase is never added to the UTXO set, as in Bitcoin.

**Why:** the prompt's parameter table says "Premine (genesis output)" and "no
PoW after genesis". CAC's window contradicts both.

**As implemented** (full rationale in [`genesis.md`](genesis.md)):

1. `ConnectBlock()`'s genesis special case now adds the coinbase outputs to the
   UTXO set instead of skipping them.
2. **Genesis outputs are exempt from maturity** — `IsStakeMature()` in `pos.h` —
   so something can stake block 1. Applied in `CheckProofOfStake`,
   `CheckKernel`, `CacheKernel`, `Consensus::CheckTxInputs`, the mempool's reorg
   maturity check, `CWallet::GetTxBlocksToMaturity` and the wallet's staking
   selection. Height-0 coins only; every other coin still needs
   `nCoinbaseMaturity`. Safe because the only thing maturity protects against,
   a reorganisation, cannot happen to the genesis block.
3. **The premine is 1,000 equal outputs, not one.** Found during
   implementation: with a single output the chain produces block 1 and then
   stalls, because staking the output turns it into a coinstake output that
   must wait out full maturity, and nothing else exists to stake block 2. With
   1,000, genesis outputs cover the first 500 blocks, after which coinstake
   outputs mature on a rolling basis.
4. The genesis transaction is **indexed** (`TxIndex` skipped it; staking finds
   kernels through the index), **retrievable** (`getrawtransaction`'s genesis
   exception removed) and **counted** by `coinstatsindex`, which now treats
   `GetBlockSubsidy(0)` as the premine rather than an unspendable subsidy.
5. `nLastPOWBlock = 0` on mainnet and testnet: proof of work is rejected from
   block 1.
6. The premine is exact: `chainparams.cpp` splits `nPremineTotal` into outputs
   and `fic_genesis_tests` checks the total, count, values and scripts.

**Consequence for the key ceremony:** staking kernels must be single-key
outputs (P2PK, P2PKH, P2WPKH, P2TR). The premine cannot go straight into a
multisig cold wallet and still bootstrap the chain. `TODO-HUMAN`.

Checked and clear: `MAX_MONEY` is `int64_max` in this tree, so large genesis
outputs pass `MoneyRange()`. `MAX_MONEY = int64_max` also removes upstream's
overflow headroom — inherited from CAC, flagged for the Phase 10 security review.

### Decision 2 — Strip the developer donation

**Decided:** remove it entirely.

It was already inert — wallet-side rather than consensus, opt-out-able, and
`vDevFundAddress` was empty on every network, so it never paid out — which made
removal a clean deletion. Removed: `-donatetodevfund`, the wallet member and
constants, `interfaces::Wallet::getDonationPercentage`,
`CChainParams::GetDevFundAddress`/`GetDevRewardScript` and `vDevFundAddress`,
the donation output in `CreateCoinStake`, the Options dialog spin box and
settings migration, and the Overview page's "Donations" row.

### Decision 3 — Drop the issuer and DEX components

**Decided:** `base-issuer/`, `bnb-issuer/`, `stellar-issuer/` and
`checkout-widget/` are not carried into FIC.

CAC has live wrapped-token listings on BNB Chain and Base. None appears in the
FIC target layout, and a wrapped-token DEX listing raises questions that belong
with a Shariah advisory review rather than an engineering rebrand.

---

## Phase 1 — Core rebrand, chain parameters, fixed reward

*2026-09-13*

### Commits

| Commit | |
|---|---|
| `3df79ad` | Import `codexacoin-core` @ `50b1dce` verbatim |
| `604a308` | Fixed per-block reward, genesis-output premine, donation removed, FIC chain parameters, tests, docs |
| `348fd90` | Restore executable file modes lost when importing on Windows |
| `8f02b82` | Stop listing minisketch's missing test program in `make check` |
| `0dcab52` | Replace CAC artwork with the FIC brand kit |
| `f014d64` | Track the Makefile wrappers the import dropped |
| `57e2fba` | Rebrand CodexaCoin → FirstIslamicCoin |
| `548b370` | Fix a compile error in the genesis placeholder guard |
| `4a15a70` | Move the placeholder guard out of the path unit tests use; fix `TestChain100Setup`'s clock and pinned hash; fix `rpcnestedtests` |
| `6df748f` | Test helpers mine blocks this chain accepts (merkle root, scrypt proof of work) |
| `5a998ce` | Lift regtest's proof-of-work window in `TestChain100Setup` |
| `1268e21` | Test framework: re-encode hardcoded regtest addresses for `rfic` |
| `d65c608` | `validation_flush_tests`: flush genesis premine coins first |
| `080be2b` | Qt tests: record the real tip height for test wallets |
| `cb8d443` | `feature_init`: aim the `blk*.dat` perturbation past FIC's genesis block |
| `56c5a11` | Qt tests: derive the expected transaction count from the fixture |
| `8b60f2a` | **GUI: accept amounts of 10 billion FIC and more** |
| `76af7fd` | Label amounts and fee rates FIC in RPC, not BTC |
| `e7f2b25` | Use `CURRENCY_UNIT` in the `send` RPC's help examples |

### The fixed reward

- `Consensus::Params` gains `nFixedStakeReward` (10 FIC on every network),
  `nRewardHalvingInterval` (0 — disabled on every network) and
  `StakeReward(nHeight)`, which applies halving when enabled.
- `GetProofOfStakeReward(nHeight, nFees, params)` returns the fixed reward plus
  fees. It deliberately takes nothing about the stake.
- `ConnectBlock()` requires a coinstake to mint **exactly** that amount,
  through `IsValidCoinstakeReward()`. CAC only capped it from above.
- `CreateCoinStake()` builds exactly that amount.
- Removed from CAC: `ComputeCoinAgeReward`, `GetCoinstakeMaxReward`,
  `nStakeRewardAnnualBP`, `nStakeRewardAgeCapSeconds`, `SECONDS_PER_YEAR`, the
  wallet's origin-time lookup, the 60-day cap and the 128-bit overflow handling.
- `GetProofOfStakeSubsidy()`'s hardcoded 1.5-coin placeholder is gone;
  `GetBlockSubsidy()` now reports the real reward, so `getblockstats` and
  `coinstatsindex` are correct again.
- Kernel weight needed no change — already amount-only.
- The Overview page's "Est. monthly reward" percentage projection is replaced by
  "Block reward: 10.00000000 FIC + fees".

### Upstream bug fixed: fees counted twice

`ConnectBlock()` added each transaction's fee once from `CheckTxInputs` and again
as value-in minus value-out, so a block could claim up to double its fees. Fees
are now counted once; `fic_reward_tests` covers the double claim being rejected.

### Chain parameters

| | Mainnet | Testnet | Regtest |
|---|---|---|---|
| Magic | `F1 1C 51 A3` | `F1 1C 54 B3` | `F1 1C 52 C3` |
| P2P / RPC / onion port | 19770 / 19771 / 19773 | 29770 / 29771 / 29773 | 39770 / 39771 / 39773 |
| P2PKH / P2SH / WIF | 36 / 28 / 164 | 111 / 196 / 239 | 111 / 196 / 239 |
| xpub / xprv | `0488B21E` / `0488ADE4` | `043587CF` / `04358394` | same as testnet |
| Bech32 HRP | `fic` | `tfic` | `rfic` |
| Maturity | 500 | 50 | 10 |
| Spacing | 64 s | 64 s | **1 s** (stake timestamp mask 0) |
| `nLastPOWBlock` | 0 | 0 | 500, `-lastpowblock` to override |
| Checkpoints | genesis only | genesis only | genesis only |
| DNS seeds | `seed{1,2,3}.firstislamiccoin.com` (not yet live) | none yet | — |

Signet (not planned for launch) uses port 49770 and reuses the testnet genesis.
BIP44 coin type 9770 (descriptor wallets derive `m/…/9770h`); not yet registered
with SLIP-0044. Genesis values are in [`genesis.md`](genesis.md).

### Choices made without a separate decision

- **Minimum stake age is a confirmation depth.** CAC has no timestamp-based
  `nStakeMinAge`, so the prompt's 8 h / 1 h / 0 map onto maturity: 500 blocks
  (≈ 8.9 h), 50 blocks (≈ 53 min) and 10 blocks (regtest cannot use 0).
- **Genesis phrase kept verbatim**, em dash included. It fits, at 99 of 100
  scriptSig bytes; the C++ source spells the dash as UTF-8 escapes.
- **Regtest keeps a PoW window** (500 blocks at 28,000,000 each, as in CAC)
  because the inherited functional-test harness mines on demand. FIC's premine
  and reward tests run with `-lastpowblock=0`, which reproduces mainnet.
- **Mainnet genesis is a placeholder.** It pays BIP-341's NUMS point, whose
  private key nobody knows; the node refuses to start mainnet while
  `m_genesis_premine_placeholder` is set. Testnet's key is in
  `secrets/testnet-genesis-key.txt` (git-ignored); regtest's is public by design.
- **Per-file copyright headers** reading "The CodexaCoin developers" now read
  "The FirstIslamicCoin developers", as the acceptance grep requires. `COPYING`
  keeps the CodexaCoin notice verbatim and adds a FirstIslamicCoin line, which is
  what the MIT licence requires to be preserved.
- **RPC's `CURRENCY_UNIT` is now `"FIC"`** (CAC had left Bitcoin's `"BTC"`). It
  only labels fee rates and amounts in RPC help, errors and `-getinfo`; no
  parsing depends on it. The five test assertions on that text
  (`amount_tests`, `interface_bitcoin_cli.py`, `rpc_psbt.py`,
  `wallet_fundrawtransaction.py`) follow it, and the `send` RPC's help examples,
  which spelled "BTC" out beside `CURRENCY_ATOM`, now use it too. Inherited comments that still say
  "BTC" in test prose were left alone. `CURRENCY_ATOM` stays `"sat"`, because
  `sat/vB` is also an accepted RPC fee-rate unit.

### Genesis tooling

`contrib/genesis/generate_genesis.py` replaces CAC's C++ `generate_genesis.cpp`.
It needs no build, mines in parallel, and runs `--self-test` first: rebuilding
CAC's three live genesis blocks and Blackcoin's mainnet genesis from their
published parameters. That self-test found that CAC's `CreateGenesisBlock()`
built a P2PK output script and **never assigned it** — CAC's genesis output has
an empty script. Harmless there (the output was unspendable anyway); noted
because it would have silently broken any regeneration that trusted the code
as written.

### Rebrand

Case-preserving rename across 238 files, 13 paths renamed (init scripts, man
pages, example config, config generator). Ticker `CAC` → `FIC` in reviewed
ticker contexts. GUI units are FIC, mFIC, µFIC and **fils** (CAC still showed
Blackcoin's "mBLK"/"blits" and Bitcoin's "Satoshi"). Comments contrasting FIC
with its origin say "upstream CAC" — a blind rename had turned eleven of them
into false statements about FIC, and they were corrected before committing.
`grep -rni codexa` over `firstislamiccoin-core/` matches only `COPYING`.

The core `README.md` is rewritten for FIC; `CHANGELOG.md` points here and to the
archived upstream history.

### Artwork

App icons (PNG, multi-size ICO, ICNS; testnet icon hue-shifted as Qt's
`NetworkStyle` does at runtime), Linux PNG and XPM pixmaps, NSIS installer
bitmaps at their existing dimensions, README logo and branding sources, all
from `firstislamiccoin-brand/`. File names are unchanged, so no build or
installer script needed editing.

### Defects found in the inherited tree

| Defect | Effect in CAC | Fixed |
|---|---|---|
| Test framework used **Bitcoin's P2P magic bytes** | Every test opening a P2P connection timed out after 60 s | yes |
| Test framework used Bitcoin's bech32 HRPs | segwit address helpers produced foreign addresses | yes |
| `minisketch/src/test.cpp` missing but listed in `make check` | `make check` failed before running a single unit test | yes |
| Fees counted twice in `ConnectBlock()` | blocks could claim double fees | yes |
| Genesis output script never assigned | none (unspendable output) | superseded |
| `TestChain100Setup` mocked the clock to 2020, before the 2026 genesis | every block the fixture built was rejected `time-too-new` | yes |
| `TestChain100Setup` asserted a tip hash that was **Blackcoin's testnet genesis** | would abort even with valid blocks | yes (asserts height) |
| `TestChain100Setup::CreateBlock` never set the merkle root, and solved proof of work against `GetHash()` (SHA256d for version-7 blocks) instead of scrypt `GetPoWHash()` | the fixture never produced a valid block; no test built on it could pass | yes |
| Same `GetHash()` proof-of-work mistake in `util/mining.cpp`, `blockencodings_tests`, `blockfilter_index_tests` | blocks failed `CheckBlock` at random | yes |
| Fixture chains end exactly at regtest's last PoW block (500) | tests mining more blocks hit `reject-pow` | yes (`-lastpowblock` in the fixture) |
| `rpcnestedtests` expected Blackcoin's mainnet genesis coinbase | Qt test failure | yes |
| Qt `wallettests` hardcoded the 100+5-block fixture (last-processed height 105, 105/107 transactions) after CAC grew the fixture to 500+5 | coinbases at negative depth tripped a wallet assertion; row counts wrong | yes (derived from the chain) |
| Test framework `address.py` hardcoded Bitcoin `bcrt1…` P2WSH/P2TR OP_TRUE constants | once the framework spoke FIC's `rfic` HRP, every MiniWallet test failed at setup | yes (re-encoded; descriptor checksum derived) |
| **GUI `BitcoinUnits::parse` refused amounts over 18 digits** | fine for 21 million BTC, but every FIC amount of 10 billion or more is 19 digits in fils — the premine holder could not enter their own balance | **yes — a real wallet bug for FIC** |

Two inherited tests broke because of FIC's own genesis design and were adapted
without weakening them:

- `validation_flush_tests` assumed an empty coins cache at startup; FIC's 1,000
  genesis outputs are in it. The test now flushes them to the database first.
- `feature_init.py` corrupts bytes 150–350 of `blk*.dat` expecting to hit a block
  that `-checkblocks` verifies; with FIC's ~34 KB genesis block that window only
  touched genesis. The window is now offset by the genesis block's measured size.

Two tests are **clock-dependent** rather than broken: `net_tests` and
`feature_maxtipage.py` assume the regtest genesis block is more than 24 hours
old. A new block must be later than genesis, so on a younger genesis the tip is
never old enough to keep a node in initial block download, and both tests'
"still in IBD" assertions fail (confirmed at `feature_maxtipage.py:39` with the
genesis 22 hours old). FIC's regtest genesis is dated 2026-09-12 00:00 UTC, so
both fail on runs before 2026-09-13 00:00 UTC and should pass after. CAC's July
genesis never exposed this.

`headers_sync_chainwork_tests` deliberately still solves headers against
`GetHash()`: the headers-presync check it exercises (`validation.cpp`) validates
headers against `GetHash()`, an inherited inconsistency with full-block
validation that is noted for the Phase 10 security review rather than changed
in consensus-adjacent P2P code here.

Baseline on unmodified CAC in the same container: **51 of 280** functional tests
passed (173 failed, 57 skipped). `make check` ran no unit tests at all; run one
suite per process, **79 of 119** unit suites passed.

### Defects in this phase's own import, found and fixed

- Importing through Git on Windows recorded every file as `100644`, so
  `autogen.sh` could not run. Modes restored from upstream's tree (`348fd90`).
- `git add` honoured upstream's `.gitignore` and skipped three `Makefile`
  wrappers that upstream tracks anyway, breaking `autogen.sh` (`f014d64`).
- The blind rename turned eleven comments contrasting FIC with its upstream
  into false statements about FIC; corrected before the rebrand was committed.
- The mainnet placeholder guard first called a function that does not exist
  in this Core version (`548b370`), then sat in `AppInitParameterInteraction`,
  which unit tests and Qt's option tests call on mainnet, so it cut their
  parameter setup short. It now lives in `AppInitSanityChecks`, which only
  `firstislamiccoind` and the GUI run (`4a15a70`).

### Tests

| | |
|---|---|
| **New** `src/test/fic_reward_tests.cpp` | fixed reward on every network; exactly reward + fees (±1 fil and double fees rejected); constant across stake amounts from 1 fil to the whole premine; constant across coin ages from maturity to four years; halving path when enabled on regtest |
| **New** `src/test/fic_genesis_tests.cpp` | premine total, output count and scripts on every network; genesis phrase and scriptSig limit; no PoW after genesis; genesis maturity exemption; mainnet placeholder; magic, ports, prefixes, HRPs, maturity, spacing and checkpoints against the spec |
| **Updated** `src/test/pos_tests.cpp` | kernel-independence test kept; coin-age reward cases removed with the formula |
| **New** `feature_fic_genesis_premine.py` | premine in UTXO set, genesis tx retrievable, PoW rejected, premine spendable before block 1, chain staked from genesis past the maturity window, supply exact |
| **New** `feature_fic_fixed_reward.py` | two nodes, stakes differing by orders of magnitude, fee traffic; every block mints 10 + fees; supply exact |
| **Updated** `feature_pos_reorg.py` | supply after reorg asserted exactly |
| **Replaced** `feature_premine.py`, `feature_coinage_reward.py` | tested removed CAC behaviour; superseded by the two tests above |

### Verification

Clean build of `e7f2b25` from `git archive` in a Debian bookworm container
(autotools, Qt 5, SQLite wallet, no BDB), 2026-09-12. Compared against the same
build of unmodified CAC `50b1dce` in the same container.

| Check | Result |
|---|---|
| `make` | clean, exit 0 — `firstislamiccoind`, `-cli`, `-qt`, `test_firstislamiccoin` |
| `fic_reward_tests`, `fic_genesis_tests`, `pos_tests` | **all pass** |
| Qt tests (`test_firstislamiccoin-qt`, offscreen) | **21 of 21 pass** across 6 test classes |
| Unit suites, one process each | **89 of 121 pass** (CAC: 79 of 119). 9 suites fixed that failed in CAC; 31 fail in both; 1 regression, `net_tests`, clock-dependent (see above) |
| FIC functional tests | **all 3 pass** (`feature_fic_genesis_premine`, `feature_fic_fixed_reward`, `feature_pos_reorg`) |
| Full functional suite | **69 pass**, 155 fail, 57 skip (CAC: 51 / 173 / 57). 19 fixed that failed in CAC; 154 fail in both; 1 regression, `feature_maxtipage.py`, clock-dependent (see above) |
| Acceptance script, real regtest node | **PASS** — genesis `360afc3e…d4e712` reported; 14,000,000,000 FIC premine imported and spendable; `generatetoaddress` rejected with `reject-pow`; 3 proof-of-stake blocks staked from genesis outputs; `getstakinginfo` works; supply audit exact at 14,000,000,030 |
| `git grep -il codexa` in `firstislamiccoin-core/` | `COPYING` only |

Unit suites fixed relative to CAC: `argsman`, `bip32`, `blockencodings`,
`blockfilter_index`, `coinstatsindex`, `miniminer`, `psbt_wallet`,
`txvalidation`, `walletload`. Functional tests fixed: `feature_addrman`,
`feature_anchors`, `feature_minchainwork`, `p2p_add_connections`,
`p2p_addrv2_relay`, `p2p_dns_seeds`, `p2p_getaddr_caching`, `p2p_getdata`,
`p2p_invalid_locator`, `p2p_leak`, `p2p_message_capture`,
`p2p_nobloomfilter_messages`, `p2p_ping`, `p2p_sendtxrcncl`, `p2p_timeouts`,
`p2p_v2_transport`, `rpc_getdescriptorinfo`, `rpc_invalidateblock`,
`rpc_signrawtransactionwithkey` — mostly the P2P magic-bytes fix.

**The failures common to both trees are inherited, not introduced.** They are
Bitcoin Core tests that CAC carried over without adapting to proof of stake,
scrypt proof of work, its own chain parameters or its 500-block regtest
fixture. Phase 2's "all functional tests green" requires working through them;
No test that passed on CAC fails on FIC apart from the clock-dependent pair;
the shared failures were not individually re-diagnosed, so some may now fail
for a different reason than they did on CAC.

Clock-dependent tests re-run once the regtest genesis is more than 24 hours old: *pending*.

---

## Prompt items that need no work

**Kernel stake weight is already amount-only.** `pos.cpp` computes
`bnWeight = arith_uint256(nValueIn)` with no age term. FIC's "stake weight
proportional to coin amount only" is the existing behaviour.

**`nMinimumChainWork` and `defaultAssumeValid` were already zeroed.** Only
`checkpointData` held real values — 500 hashes from CAC's live mainnet — and
those are removed.

---

## Open `TODO-HUMAN`

| # | Item | Blocks |
|---|---|---|
| 1 | **Genesis key ceremony.** Choose the mainnet premine outputs — enough single-key outputs to bootstrap staking — then re-mine mainnet genesis and clear the placeholder flag | Mainnet |
| 2 | **P2CS does not exist in CAC.** The prompt assumes it is reusable in Phases 3.4, 5.3, 6.2, 7.2 and 8.2; it is an unbuilt consensus feature. Build it, or ship custodial-only and defer? | Phase 3 |
| 3 | The first staker at testnet and mainnet launch must run with `-maxtipage` longer than the genesis block's age, or it will not leave initial block download | Phase 2 |
| 4 | Register BIP44 coin type 9770 via SLIP-0044 | Phase 10 |
| 5 | Shariah advisory board review. No endorsement, scholar name or certification to be written anywhere until real | Phase 9 |
| 6 | DNS seeders for `seed{1,2,3}.firstislamiccoin.com`; testnet seeds | Phase 6 |
| 7 | `generate.py` in the brand kit hardcodes `/home/claude/fic-brand` and Linux font paths | — |
| 8 | Verify ElectrumX full block indexing end-to-end — never done upstream | Phase 4 |
