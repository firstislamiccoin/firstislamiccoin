# CodexaCoin audit — the starting point for FirstIslamicCoin

Phase 0, step 1. Audit of `github.com/fakharnaqvi5313/codexacoin` at commit
`50b1dce` ("Add CAC/USD price alerts, web PancakeSwap swap link"), 91 commits,
99 MB working tree.

Everything below was read out of the tree or verified against source. Where CAC's
own `PARAMETERS.md` makes a claim, I checked it against the code and say so.

---

## 1. Shape of the repository

CAC is a **single monorepo**, not the nine separate repositories the FIC prompt's
target layout assumes. See [`repo-map.md`](repo-map.md) for the directory → FIC
mapping.

| Directory | Files | What it is | State |
|---|---:|---|---|
| `codexacoin-core/` | 2,650 | The node: `codexacoind`, `codexacoin-cli`, `CodexaCoin-Qt` | Builds; mainnet live |
| `cac_wallet/` | 110 | Flutter mobile wallet (Android + iOS) | Builds; store-ready metadata written |
| `web-wallet/` | 11 | Browser light wallet | Deployed |
| `vps-gateway/` | 16 | REST API + custodial staking pool | Deployed |
| `explorer/` | 9 | Block explorer (Flask + static frontend) | Deployed |
| `electrumx-cac/` | 274 | Electrum protocol server | **Indexing never verified** |
| `faucet/` | 5 | Testnet faucet | Works |
| `provisioning/` | 20 | systemd/Docker/nginx deploy scripts | In use |
| `docker/` | 4 | Multi-node regtest environment | Works |
| `website/` | 13 | Marketing site | Deployed |
| `base-issuer/` | 9 | Wrapped ERC-20 on Base (Uniswap) | Live — **dropped for FIC** |
| `bnb-issuer/` | 10 | Wrapped BEP-20 on BNB Chain (PancakeSwap) | Live — **dropped for FIC** |
| `stellar-issuer/` | 9 | Stellar asset issuer | **dropped for FIC** |
| `checkout-widget/` | 3 | Merchant payment widget | **dropped for FIC** |
| `docs/` | 2 | `mobile-api.md`, `store-compliance.md` | — |

Two root documents are the real value of this repo and should be read before any
code is touched:

- **`PARAMETERS.md`** (3,459 lines) — the single source of truth for every
  consensus constant, with a per-phase "what was actually verified, and what
  wasn't" record. Unusually honest; several sections document bugs found only by
  running the node rather than by inspection.
- **`CHANGELOG.md`** (1,746 lines) — phase-by-phase build history.

## 2. Build system and tests

`codexacoin-core` is **autotools** (`configure.ac`, `Makefile.am`, `autogen.sh`,
`depends/`) — i.e. pre-CMake Bitcoin Core lineage. Plan Phase 1/3 around
autotools, not the CMake build Bitcoin Core 29+ uses.

- 107 unit-test files in `src/test/`
- 228 functional tests in `test/functional/`
- `src/test/pos_tests.cpp` is the coin-age reward suite (7 cases: overflow,
  age cap, full-year calibration, kernel-independence statistical test).
  **This is the file FIC replaces** with `fic_reward_tests.cpp`.

### What builds, per CAC's own record (§9, §10.1)

| Target | Status |
|---|---|
| Linux x86_64, full GUI | Built natively in Ubuntu 22.04 Docker; **live-verified** (ran regtest, `createwallet`/`getnewaddress` over RPC) |
| Windows x86_64 | Cross-compiled via mingw-w64 through `depends/`, **CLI only, no Qt**. Valid PE32+ binaries; never runtime-tested on Windows or Wine |
| macOS | `qt@5` built from source, `CodexaCoin-Qt.app` verified launching, packaged to `.dmg`. **Not codesigned, not notarized** |
| `.github/workflows/release.yml` | Written but **never run end-to-end on GitHub Actions** |

Fixing the Windows leg uncovered two real portability bugs upstream: missing
`<cstdint>` includes across ~50 headers, and a stack-protector link conflict.
Those fixes are in the tree and carry over to FIC for free.

**I could not build anything locally this phase.** This is a Windows host with no
autotools toolchain, no Docker, and no `depends/` prerequisites. Phase 1's build
acceptance needs a Linux host or container.

## 3. Consensus parameters as they stand

From `src/kernel/chainparams.cpp` and `src/consensus/params.h`.

| Parameter | CAC mainnet | FIC target |
|---|---|---|
| Magic | `0x74 0x80 0x2a 0xa6` | `0xF1 0x1C 0x51 0xA3` |
| P2P / RPC port | 16210 / 16211 | 19770 / 19771 |
| P2PKH prefix | 28 → `C…` | 36 → `F…` |
| P2SH prefix | 63 → `S…` | 28 → `C…` |
| WIF prefix | 156 | 164 |
| Bech32 HRP | `cac` | `fic` |
| BIP44 coin type | 3377 (**unregistered**) | 9770 (**also unregistered**) |
| Block spacing | 64 s | 64 s (unchanged) |
| Coinbase maturity | 500 | 500 (unchanged) |
| Premine total | 14,000,000,000 CAC | 14,000,000,000 FIC |
| Genesis nTime | 1785326400 | 1789171200 |
| Genesis nVersion | **7** | 7 (must keep — see below) |

Note the P2SH collision: FIC's P2SH prefix (28, `C…`) is exactly CAC's *P2PKH*
prefix. Harmless across separate networks, but it means a CAC P2PKH address and
an FIC P2SH address look alike. Worth a line in the launch comms.

### Three inherited traps to preserve

All three were found by CAC only by *running* the node, not by reading code, and
all three will bite FIC identically when genesis is regenerated:

1. **Genesis `nVersion` must be 7, not 1.** `CheckBlockHeader()` rejects
   `nVersion < 7` once `IsProtocolV2(blockTime)` is true, and any 2026 timestamp
   is well past the inherited `nProtocolV2Time`/`V3Time`/`V3_1Time` thresholds.
2. **PoW validation uses `GetPoWHash()` (scrypt), never `GetHash()` (SHA256d).**
   `primitives/block.cpp::GetHash()` is version-conditional; PoW checking is not.
   CAC's first genesis-mining attempts checked the wrong hash and every candidate
   silently failed `high-hash`.
3. **The coinbase scriptSig has a hard 100-byte consensus limit** —
   `src/consensus/tx_check.cpp:51` requires
   `2 <= tx.vin[0].scriptSig.size() <= 100`. CAC hit `bad-cb-length` at genesis
   load with an earlier, longer candidate headline.

   FIC's specified phrase **fits, but only just.** The scriptSig is built as
   `CScript() << 0 << CScriptNum(42) << pszTimestamp`
   (`chainparams.cpp:56`), so the encoded size is
   1 byte `OP_0` + 2 bytes for `CScriptNum(42)` + the phrase's push prefix +
   the phrase itself. At 94 UTF-8 bytes the phrase needs `OP_PUSHDATA1`
   (2-byte prefix), giving:

   | Phrase | Phrase bytes | scriptSig | Spare |
   |---|---:|---:|---:|
   | CAC's live phrase (reference) | 45 | 49 / 100 | 51 |
   | FIC as specified, em-dash `—` | 94 | **99 / 100** | **1** |
   | FIC with ASCII hyphen `-` | 92 | 97 / 100 | 3 |

   Valid as written — but with **one byte of headroom**, so any single added
   character breaks genesis. The em-dash costs 3 bytes for 1 character;
   substituting an ASCII hyphen buys 2 more bytes of margin at no real cost to
   the text. Recommended, not required. Recorded in
   [`CHANGELOG-FIC.md`](CHANGELOG-FIC.md).

CAC's genesis generator is `contrib/genesis/generate_genesis.cpp` — **C++, not
Python**, compiled manually against the built static libs and deliberately not
wired into `Makefile.am`. The FIC prompt asks for a `generate_genesis.py`; port
the working C++ tool rather than writing a Python scrypt miner from scratch.

## 4. The reward model — what actually has to change

Better news than the prompt assumes. The coin-age logic is tightly localised:

| Location | Role |
|---|---|
| `src/consensus/params.h:142-144` | `nStakeRewardAnnualBP` = 1368, `nStakeRewardAgeCapSeconds` = 60 d |
| `src/kernel/chainparams.cpp:176,813,967,1065` | Those two values, set per network |
| `src/pos.cpp:243` | `ComputeCoinAgeReward()` — the formula |
| `src/pos.cpp:265-304` | `GetCoinstakeMaxReward()` — sums it across coinstake inputs |
| `src/wallet/staking.cpp:377,467,523,532-545` | Coinstake construction |
| `src/validation.cpp` (`ConnectBlock`, `nMaxStakeReward`) | Consensus enforcement |
| `src/qt/overviewpage.cpp:234-244` | UI monthly-yield projection |
| `src/test/pos_tests.cpp` | The 7-case coin-age test suite |

1368 bp = 13.68 % simple annual = 1.14 %/month, capped at 60 days of age per
input, computed in 128-bit intermediates because `14e9 × 1e8 × 5,184,000`
overflows `int64`. Under FIC's fixed reward, **all of that arithmetic and its
overflow handling disappears.**

### Prompt item 2 is already satisfied — do not "fix" it

The FIC prompt says: *"If CAC's kernel multiplies weight by age, remove the age
factor."* It does not. Verified at `src/pos.cpp:87-91`:

```cpp
int64_t nValueIn = prevoutValue;
if (nValueIn == 0)
    return error("CheckStakeKernelHash() : nValueIn = 0");
arith_uint256 bnWeight = arith_uint256(nValueIn);
bnTarget *= bnWeight;
```

Amount-only, no age term — this is Blackcoin's own defence against coin-age
hoarding, inherited untouched. Coin age in CAC affects **only** the reward
formula, never kernel weight or stake eligibility. So FIC's "stake weight
proportional to coin amount only" requirement needs **zero consensus work**; it
is the existing behaviour. Removing the reward formula is the whole job.

### `GetProofOfStakeSubsidy()` is a free win

`src/validation.cpp:1671-1688` currently returns a hardcoded `COIN * 3 / 2` as a
dead legacy placeholder. `ConnectBlock()` does not consult it; only
`coinstatsindex.cpp` and `getblockstats`'s `subsidy` field do — which CAC
documents as **reporting wrong numbers**, tracked as an unfixed follow-up.

Under a fixed per-block reward this function becomes authoritative again. Making
it return `consensusParams.nFixedStakeReward` fixes that reporting bug as a side
effect rather than carrying it forward.

### "Minimum stake age" is not a field

The FIC prompt's table specifies minimum stake age 8 h / 1 h / 0. **No such
timestamp field exists in this codebase.** The old Peercoin-lineage `nStakeMinAge`
is gone; PoS v3+ enforces stake eligibility by *confirmation depth* instead —
`src/wallet/staking.cpp:161`:

```cpp
if (wallet.GetTxDepthInMainChain(*pcoin.first) >= Params().GetConsensus().nCoinbaseMaturity)
```

At 500 confirmations × 64 s ≈ **8.89 hours**, which is why the spec's "8 hours"
and the real rule land in nearly the same place — but the mechanism is depth, not
elapsed seconds. FIC has to either accept depth-based eligibility and restate the
docs, or add a real `nStakeMinAge`. Recorded as an open decision.

## 5. Premine: the mechanism is not what the prompt says

The FIC prompt's table reads *"Premine (genesis output) 14,000,000,000 FIC (same
as CAC)"*. CAC does **not** use a genesis output. Per `PARAMETERS.md` §5 and
`src/validation.cpp:1658-1669`:

- `nLastPOWBlock = 500`; `GetProofOfWorkSubsidy()` returns
  `nPremineTotal / nLastPOWBlock` = a flat **28,000,000 CAC** for blocks 1–500
- exact integer division, no remainder, no dust
- all 500 blocks mined privately pre-launch, then all 501 hashes (genesis→500)
  hardcoded into `checkpointData`
- at block 501 `ContextualCheckBlockHeader` rejects further PoW permanently

CAC chose this over a genesis output for a hard reason, documented in §5:
`CreateGenesisBlock()` carries the standard Satoshi-derived behaviour where **the
genesis coinbase is never added to the UTXO set** — the function's own doc comment
says the output *"cannot be spent since it did not originally exist in the
database."* A spendable genesis premine is therefore not reachable without
patching UTXO-set initialisation.

### And there is a second, worse problem

`PARAMETERS.md` §5.2 documents why the window is 500 blocks and not fewer: stake
eligibility needs 500 confirmations, so a shorter PoW window leaves a **dead zone**
where PoW is already disallowed but no UTXO is yet stake-eligible — and nobody can
produce a block at all.

Removing the PoW window entirely makes that dead zone permanent. A genesis output
at height 0 has depth 1; it needs depth 500 to stake; reaching depth 500 needs 499
more blocks; no block can be produced because no UTXO is eligible and PoW is
disallowed. **The chain deadlocks at height 1 and never starts.**

So "true genesis output" is two consensus changes, not one:

1. Add the genesis coinbase output to the UTXO set at chainstate init.
2. Exempt that output from the 500-confirmation staking-eligibility rule, or the
   chain cannot bootstrap.

See [`CHANGELOG-FIC.md`](CHANGELOG-FIC.md) for the approach adopted.

## 6. The developer donation is dead code, not a live tax

`src/wallet/staking.cpp:539-572`, `src/wallet/wallet.cpp:3104-3110`,
`src/wallet/wallet.h:144-146`:

```cpp
static const unsigned int DEFAULT_DONATION_PERCENTAGE = 20;
static const unsigned int MIN_DONATION_PERCENTAGE = 0;
static const unsigned int MAX_DONATION_PERCENTAGE = 95;
```

Three things make this benign, and they matter for the "no developer taxes"
requirement:

- It is **wallet-side, not consensus** — it shapes the coinstake a staker's own
  wallet builds, via `-donatetodevfund`. No validation rule requires it.
- `MIN_DONATION_PERCENTAGE = 0`, so it is genuinely opt-out-able despite the 20 %
  default.
- `vDevFundAddress = {}` on **all four networks**
  (`chainparams.cpp:759,876,1004,1140`), so
  `isDevFundEnabled = (m_donation_percentage > 0 && !GetDevFundAddress().empty())`
  is **always false** as shipped.

It has never paid out a satoshi. Stripping it is dead-code removal across ~8
call sites plus the Qt "% of stake rewards" label, not consensus surgery.

## 7. Cold staking / P2CS does not exist

This is the largest gap between the prompt and reality.

`PARAMETERS.md` §14 is explicit: Phase 6 was deliberately limited to custodial
pooling, and the codebase has **"no cold-staking script support at all"** —
confirmed by searching for any delegation opcode or P2CS template before writing
that section. I re-ran the search independently: `grep -rlI "P2CS\|ColdStake\|coldstake" codexacoin-core/src/`
returns **nothing**.

§14 is a design document for a feature that was never built. It correctly
describes what building it needs: a new `OP_CHECKCOLDSTAKEVERIFY`-style opcode in
the `OP_NOP` range, a new output-script template, script-interpreter changes,
coinstake validation changes, wallet support, and a consensus activation path.

The FIC prompt assumes P2CS is available for reuse in **five** places:

| Prompt location | Assumption |
|---|---|
| Phase 3.4 | "Cold Staking (P2CS) delegation dialog **reused from CAC**" |
| Phase 5.3 | mobile "Cold Staking" screen constructing P2CS delegations |
| Phase 6.2 | non-custodial P2CS mode with reward-only fee split |
| Phase 7.2 | web wallet P2CS delegation UI |
| Phase 8.2 | explorer P2CS delegation stats |

None of it can be reused, because none of it exists. This is a ground-up
consensus feature plus UI surface in four clients — plausibly larger than the rest
of the FIC prompt combined. It needs a scope decision before Phase 3.

What *does* exist is `vps-gateway/staking.py` — the **custodial** pool (CAC's
"6A"), with proportional reward distribution, payout jobs and an audit log. That
covers the prompt's Phase 6.3 and carries over directly.

## 8. Other gaps between prompt and reality

| Prompt expects | CAC actually has |
|---|---|
| `firstislamiccoin-electrumx` syncing full testnet | ElectrumX adapted from `electrumx-blk`; RPC connectivity verified, **full block indexing never verified end-to-end** (blocked on a macOS-12 Python C-extension packaging issue; the Dockerfile is believed to sidestep it but that was never run) |
| Web wallet in React + TypeScript + Vite | Static vanilla JS, **no build step** (`app.js`, `crypto.js`, `storage.js`, …). Prompt allows "or match CAC's stack" |
| Explorer as a `btc-rpc-explorer` fork | Custom Flask app (`app.py`, `rpc.py`, `style.css`). Prompt allows reusing CAC's stack |
| Staking service, FastAPI or Node | Python (`vps-gateway/`), incl. `kyc.py`, `referral.py`, `push.py`, `price_alerts.py` |
| Palette greps `0B2A45\|F0C24E` | Match **zero files**. CAC's real palette is gold `#F0C350` with dark purples `#1C1922`, `#121016`, `#0D0B11`, `#201A08`, `#322C3A` |
| BIP39 Arabic/Urdu wordlists | Not present. Prompt already says English-only unless the library supports them — **do not invent wordlists** |

## 9. CAC mainnet is live — FIC is a fresh chain, not a continuation

Worth stating plainly because it shapes Phase 1 step 6 and Phase 10:

- The 500-block premine window was mined **live on mainnet on 2026-08-01** and
  audited to exactly `14,000,000,000.00000000 CAC` with zero drift
- 501 block hashes are hardcoded in mainnet `checkpointData`
- wrapped-token listings are **live**: PancakeSwap on BNB Chain, Uniswap on Base
- the CAC contract source is verified on BscScan

So `checkpointData`, `chainTxData`, `nMinimumChainWork` and `defaultAssumeValid`
must all be cleared for FIC. `nMinimumChainWork` and `defaultAssumeValid` are
**already** `uint256{}` in CAC (`chainparams.cpp:181-184`) — only
`checkpointData` carries real values that must go.

## 10. Rebrand surface

Generated into [`rebrand-manifest.txt`](rebrand-manifest.txt): **375 unique files**
need edits.

| Pattern | Files |
|---|---:|
| `codexacoin` | 220 |
| `CodexaCoin` | 231 |
| `CODEXACOIN` | 7 |
| `\bCAC\b` (ticker; review each) | 93 |
| CAC palette hexes | see manifest |

The `\bCAC\b` hits need manual review — the prompt's own warning about ticker
contexts applies, and some hits are unrelated acronyms.

## 11. Open decisions

Carried into [`CHANGELOG-FIC.md`](CHANGELOG-FIC.md). Only the first genuinely
blocks Phase 1.

1. **Genesis premine bootstrap** — how the genesis output becomes stake-eligible
   without a PoW window (§5 above). An approach is adopted in `CHANGELOG-FIC.md`;
   confirm before implementation.
2. **Genesis phrase leaves 1 byte of scriptSig headroom** (99/100). Valid, but
   swapping the em-dash for an ASCII hyphen raises that to 3 (§3).
3. **Minimum stake age** — accept depth-based eligibility and restate the docs, or
   add a real `nStakeMinAge` field (§4).
4. **P2CS scope** — build the consensus feature, or ship custodial-only at launch
   and defer non-custodial delegation (§7).
5. **BIP44 coin type 9770** — unregistered, same status as CAC's 3377. SLIP-0044
   PR needed.
6. **ElectrumX indexing** — must be verified end-to-end on Linux before Phase 4
   can claim acceptance.
