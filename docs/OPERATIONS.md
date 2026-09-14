# FirstIslamicCoin operations

Backups, upgrades, incident response, and how the halving schedule this
project deliberately shipped disabled would be turned on later. Written for
whoever operates seed nodes, ElectrumX, the explorer, and the staking service
after launch — see `docs/LAUNCH-RUNBOOK.md` for bringing them up the first
time.

## Backups

| What | Where | How |
|---|---|---|
| Node wallet (bootstrap staking keys) | `~/.firstislamiccoin/wallets/<name>/wallet.dat` (or the wallet's SQLite file, per `-descriptors`) | `firstislamiccoin-cli backupwallet <path>`, taken after every new address/key is generated, stored off-host and encrypted at rest |
| Genesis ceremony multisig keys | Wherever your cold-storage procedure puts them (§1 of `docs/LAUNCH-RUNBOOK.md`) | Follow that procedure's own backup/redundancy requirements — this document does not set cold-storage policy |
| ElectrumX UTXO/history DB | `DB_DIRECTORY` (`/var/lib/firstislamiccoin-electrumx/db` per `provisioning/electrumx/provision.sh`) | **Not precious** — it's a derived index. Losing it means a re-sync from the node, not data loss. Back up only if a full resync would be unacceptably slow for your setup |
| Staking-service database | Wherever `firstislamiccoin-staking-service/db.py` points (see its own README) | Regular dump on whatever schedule matches your acceptable data-loss window — this holds user deposit/referral/KYC records, unlike ElectrumX's derived data |
| `GATEWAY_JWT_SECRET` / `GATEWAY_KYC_ENCRYPTION_KEY` / VAPID keys | Wherever your secrets manager holds them | Rotating any of these invalidates existing sessions/subscriptions — coordinate before rotating, don't lose them without a rotation plan already in motion |

Test restores, not just backups: a backup nobody has restored from is a hope, not a backup.

## Upgrades

1. **Node (`firstislamiccoind`)**: read the release's changelog for any `-reindex` or
   `-reindex-chainstate` requirement before upgrading (consensus-affecting changes will say so).
   Upgrade seed nodes one at a time, confirming each rejoins the network and matches the others'
   `getbestblockhash` before moving to the next — never upgrade every seed node simultaneously.
   A staking node's wallet does not need to be closed for a binary upgrade; a version with a
   different wallet format might, per its own release notes.
2. **ElectrumX**: stop the service, upgrade, restart — it re-syncs any blocks it missed while
   down. No special handling needed since its DB is a disposable index (see Backups above).
3. **Explorer / staking service (Flask apps)**: `pip install -r requirements.txt` inside the
   existing venv, restart the systemd unit (`gunicorn` reload is safe — no persistent
   in-process state beyond what's already in the database). Re-run
   `pip-audit -r requirements.txt` as part of every upgrade, not just at launch — see
   `docs/security-review.md` §5 for why this matters (real CVEs were found in pinned versions
   during Phase 10; new ones will appear over time).
4. **Web wallet / website / explorer frontend**: static files, redeploy any time, no
   coordination needed with the backend services they call.
5. **Mobile app**: store review lag means a consensus-breaking node upgrade should ship with
   enough lead time for the app update to reach most users before enforcement height, if the
   mobile app itself encodes any consensus-sensitive logic (fee calculation, address versions).

A **consensus-changing** node upgrade (the halving activation below is the one this project has
built and disabled; any other future one) needs every seed node, and ideally every actively
staking node, upgraded before its activation height — a node still running the old rules will
reject blocks the new rules produce (or vice versa), causing a chain split. Announce the upgrade
and activation height well before it arrives, the way Bitcoin Core's own soft-fork activations do.

## Incident response

**Node crash or corruption**: restart with `-reindex-chainstate` (faster, keeps block files) or
`-reindex` (slower, rebuilds from raw blocks) as appropriate. If the datadir itself is suspect,
restore from another synced node's `blocks/`+`chainstate/` directories or resync from peers —
never restore a *wallet* file from another node's datadir, only from its own backup.

**Suspected chain split / stuck chain**: compare `getbestblockhash` and `getblockcount` across
every seed node. A node that's behind and not catching up: check its peer count
(`getpeerinfo`) and whether `-maxtipage` is still needed (only relevant in the first hours after
launch — see `docs/genesis.md`). A node that disagrees on the *same height*: do not act
unilaterally — this is a potential consensus bug or an actual attack, and needs the same kind of
deliberate crash-recovery-drill thinking `docs/CHANGELOG-FIC.md` TODO-HUMAN row 8 already flags as
untested. Preserve the divergent node's state (don't reindex it away) before investigating.

**Staking-service incident (deposit/balance discrepancy, suspected unauthorized access)**:
`firstislamiccoin-staking-service/watcher.py` and the audit log (`docs/CHANGELOG-FIC.md` Phase 6)
are the first places to check. Rotate `GATEWAY_JWT_SECRET` if session compromise is suspected —
this invalidates every existing session, so pair it with user communication. Never restore user
balances from anything other than the chain itself (`firstislamiccoin-cli listunspent` / the
gateway's own transaction history) — the database is a cache of chain state, not its source of
truth.

**Key ceremony key compromise (any of the 5 multisig keys, post-launch)**: this is why it's 3-of-5
and not 5-of-5 — rotate the compromised key by moving the multisig's funds to a freshly-generated
3-of-5 (or higher) multisig using the remaining 4 (or fewer, if more are compromised) plus new
keys, via a standard multisig-to-multisig transaction. Do this the moment compromise is suspected,
not after confirming it.

## Enabling the halving schedule

`consensus.nRewardHalvingInterval` (`src/consensus/params.h`) is **0 on every network at launch —
halving is built, unit-tested, and deliberately disabled** (see `docs/tokenomics.md`). Turning it
on is a consensus change, not a config toggle:

1. **This needs a community decision first**, per the prompt's own framing ("if the community
   later votes for it") — whatever governance process FirstIslamicCoin actually adopts (not
   specified anywhere in this codebase; decide and document it before using this section).
2. **Pick an activation height**, not "now" — enough blocks in the future that every node
   operator has time to upgrade. Bitcoin Core's own soft-fork activation lead times (months, not
   days) are the right order of magnitude to think in for a change every staking node must apply
   in lockstep.
3. **Pick the interval** (`nRewardHalvingInterval`, in blocks). `StakeReward()` already implements
   `10 FIC >> (height / interval)`, floor-dividing and right-shifting, reaching exactly 0 after 63
   halvings (the code guards the 64-bit shift-overflow case explicitly).
4. **Implement the height gate.** The cleanest approach, matching how this codebase already
   activates other height-conditional rules (see `nProtocolV2Time`/similar in
   `kernel/chainparams.cpp`): set `nRewardHalvingInterval` to a real value only from the chosen
   activation height onward — either by keying `StakeReward()`'s halving branch off
   `nHeight >= nHalvingActivationHeight` in addition to the interval, or by giving
   `nRewardHalvingInterval` itself a per-height rule. Whichever shape is chosen, **add the new
   activation-height constant next to the other consensus constants in `docs/tokenomics.md`** —
   this project's own rule is that no consensus-affecting constant exists undocumented there.
5. **Extend `src/test/pos_tests.cpp`** (or add a dedicated test) asserting the reward is still
   `nFixedStakeReward` immediately before the activation height and exactly half immediately after
   — an off-by-one here pays or burns real value at a real, public, unrepeatable moment.
6. **Ship it in a tagged release with enough lead time before the activation height** that seed
   node operators, ElectrumX/explorer operators (unaffected by this specific change, but should
   still run current software), and staking node operators have all upgraded. A staking node
   still on old rules at the activation height will produce blocks the upgraded network rejects.
7. **Do not backdate or retroactively change past rewards.** Halving only ever applies going
   forward from the activation height; every already-mined block keeps whatever reward it was
   actually paid.

## Consensus constants: keep `docs/tokenomics.md` current

Every value in this document that affects consensus (fixed reward, halving interval and
activation height if enabled, coinbase maturity, block spacing) must have a matching entry in
`docs/tokenomics.md`. If you change one without updating the other, that is a bug in
`docs/tokenomics.md`, not a documentation nice-to-have — this is the project's own standing rule,
repeated here because operations work is exactly where a quiet undocumented consensus change is
most likely to slip in unnoticed.
