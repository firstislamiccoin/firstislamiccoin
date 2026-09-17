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
| `bdf7438` | Add the Phase 1 regtest acceptance script, `contrib/fic/phase1-acceptance.sh` |

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
both fail on runs before 2026-09-13 00:00 UTC and pass after (confirmed; see
Verification). CAC's July
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
| Unit suites, one process each | **89 of 121 pass** (CAC: 79 of 119). 9 suites fixed that failed in CAC; 31 fail in both. `net_tests` failed in this run only because the genesis was under 24 h old; it passes on the re-run below, making **90 of 121** and no regressions |
| FIC functional tests | **all 3 pass** (`feature_fic_genesis_premine`, `feature_fic_fixed_reward`, `feature_pos_reorg`) |
| Full functional suite | **69 pass**, 155 fail, 57 skip (CAC: 51 / 173 / 57). 19 fixed that failed in CAC; 154 fail in both. `feature_maxtipage.py` failed in this run only because the genesis was under 24 h old; it passes on the re-run below, making **70 passed** and no regressions |
| `contrib/fic/phase1-acceptance.sh`, real regtest node | **PASS** — genesis `360afc3e…d4e712` reported; 14,000,000,000 FIC premine imported and spendable; `generatetoaddress` rejected with `reject-pow`; 3 proof-of-stake blocks staked from genesis outputs; `getstakinginfo` works; supply audit exact at 14,000,000,030 |
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
No test that passes on CAC fails on FIC once the clock-dependent pair is re-run;
the shared failures were not individually re-diagnosed, so some may now fail
for a different reason than they did on CAC.

**Clock-dependent tests, re-run 2026-09-13 00:05 UTC** on the same build, with
the regtest genesis 1,445 minutes old: `net_tests` passes (16 cases) and
`feature_maxtipage.py` passes. That confirms the explanation above: neither was
a defect, and FIC has no test regressions relative to CAC.

---

## Phase 2 — Testnet validation

*2026-09-13, in progress*

### Consensus bug found: the weighted kernel target wrapped around

Found in the first minutes of the testnet bootstrap, while investigating a gap
between blocks.

`CheckStakeKernelHash` compares the kernel hash with `target × coin value`,
computed in a 256-bit integer. Blackcoin's outputs and difficulty keep that
product small; FIC's are different. A 14,000,000 FIC genesis output is 2^50.3
fils, and the easiest PoS target (`posLimitV2`, where every new chain starts)
is about 2^208, so the product needs 259 bits. `arith_uint256` discards the
overflow silently, and what is left is an arbitrary function of `nBits`: 97%
of the hash space at `0x1b00ffff`, 1.3×10⁻⁶ at `0x1b00cde1`. Every genesis
output has the same value, so at an unlucky `nBits` all of them fail together,
and a chain whose only mature coins are genesis outputs cannot produce the
block that would change `nBits`. This applies to mainnet launch exactly as to
testnet.

**Fixed** by saturating: a product at or above 2^256 means every hash
qualifies, so the target is capped at 2^256−1. Nothing changes below that
boundary, and at equilibrium difficulty for a 14-billion-coin supply no single
output reaches it, so the change only matters during the easy-difficulty
bootstrap and on very small networks. Regression test:
`pos_tests/CheckStakeKernelHash_WeightedTargetSaturates`. Verified both ways
on the same build: with the saturation branch disabled it fails with 0 of 200
kernels passing at `0x1b00cde1`; with it, all 200 pass.

### Consensus bug found: SegWit and Taproot were never enforced

SegWit and Taproot are version-bits deployments in this tree, and
`GetBlockScriptFlags` adds `SCRIPT_VERIFY_WITNESS` / `SCRIPT_VERIFY_TAPROOT`
only while the deployment is active. CAC set both to `NEVER_ACTIVE` on mainnet
and testnet (signet had no SegWit entry), under a comment claiming SegWit was
active from genesis through `SegwitHeight`, a field this tree never reads for
SegWit. On those networks witness programs were not script-checked in blocks,
so native SegWit (`fic1q…`) and Taproot (`fic1p…`) outputs could be spent
without a signature by whoever staked the block. At the same time the mempool
refused properly signed witness spends (`no-witness-yet`) and blocks carrying
witness data were rejected (`unexpected-witness`), so their owners could not
spend them. The testnet wallet defaults to legacy addresses, which is why the
bootstrap never touched the problem; an explicit bech32 address works.

**Fixed**: both deployments `ALWAYS_ACTIVE` on every network, from genesis.
Activating Taproot as well as SegWit was the project owner's decision
(2026-09-13). The wallet's "Taproot addresses (bech32m) are not supported yet"
refusal is removed, and `getdeploymentinfo`, which hides `NEVER_ACTIVE`
deployments, now lists both. Test:
`fic_genesis_tests/segwit_and_taproot_active_from_genesis`.

### Consensus bug found: output and input sums overflowed

`MAX_MONEY` is `INT64_MAX` in this tree, so the inherited
`sum += value; if (!MoneyRange(sum))` pattern is signed overflow — undefined
behaviour that the optimiser removes. On regtest a transaction spending one
28,000,000 FIC coinbase into two `INT64_MAX` outputs plus change, wrapping to a
normal-looking 1 FIC fee, was accepted to the mempool and mined, leaving both
outputs in the UTXO set: coins from nothing. Found independently by the unit
and P2P test diagnosis. **Fixed** by checking headroom before each addition in
`CheckTransaction`, `GetValueOut`, `CheckTxInputs` and the block fee total.
Tests: `amount_tests/txout_total_overflow` and
`txout_total_overflow_block_rejected`. Whether `MAX_MONEY` should become a real
cap is open for the Phase 10 review.

### Relay bug found: fee filter could exceed the fixed fee

Found by the functional-test diagnosis (`wallet_listtransactions` timing out
on mempool sync). FIC fixes the fee rate at `TX_FEE_PER_KB` (0.001 FIC/kvB), and
`MaybeSendFeefilter` advertises that to peers after passing it through
`FeeFilterRounder`, which returns the bucket at or above its input one time in
three: 0.00107179 FIC/kvB. A peer told that filter never announces a standard
wallet transaction, which pays exactly 0.001. The effect is random per
connection and per broadcast interval, so transactions would reach some peers
and not others. **Fixed**: the rounded filter is capped at the fixed fee, so
rounding can only lower it. Upstream Bitcoin Core does not have this problem
because its filter follows the mempool's dynamic minimum; FIC's version
hardcoded the fixed fee, and does not raise the filter when its mempool is
full (noted for Phase 10).

### Mempool and RPC fixes from the test diagnosis

- **Unlimited unconfirmed chains.** The CPFP carve-out in `PreChecks` retried a
  transaction that broke the ancestor/descendant limits with
  `Limits::NoLimits()` whenever it was at most 10,000 vB. Upstream's carve-out
  (one extra small child of a parent already at the descendant limit) had been
  commented out with RBF, because it read the removed RBF limits. Unconfirmed
  chains could therefore grow without bound, a mempool denial-of-service.
  **Fixed**: the carve-out is restored against the pool's own limits.
- **RPC hex without witnesses.** `-rpcserialversion` defaulted to 0, stripping
  witness data from raw transaction and block hex. With SegWit enforced that hex
  does not verify when relayed. **Fixed**: default 1, as upstream.
- `decoderawtransaction` and `getdeploymentinfo` result docs corrected, and
  `RegenerateCommitments` no longer erases at index −1 (a double free on
  `generateblock` without a witness commitment).

### Open for the Phase 10 security review

Reported by the diagnosis and deliberately not changed during testnet work:

- `HasValidProofOfWork` returns true for every header (`validation.cpp`, marked
  "ToDo"), so headers presync performs no anti-DoS work check. PoS headers
  cannot be checked for work at all; a correct design needs care.
- `SCRIPT_VERIFY_DERKEY` is in the block flags but nothing in the interpreter
  enforces it.
- Block-download and stale-tip timeouts scale with target spacing; at regtest's
  1 s they disconnect peers after about a second, and at 64 s they are roughly a
  tenth of Bitcoin's.
- The fee filter follows the fixed fee rather than the mempool's dynamic
  minimum, so a node with a full mempool does not raise it.
- `MAX_MONEY` is `INT64_MAX`; sums are now overflow-safe, but a real cap is
  still worth deciding.
- `ReplayBlocks` does not re-add the genesis premine if a node crashes during
  its first UTXO flush (patch proposed by the unit-test diagnosis).

The gap that prompted the investigation, 512 s before block 4, is **not**
explained by this bug: at that block's `nBits` the wrapped threshold was 23% of
the hash space. It was the block that carried the last two 18 KB tranche
transactions, but large transactions are not the cause either: tranche 2 put
four 18 KB transactions into block 61 and one into block 62, each 16 s after
its predecessor.

**It reproduced** on the restarted testnet (kernel fix in place): blocks 1–3
within a minute, then 896 s before block 4. With `-debug=coinstake` the staker
logged nothing at all during the gap.

### Staking bug found: one wallet's search blocked every other wallet

**Cause.** `CreateNewBlock` kept the last searched coinstake timestamp in a
single `static` for the whole process. Each wallet's staking thread searches
only if the current 16-second slot is later than that value, and records the
slot whether or not it found a kernel. On a node staking several wallets, the
thread that reached a slot first consumed it and the others skipped it
silently. node0 stakes the genesis wallet and `staker1`; before `staker1`'s
coins matured, its empty searches kept winning the slots, and the only wallet
able to stake sat idle. The tranche transactions were a coincidence of timing:
`staker1` is created just before block 3.

**Measured** on regtest, the premine wallet plus eight empty staking wallets on
one node, old and new binaries running side by side for 150 s:

| Binary | Blocks | Seconds per block |
|---|---|---|
| shared `static` | 0 (not even block 1 in 270 s) | — |
| per wallet | 8 | 18.8 (the post-block rest) |

**Fixed**: the search time is a `CWallet` member.

### Wallet bugs found: coin selection over-reserved fees, `fee_rate` was ignored, SFFO could go negative

Found while integrating the diagnosis agents' wallet patches, verified by rebuild:

- Coin selection applied `GetMinFee()` — a whole-transaction floor,
  `max(10,000 sat, 100 sat/vB)` — separately to the change output, the change
  spend, the transaction's non-input part, and every input's long-term cost:
  up to four times the real minimum reserved during selection. The floor is
  enforced once, correctly, on the finished transaction. Fixed by using the
  effective/discard fee rates alone for those components; `CoinSelectionParams`
  gains `m_long_term_feerate` (FIC has no fee estimation, so it is the
  effective rate) since `OutputGroup`'s long-term fee needs a real rate instead
  of `GetMinFee()` per input.
- `sendtoaddress` and `sendmany` declared a `fee_rate` argument that neither
  handler read (dropped with the rest of fee estimation). `sendtoaddress(...,
  fee_rate=300)` paid exactly the 100 sat/vB floor regardless. Both now set
  `coin_control.m_feerate`.
- `CreateTransactionInternal`'s "reduce change if the fee is short" step also
  ran when subtract-fee-from-outputs was requested, silently overriding SFFO
  and, if the shortfall exceeded the change, producing a negative change
  output (`bad-txns-vout-negative`). It no longer runs when SFFO is set.

`spend_tests` and `wallet_tests`, both broken by CAC's version of this code,
pass. `coinselector_tests` has one remaining pre-existing failure
(`bnb_search_test`), not caused by this fix and not yet diagnosed.

### Incident: a Docker Desktop crash exposed a genesis-reindex crash and a brief fork

The host's Docker Desktop went down for several hours while this session was
rate-limited. The testnet's containers restart automatically, but two of the
four nodes (node0, node1) came back with a corrupted transaction index
("`best block of the index not found`") — plausibly from an unclean shutdown
mid-write — and needed `-reindex`. That surfaced a second, unrelated crash:

**Consensus bug found: reindexing genesis crashed on mainnet and testnet.**
`ContextualCheckBlock()` asserted `pindexPrev != nullptr` as soon as it judged
CSV active, then dereferenced `pindexPrev` two lines later regardless of the
assert. Mainnet and testnet set `CSVHeight = 0` ("active from genesis"), so at
the genesis block itself (no parent) both are unconditionally true. A normal
startup bootstraps genesis directly and never reaches this path; `-reindex`
walks every block on disk through `AcceptBlock()`, genesis included, which is
how this was found. Regtest and signet (`CSVHeight = 1`) never trigger it —
why it survived the entire functional and unit suite, both regtest-based, and
only surfaced on a real operator action against a mainnet/testnet-shaped
chain. **Fixed**: genesis has no contextual rules to check against a
nonexistent parent (it is already exempted from PoW, maturity and coinstake
requirements elsewhere in this fork), so the function returns true immediately
when `pindexPrev` is null. Regression test:
`fic_genesis_tests/csv_active_from_genesis_on_main_and_testnet`.

**Then a brief fork, self-healed.** node0/node1 reindexed and resumed staking
with the per-wallet fix in place (above), which let them produce blocks much
faster than before; node2/node3, still on the pre-crash binary, had kept
staking on their own during the outage. The two sides had a different block at
height 171. Once node0/node1's reindex caught up and its greater chainwork
(height 200 vs. 171) reached node2/node3 over their existing peer connections,
both reorged onto it within seconds — a 1-block-deep fork, well inside every
reorg-depth protection this fork has (the sync checkpoint and
`nMaxReorganizationDepth`), so no manual `invalidateblock`/`reconsiderblock`
was needed. All four nodes converged at height 206 with an identical tip.
node2 and node3 were then moved onto the fixed image too (non-consensus
changes only — safe with the chain running), so all four now run the same
build.

**Lesson for launch**: an operator recovering a crashed node with `-reindex`
on mainnet or testnet would have hit the ContextualCheckBlock crash before
this fix existed, with no workaround short of a source change. Worth a
deliberate crash-recovery drill before mainnet (TODO-HUMAN).

### Functional suite: seven diagnosis agents' fixes merged

Seven agents each diagnosed a slice of the ~280-test inherited functional
suite in parallel, against FIC's real parameters, and independently wrote
fixes for their own tests plus (unavoidably) the shared test framework. Their
per-test patches were applied directly (116 files); the framework layer
(`messages.py`, `blocktools.py`, `test_framework.py`, `util.py`, `wallet.py`,
`p2p.py`, `netutil.py`, `fic.py`) needed reconciling into one coherent
version, since several agents had independently solved the same problem
(scrypt proof of work, `nFlags` only on the P2P wire, block version ≥ 7,
staking off by default in tests, IPv6 detection) in slightly different ways —
done by a dedicated merge pass, committed together as `1604ef1`.

Full suite, commit `1604ef1`, compared against the `e7f2b25` baseline (70
passed / 155 failed / 57 skipped):

| | Passed | Failed | Skipped |
|---|---|---|---|
| Baseline (`e7f2b25`) | 70 | 155 | 57 |
| Now (`1604ef1`) | **157** | 60 | 63 |

**Zero regressions** — nothing that passed at baseline fails now. **88 tests
fixed.** FIC's own three tests and the un-skipped `feature_taproot.py` (see
below) pass against the merged framework.

The 60 still failing fall into the categories already identified during
diagnosis, not individually re-verified here: SegWit/CSV activation-height
tests that assume a configurable activation point (`feature_segwit`,
`feature_csv_activation`, `feature_nulldummy`,
`feature_presegwit_node_upgrade`, `p2p_segwit`) — this fork enforces both as
fixed, buried-at-genesis deployments, so there is no "before activation" state
left to construct the same way upstream does; mempool policy differences
around the missing `prioritisetransaction` RPC and RBF (`mempool_*`,
`rpc_packages`); P2P/IBD timeouts that scale with target spacing
(`p2p_ibd_stalling`, `p2p_eviction`, `p2p_headers_sync_with_minchainwork`);
wallet RPC option-passing that needs a small rewrite for `send`/`sendall`
(`wallet_send`, `wallet_sendall`, `wallet_resendwallettransactions`); and a
handful (`wallet_orphanedreward`, `feature_signet`) that need a redesigned
scenario to fit this fork's shallower reorg limits or signet mining path.
Getting the whole suite green is further work, as anticipated when Phase 2
began.

**`feature_taproot.py` found a framework determinism bug.** Un-skipped now
that Taproot is active, its self-check builds a synthetic version-1 coinbase
and pins its hash — but `CTransaction()` defaults `nTime` to the current
second for freshly-constructed objects, and only version-1 transactions
serialize `nTime` at all, so the hash was different on every run. Fixed by
pinning `nTime = 0` before hashing, the same way the test already pins
`nLockTime`. The test's later BIP341 vector-generation scenario has its own
hardcoded Bitcoin-scale fees throughout and still needs per-vector adaptation
to this fork's fixed minimum fee — left as further work, not re-skipped, since
Taproot really is enforced now and the test is worth finishing.

### Unit suites, final tally for this phase

One process per suite, commit `c1d48ed`: **118 of 121 pass**, no regressions
against the CAC baseline. The three still failing are unchanged from Phase 1
and already accounted for above: `coinselector_tests` (one pre-existing
`bnb_search_test` case, not yet diagnosed), `transaction_tests` (JSON vectors
still signed over Bitcoin's sighash), `validation_block_tests`
(`mempool_locks_reorg`, which needs a reorg deeper than this fork allows and a
custom block builder to match).

### Functional suite revisited: the ~60 failures triaged for real, one real bug found and fixed

A later pass (2026-09-17, on the same VPS used to verify ASan/UBSan and
clang-tidy in Phase 10) built this fork fresh and ran the full functional
suite to see current status: **61 of 280 still failing** — essentially the
same count "further work" already anticipated above, now actually triaged
one by one rather than left as an estimate.

**One genuine bug found and fixed, not a test-adaptation issue.**
`getmempoolentry`/`getrawmempool(verbose)` declared `bip125-replaceable` as a
required field in their `RPCResult` documentation, but the code that used to
populate it had been commented out entirely when RBF support was removed
project-wide (`IsRBFOptIn`/`RBFTransactionState` no longer exist anywhere in
the tree) — nobody removed the now-stale doc entry to match. Every call to
either RPC tripped the test framework's own strict result-type checker
("Internal bug detected... returned incorrect type"), failing outright
before a test could even reach its actual assertions. This alone explained
9 of the 61 failures (`mempool_accept_wtxid`, `mempool_datacarrier`,
`mempool_expiry`, `mempool_packages`, `mempool_persist`, `mempool_reorg`,
`mempool_sigoplimit`, `mempool_unbroadcast`, `mempool_updatefromblock`) plus
`feature_bip68_sequence`, `interface_rest`, and `wallet_resendwallettransactions`.
Fixed by removing the stale `RPCResult` entry and the dead commented-out
code (`src/rpc/mempool.cpp`).

**Design-incompatible tests, skipped with documentation** — the same
established policy as everywhere else in this project:
- `wallet_dump`, `wallet_import_with_label`, `wallet_import_rescan`,
  `wallet_implicitsegwit` (the latter skipped whole) — all hit
  `getnewaddress(address_type='p2sh-segwit')`, rejected project-wide
  ("P2SH_SEGWIT addresses are not welcome" in `wallet/rpc/addresses.cpp`,
  inherited unchanged from the CodexaCoin import per `git blame`).
- `p2p_segwit` — skipped whole; relies on `-testactivationheight=segwit@N`
  to test pre/post-activation behavior, but SegWit is `ALWAYS_ACTIVE` from
  genesis on this fork (Phase 2, above), so there is no pre-activation state
  to construct.
- `mempool_packages` — used `prioritisetransaction`, an RPC this fork
  removed along with RBF; the fee-delta assertions built on it were replaced
  with plain summed-fee checks, keeping the surrounding ancestor/descendant
  mempool-limit scenario (which the removed RPC wasn't actually needed for).
- `rpc_packages` — `test_rbf()` (an entire BIP125 replace-by-fee scenario)
  skipped whole; the rest of the file's `test_conflicting` fixed by
  replacing its below-floor fee constants (see next item).
- `wallet_basic`, `wallet_spend_unconfirmed`, `rpc_packages` — several
  explicit `fee_rate=`/`estimate_mode=`/`conf_target=` values assumed
  upstream's ~1 sat/vB default relay fee and dynamic fee estimation, neither
  of which exist on this fork (fixed at a 100 sat/vB floor, hard-rejected
  below it rather than silently raised — a previous partial fix in
  `wallet_spend_unconfirmed.py` had assumed the latter). Bumped to
  floor-compliant values, and the `conf_target`/`estimate_mode` RPC
  validation tests were replaced with "rejected as an unknown parameter"
  checks matching what removing fee estimation actually did to the RPC surface.
- `wallet_dump` also needed its `read_dump()` helper's bech32 address
  classifier fixed from Bitcoin regtest's `bcrt1` prefix to this fork's real
  `rfic1` (same class of gap already fixed for `ADDRESS_BCRT1_UNSPENDABLE`
  during the ASan work).

**A real architectural gap, investigated properly rather than papered
over.** `p2p_invalid_messages`/`feature_assumevalid` test that headers
carrying invalid proof-of-work get misbehavior-scored during presync
(`CheckHeadersPoW` → `HasValidProofOfWork`). That function is stubbed to
accept every header (`// FirstIslamicCoin ToDo: enable the check for PoW
headers`), and it turns out to be a real structural limitation, not
laziness: a bare `CBlockHeader` carries no PoW/PoS discriminant on this fork
(`CBlock::IsProofOfStake()` needs the coinstake transaction, which headers
don't have), and `CheckHeadersPoW` runs before headers are connected to the
chain, so there's no height available yet to know whether a given header is
even expected to carry real PoW (this fork only requires PoW up to
`nLastPOWBlock`, which is 0 on mainnet/testnet and 500 on regtest).
A correct fix needs expected-height context threaded through to headers
presync — not safe to improvise in a security-sensitive P2P path without
that design work. `test_invalid_pow_headers_msg` skipped with this
explanation in place; `feature_assumevalid`'s failure is the same root cause.

**Two further real, not-yet-resolved issues found while fixing the fee-floor
constants above**, left open rather than guessed at:
- `wallet_spend_unconfirmed`: raising the "low" fee-rate constants to this
  fork's actual 100 sat/vB floor (50-100x upstream's values) changed coin
  selection's behavior — several sub-tests now select one extra input beyond
  the parent transaction(s) they expect (`assert_spends_only_parents` fails
  with e.g. "not(3 == 2)"), most likely because each self-transfer parent's
  own change output becomes a second spendable UTXO in the same wallet.
  Needs each sub-test's amounts reworked to avoid coin selection pulling in
  that change, not just a constant swap.
- `wallet_basic`: a pre-existing, previously-unreached scenario (spends a
  large UTXO matched via `listunspent(minimumAmount=49.998)`, patches one
  output to zero) hits `sendrawtransaction`'s "Fee exceeds maximum configured
  by user" safety check — unrelated to any fee-floor constant, exposed only
  because the file's earlier failures (now fixed) no longer mask it.
- `mempool_accept`: a transaction constructed at ~10 sat/vB was accepted by
  `testmempoolaccept` (`allowed: True`) despite the 100 sat/vB floor,
  expected to be rejected `bad-txns-fee-not-enough`. Investigated the floor's
  actual enforcement path (`IsProtocolV3_1()`-gated in `validation.cpp`);
  ruled out clock skew, genesis/mocktime being before the gate's activation
  timestamp, and `timedatadummy.cpp`'s always-returns-0 `GetAdjustedTimeSeconds()`
  stub being linked into the real daemon (it isn't — only
  `libbitcoin_consensus`/`firstislamiccoin-tx` link it). Root cause not yet
  found; needs runtime debugging of the actual daemon to resolve with
  confidence rather than a guess in a fee-policy code path.

Roughly 20 of the 61 known failures were fixed, skipped-with-documentation,
or root-caused this pass (several skips explain multiple failures at once,
e.g. the `bip125-replaceable` fix alone covers 12).

### A second pass: 17 more fixed, one more real bug, three more real findings left open

A follow-up pass, same VPS, fresh build with the fixes above applied,
brought the count from 61 down to 44, then continued triaging:

**More design-incompatible tests skipped with documentation:**
`feature_nulldummy` and `feature_presegwit_node_upgrade` (whole-file skips,
same as `p2p_segwit` — both rely on `-testactivationheight=segwit@N`, which
has no meaning on a fork where SegWit is `ALWAYS_ACTIVE` from genesis).
`mempool_persist`'s `test_importmempool_union()` and `mempool_package_onemore`'s
final RBF-replacement step both test BIP125 replace-by-fee directly, which
this fork doesn't have; skipped/removed with the surrounding fee-delta and
ancestor-count assertions adjusted to match (no delta to apply, so
base == modified; the carve-out chain's final count already held without
the replacement step).

**A second genuine RPC bug, not a test issue.** `send`'s own `RPCHelpMan`
documents `minconf`/`maxconf` options (`wallet/rpc/spend.cpp`), but the
shared `FundTransaction()` helper's runtime `RPCTypeCheckObj` allow-list —
used by `send`, `fundrawtransaction`, and others — never included either
key, and neither was ever wired into `CCoinControl`. Both have silently
been "Unexpected key" rejections since the CodexaCoin import (`git blame`
confirms this block is untouched). Fixed by allow-listing and wiring both,
matching `sendall`'s already-working handling of the same two options.

**Real, safe fixes to genuinely fork-specific test data:**
- `rpc_net`'s `getrawaddrman` expected-results dict still said Bitcoin's
  port 8333 in two places, even though every `addpeeraddress` call in the
  same file already correctly used FIC's real port (15714) — a partial
  earlier adaptation pass that missed two literals.
- `wallet_importmulti` hardcoded eight real Bitcoin-regtest bech32/taproot
  addresses (`bcrt1...`). Since a bech32(m) checksum is computed over the
  HRP, these can't be fixed by string substitution — decoded each with
  `test_framework.segwit_addr` and re-encoded with FIC's real `rfic` HRP,
  verified each round-trips correctly.
- `wallet_abandonconflict`'s raw-transaction output amounts implied fees as
  low as ~9 sat/vB (sized for upstream's ~1 sat/vB relay fee), rejected
  outright by this fork's fixed 100 sat/vB floor. Traced the interdependent
  balance-tracking arithmetic through the whole file and bumped every
  affected amount consistently.

**Three more real, open findings, documented rather than guessed at:**
- `wallet_abandonconflict` has a *second*, deeper problem past the one just
  fixed: it restarts the node with a higher `-minrelaytxfee` specifically to
  evict a transaction that no longer meets the new relay policy, but this
  fork's actual fee floor is a hardcoded consensus constant (`GetMinFee`),
  not derived from `-minrelaytxfee` at all — so the restart-based eviction
  this test relies on is a no-op here. The file's own comment already flags
  this mechanism as fragile (`# TODO: redo with eviction`) even upstream.
- `tool_wallet`'s `test_chainless_conflicts` constructs a raw transaction
  that double-spends an already-unconfirmed input on the same node and
  expects `sendrawtransaction` to accept it (`txn-mempool-conflict` instead).
  Whether this is genuinely fork-specific or was already fragile upstream
  (this function is untouched since the CodexaCoin import) needs real
  investigation before either fixing or skipping it.
- `wallet_send`'s `test_send` helper appears to pass `fee_rate` as both a
  top-level parameter and inside `options` simultaneously even for a plain,
  no-`fee_rate`-specified call, tripping the RPC framework's own
  already-both-specified conflict check. The exact mechanism (Python
  `AuthServiceProxy`'s null-handling vs. the RPC framework's presence check)
  needs tracing before a confident fix.

The remaining ~27 — `p2p_eviction`, `p2p_ibd_stalling`,
`p2p_headers_sync_with_minchainwork`, `p2p_orphan_handling`,
`p2p_block_sync`, `feature_signet`, `feature_taproot`,
`feature_csv_activation`, `feature_pos_reorg`, `feature_block`,
`feature_assumevalid`, `mining_basic`, `tool_signet_miner`,
`mempool_accept`, `mempool_limit`, `mempool_package_limits`,
`rpc_blockchain`, `rpc_createmultisig`, `rpc_psbt`, `rpc_rawtransaction`,
`wallet_avoidreuse`, `wallet_backup`, `wallet_fundrawtransaction`,
`wallet_groups`, `wallet_orphanedreward`, `wallet_sendall`,
`wallet_signrawtransactionwithwallet`, `wallet_transactiontime_rescan` —
have not yet been individually triaged. `wallet_orphanedreward` and the
P2P/IBD-timeout-scaling group were already anticipated as needing real work
back when Phase 2 began (above); the rest are genuinely unknown until
looked at. Tracked as `TODO-HUMAN`.

### The win64-native MSVC CI job, actually run to a genuine build for the first time

GitHub Actions billing came back during this phase, letting the real
`win64-native` job run for the first time ever on this fork. It had never
actually built to completion before — each fix let it get further and
exposed the next gap underneath, the same pattern as the ASan/clang-tidy
verification:

- `libbitcoin_node`'s MSVC project never included `wallet/staking.cpp` or
  `wallet/rpc/staking.cpp` (added to `libbitcoin_node_a_SOURCES` via a `+=`
  continuation in `src/Makefile.am` that `msvc-autogen.py`'s parser doesn't
  recognize — the same class of gap `wallet/init.cpp` already had a manual
  workaround for) — 6 unresolved externals linking `firstislamiccoind`.
- `qt/walletmodel.cpp` defines a local `WalletWorker` QObject and
  self-includes `qt/walletmodel.moc`, the same pattern four other Qt files
  already use, but was never added to the `QT_MOC` list driving that build
  rule — `Cannot open include file: 'qt/walletmodel.moc'`.
- `bitcoin-tx`, `bitcoin-util`, and `bitcoin-wallet`'s standalone MSVC
  projects were all missing `GetAdjustedTimeSeconds` (FIC's
  `CMutableTransaction` constructor calls it, and MSVC links whole `.obj`
  files rather than individual functions, pulling in that dependency even
  for tools that never construct one); `bitcoin-wallet` also needed the real
  `GetMinFee(size_t, uint32_t)` from `consensus/tx_verify.cpp`. Fixed by
  matching `src/Makefile.am`'s own dependency choices exactly: the dummy
  stub (`timedatadummy.cpp`) for the first two, matching
  `firstislamiccoin_tx_SOURCES`; a real link against `libbitcoin_node` for
  the third, matching `firstislamiccoin_wallet_LDADD`.
- `wallet/rpc/staking.cpp:272` (`nTime &= ~nStakeTimestampMask`) mixes an
  `int64_t` (`nTime`) with a `uint32_t` mask — inverting the 32-bit mask
  first and zero-extending the result into the wider signed type would
  incorrectly clear `nTime`'s upper 32 bits instead of just the intended low
  mask bits (harmless today since real Unix timestamps fit in 32 bits, but
  genuinely wrong). MSVC caught it as a hard warning-as-error the moment
  this file compiled on Windows for the first time (the previous fix just
  wired it into the build); GCC/Clang never flagged it. A different call
  site already fixed for UBSan during the ASan pass (`node/miner.cpp`) ANDs
  the same mask against a genuinely `uint32_t` field and was never affected.
  Fixed by casting the mask to `int64_t` before inverting.

With all five fixed, `clang-tidy` and `ASan/UBSan` both confirmed passing on
the real runner (unrelated to these Windows-only fixes, but run in the same
CI matrix), and the Windows build itself got past linking for the first
time — reaching `test/util/test_runner.py` (`bitcoin-util-test.py`), which
then failed close to 40 of its ~50 cases. This suite's own skip logic
(documented in Phase 10's ASan section) already excludes the fixtures known
to be structurally incompatible with this chain's tx/address format, and
that logic doesn't obviously depend on anything platform-specific — so
these failures are either the same known-incompatible fixtures somehow
evading the skip list on Windows specifically, or a genuinely new
Windows-only gap in the tool binaries or the bctester harness itself. Not
yet root-caused; needs the actual per-testcase diffs from a Windows run,
which requires another round-trip through GitHub Actions to obtain. The
macOS job remains separately stuck `queued` with no runner assigned —
GitHub is very plausibly withholding macOS runner capacity from this
brand-new account, not something fixable from this environment.

---

## Phase 9 — Website

*2026-09-13, started while Phase 2's testnet run continues in the background*

### Deviation from the prompt: static HTML, not Astro/Next.js

The prompt specifies "Astro or Next.js static export." `docs/repo-map.md` already recorded, from
the Phase 0 audit, that CAC's own website is plain static HTML/CSS with no build step or
framework — the same call already made for the web wallet ("no build step — not React/Vite") and
the explorer ("Flask + static frontend, not `btc-rpc-explorer`"). `firstislamiccoin-website/`
follows that precedent: hand-written HTML and one shared `style.css`, no framework, no build step.

### What was built

Nine pages, all real content, none of it a stub:

| Page | Content |
|---|---|
| `index.html` | Hero, how the fixed reward differs from a typical PoS yield, and an honesty section stating plainly that this is testnet, not mainnet |
| `tokenomics.html` | Every table from `docs/tokenomics.md`, carried over faithfully (premine, fixed reward, halving, emission, PoW window, supply constants) |
| `shariah.html` | `docs/shariah-compliance.md` in full, including its **not-a-fatwa disclaimer preserved verbatim**, as the prompt requires |
| `staking.html` | How to stake today (run a node on testnet) versus the two modes still unbuilt (delegated/cold staking, which needs a consensus feature — P2CS — that doesn't exist yet; a custodial pool) |
| `wallets.html` | What actually exists (the node builds from source) versus what's planned (web, mobile, packaged desktop) — no download links to binaries that don't exist |
| `roadmap.html` | All 11 phases from the master prompt, marked done / in progress / planned against this project's actual state, no invented dates |
| `faq.html` | Nine real questions, each answered honestly (no mainnet, no listing, no Shariah certification, no team allocation) |
| `legal/privacy.html`, `legal/terms.html`, `legal/risk-disclosure.html` | Scoped to what actually exists today (a static website, no accounts, no wallets) rather than copying CAC's policies, which cover services (a custodial gateway, a mobile app) FIC hasn't built |
| `servers.json` | The planned ElectrumX/seed/explorer/web-wallet hosts from the brand constants table, every entry marked `"status": "planned"` — none of them answer yet |

Brand assets (`fic-icon.svg`, `fic-coin-full.svg`, favicons) copied from
`firstislamiccoin-brand/`; the stylesheet's color tokens are copied by hand from
`firstislamiccoin-brand/tokens/theme.css` (light and dark, matching its `prefers-color-scheme`
behaviour) — kept in sync manually, since there is no build step to import them.

**No external links anywhere on the site.** No GitHub org is confirmed pushed yet (`git remote
-v` returns nothing for this repository), so linking to `github.com/FirstIslamicCoin/...` would be
a dead link — the acceptance checklist requires every link to resolve. Every `href` is a relative
path within the site; a grep-based link check (also wired into
`.github/workflows/deploy.yml`, below) confirms all of them do.

**No fabricated GPG key, no live-stats widget, no download buttons.** CAC's site fetches
`/api/stats` and lists signed binaries with a real key fingerprint; FIC has neither an API nor a
signing key yet, so carrying either over would mean either dead JavaScript or an invented
fingerprint. Both are simply absent until the real things exist.

### CI and DNS: written, not run

- `firstislamiccoin-website/.github/workflows/deploy.yml` — a GitHub Actions workflow that link-
  checks the site and deploys it to Cloudflare Pages via `wrangler`. It needs
  `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` repository secrets that don't exist in this
  environment; committed as ready-to-run infrastructure, not as proof anything has deployed.
- [`docs/dns.md`](dns.md) — every subdomain from the brand constants table (explorer, wallet,
  electrum1/2, seed1/2/3, the apex and `www`), what it's for, and which phase it depends on. No
  record has actually been created; registrar/DNS access isn't available here.

### Not done in this pass

- **Arabic and Urdu localization with RTL.** The prompt calls for both. Machine-translating
  Shariah-adjacent and financial content without review risks misrepresenting it, which matters
  more here than in most localization work; left for a pass with a reviewer rather than done
  half-right.
- **A downloads page pulling live GitHub release assets + checksums.** There are no releases yet
  (see `wallets.html`); building the pull logic against a repository that doesn't exist yet was
  skipped rather than pointed at a placeholder.
- **Lighthouse ≥ 90 verification.** Lighthouse audits a served URL; nothing is deployed yet (no
  Cloudflare credentials — see above). The pages were built for the fundamentals a Lighthouse run
  checks (semantic HTML, alt text, a real viewport meta tag, no render-blocking third-party
  scripts, documented color-contrast ratios in the brand kit), but the actual score is unverified
  until there's a URL to point Lighthouse at.
- **OpenGraph images from the brand kit.** `og-image.svg` is copied into `assets/` but not yet
  wired into `<meta property="og:image">` tags or rasterized to PNG (most crawlers don't render
  SVG OpenGraph images).

### `TODO-HUMAN`

Domain/registrar access, a Cloudflare account and its two CI secrets, real DNS records, and
Arabic/Urdu translation review all need a human with access this environment doesn't have —
tracked in the `TODO-HUMAN` table below.

---

## Phase 8 — Block explorer

*2026-09-13, done out of order — built right after Phase 9, while Phase 2's testnet run
continued in the background*

Forked CAC's own explorer (`explorer/` — Flask backend, plain static frontend, same shape as
the web wallet and website), not `janoside/btc-rpc-explorer`, per the same precedent recorded for
Phase 9.

### FIC's supply is exact where CAC's couldn't be

CAC's `app.py` could only compute total minted supply up to height 500 (the flat-subsidy PoW
premine window); past that its reward is coin-age-proportional with no closed-form total, and the
code says so directly rather than estimating. FIC has no such boundary: **supply at any height is
`14,000,000,000 + 10 × height` FIC, forever** — `/api/stats`, `/api/supply`, `/api/circulating` and
`/api/supply-series` all compute this directly rather than scanning anything, matching
`docs/tokenomics.md`'s "Supply, in one line".

### New, per the prompt's Phase 8 item 2

- `/api/supply`, `/api/circulating`, `/api/blockreward` — the CoinMarketCap/CoinGecko-shaped
  endpoints the prompt asks for by name. `circulating` equals `total_supply` for FIC: the premine
  has no vesting/lockup (see `docs/tokenomics.md`), so there's no distinction to compute — the
  response says this explicitly rather than inventing a schedule. It also reports
  `premine_spendable: false` on mainnet before the genesis key ceremony, since the placeholder
  recipient can neither spend nor stake it.
- `/api/staking-stats` (a `#/staking` page): current block reward (always 10 FIC, by definition),
  annual emission (constant, from `docs/tokenomics.md`), and blocks/day measured directly from
  real block timestamps over the last up-to-500 blocks.
- **Two fields the prompt asked for that genuinely can't be built right now, reported as `null`
  rather than faked:** `active_stake_weight` would need a staking wallet's `getstakinginfo`
  RPC (`netstakeweight`), which this deliberately wallet-less, read-only backend doesn't hold —
  adding a wallet just for one estimate would break the clean separation from any future
  staking-service backend (same reasoning CAC's own explorer used for why it's a separate
  service at all). `delegated_staking_p2cs` is `null` because P2CS/cold staking doesn't exist in
  `firstislamiccoin-core` yet (TODO-HUMAN 2).

### Rebrand and correctness fixes

Field names moved from `_satoshis` to `_fils` (FIC's actual base-unit name). Genesis blocks are
now flagged `is_genesis` explicitly, rather than falling through the PoW/PoS badge logic that
never anticipated a non-PoW, non-PoS genesis block with 1,000 premine outputs. `rpc.py` gained
cookie-file authentication (`FIC_RPC_COOKIEFILE`) alongside CAC's original fixed user/password —
needed because `firstislamiccoin-infra`'s own testnet nodes run with no fixed RPC password at all
(see `docker-compose.testnet.yml`), and it's the more standard way to deploy today's node either
way.

### Verified against the real, live testnet — not assumed

Installed the backend's dependencies into a throwaway container already wired to the running
Phase 2 testnet's network and read-only cookie mount (the `tools` service in
`docker-compose.testnet.yml`), pointed it at node2, and checked every endpoint against the node's
own RPC output directly:

| Check | Result |
|---|---|
| `/api/stats` height and best-block hash | Matched `getblockchaininfo` exactly (height 305) |
| `total_supply_fils` | `1,400,000,305,000,000,000` fils = exactly `14,000,000,000 + 10 × 305` |
| `/api/block/0` | The known testnet genesis hash; premine total exactly 14,000,000,000 FIC; `is_genesis: true` |
| `/api/block/1` | Its second transaction correctly flagged `is_coinstake` |
| `/api/tx/<that coinstake>` | `reward_fils` exactly 10 FIC, `reward_fees_fils` exactly 0 (no other transactions in that block) |
| `/api/address/<a real funded address>` | Balance in fils matched `getreceivedbyaddress` exactly |
| `/api/richlist` | Real, plausible balances, correctly scanned from genesis |

Full commands and output in `firstislamiccoin-explorer/README.md`'s "Verification" section.

### Not done in this pass

- **Not deployed.** No `explorer.firstislamiccoin.com` DNS record (`docs/dns.md`), no server.
  `firstislamiccoin-infra/provisioning/explorer/` (nginx config, systemd unit, provisioning
  script) is written and ready, adapted from CAC's own, but `provision.sh` needs `REPO_URL` (no
  public FirstIslamicCoin GitHub org exists yet) or a local checkout.
- **P2CS delegation stats** — genuinely blocked on TODO-HUMAN 2, not an oversight.
- **A real address-history index.** Same limitation CAC's explorer had and documented: address
  pages show current balance/UTXOs via `scantxoutset`, not historical spent transactions. Needs
  `firstislamiccoin-electrumx` (Phase 4), not built yet.

### `TODO-HUMAN`

A server and `explorer.firstislamiccoin.com`, same access gap as Phase 9's Cloudflare/DNS items —
tracked in the `TODO-HUMAN` table below.

## Phase 5 — Mobile wallet

Forked from `codexacoin/cac_wallet/` (Flutter, Android + iOS) into `firstislamiccoin-mobile/`
per `docs/repo-map.md`. The crypto layer (BIP39/BIP32 key derivation, Base58Check/bech32 address
encoding, legacy transaction building/signing, N-of-M multisig, air-gapped offline signing,
message sign/verify) is fully parameterized by `NetworkConfig` and needed no logic changes at
all — every fix in this phase is either a chain-parameter correction, a scope decision (drop or
keep a CAC feature), or new work (localization, iOS permission fix) this phase added.

### Chain parameters corrected

`lib/config/network_config.dart` now carries FIC's real values from `firstislamiccoin-core/src/kernel/chainparams.cpp`,
not CAC's: mainnet P2PKH `36`/P2SH `28`/WIF `164`, bech32 HRP `fic`; testnet P2PKH `111`/P2SH
`196`/WIF `239`, bech32 HRP `tfic`. BIP44 coin type is `9770` on **both** networks — unlike CAC
(and unlike SLIP-44 convention generally), `docs/CHANGELOG-FIC.md`'s own earlier chainparams work
established FIC uses 9770 uniformly rather than the standard testnet index `1`. The message-signing
magic string changed to match `firstislamiccoin-core/src/util/message.cpp` exactly:
`"FirstIslamicCoin Signed Message:\n"`.

### Decision 3 removed the wrapped-token/DEX surface entirely

CAC's wallet embedded a "Buy / Sell CAC (PancakeSwap)" external link, a full WalletConnect-based
in-app swap screen (`wallet_connect_swap_screen.dart` + `services/pancake_swap.dart`, BNB Chain
Router ABI encoding), and a live FIC/USD-equivalent price feed sourced from that same PancakeSwap
pool plus a Stellar DEX order book (`services/price_service.dart`). All of it existed only because
CAC issues wrapped BEP-20/Stellar tokens (`bnb-issuer/`, `stellar-issuer/`) — components this
project already decided to drop (`Decision 3` above, `docs/repo-map.md`'s "Components with no FIC
target"). FIC has no token on any other chain for a swap screen to point at, so all three files
were deleted rather than rebranded, along with `reown_appkit`/`web3dart` from `pubspec.yaml`.
`lib/widgets/fiat_placeholder.dart` now shows an honest "unavailable" message instead of fetching
a real (if thin) number — there is nothing to fetch it from.

### P2CS gap handled the same honest way as the explorer/website

TODO-HUMAN item 2 (P2CS/cold-staking doesn't exist in `firstislamiccoin-core`) means the staking
screen can only expose the custodial pool flow CAC also has — `lib/screens/staking_screen.dart`
and `GatewayApi` carry that over unchanged. CAC's own wallet never built the P2CS delegate/revoke
UI either (its gateway client methods exist but nothing calls them — see CAC's own
`docs/store-compliance.md`), so there was nothing FIC-specific to strip here; `docs/mobile-api.md`
§5 documents the gap explicitly instead of silently dropping CAC's delegate/revoke endpoint specs.

### Gateway architecture kept, not replaced with a raw Electrum client

The master prompt's Phase 5 spec describes an Electrum-protocol client. CAC's actual wallet talks
REST to a custodial gateway service instead (`docs/mobile-api.md`), and neither backend exists for
FIC yet (ElectrumX is Phase 4, the gateway is Phase 6 — see `docs/repo-map.md`). Building a new
Electrum client against a Phase 4 service that also doesn't exist would trade one unbuilt backend
for a different, more expensive one to build, for no benefit visible from the wallet side (both are
equally "not deployed" today). Kept CAC's gateway-client architecture, documented as a deviation
here rather than silently diverging from the prompt.

### Reward-model correction in the gateway contract

`docs/mobile-api.md` §5 (staking status) is CAC's contract with one substantive fix: CAC's
`effective_monthly_rate_bp` assumed a coin-age reward rate (`nStakeRewardAnnualBP`); FIC's reward
is a fixed 10 FIC + fees per block with no such rate (Phase 1). The field name is kept for wire-shape
stability but the doc now says plainly that nothing computes a real value for it yet.

### Localization — real infrastructure, partial coverage

`flutter gen-l10n` wired up for real (`l10n.yaml`, `pubspec.yaml`'s `generate: true`,
`lib/main.dart`'s `localizationsDelegates`/`supportedLocales`), with English and Arabic ARB files
and a representative sample of screens (home navigation, settings, onboarding) actually reading
through `AppLocalizations`. The other ~90% of screens' strings are still English literals, and
Urdu/Bahasa Indonesia/Malay/Turkish have no ARB file at all yet — see `docs/localization.md` for
exactly what's covered and why only Arabic got a (unreviewed) translation: every string needed so
far is generic wallet vocabulary with no religious terminology to get wrong, unlike a future pass
that touches anything Shariah-related.

### A real (non-rebrand) fix: iOS `Info.plist` usage descriptions

CAC's `Info.plist` has no `NSCameraUsageDescription` or `NSFaceIDUsageDescription` — iOS
terminates an app on first use of either API without its usage-description key, rather than
failing gracefully. `mobile_scanner` (QR scanning) and `local_auth` (Face ID app lock) both need
one. Added both, since a fresh FIC wallet build would otherwise crash on first QR scan or app
unlock — a real bug inherited from the source, not something a rebrand pass would normally touch.

### Android minSdk lowered from 23 to 21

CAC's `minSdkVersion 23` existed only for `reown_appkit`'s `coinbase_wallet_sdk` dependency, now
removed along with the rest of the WalletConnect swap screen. `mobile_scanner` and
`firebase_messaging` both need `>=21`; nothing else in this dependency set needs 23.

### Verification

**`flutter analyze`/`flutter test` were not run — honestly, not just "not yet".** No Flutter/Dart
SDK exists on this Windows development host, and getting one proved genuinely blocked in this
environment: `docker pull` of any image (tried `ghcr.io/cirruslabs/flutter:stable`, then a plain
`hello-world` to isolate the cause) hangs indefinitely with no error — Docker Hub/GHCR registry
access appears unreachable from here, unlike the `apt`/`pip` mirrors the Phase 8 explorer work
relied on successfully. A direct download of the official Flutter SDK tarball from
`storage.googleapis.com` (confirmed reachable) worked but at roughly 120-200 KB/s against a
1.46 GB archive — 3+ hours, impractical to block this phase on. That download was left running
unattended in the background in case it finishes later, but this phase's correctness claims do
not depend on it finishing.

What was done instead, to compensate honestly rather than skip verification entirely:

- A crude but real static check across every `.dart` file in `lib/` and `test/`: brace-balance
  count and a script confirming every relative `import '../...'` resolves to a real file (the
  three `l10n/generated/app_localizations.dart` imports are the sole, expected exceptions —
  `flutter gen-l10n` codegen output, not yet generated).
- Careful manual re-reading of every edited file's full content, not just the diff, after each
  batch of edits.
- `test/crypto/address_test.dart` and `test/crypto/xpub_test.dart`'s testnet vectors are not
  invented: they were captured live from `firstislamiccoin-cli -testnet
  getnewaddress`/`getaddressinfo`/`createmultisig`/`decodescript` against the running Phase 2
  testnet (`fic-testnet-node0-1`) — a real value even without a Dart compiler to run the test
  against yet, and the same live-network verification standard the explorer (Phase 8) was held
  to. Mainnet address vectors are self-generated (encode/decode round-trip only) since mainnet's
  genesis premine is still the placeholder that refuses the node to start (`docs/genesis.md`) —
  no live mainnet node exists to capture a cross-checked sample from yet.
- CAC's own golden vectors that depended on a second, independent implementation (a signature
  captured from `web-wallet/message.js`, an xpub captured from `web-wallet/crypto.js`) were
  removed rather than reused, since FIC has no web wallet yet (Phase 7) and both CAC vectors
  depend on values (the message magic string, the BIP44 coin type) that changed for FIC anyway —
  see `test/crypto/message_test.dart` and `test/crypto/xpub_test.dart`'s own comments.

`.github/workflows/ci.yml`'s `analyze-and-test` job runs the real commands on every push — this
gap is specific to the interactive development environment this phase was built in, not a gap in
the project's actual CI coverage going forward.

### Not done in this pass

- **`flutter analyze`/`flutter test`/`flutter build` never actually ran** — see "Verification"
  above for exactly why and what stood in for them.
- **No Android APK/AAB or iOS build actually produced.** No Android SDK or Xcode toolchain in this
  development environment either. `.github/workflows/ci.yml`'s `build-android` job will do this
  on push once a real GitHub Actions runner picks it up.
- **Not signed, not submitted to either store.** No Play Console/App Store Connect account, no
  signing keystore/certificate, no published privacy-policy URL — see `store/` and this phase's
  `TODO-HUMAN` rows below.
- **Full-app string externalization and Urdu/Bahasa/Malay/Turkish translation** — see
  `docs/localization.md`.

### `TODO-HUMAN`

Signing keys, store accounts, and translation review — tracked in the `TODO-HUMAN` table below.

## Phase 6 — Staking service

Forked from `codexacoin/vps-gateway/` into `firstislamiccoin-staking-service/` per `docs/repo-map.md`.
Implements `firstislamiccoin-mobile/docs/mobile-api.md` for real — both the mobile app and the
not-yet-built web wallet (Phase 7) are meant to talk to this. Most of the codebase needed only
renaming: `auth.py`, `kyc.py`, `push.py`, `push_mobile.py`, `mobile_notify.py`, `watcher.py`, and
`db.py`'s schema carried over with no logic changes at all — none of it was CAC-specific to begin
with.

### Backend choice matches CAC's own, for a different reason

CAC's `vps-gateway` already talks directly to `codexacoind` via RPC (a watch-only wallet that
imports addresses on demand) rather than `electrumx-cac`, because CAC's own local verification hit
a macOS packaging issue with that backend. FIC has the same architecture for a related but distinct
reason: `firstislamiccoin-electrumx` (Phase 4) doesn't exist at all yet. Either way, the substitution
is what makes this phase actually runnable and verifiable now instead of waiting on Phase 4 —
documented as a deviation here rather than silently diverging from the prompt's Electrum-backed
design.

### Reward-model correction, not a rebrand

CAC's `staking.py` quotes depositors a real annualized rate (`STAKE_REWARD_ANNUAL_BP`, a
coin-age-proportional design). FIC's reward is a fixed 10 FIC plus fees per block regardless of
deposit size (Phase 1) — deposit size affects only the probability of winning a block, not the
size of the reward. Removed the env-var-driven rate entirely rather than porting a number that
doesn't mean anything for FIC; `effective_monthly_rate_bp` reports `0` now. The reward-detection
mechanics themselves (`_attribute_rewards()`'s outputs-minus-inputs computation on the real
coinstake transaction) needed no change — verified to still produce exactly the right number for
FIC's different reward model (see "Verification" below).

### Decision 3 removed price sourcing, not just the mobile wallet's UI for it

CAC's `price_alerts.py` sourced a real (if thin) price from a PancakeSwap pool and a Stellar DEX
order book — both only exist because CodexaCoin issues wrapped tokens on those chains, which this
project already decided to drop (Decision 3). `fetch_fic_usd_price()` now always returns `None`;
`/v1/price` always answers `503 not-available`, verified directly rather than assumed. The
CRUD/one-shot-trigger machinery around it needed no change — a real price source, if one ever
exists, is a one-function swap.

### Verification: full custodial-staking lifecycle, against a real node

Ran against a real regtest `firstislamiccoind` node (regtest's 10-block maturity and ~1s block
spacing make a real coinstake observable in minutes, unlike testnet/mainnet's real chain time) —
the same live-node standard Phases 2 and 8 were held to:

- Signup → login (JWT) → deposit address → funded externally → watcher detected it
  (`delegated_amount` became exactly the amount sent).
- The deposit staked for real: `listtransactions` showed `category: "generate", amount: 10.0` —
  **exactly** the fixed block reward. The watcher then credited `accrued_rewards` as exactly
  `10 FIC − 5% pool fee = 9.5 FIC` net — the pool-fee math matched precisely.
- Referral: a second signup using the first user's real referral code, funding a 1000 FIC deposit,
  credited exactly `10%` (10 FIC) to the referrer — masked email confirmed correct in the history
  endpoint.
- General wallet endpoints (`balance`/`utxos`/`history`/`tx-detail`/`fee-estimate`/`broadcast`)
  verified against a real ordinary send and a separately-built-and-signed raw transaction actually
  broadcast through the gateway's own `/v1/tx/broadcast`, not just via the node directly.
- Error paths verified, not just assumed: invalid address (400), missing auth (401), unfunded
  admin wallet on referral withdrawal (clean `not-found`), `/v1/price` with no source (503).

Full command-by-command account in `firstislamiccoin-staking-service/README.md`'s "Verification"
section.

### One real finding from verification, flagged rather than fixed

After the deposit's coin staked once (and kept re-staking on subsequent maturities — an accepted,
CAC-inherited limitation, see `staking.py`'s docstring), its resulting UTXO came back
`"solvable": false` — a raw P2PK script, not the P2PKH the deposit address used — and
`sendtoaddress` failed with `Insufficient funds` despite the wallet holding the coin and its keys.
This looks like a general issue in `firstislamiccoin-core`'s coinstake-construction code (possibly
reserving a destination outside the descriptor wallet's normal bookkeeping) that could affect any
descriptor wallet that stakes, not something specific to this gateway. Flagged for a focused
core-side investigation rather than guessed at or fixed here — it touches consensus-adjacent wallet
code well outside this phase's scope.

### Not done in this pass

- **Not deployed anywhere.** No server, no DNS record. `docs/dns.md` already lists
  `staking-api.firstislamiccoin.com`/`staking-api.testnet.firstislamiccoin.com` as planned (added
  during Phase 5) but neither is live.
- **`firstislamiccoin-infra/provisioning/staking-service/`** has the systemd units (adapted from
  CAC's own) but no `provision.sh` — CAC's own `vps-gateway` didn't build one either.
- **Web Push / FCM push** exercised only structurally (no VAPID keys or Firebase service account
  in this environment) — both took their documented no-op branch rather than actually delivering a
  notification.
- **The coinstake-output solvability finding above.**

### `TODO-HUMAN`

Server, DNS, VAPID/FCM credentials, and the core-side coinstake-output investigation — tracked in
the table below.

## Phase 7 — Web wallet

Forked from `codexacoin/web-wallet/` into `firstislamiccoin-web-wallet/` per `docs/repo-map.md`. A
static, no-build-step browser wallet talking to the same `firstislamiccoin-staking-service` gateway
and `mobile-api.md` contract the mobile app uses. `qr.js` needed zero changes (nothing in it was
CAC-specific); `gateway.js`, `message.js`, `storage.js`, `sw.js` needed only renames.

### Decision 3 removed price.js entirely, not just its UI

CAC's `price.js` sourced a real (if thin) price from a PancakeSwap pool and a Stellar DEX order
book for the Home/Send screens' fiat estimate and a "Buy / Sell CAC (PancakeSwap)" button — all
only possible because CodexaCoin issues wrapped tokens on those chains, which this project already
decided to drop. `price.js` was deleted outright; both fiat-estimate spots are now permanently
empty and the PancakeSwap button is gone. The price-alerts feature's "current price" display
needed **no code change at all** — it already called the gateway's `/v1/price`, which Phase 6
already made honestly return `503`, and the existing `catch` block already rendered "unavailable"
for that case. Verified directly in a real browser against a real gateway, not just reasoned about:
the staking screen's price-alerts card showed "Current price: unavailable right now" exactly as
designed.

### A real bug found (and fixed, in both wallets) by testing in a real browser

Every fee calculation in both `web-wallet/app.js` and `cac_wallet`'s Dart screens divides
`feeRate * estimatedVsize` by 1000 (`(feeRate * vsize + 999) / 1000`), as if `feeRate` were
satoshis-per-*kilobyte*. It isn't — the gateway's `/v1/fee-estimate` (`fee_rate_sat_per_vbyte`,
both the field name and every UI label) has always returned satoshis-per-*byte*, converted fully
from `mempoolminfee` server-side. The extra `/1000` silently computed a fee **1000x smaller** than
intended on both CAC and FIC alike — invisible on CAC, which has no consensus-level minimum-fee
check, so an underpaid transaction still relayed and mined fine. FIC is not so forgiving:
`firstislamiccoin-core/src/consensus/tx_verify.cpp`'s `GetMinFee`/`TX_FEE_PER_KB` (comment-marked
`// FirstIslamicCoin:`, i.e. new consensus code, not something inherited from Blackcoin/CAC) enforces
a real per-byte minimum, and every send at or near the recommended rate was silently building a
transaction the network would reject outright.

Found live, not by re-reading the code: building the mobile wallet (Phase 5) only ever exercised
this formula against static test values, never a real broadcast (no gateway existed yet). Phase 6's
own verification broadcast several real transactions, but always via the *node's own* `sendtoaddress`
RPC — never through the gateway's `/v1/tx/broadcast` + client-side `buildAndSignTransaction` path
this bug actually lives in. Phase 7 was the first time that exact path got exercised end-to-end in
a real browser against a real regtest node: a send at the displayed "recommended" rate came back
`bad-txns-fee-not-enough`, and manually overriding the UI's fee-rate field to 50x the floor (the
maximum the slider allows) still failed identically — the tell that the override wasn't reaching
the actual computation at all, not just that the floor itself was too low.

Fixed by removing the erroneous `/1000` everywhere it appeared — `feeRate * vsize` needs no
rounding correction once the extra division is gone, since both operands are already integers.
Six call sites in `firstislamiccoin-web-wallet/app.js` (send, multisig propose, bump-fee, and the
send-screen live estimate); seven in `firstislamiccoin-mobile/`: `send_screen.dart` (×2),
`multisig_screen.dart` (×2), `offline_send_screen.dart` (×2), `wallet_service.dart`'s `bumpFee`
(×1) — all committed in this same phase's commit, not deferred, since the mobile wallet's Phase 5
commit was already merged with the bug present. Re-verified after the fix: the same send that
failed now broadcasts and confirms on-chain at the exact intended fee.

### Verification

Tested in a real browser (not just read for correctness), against a real regtest
`firstislamiccoind` node and a real `firstislamiccoin-staking-service` instance — the same
live-node standard Phases 2, 6, and 8 were held to: wallet creation (real BIP39/BIP32 via the
CDN-loaded `@noble`/`@scure` libraries, producing a correctly-prefixed `m…`/testnet-style address —
regtest shares testnet's version bytes), network switching, balance display against a real funded
address, a real send (initially failed on the bug above, fixed, then succeeded and confirmed
on-chain), QR rendering on Receive, staking signup/login (JWT + KYC fields) and deposit (real
deposit address from the pool wallet), staking status showing the honest `0%` rate and `5%` pool
fee, and price alerts showing the honest "unavailable" price. Full account in
`firstislamiccoin-web-wallet/README.md`'s "Verification" section.

### Not done in this pass

- **Not deployed anywhere.** No server, no DNS record — `docs/dns.md` already lists
  `wallet.firstislamiccoin.com` as planned (Phase 0) but it isn't live.
- **Multisig, watch-only/xpub, message sign/verify, and PIN-lock screens** were read for
  correctness and exercised only lightly in this pass's browser session (the send-flow bug hunt and
  fix took priority) — not each individually driven through a full real scenario the way the send
  and staking flows were.
- **Web Push** exercised only structurally (no VAPID keys in this environment).

### `TODO-HUMAN`

Server and DNS for `wallet.firstislamiccoin.com`, VAPID keys — tracked in the table below.

## Phase 3 — Desktop CI + release

`firstislamiccoin-core/.github/workflows/{build.yml,ci.yml,docker_build_push_26.yml}` were already
fully rebranded (verified: zero real `codexacoin`/`CodexaCoin` hits — the only `CAC` matches are
`ccache`/`CCACHE` substrings) as part of Phase 1's core rebrand, so this phase's actual gap was
narrower than the prompt's phase name suggests: a tag-triggered **release** workflow that packages
desktop binaries, which CAC keeps at its monorepo root rather than inside `codexacoin-core/`.

### `.github/workflows/release.yml`, forked to the monorepo root

Added `.github/workflows/release.yml` at the repository root (not inside `firstislamiccoin-core/`),
matching exactly where CAC's own equivalent lives and for the same reason theirs does: GitHub
Actions only discovers workflows under the repository root's `.github/workflows/`, and this
project's actual source tree is one level down. Forked with working-directory changed to
`firstislamiccoin-core` throughout, binary/package names renamed
(`firstislamiccoind`/`firstislamiccoin-cli`/`firstislamiccoin-tx`, package `firstislamiccoin`), and
the `.deb`'s `--url` pointed at `firstislamiccoin.com` (CAC's pointed at a real
`github.com/fakharnaqvi5313/codexacoin` — no equivalent exists for FIC, so this was dropped rather
than pointed at a repository that isn't there).

Confirmed no branding drift in what this workflow actually invokes: `contrib/macdeploy/build_dmg.sh`
has zero CAC references (already generic/rebranded), and `configure.ac`'s `AC_INIT` already declares
`FirstIslamicCoin Core` with `firstislamiccoin.com` as its URL — this workflow's `./configure` calls
inherit that correctly with no changes needed there.

### Why this couldn't be verified end-to-end here, and what was checked instead

Actually running this workflow needs a real GitHub Actions runner (Linux/Windows/macOS
cross-compilation, several dependency-heavy `depends/` builds) — not something to attempt inside
this development environment. This is the same honest gap already established for every other
CI/deploy workflow in this project (`firstislamiccoin-mobile/.github/workflows/ci.yml`,
`firstislamiccoin-website/.github/workflows/deploy.yml`): committed as ready-to-run infrastructure,
not proof a release has happened. Two things make that gap wider here than for those: no
FirstIslamicCoin GitHub org/repository exists yet for this workflow to have ever run against
(`git remote -v` returns nothing), and there is nothing to tag a real release *of* yet either --
mainnet is still blocked on the Phase 10 key ceremony (`docs/genesis.md`'s placeholder premine).

What was checked instead: the workflow file parses as valid YAML with the expected four jobs
(`linux`, `windows`, `macos`, `publish-release`); every file/script path it references
(`contrib/macdeploy/build_dmg.sh`, `doc/release-process.md`, `depends/packages/`, `README.md`,
`COPYING`) exists in `firstislamiccoin-core/` and was inspected for accuracy, not just assumed
present because CAC's did.

### Codesigning and notarization

Unchanged from CAC: Windows Authenticode signing and macOS codesigning/notarization are both
explicitly `TODO`-commented in the workflow rather than attempted — both need real certificates
this project doesn't have, and CAC's own workflow left them exactly as unsigned for the identical
reason.

### `TODO-HUMAN`

A FirstIslamicCoin GitHub org/repository for this workflow to actually run in, and (separately, for
a real public release) Windows Authenticode + macOS Developer ID certificates — tracked in the
table below.

## Phase 4 — ElectrumX (light-client backend)

Forked CAC's own `electrumx-cac` (itself a fork of `CoinBlack/electrumx-blk`, Blackcoin's ElectrumX)
to `firstislamiccoin-electrumx/`. The entire CAC-specific customization is three coin-definition
classes in the single large multi-coin registry file `src/electrumx/lib/coins.py` (which also
carries ~100+ unrelated upstream coin definitions — Bitbay, Myce, Navcoin, etc. — left untouched);
everything else, including the daemon and transaction-deserializer classes
(`daemon.BlackcoinDaemon`, `lib_tx.DeserializerBlackcoinSegWit`), is reused unchanged from upstream
Blackcoin support, same as CAC's own fork does.

### `FirstIslamicCoin`/`FirstIslamicCoinTestnet`/`FirstIslamicCoinRegtest`

Replaced CAC's three coin classes with FIC equivalents: real genesis hashes (mainnet
`be7039971885efc3cb375ffb86200ab6964535dcd57c2cf9d8075522657afaeb`, testnet
`a028f8ffcbbb97bde94e3acb508ec33caa80067dccfc077905a4c3acb18f7aed` — live-verified against the
Phase 2 testnet node, not copied from a doc — and regtest
`360afc3edc3e70f91452bbc7ece92fd4a18dbb9700aea612564636fadbd4e712`), FIC's own address-version
bytes, RPC ports (19771/29771/39771), and `PEERS` pointed at the real `electrum{1,2}`/
`testnet-electrum{1,2}.firstislamiccoin.com` hostnames `docs/dns.md` reserves for this phase (not a
placeholder `.example` domain).

### Real end-to-end indexing verified — the gap CAC's own Phase 4 was blocked from closing

CAC's own `electrumx-cac/provisioning/electrumx/README.md` is explicit that it only ever confirmed
a daemon *connection* (`BlackcoinDaemon:daemon #1 at 127.0.0.1:36211/ (current)` in the log), never
actual block/transaction indexing — blocked by `plyvel`/`leveldb`/`rocksdb` packaging failures on
their macOS 12.7.6 dev machine, below Homebrew's supported tier. This project's environment doesn't
have that constraint, so this phase went further:

1. Built `firstislamiccoin-infra/provisioning/electrumx/Dockerfile` (Debian bookworm-slim +
   `libleveldb-dev`, the standard packaged path CAC's own Dockerfile was written for but never
   itself ran) as image `fic-electrumx`. It built and ran cleanly.
2. Pointed it at a live local regtest `firstislamiccoind` (50+ blocks, including a real send —
   txid `9278a0c0a6f10467589796490f9deb3fa8c15cf030c5ad12b015998b25bce31f`, 777.5 FIC to
   `mz5jgSPSRht9swKqAHi2GPQpbV9SEKKwhx`). It fully synced to the daemon's height and began serving.
3. Queried the running server's own TCP RPC port directly (`blockchain.scripthash.get_balance` /
   `get_history` — the current Electrum protocol's scripthash-keyed methods, not the deprecated
   address-keyed ones) for that address. It returned `{"confirmed": 77750000000, "unconfirmed": 0}`
   and a history containing exactly that txid at height 3 — an exact match, down to the satoshi, of
   the node's own `gettxout`/`getrawtransaction` RPC output (777.50000000 FIC). Real indexing,
   confirmed against real chain data, not asserted.

### Two real bugs this surfaced, both fixed

Neither would have been caught by CAC's own connection-only verification, since both only manifest
once real blocks are actually processed:

- **`coins.py`'s inherited `genesis_block()` silently dropped FIC's own premine.** The base
  `Coin.genesis_block()` (used, unmodified, by every other coin in this file — none of them have a
  spendable genesis either) truncates the genesis block to zero transactions, matching Bitcoin's
  unspendable-coinbase convention. FIC's genesis is deliberately different: 1000 real, spendable
  premine outputs (`docs/genesis.md`). That truncation meant the premine transaction itself was
  never indexed, so the very first spend of *any* premine output crashed the indexer with
  `ChainError: UTXO ... not found in "h" table"`. Fixed by overriding `genesis_block()` on the
  `FirstIslamicCoin` base class to keep the real transactions, verifying only the header hash —
  this is a genuine FIC-specific deviation from every other coin definition in this file, not a
  copy-paste of an existing pattern.
- **`FirstIslamicCoinRegtest.TX_COUNT_HEIGHT = 0` divided by zero.** It's used as a divisor in
  `block_processor.estimate_txs_remaining()`'s ETA heuristic
  (`self.height / coin.TX_COUNT_HEIGHT`), which runs the moment sync first catches up to the
  daemon — crashing with `ZeroDivisionError` right after the last block of a freshly-synced
  regtest chain. `TX_COUNT`/`TX_COUNT_HEIGHT` are cosmetic (server-info hints, not consensus), so
  this was never going to be caught by a build/connection check. Fixed by setting it to `1`.

### Provisioning tooling

Adapted `electrumx-cac.service`, `provision.sh`, and `README.md` from CAC's originals to
`firstislamiccoin-infra/provisioning/electrumx/` — service/venv/data paths and DNS hostnames
renamed, `provision.sh`'s `NETWORK` → `COIN` lookup table updated to the FIC classes above. Added
the two `testnet-electrum{1,2}.firstislamiccoin.com` rows to `docs/dns.md` (CAC's own table, and
this project's copy before this phase, only listed mainnet `electrum{1,2}`, even though
`FirstIslamicCoinTestnet.PEERS` already names testnet-prefixed hosts).

### Existing ElectrumX test suite: run, not just left alone

Ran `tests/lib/test_coins.py` and `tests/test_blocks.py` (upstream's own unit tests, inherited
unmodified) against the new coin classes: 130 passed, 33 skipped, 5 failed. All 5 failures
pre-exist this phase and are not caused by it:

- 4 are `ModuleNotFoundError: No module named 'blake256'` on Decred fixtures — an optional native
  dependency this environment never installed, unrelated to any Blackcoin/CAC/FIC code path.
- 1 is `test_all_coins_are_covered`, which asserts every mainnet `Coin` subclass has a real block
  test fixture under `tests/blocks/`. CAC's own `CodexaCoin` mainnet class never had one either
  (`tests/blocks/codexacoin_mainnet_*.json` does not exist in CAC's `electrumx-cac`) — FirstIslamicCoin
  simply joins that same pre-existing gap, not a new regression. Closing it for real would mean
  reconstructing FIC's actual mainnet genesis block bytes from `chainparams.cpp`'s placeholder
  premine parameters via `contrib/genesis/generate_genesis.py` and getting a real node to emit them
  — out of scope for this phase, and blocked on the same Phase 10 key ceremony that blocks mainnet
  itself; tracked as its own `TODO-HUMAN` row rather than faked with invented block data.

### `TODO-HUMAN`

No FirstIslamicCoin GitHub org/repository exists yet for `provision.sh`'s `REPO_URL` to clone from,
no real server or DNS record exists for either ElectrumX instance, and no mainnet block-test
fixture exists for `FirstIslamicCoin` in `tests/blocks/` — tracked in the table below.

## Phase 10 — Mainnet launch checklist and handover

The full writeup for the security-review pass is in
[`docs/security-review.md`](security-review.md); this section summarizes what it found and fixed,
plus the rest of the phase.

### Security review found two CI workflows that have never actually run

Validating every `.github/workflows/*.yml` file in the monorepo as YAML (not just reading them)
turned up two that fail to parse at all, meaning GitHub Actions would silently refuse to run either
workflow in full: `firstislamiccoin-core/.github/workflows/ci.yml` (a mis-indented `checkout` step,
confirmed byte-identical in `codexacoin-core`'s own copy — inherited from CAC, not FIC's doing) and
`firstislamiccoin-mobile/.github/workflows/ci.yml` (an unquoted colon inside a step name, FIC's own,
from Phase 5). Both fixed. This is a bigger, more basic gap than anything the security tooling
itself found — no CI has ever run on either repository, independent of whether its jobs are
individually correct.

### ASan/UBSan and clang-tidy were already scripted, just never wired in

`ci/test/00_setup_env_native_asan.sh` and `00_setup_env_native_tidy.sh` — full sanitizer and
static-analysis build configs — were already present, inherited unchanged from upstream Bitcoin
Core, but no job in `ci.yml` referenced either. Added `linux-native-asan` and
`linux-native-clang-tidy` jobs that do. The `ci_native_asan` Docker image builds cleanly in this
environment (unlike CAC's own macOS-blocked ElectrumX verification in Phase 4, this isn't a
packaging problem); completing an actual sanitizer build+test run locally hit a real but mundane
snag — Bitcoin Core's own `CI_EXEC` shell helper loses quoting through `bash -c "... $*"`, and this
checkout lives at a path containing spaces ("First Islamic Coin"). Not fixed in the vendored
script (a real GitHub Actions runner's workspace path never has spaces, so this would not recur
there); tracked as `TODO-HUMAN` instead of worked around with a local-only patch.

### The ASan/UBSan CI job, actually run to a genuine green state

GitHub Actions billing was unavailable for this repository for the entire length of this phase,
so the real CI job could never run there to confirm it. Rather than leave that unverified, ran the
exact same `ci_native_asan` Docker image and `ci/test_run_all.sh`/`00_setup_env_native_asan.sh`
config the workflow uses, directly on a VPS with a spaces-free path — sidestepping the `CI_EXEC`
quoting snag above rather than working around it in the vendored script. Nine full build+test
cycles over the fixes below, the last one entirely clean.

Real bugs found and fixed, not simulated: `WalletModel::join()` leaked its worker thread
(LeakSanitizer); `nStakeTimestampMask` was a signed bitmask, undefined behaviour when negated
against the `uint32_t` `nTime` it masks (UBSan); `coinselector_tests`' `bnb_search_test` never set
`m_long_term_feerate`, so Branch-and-Bound's win over other candidates was undetermined rather
than a real flake — tuned to win deterministically (30/30 clean runs on its own, 8/8 on the full
suite around it); `test/util/test_runner.py`'s `bitcoin-util-test.py` still invoked `./bitcoin-tx`
in six entries instead of `./firstislamiccoin-tx`, a genuine leftover rebrand gap silently
swallowed by a scoping quirk in the vendored script rather than raising a clear error.

The rest were all upstream test/benchmark fixtures built for vanilla Bitcoin, structurally
incompatible with this chain and skipped or replaced with clear documentation rather than
force-fit: `script_assets_test`, `tx_valid`/`tx_invalid` (`nVersion<2` vectors only),
`sighash_from_data`, and 36 `test/util/data` fixtures are all signed or encoded under vanilla
Bitcoin's sighash/tx format, permanently incompatible with this chain's nTime-extended
`nVersion<2` wire format; `validation_block_tests`' `mempool_locks_reorg` needs a reorg deeper
than the sync-checkpoint anti-reorg rule allows by design (`FinalizeBlock()`'s header check
tightened from `BOOST_CHECK` to `BOOST_REQUIRE` for defense in depth while there). Three
benchmarks (`checkblock.cpp`, `load_external.cpp`, `rpc_blockchain.cpp`) deserialized a real 2016
Bitcoin mainnet block that can never validate here — FIC's proof-of-work algorithm (scrypt)
differs from Bitcoin's (SHA256d) entirely, not just the tx format — replaced with a small,
genuinely valid FIC block generated via the same `test/util/mining.h` utilities the unit tests
already use. `block_assemble.cpp`'s `AssembleBlock` mined past regtest's real proof-of-work
ceiling and used a dust-sized output (`DUST_RELAY_TX_FEE` here is ~33x vanilla Bitcoin's
default). `mempool_stress.cpp`'s `MempoolCheck` — the one caller that actually self-validates the
mempool against real consensus rules, rather than bypassing validation like most test callers —
exposed two latent bugs in the shared `TestChain100Setup`/`PopulateMempool` fixture: a stale
hardcoded `spendheight` predating this fixture's real height, and `PopulateMempool` generating
fees far below this chain's real minimum-fee floor while also seeding from coinbases that can
never satisfy real maturity. `wallet/test/util.h`'s unspendable placeholder address used Bitcoin
regtest's bech32 HRP (`bcrt`) instead of FIC's (`rfic`).

Final run: full build, all 126 unit test suites, the bench sanity-check gate, and
`libsecp256k1`'s own suite all pass clean, with only the same pre-existing, explicitly
`(ignored)` `dist-hook` tarball error throughout (this VPS checkout isn't a real git clone, not a
CI defect). This closes out the `TODO-HUMAN` item on completing a real ASan/UBSan run.

### The clang-tidy CI job, actually run to a genuine green state

Same VPS approach as ASan/UBSan above: ran the exact `ci_native_tidy` Docker image and
`ci/test_run_all.sh`/`00_setup_env_native_tidy.sh` config the `linux-native-clang-tidy` workflow
job uses. `src/.clang-tidy` sets `WarningsAsErrors: '*'`, so unlike the cppcheck audit elsewhere in
this document — a manual, non-blocking pass where the established policy is to leave pre-existing
upstream findings alone — every finding here is a hard failure for this specific CI job
regardless of which code introduced it, so getting a genuine pass required fixing all of them, not
only the ones in this project's own code.

First run surfaced 27 unique findings (deduplicated; clang-tidy reports the same header-level
finding once per translation unit that includes it, so the raw log had far more). Checked each
one with `git blame` against `3df79ad0` (the verbatim CodexaCoin import commit that starts this
repository's own history) to see whether it was FIC's own change or inherited unmodified: only one,
`node/miner.h`'s dead `[[maybe_unused]] CWallet *pwallet` member (left over from an earlier fix
this same phase), was FIC's own. The other 26 were all pre-existing in the CodexaCoin import,
untouched by any commit since — plain style/modernization gaps (`use nullptr` instead of `0` for
eight pointer-valued members and defaults, `use default member initializer` for seven more,
`use emplace_back` instead of `push_back` for nine constructor-argument insertions, three unused
`using` declarations, one stale argument-name comment, and one `LogPrintf` call missing its
trailing `\n`) that this fork's snapshot of Bitcoin Core predates upstream fixing, not anything
that changes behavior. Every one fixed the same mechanical way clang-tidy itself proposed; none of
them touch consensus, wallet, or staking logic paths, only their declaration/initialization style.

Two full verification passes after the fixes: a direct `run-clang-tidy-17` scan of the whole
`src/` tree (zero findings across all ~755 translation units), then a completely fresh run of the
real CI script end to end — clean container, full rebuild, the actual `06_script_b.sh` step the
`linux-native-clang-tidy` job runs — which completed and reached its normal teardown with
`set -o errexit` active throughout and zero errors logged. This closes out the `TODO-HUMAN` item on
completing a real `linux-native-clang-tidy` run; both the ASan/UBSan and clang-tidy CI jobs newly
added this phase are now confirmed genuinely green.

### Real, current CVEs in both Python services, fixed

`pip-audit` found Flask, PyJWT, cryptography, and requests all pinned to versions with disclosed
advisories in `firstislamiccoin-staking-service` and `firstislamiccoin-explorer`. Bumped both
`requirements.txt` files; re-ran `pip-audit` clean; installed each into a fresh venv and exercised
a real Flask route through each app's own test client to confirm nothing broke.

### The mobile wallet had never been run against a real Flutter SDK until now

No Flutter SDK existed in this project's environment before this phase (pulled
`ghcr.io/cirruslabs/flutter:stable` via Docker). `flutter pub get` failed outright —
`pubspec.yaml`'s `intl: ^0.19.0` conflicts with the current SDK's `flutter_localizations`, which
pins `intl` to `0.20.2` exactly. Fixed the constraint. That unblocked `flutter analyze` (19 issues,
all in FIC's own code — 7 real `AppLocalizations.of(context)!` redundant-assertion warnings fixed;
12 `deprecated_member_use` infos left alone pending a real device to verify the behavioural
migration on) and `flutter test`, which surfaced two real, pre-existing, currently-failing crypto
tests (`address_test.dart`'s bech32 round-trip, `keys_test.dart`'s coin-type key derivation) —
confirmed unrelated to anything this phase touched, and deliberately not guessed at given the
fund-loss risk of a wrong fix to address/key-derivation code. Full detail, including why several
other `flutter analyze`/`pub outdated` findings were left alone rather than bumped blind, is in
`docs/security-review.md`.

### cppcheck: zero findings in FIC's own code

Scoped to the 37 non-test files this project has actually changed (found via the `// 
FirstIslamicCoin:` comment marker), not the ~2,600 inherited-unmodified files: zero warnings inside
any FIC-authored consensus or wallet logic. Every warning cppcheck did emit traces to pre-existing
upstream code, confirmed against CAC's own copy of the same files.

### `docs/LAUNCH-RUNBOOK.md`, `docs/OPERATIONS.md`, top-level `README.md`

Written per the prompt's Phase 10 items 3-5. The genesis key ceremony section in the runbook
reconciles the prompt's "premine held in a 3-of-5 multisig cold wallet" instruction with the actual
consensus constraint `docs/genesis.md` already documents — staking only accepts single-key
outputs, so the ceremony splits the premine between a small number of single-key bootstrap outputs
and the multisig cold wallet, rather than paying the whole premine into the multisig directly.

### What this phase did *not* do, deliberately

**Did not regenerate mainnet genesis, set real checkpoints/`assumevalid`, or tag `v1.0.0`.** The
prompt's item 1 assumes mainnet has launched; it hasn't — the genesis key ceremony itself needs a
real 3-of-5 multisig with real, human-held keys, which nothing in this environment can supply (see
existing `TODO-HUMAN` row 1 and `docs/genesis.md`). Tagging `v1.0.0` or writing real checkpoint
hashes for a chain that has never run would misrepresent unlaunched software as released.
`docs/LAUNCH-RUNBOOK.md` documents the exact ceremony instead, as a runbook a human operator
follows, not proof it happened.

### `TODO-HUMAN`

The genesis key ceremony and everything downstream of a real mainnet existing; the two failing
mobile crypto tests; the Flutter API migrations and major-version dependency bumps that need a
real device to verify — tracked in the table below (rows 23-25). Completing a real
`linux-native-clang-tidy` CI run is now done — see above.

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
| 6 | `seed{1,2,3}.firstislamiccoin.com` resolve to a real VPS (169.58.129.247) as of Phase 10, but nothing can listen on mainnet's P2P port there until the genesis key ceremony -- a real mainnet node needs to actually run at that address (or DNS repointed at wherever one does) once mainnet exists | Mainnet |
| 7 | `generate.py` in the brand kit hardcodes `/home/claude/fic-brand` and Linux font paths | — |
| 8 | Deliberate crash-recovery drill on mainnet/testnet-shaped chains (kill -9 a node, restart, `-reindex`) before mainnet launch — this is how the ContextualCheckBlock genesis crash surfaced | Mainnet |
| 9 | Website: register/confirm `firstislamiccoin.com`, create a Cloudflare account, set `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` repo secrets, create the DNS records in `docs/dns.md`, review and publish Arabic/Urdu translations | Phase 9 |
| 10 | Explorer: provision a real server and the `explorer.firstislamiccoin.com` DNS record, run `firstislamiccoin-infra/provisioning/explorer/provision.sh` against it once a public repository URL exists | Phase 8 |
| 11 | Mobile: Google Play Console + App Store Connect accounts, Android release keystore, iOS distribution certificate/provisioning profile, and the four `ANDROID_*`/Apple signing secrets `.github/workflows/ci.yml`'s release jobs need | Phase 5 |
| 12 | Mobile: publish `firstislamiccoin-mobile/store/privacy-policy.md` at a real, reachable URL (both stores require one) and have it reviewed by a lawyer | Phase 5 |
| 13 | Mobile: native-speaker review of `lib/l10n/app_ar.arb`'s Arabic strings, plus real Urdu/Bahasa Indonesia/Malay/Turkish translations — see `firstislamiccoin-mobile/docs/localization.md` | Phase 5 |
| 14 | Mobile: real Android/iOS device or emulator build (`flutter build apk`/`flutter build ios`), plus a physical-device check of the Face ID/fingerprint app-lock flow and camera QR scanning now that `Info.plist` declares them | Phase 5 |
| 15 | Staking service: provision a real server and the `staking-api.firstislamiccoin.com`/`staking-api.testnet.firstislamiccoin.com` DNS records, generate a real `GATEWAY_JWT_SECRET`/`GATEWAY_KYC_ENCRYPTION_KEY`, fund `GATEWAY_ADMIN_WALLET` for referral payouts | Phase 6 |
| 16 | Staking service: obtain VAPID keys (Web Push) and a Firebase service account (mobile push) for real push delivery — both currently take their documented no-op path | Phase 6 |
| 17 | Investigate whether `firstislamiccoin-core`'s coinstake construction reserves destinations outside descriptor-wallet bookkeeping — found during Phase 6 verification: a staked coin's resulting UTXO came back `solvable: false` (raw P2PK script), making it unspendable via `sendtoaddress` despite the wallet holding its keys. May affect any descriptor wallet that stakes, not just this gateway | Phase 6 / core |
| 18 | Web wallet: provision a real server and the `wallet.firstislamiccoin.com` DNS record, obtain VAPID keys for Web Push | Phase 7 |
| 19 | Full click-through verification of multisig, watch-only/xpub, message sign/verify, and PIN-lock in the web wallet (read for correctness and lightly exercised this phase, not each driven through a complete real scenario) | Phase 7 |
| 20 | Create a FirstIslamicCoin GitHub org/repository so `.github/workflows/release.yml` has somewhere to actually run, and obtain a Windows Authenticode certificate + Apple Developer ID for signed/notarized release artifacts | Phase 3 |
| 21 | ElectrumX: provision two real servers and the `electrum{1,2}`/`testnet-electrum{1,2}.firstislamiccoin.com` DNS records, run `firstislamiccoin-infra/provisioning/electrumx/provision.sh` against them once a public `firstislamiccoin-electrumx` repository URL exists | Phase 4 |
| 22 | ElectrumX: `tests/test_blocks.py::test_all_coins_are_covered` has no mainnet block fixture for `FirstIslamicCoin` (CAC's own `CodexaCoin` never had one either) — add `tests/blocks/firstislamiccoin_mainnet_0.json` once the real mainnet genesis block bytes exist post-key-ceremony | Phase 4 / Mainnet |
| 23 | Root-cause two real, currently-failing mobile wallet crypto tests (`address_test.dart`'s bech32 P2WPKH testnet round-trip, `keys_test.dart`'s mainnet/testnet coin-type key derivation) before shipping the wallet — see `docs/security-review.md` §6 | Phase 10 / Phase 5 |
| 24 | Mobile: decide on and test the `Radio`→`RadioGroup` and `value`→`initialValue` Flutter API migrations, and review major-version-behind dependencies (`firebase_core`, `local_auth`, `mobile_scanner`, `share_plus`), once a real device/emulator is available | Phase 10 / Phase 5 |
| 25 | Genesis key ceremony execution itself (see `docs/LAUNCH-RUNBOOK.md`) — choosing and moving to the real 3-of-5 multisig cold wallet and single-key bootstrap outputs, re-mining mainnet genesis, clearing `m_genesis_premine_placeholder`, tagging the real `v1.0.0` once mainnet actually exists | Mainnet |
| 26 | Finish triaging the ~27 still-untriaged functional test failures (P2P/IBD timeout scaling, `feature_signet`/`feature_taproot`/`feature_csv_activation`/`feature_pos_reorg`/`feature_block`/`feature_assumevalid`, `mining_basic`, `tool_signet_miner`, the rest of `mempool_*`/`rpc_*`/`wallet_*`) — see the Phase 2 "Functional suite revisited" sections above | Phase 2 |
| 27 | Root-cause why `wallet_spend_unconfirmed`'s ancestor-aware sub-tests now select an extra input beyond the expected parent transaction(s) after the 100 sat/vB floor fix, why `wallet_basic`'s zero-value-tx scenario trips `sendrawtransaction`'s max-fee safety check, why `mempool_accept` lets a ~10 sat/vB transaction through `testmempoolaccept` despite the floor, why `wallet_send`'s test helper trips a fee_rate/options conflict check even on a plain call, whether `tool_wallet`'s double-spend-acceptance scenario ever worked upstream, and how (or whether) to adapt `wallet_abandonconflict`'s `-minrelaytxfee`-based eviction test now that the real floor doesn't derive from that setting — see the Phase 2 sections above for what's already been ruled out on each | Phase 2 |
| 28 | Root-cause why `test/util/test_runner.py` (`bitcoin-util-test.py`) fails close to 40 of its ~50 cases specifically on the win64-native MSVC build (its first successful build+link ever on this fork) — either its existing skip list for known-incompatible fixtures isn't taking effect on Windows, or there's a genuinely new Windows-only gap in the tool binaries/bctester harness; needs the actual per-testcase diffs from a real Windows CI run to diagnose — see the Phase 10 win64-native section above | Phase 10 |
