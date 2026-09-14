# FirstIslamicCoin mainnet launch runbook

This is a runbook for a human operator to follow, not a record of a launch
that has happened. Nothing in this document has been executed — mainnet
cannot start until the genesis key ceremony (§1) replaces the placeholder
premine `docs/genesis.md` already documents, and every step below assumes
real infrastructure (servers, DNS, a GitHub organization) that does not exist
yet (see the `TODO-HUMAN` rows in `docs/CHANGELOG-FIC.md`).

## 0. Before you start

- [ ] Read `docs/genesis.md`, `docs/tokenomics.md`, and `docs/security-review.md` in full.
- [ ] A `FirstIslamicCoin` GitHub organization exists and `.github/workflows/release.yml` /
      `ci.yml` have run successfully at least once against it (`TODO-HUMAN` row 20).
- [ ] `docs/security-review.md`'s open `TODO-HUMAN` items are resolved or explicitly accepted as
      known-at-launch risk by whoever is authorizing this — in particular the two failing mobile
      wallet crypto tests (row 24) should not still be failing when real funds are at stake.
- [ ] Seed, ElectrumX, explorer, and staking-service servers are provisioned (their own
      `firstislamiccoin-infra/provisioning/*/README.md` and `provision.sh` cover each) and DNS
      records from `docs/dns.md` exist and resolve.

## 1. Genesis key ceremony

`docs/genesis.md` already documents the constraint this ceremony has to satisfy: **staking only
accepts single-key outputs** (P2PK, P2PKH, P2WPKH, P2TR) — a coin sitting in a multisig cannot
stake. The 14,000,000,000 FIC premine cannot go straight into a 3-of-5 cold wallet and also
produce blocks. The ceremony therefore splits it:

1. **Decide the split.** Recommended: a small number of the 1,000 premine outputs (enough to keep
   the chain producing blocks past height 500, per `docs/genesis.md`'s "why 1,000 outputs"
   explanation — 10-20 outputs is a comfortable margin) go to single keys the launch operator
   controls directly (a hot/warm wallet, since these need to be online to stake). The remaining
   ~980+ outputs go to addresses derived from a **3-of-5 multisig** whose 5 keys are generated and
   stored following your organization's cold-storage procedure (hardware wallets, air-gapped
   generation, geographically separated key custodians — specify and follow your own procedure
   here; this runbook does not invent one for you).
2. **Generate the bootstrap single-keys and the multisig.** Standard `firstislamiccoin-cli`
   tooling: `getnewaddress` (or `deriveaddresses` from a fresh xpub) for the bootstrap keys;
   `createmultisig 3 '["<pubkey1>","<pubkey2>","<pubkey3>","<pubkey4>","<pubkey5>"]'` for the cold
   wallet, using 5 independently-generated public keys, none of which share a seed.
3. **Pick the launch `nTime`.** Near the actual announced launch time, per `docs/genesis.md`'s
   "Common to every network" table (mainnet's current value, `1789171200`, is a placeholder — a
   real ceremony picks a real one).
4. **Re-mine the genesis block.**
   ```bash
   cd firstislamiccoin-core
   python3 contrib/genesis/generate_genesis.py --network mainnet \
     --time <chosen nTime> --bits 1e0fffff \
     --script <hex-encoded scriptPubKey for the split of bootstrap + multisig outputs>
   ```
   `generate_genesis.py --self-test` (no arguments needed) is worth re-running first, to confirm
   the script still rebuilds CAC's and Blackcoin's own historical genesis blocks exactly before
   trusting it with a real one.
5. **Paste the new hash, merkle root, and nonce into `src/kernel/chainparams.cpp`'s `CMainParams`**,
   replacing the placeholder values, and **remove `m_genesis_premine_placeholder`** (the flag that
   currently makes the node refuse to start mainnet — see `docs/genesis.md` and
   `src/kernel/chainparams.cpp`).
6. **Flip `fic_genesis_tests`'s placeholder expectation** — `docs/genesis.md` calls this out as "a
   deliberate speed bump": the test currently asserts the placeholder flag is set, and needs to
   assert the opposite once it's gone.
7. **Update `docs/genesis.md` and `docs/tokenomics.md`** with the real hash, `nTime`, and premine
   recipient addresses (not the placeholder script) — this is a consensus-affecting constant, and
   per this project's own rule, every one belongs in `docs/tokenomics.md`.
8. **Rebuild, run the full test suite (`make check`, `test/functional/test_runner.py`), and confirm
   `fic_genesis_tests` and `feature_fic_genesis_premine.py` both pass** against the real genesis
   before going further.

Do not skip re-running `--self-test` and the genesis-specific tests. A mistake here is
irreversible once real value is staked on top of it.

## 2. Tag the release

Only after step 1 is committed and its own tests pass:

```bash
git tag -a v1.0.0 -m "FirstIslamicCoin v1.0.0 -- mainnet genesis"
git push origin v1.0.0
```

This triggers `.github/workflows/release.yml` (linux/windows/macos build + draft GitHub Release —
see its own comments for what is and isn't signed). Review the draft release before publishing it.

## 3. Seed node bring-up

Bring up at least 2-3 independent seed nodes (mirroring `docs/dns.md`'s `seed{1,2,3}.
firstislamiccoin.com` reservations) **before** anything downstream, since ElectrumX/explorer/
staking-service all need a synced node to talk to:

1. Provision each server, install the tagged release build (or build from source).
2. Install `contrib/init/firstislamiccoind.service` (systemd) with mainnet config
   (`-listen=1 -maxtipage=<longer than genesis block age>` — see §4 below for why).
3. Start with the bootstrap single-keys' wallet loaded and `staking=1` on **at least one** of
   these nodes, so the chain actually produces blocks once peers connect. Confirm with
   `getstakinginfo` and `getblockcount` advancing.
4. Once 2+ nodes see each other and are producing/relaying blocks, point `seed{1,2,3}.
   firstislamiccoin.com`'s DNS `A`/`AAAA` records at them (`docs/dns.md`).

## 4. The `-maxtipage` gate

`docs/genesis.md`'s "Launch note" applies here directly: a node stays in initial block download
(and therefore never stakes) while its tip is more than 24 hours old, and at launch the tip *is*
the genesis block, whose timestamp is fixed and already in the past by the time anyone starts a
node. **Whoever runs the first staking node(s) must start with `-maxtipage` set longer than
`(now - genesis nTime)`**, or it will sit in IBD forever waiting for a "recent" block that nothing
can produce without first leaving IBD. Once real blocks a few hours old exist, later nodes don't
need this flag.

## 5. ElectrumX

Once at least one seed node is synced and staking:

```bash
# on each of the two electrum{1,2}.firstislamiccoin.com hosts
firstislamiccoin-infra/provisioning/electrumx/provision.sh
```

with `NETWORK=mainnet` and `DAEMON_URL` pointed at a seed node's RPC (or a local node run
specifically for this — either works; `docs/security-review.md`/Phase 4's `CHANGELOG-FIC.md`
section already verified this indexes correctly end-to-end against regtest, the same code path).
Confirm indexing with `blockchain.headers.subscribe` against the live TCP/SSL port (see
`firstislamiccoin-infra/provisioning/electrumx/README.md`'s "Verifying" section) before moving on.

## 6. Explorer and staking service

Both need a synced node's RPC, same as ElectrumX:

```bash
firstislamiccoin-infra/provisioning/explorer/provision.sh          # explorer.firstislamiccoin.com
firstislamiccoin-infra/provisioning/staking-service/                # staking-api.firstislamiccoin.com
```

For the staking service specifically, before real users touch it: generate a real
`GATEWAY_JWT_SECRET`/`GATEWAY_KYC_ENCRYPTION_KEY` (not a dev placeholder), fund
`GATEWAY_ADMIN_WALLET` for referral payouts, and obtain real VAPID keys / a Firebase service
account if push notifications should actually deliver (`docs/CHANGELOG-FIC.md` TODO-HUMAN rows
15-16 track exactly this).

## 7. Web wallet and website

Both are static (no server-side state to bring up) — deploy per their own READMEs
(`firstislamiccoin-web-wallet/README.md`, `firstislamiccoin-website/.github/workflows/deploy.yml`)
to `wallet.firstislamiccoin.com` / `firstislamiccoin.com`. Logically last, since the web wallet's
first real use will call the now-live `staking-api.firstislamiccoin.com` from step 6 — bring that
up first so the wallet isn't pointed at nothing.

## 8. Wallet releases

Desktop: the `v1.0.0` tag from §2 already built these. Mobile: `firstislamiccoin-mobile/.github/
workflows/ci.yml`'s `release-android`/`release-ios` jobs need the signing secrets
`docs/CHANGELOG-FIC.md` TODO-HUMAN rows 11-12 track (Play Console, App Store Connect, Android
keystore, iOS distribution cert) — none of which exist yet. Do not publish to either store until
the two failing crypto tests from `docs/security-review.md` §6 are resolved.

## 9. Announcement copy

A short, honest draft — fill in the bracketed placeholders, and do not add anything to this list
without it being true at the time of publishing:

> FirstIslamicCoin (FIC) mainnet is live. FIC is a proof-of-stake network with a fixed 10 FIC
> block reward — no coin-age weighting, no developer tax, no premine beyond the [N]-output
> genesis allocation documented at firstislamiccoin.com/tokenomics.html. Get started: [wallet
> download links]. Full source: [GitHub org URL]. Block explorer: explorer.firstislamiccoin.com.
>
> FirstIslamicCoin was designed with Islamic finance questions in mind — see
> firstislamiccoin.com/shariah.html for what that does and doesn't mean. **No Shariah board or
> scholar has reviewed or endorsed FIC as of this launch.** [Update this line only once a real
> review has actually happened — see `docs/shariah-compliance.md` and `TODO-HUMAN` row 5. Never
> name a scholar, board, or certification here unless it is real.]

Do not publish any version of this that names a person, board, certification, exchange listing, or
audit firm that has not actually reviewed or listed FIC. `docs/shariah-compliance.md`'s own opening
disclaimer is the standard to match.
