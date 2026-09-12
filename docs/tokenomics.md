# FirstIslamicCoin tokenomics

Every constant that affects how many FIC exist, or how they come into existence.
If a consensus constant touching supply is not in this file, that is a bug in
this file. Source of truth for the values: `firstislamiccoin-core/src/kernel/chainparams.cpp`
and `src/consensus/params.h`; `src/test/fic_genesis_tests.cpp` fails if the two
drift apart.

## Supply in one line

**Supply at height *N* = 14,000,000,000 + 10 × *N* FIC**, less anything
provably burned. Fees move existing coins between people and create none.

## The premine

| | |
|---|---|
| Total | **14,000,000,000 FIC** (1.4 × 10¹⁸ fils) |
| Where it lives | the genesis block's coinbase, as ordinary spendable outputs |
| Shape | **1,000 outputs of 14,000,000 FIC each** |
| When it is spendable | immediately — genesis outputs are exempt from coinbase maturity |
| Mainnet recipient | **placeholder**, pending the genesis key ceremony (`TODO-HUMAN`) |

There are no other premine outputs, no founder reward, no developer fund and no
tax on staking rewards. CodexaCoin's opt-in developer donation was removed from
the code entirely (see `CHANGELOG-FIC.md`).

**Why 1,000 outputs rather than one.** A coin must wait 500 blocks
(`nCoinbaseMaturity`) before it can stake. Genesis outputs are exempt so that
the chain can start, but each staked block turns the output it used into a new
coinstake output that must then wait the full 500 blocks. With a single
premine output the chain would produce block 1 and then stop. With 1,000, there
is always a mature genesis output available until the first coinstake outputs
come of age at height 501, after which the chain sustains itself. Full detail
in [`genesis.md`](genesis.md).

**Why the mainnet recipient is still a placeholder.** It pays a provably
unspendable public key — BIP-341's "nothing up my sleeve" point, whose private
key nobody knows. A mainnet started from it could neither spend nor stake the
premine, so it could never produce a block, and the node refuses to start
mainnet while it is in place. The real recipient is set at the key ceremony,
and mainnet genesis is re-mined then.

The staking kernel accepts only single-key outputs (P2PK, P2PKH, P2WPKH, P2TR).
A multisig cold wallet cannot stake, so the ceremony must decide how much of the
premine sits in single-key hot outputs to bootstrap the chain, and how and when
the rest moves to cold storage. That is a human decision, not a code one.

## The staking reward

| | |
|---|---|
| Per proof-of-stake block | **10 FIC + the fees of that block's transactions** |
| Depends on stake amount | **no** |
| Depends on stake age | **no** |
| Enforced as | an exact amount — a block minting a single fil more *or less* is invalid |
| Parameter | `consensus.nFixedStakeReward = 10 * COIN`, identical on all networks |

A larger stake wins blocks *more often*, in proportion to its size. It does not
earn more per block. There is no rate of return on a balance anywhere in the
protocol, and no maximum stake age.

This replaces CodexaCoin's reward of 13.68 % a year on each staked coin's value
multiplied by its age, capped at 60 days. That formula, its age cap and its
128-bit overflow handling were removed.

`ConnectBlock()` previously counted each block's transaction fees twice, which
let a coinstake claim up to double the fees it collected. That is fixed: fees
are counted once, and the reward must match exactly.

## Halving

| | |
|---|---|
| Parameter | `consensus.nRewardHalvingInterval` |
| At launch | **0 — disabled on every network** |
| When set to *k* | reward at height *h* is `10 FIC >> (h / k)`, reaching zero after 30 halvings |

The code path is implemented and unit-tested so it can be switched on later, but
switching it on changes consensus. It would need a scheduled activation height
and a network upgrade; `docs/OPERATIONS.md` (Phase 10) will describe how.

## Emission

| | |
|---|---|
| Target block spacing | 64 seconds |
| Blocks per year | 31,536,000 s ÷ 64 s = **492,750** |
| New FIC per year | 492,750 × 10 = **4,927,500 FIC** |
| As a share of the premine | 4,927,500 ÷ 14,000,000,000 ≈ **0.035 % a year** |

Emission is per block, not per unit of time, so the real figure follows the real
block count. Difficulty retargets towards 64-second blocks.

Because the reward is a fixed number of coins, annual inflation falls every year
as a share of total supply: 0.0352 % in year one, 0.0334 % after ten years.

## Proof of work

| | Mainnet | Testnet | Regtest |
|---|---|---|---|
| `nLastPOWBlock` | **0** | **0** | 500 (override with `-lastpowblock`) |
| `nPowSubsidy` | 0 | 0 | 28,000,000 |

Mainnet and testnet reject proof-of-work from block 1. Regtest keeps a PoW
window only because the inherited functional-test harness mines blocks on
demand; `-lastpowblock=0` gives regtest mainnet's rules, and FIC's own premine
and reward tests run that way.

## Other constants that bear on supply

| Constant | Mainnet | Testnet | Regtest | Effect |
|---|---|---|---|---|
| `nCoinbaseMaturity` | 500 | 50 | 10 | confirmations before a coinbase or coinstake output can be spent or staked (genesis outputs excepted) |
| Minimum stake age | ≈ 8.9 h | ≈ 53 min | 10 blocks | enforced as the same confirmation depth, not as a timestamp |
| `nTargetSpacing` | 64 s | 64 s | 1 s | |
| `nStakeTimestampMask` | 15 | 15 | 0 | stake timestamps fall on 16-second boundaries |
| `MAX_MONEY` | int64 max | | | inherited from CodexaCoin; flagged for the Phase 10 security review |
| Unit | 1 FIC = 100,000,000 fils | | | |

Minimum transaction fees (`GetMinFee`, inherited from Blackcoin's protocol v3.1)
are paid to the staker and are not burned.
