# FirstIslamicCoin and Shariah: design notes

> **This document is not a fatwa.** It is not a religious ruling, a legal
> opinion, or a certification of any kind. It was written by the project's
> engineers to explain, in plain English, what the software does and why it was
> designed that way. No scholar, Shariah board or certification body has
> reviewed or endorsed FirstIslamicCoin. The project intends to seek review
> from a qualified Shariah advisory board; until that review happens, nothing
> here should be relied on as a statement that FIC is permissible.

## What "Shariah-conscious" means here

It means that questions of Islamic finance shaped the design, and that where the
engineering could avoid something widely considered problematic, it tries to.
It does not mean those questions have been answered.

The most important of these choices is how staking rewards work.

## How staking rewards work

FirstIslamicCoin is a proof-of-stake network. Instead of miners spending
electricity, people who hold FIC keep a wallet online and take turns producing
the blocks that record transactions. The protocol chooses who produces each
block at random, weighted by how many coins each participant has put forward.

Whoever produces a block receives **a fixed 10 FIC, plus the fees paid by the
transactions in that block**. This is enforced by every node on the network: a
block that pays itself any other amount is rejected.

### A reward for work, not a return on money held

The 10 FIC is paid for doing something: checking transactions, assembling them
into a block, signing it and publishing it to the network. A participant who
does not run a node and produce blocks receives nothing, however many coins
they hold.

### The amount does not grow with the balance

Every block pays the same 10 FIC. Someone staking 100 FIC and someone staking
100 million FIC receive exactly the same reward *for each block they produce*.
There is no percentage, no annual rate and no figure calculated from the size
of anyone's holding.

This is a deliberate change from the project FIC was built from. CodexaCoin paid
stakers about 13.7 % a year on the value of their coins, multiplied by how long
the coins had been held. That model was removed completely because it resembled
interest on a deposit.

Holding coins for longer earns nothing extra either. Coin age has no effect on
the reward, or on the chance of being chosen.

### A larger stake wins more often

What a larger stake does change is **how often** a participant is chosen. A
participant who puts forward twice as many coins can expect, over time, to
produce about twice as many blocks.

One way to think about this is as proportional participation in a shared
undertaking: each participant contributes coins and the work of running a node,
and the rewards of the undertaking are shared in proportion to what each put
in — in some ways like the profit share in a *mudarabah*-style joint venture.
Whether that comparison actually holds up is exactly the kind of question for a
Shariah advisory board, not for engineers; it is offered only to explain the
intent.

### Rewards are uncertain and not guaranteed

Block production is random. A participant may produce many blocks in a day or
none for a long time. The network does not promise anyone any reward, at any
rate, over any period. If a participant's node is offline, out of date or
connected to the wrong chain, it produces nothing.

FIC's value in other currencies is not fixed either, and can fall as well as
rise. Nothing about the protocol guarantees the worth of a reward.

## Other design choices

- **No developer fund or tax.** No part of any reward goes to the developers or
  anyone else. CodexaCoin had an optional donation to a developer fund; FIC
  removed it from the code.
- **No hidden supply.** The premine is recorded openly in the first block, and
  new coins come into existence only as the fixed per-block reward. The total
  at any height can be checked by anyone; see [`tokenomics.md`](tokenomics.md).
- **No wrapped tokens or exchange listings at launch.** CodexaCoin issued
  wrapped versions of its coin on other blockchains and listed them on
  decentralised exchanges. FIC does not carry that work over; any such step
  would be a separate decision.

## Open questions for review

These have not been resolved and are not claimed to be. They are listed so an
advisory board can see them plainly.

1. **The premine.** 14 billion FIC exist from the first block. Who controls
   them, how they are used and how that is governed are not yet decided.
2. **Whether the staking reward is permissible**, given the reasoning above.
3. **Custodial staking.** A planned optional service would stake on users'
   behalf and pool rewards. Its terms would need their own review.
4. **Speculation and uncertainty** (*gharar* and *maysir*) in holding and
   trading a cryptocurrency whose price can change sharply.
5. **Transaction fees**, and whether their treatment raises any concern.

## Status

| | |
|---|---|
| Shariah advisory board appointed | **No** — `TODO-HUMAN` |
| Review of this document | **Not yet requested** |
| Fatwa or certification | **None** |

This page will be updated only with the outcome of a real review, and will
never name a scholar or board that has not agreed to be named.
