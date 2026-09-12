# CHANGELOG-FIC

Every deviation of FirstIslamicCoin from CodexaCoin, in the order decided.

Upstream baseline: `github.com/fakharnaqvi5313/codexacoin` @ `50b1dce`.

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
via cairosvg), and by visual inspection of the preview sheet. A byte-fresh
rasterization still wants a Linux box or CI run.

---

## Decisions

Three scope decisions taken before Phase 1, after the audit surfaced that the
prompt's assumptions about CAC were wrong in each case.

### Decision 1 — Premine becomes a true genesis output

**Decided:** convert to a spendable genesis-coinbase premine. Drop CAC's
500-block PoW window entirely.

**What CAC does:** mints the 14,000,000,000 premine across a fixed PoW window,
blocks 1–500, at a flat 28,000,000/block (`validation.cpp:1658-1669`), then
`ContextualCheckBlockHeader` rejects PoW forever after. CAC's `PARAMETERS.md` §5
chose this over a genesis output deliberately, because `CreateGenesisBlock()`
carries the Satoshi-derived behaviour where the genesis coinbase is never added
to the UTXO set.

**Why it matters for FIC:** the prompt's chain-parameter table says "Premine
(genesis output)" and "no PoW after genesis". CAC's window contradicts both. A
genesis output makes the no-PoW claim literally true and removes a 500-block
window of PoW from a chain marketed as pure PoS.

**Two changes, not one.** Beyond making the genesis output spendable, there is a
bootstrap deadlock to solve, and it is easy to miss. Stake eligibility requires
500 confirmations (`staking.cpp:161`). A genesis output at height 0 has depth 1;
it needs depth 500; reaching depth 500 needs 499 more blocks; no block can be
produced because no UTXO is eligible and PoW is disallowed. **The chain would
deadlock at height 1 and never start.** This is the same dead zone CAC's
`PARAMETERS.md` §5.2 describes as its reason for sizing the window at exactly
500 — removing the window makes that dead zone permanent rather than transient.

**Approach adopted:**

1. Pass `nPremineTotal` as `genesisReward` to `CreateGenesisBlock()`, with
   `genesisOutputScript` set to the 3-of-5 cold multisig from Phase 10.3.
2. Add the genesis coinbase's outputs to the UTXO set at chainstate
   initialisation. Genesis is connected specially in this lineage —
   `ConnectBlock()` never runs for it — so the coins must be added explicitly.
3. Exempt **only** the genesis output (`coin.nHeight == 0`) from the
   500-confirmation staking-eligibility rule, on both sides:
   wallet (`staking.cpp:161` and the `min_depth` at `:182`) and the consensus-side
   coinstake input check. `nCoinbaseMaturity` stays 500 for every other coin.
4. Set `nLastPOWBlock = 0`. `GetProofOfWorkSubsidy()`'s existing
   `nLastPOWBlock <= 0` guard then returns 0, and PoW is disallowed from block 1.
5. Rewrite `scripts/audit_premine_supply.py` to assert the genesis output equals
   exactly `14e9 * COIN` and that no coins are ever minted outside coinstakes.

Checked and clear: `MAX_MONEY` is `int64_max` in this tree
(`consensus/amount.h:27`), so a single 1.4×10¹⁸-satoshi output passes
`MoneyRange()`. Separately, `MAX_MONEY = int64_max` removes upstream's
overflow-guard headroom — inherited from CAC, flagged for Phase 10.2 security
review, not changed here.

Regtest must prove, before Phase 1 acceptance: the chain starts and produces
block 1 by PoS from the genesis UTXO; the genesis output is spendable; no PoW
block is accepted at any height; and total supply at height *N* is exactly
`14e9 + 10N`.

**Risk accepted:** step 3 is a consensus rule that exists solely to let the chain
start, and a single 14 B UTXO means exactly one stake kernel attempt per eligible
timestamp until the premine is split. Phase 2's distribution across 5 wallets
should happen immediately after launch. Both go in `docs/tokenomics.md`.

### Decision 2 — Strip the developer donation

**Decided:** remove it entirely.

The audit found it is already inert, which makes removal cheap: it is
**wallet-side, not consensus** (`-donatetodevfund` shapes the coinstake a
staker's own wallet builds; no validation rule requires it),
`MIN_DONATION_PERCENTAGE = 0` so it is genuinely opt-out-able despite the 20 %
default, and `vDevFundAddress = {}` on all four networks
(`chainparams.cpp:759,876,1004,1140`) means
`isDevFundEnabled` is always false. It has never paid out.

Removal covers `staking.cpp:539-572`, `wallet.cpp:3104-3110`,
`wallet.h:144-146,724`, `interfaces.cpp:503`, `chainparams.cpp` (`vDevFundAddress`,
`GetDevFundAddress`, `GetDevFundScript`), `kernel/chainparams.h:129,180`, and the
Qt "% of stake rewards" label at `overviewpage.cpp:199,226,257`.

Satisfies the prompt's "never introduce hidden premine outputs, developer taxes,
or backdoors" as a removal rather than a promise.

### Decision 3 — Drop the issuer and DEX components

**Decided:** `base-issuer/`, `bnb-issuer/`, `stellar-issuer/` and
`checkout-widget/` are not carried into FIC.

CAC has live wrapped-token listings — BEP-20 on BNB Chain via PancakeSwap,
ERC-20 on Base via Uniswap, with the BscScan contract source verified. None of it
appears in the FIC prompt's target layout, and a wrapped-token DEX listing raises
questions beyond scope that belong with the Shariah advisory review, not with an
engineering rebrand.

FIC ships the L1, its wallets, and its own infrastructure. No DEX listing, no
wrapped representations, no merchant widget at launch. Revisitable later as an
explicit decision with advisory input; not a silent carry-over.

---

## Prompt items that need no work

Recorded so no one "fixes" already-correct code. Both verified against source,
not taken from CAC's docs.

**Kernel stake weight is already amount-only.** The prompt's reward-model item 2
says to remove an age factor from `CheckStakeKernelHash` if CAC multiplies weight
by age. It does not — `pos.cpp:90` is `arith_uint256 bnWeight = arith_uint256(nValueIn)`,
no age term, inherited from Blackcoin as its defence against coin-age hoarding.
Coin age in CAC affects the reward formula only. FIC's "stake weight proportional
to coin amount only" requirement is **already the existing behaviour** and needs
zero consensus work.

**`nMinimumChainWork` and `defaultAssumeValid` are already zeroed**
(`chainparams.cpp:181-184`). Of the things Phase 1 step 6 says to clear, only
`checkpointData` holds real values — 501 hashes frozen from CAC's live mainnet.

---

## Open `TODO-HUMAN`

| # | Item | Blocks |
|---|---|---|
| 1 | Confirm the Decision 1 approach, particularly the genesis-only staking exemption | Phase 1 |
| 2 | **P2CS does not exist in CAC.** The prompt assumes it is reusable in Phases 3.4, 5.3, 6.2, 7.2 and 8.2; `PARAMETERS.md` §14 is a design doc for an unbuilt feature. Build the consensus feature, or ship custodial-only and defer? | Phase 3 |
| 3 | Minimum stake age: accept CAC's depth-based eligibility (500 conf ≈ 8.89 h) and restate the prompt's "8 hours", or add a real `nStakeMinAge` field | Phase 1 |
| 4 | Genesis phrase has 1 byte of scriptSig headroom (99/100). Swap the em-dash for an ASCII hyphen for 3? | Phase 1 |
| 5 | Register BIP44 coin type 9770 via SLIP-0044 PR. Unregistered, same status as CAC's 3377 | Phase 10 |
| 6 | Shariah advisory board review. No endorsement, scholar name, or certification to be written anywhere until real | Phase 9 |
| 7 | Genesis key ceremony: generate the 3-of-5 cold multisig that receives the premine output | Phase 1 |
| 8 | `generate.py` hardcodes `/home/claude/fic-brand` and Linux font paths | — |
| 9 | Verify ElectrumX full block indexing end-to-end on Linux — never done upstream | Phase 4 |
| 10 | A Linux host or container is required. Nothing in this repo can be built on this Windows machine | Phase 1 |
