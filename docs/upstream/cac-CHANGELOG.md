# Changelog

All notable changes to the CodexaCoin project. Format is loosely
[Keep a Changelog](https://keepachangelog.com/); dates are UTC.

## Phase 1 — Fork, rebrand, and reconfigure the core

### 2026-07-31

- **Fork imported.** Cloned `CoinBlack/blackcoin-more` at commit
  `223024fb2fe04be7d3e720dd1660f6e10ab72c88` (`master`/`28.x`, v26.2.x line)
  into `codexacoin-core/`, committed as a pristine baseline before any changes.
- **`PARAMETERS.md` added.** Single source of truth for every
  consensus-relevant constant: magic bytes, ports, address prefixes, bech32
  HRP, BIP44 coin type (placeholder), premine design, staking reward
  formula, and `MAX_MONEY`/`int64` supply-ceiling analysis with 20-year
  projections at 25/50/100% network participation.
- **Full rebrand.** `blackcoin`/`Blackcoin`/`BLACKCOIN`/`BLK` →
  `codexacoin`/`CodexaCoin`/`CODEXACOIN`/`CAC` across source, build scripts,
  Qt resources/forms, man pages, contrib/init service files, and binary
  names (`blackmored` → `codexacoind`, `blackmore-{cli,tx,qt,util,wallet,
  chainstate,node,gui}` → `codexacoin-*`). Generated a placeholder app icon
  and replaced every `bitcoin.{png,ico,icns,xpm}` icon file in place.
  Preserved all original copyright attribution per the MIT license (see
  commit message on the rebrand commit for the details of what had to be
  reverted after an initial overly-broad pass). Fixed
  `MESSAGE_MAGIC` (`util/message.cpp`) from Blackcoin's signing-domain
  string to CodexaCoin's own — this one is functional, not cosmetic.
- **Chain parameters reconfigured** (`kernel/chainparams.cpp`,
  `chainparamsbase.cpp`): new magic bytes, P2P/RPC ports, Base58 address
  prefixes (`C...`/`S...`), bech32 HRP (`cac`/`tcac`/`cacrt`), new genesis
  timestamp phrase, checkpoints reset to genesis-only, `chainTxData` and
  `nMinimumChainWork` zeroed, placeholder `seed*.codexacoin.example` DNS
  seeds (marked TODO), CSV/SegWit active from genesis (fresh chain, no
  legacy activation history to preserve).
- **Premine mechanism.** New `Consensus::Params::nPremineTotal` field;
  `GetProofOfWorkSubsidy()` now mints `nPremineTotal / nLastPOWBlock` per
  block across a fixed `nLastPOWBlock`-block PoW window
  (500 blocks on mainnet — chosen to exactly equal `nCoinbaseMaturity`,
  which closes a chain-halting gap a shorter window would introduce; see
  `PARAMETERS.md` §5.2). Total mints to exactly 14,000,000,000 CAC on
  mainnet/testnet/regtest.
- **Coin-age-proportional staking reward** (spec Appendix A) implemented in
  `pos.cpp` (`ComputeCoinAgeReward`, `GetCoinstakeMaxReward`) using
  128-bit (`arith_uint256`) intermediate arithmetic, and wired into both
  consensus validation (`validation.cpp::ConnectBlock`, replacing the old
  flat `GetProofOfStakeSubsidy()` check with a per-coinstake computed
  maximum) and wallet coinstake construction (`wallet/staking.cpp::
  CreateCoinStake`), so the wallet never builds a block consensus would
  reject. New tunable consensus parameters `nStakeRewardAnnualBP` (default
  1368 = 13.68%/yr ≈ 1.14%/mo) and `nStakeRewardAgeCapSeconds` (60 days).
  **The PoS v3 kernel/stake-eligibility weight
  (`pos.cpp::CheckStakeKernelHash`) was explicitly left untouched** —
  confirmed amount-only, no coin-age term, preserving Blackcoin's existing
  fix against coin-age-hoarding attacks.
- **`MAX_MONEY`**: no code change — already set to the `int64_t` ceiling
  upstream. Documented the real constraint (92,233,720,368 CAC hard ceiling
  from `CAmount` being `int64_t`) and the mitigation (the reward-rate
  parameter is the governance lever) in `PARAMETERS.md` §7.
- **Genesis-mining tool** added: `kernel::FindGenesisBlock()` (exported from
  `kernel/chainparams.cpp`/`.h`) plus a standalone driver,
  `contrib/genesis/generate_genesis.cpp`, that reuses the real
  `CreateGenesisBlock()` rather than reimplementing block/tx serialization.
- **Supply-audit script** added: `scripts/audit_premine_supply.py`, sums
  coinbase outputs for every block in the premine window via RPC and
  asserts the total equals exactly 14,000,000,000 CAC.

- **Genesis blocks mined** for mainnet, testnet, signet, and regtest via
  `generate_genesis`. Found and fixed three real bugs only visible by
  actually running the compiled node (not by code inspection): (1) genesis
  `nVersion` had to be 7, not 1, once the chosen 2026 timestamp landed past
  Blackcoin's inherited protocol-v2 activation time; (2) the genesis
  timestamp phrase had to be short enough for the 100-byte coinbase
  `scriptSig` consensus limit, so the phrase was shortened to a complete,
  unmangled CNBC headline instead of a truncated longer one; (3) PoW
  validation checks `GetPoWHash()` (scrypt), not `GetHash()` — the mining
  tool initially checked the wrong hash and every genesis silently failed.
- **Built successfully**: `codexacoind`, `codexacoin-cli`, `codexacoin-tx`,
  `codexacoin-util`, `codexacoin-wallet` (headless, SQLite wallet, no
  Berkeley DB) on macOS. **Qt GUI wallet not built this phase** — `qt@5` has
  no prebuilt Homebrew bottle on this macOS version and would compile from
  full source (realistically 1-3+ hours); tracked as a Phase 1 follow-up in
  `PARAMETERS.md` §9.
- **End-to-end regtest verification**: ran the real daemon, mined the full
  500-block premine window (confirmed via `scripts/audit_premine_supply.py`:
  exactly 14,000,000,000 CAC, 28,000,000 CAC/block, zero drift), confirmed
  PoW is rejected at block 501 (`reject-pow`), then let the built-in staking
  thread mine PoS blocks. Block 501's coinstake reward
  (6,069,027,198 satoshis) matched the coin-age formula's prediction for
  those exact inputs **to the satoshi**. Chain continued staking normally to
  height 505 before the node was stopped. See `PARAMETERS.md` §6.1 for the
  full numbers.

See `PARAMETERS.md` §9 for the remaining open TODOs before any public
testnet/mainnet launch (mine and checkpoint the *real* mainnet premine
window, write the formal Appendix A.5 test suite, register the BIP44 coin
type, stand up seed infrastructure).

- **Qt GUI wallet built** (2026-07-31, during Phase 2 work): `qt@5` had no
  prebuilt Homebrew bottle on this macOS version and was built from full
  source (~57 minutes). `CodexaCoin-Qt.app` assembled via the project's own
  `make` bundle target and verified to launch and initialize correctly
  (wallet creation, staking thread startup — confirmed via its own
  debug.log, same as the daemon). Dynamically linked against the
  Homebrew-installed Qt/libevent, so it runs on this machine but isn't yet
  a portable, ship-to-another-Mac bundle (would need the
  `macdeployqtplus` framework-bundling step).

---

## Phase 2 — Testnet and regtest validation

### 2026-07-31

- **Two real coin-age reward bugs found and fixed**, both caught
  specifically by multi-node functional testing that exercises scenarios
  Phase 1's single-node verification never did (a node staking *received*
  coins, not just self-mined ones; two independently-staking nodes
  reconnecting and needing to agree on each other's blocks):
  - **Wallet overpay bug**: `wallet/staking.cpp` read a wallet
    transaction's `tx->nTime` directly for coin-age. `CTransaction` only
    serializes `nTime` for `nVersion<2`; this codebase's `nVersion=2`
    transactions always deserialize it as `0`. For *received* coins this
    made age ≈ the full Unix timestamp, clamped to the 60-day age cap,
    inflating a single coinstake's reward by **~21,600×**. `ConnectBlock`
    correctly rejected every such block, so nothing bad was ever accepted
    on-chain, but the wallet could never construct a valid coinstake from
    received funds at all.
  - **Cross-node disagreement bug**: the first fix's fallback (mirroring
    the kernel-hash code's `Coin.nTime`-if-set pattern) used a value
    that isn't canonical across nodes — nonzero only if *that node*
    happened to mine the input's block itself. Two nodes could compute
    two different maximum-allowed rewards for the identical coinstake
    depending purely on which one mined the spent input, and a receiving
    node could reject the originating node's own honestly-built block.
    Reproduced live: a real `coinstake pays too much` rejection
    immediately after two independently-staking nodes reconnected.
  - **Fix**: both the consensus check (`pos.cpp::GetCoinstakeMaxReward`)
    and the wallet (`wallet/staking.cpp::GetWalletTxOriginTime`) now
    resolve coin-age origin time via *only* the origin/confirming block's
    own canonical header time — identical on every node regardless of
    mining-vs-syncing history. Re-verified exact-to-the-satoshi after the
    fix (previously tolerance-bounded to absorb the bug's own timing
    slop). Full writeup: `PARAMETERS.md` §6.3.
- **Functional test suite added**: `feature_premine.py` (exact supply,
  PoW-rejection-past-window), `feature_coinage_reward.py` (formula
  verification against a live staked block), `feature_pos_reorg.py`
  (two nodes independently stake, reconnect, must converge to a single
  consistent chain and supply — the test that caught both bugs above).
  Also fixed a pre-existing, unrelated bug in the inherited test
  framework itself (`test_node.py`'s `v2transport` parameter was
  referenced but never declared, breaking *every* functional test's node
  startup) and documented a real but harmless timing behavior:
  rapidly bulk-mining the premine window leaves the chain's
  median-time-past minutes ahead of real wall-clock time, so staking
  correctly pauses until real time catches up (`PARAMETERS.md` §6.2) —
  not a hang, but worth knowing before assuming something's broken.
- **Docker Compose 3-node regtest environment** added (`docker/`):
  three `codexacoind` nodes on a private network plus a one-shot `init`
  service that mines the premine, verifies it via the (unmodified)
  `audit_premine_supply.py`, confirms PoW rejection past the window, and
  confirms PoS propagation across all three nodes. **Not independently
  executed** — no Docker runtime is installed in this environment: this
  is reviewed-consistent-with-the-real-build config, not a verified test
  run. The same behavior *is* independently verified without Docker via
  the new functional tests.
- **Testnet seed node provisioning scripts** added (`provisioning/`):
  idempotent shell script for a pure P2P relay/validating node — no
  wallet (`--disable-wallet`), no premine, no keys, systemd service,
  firewalled to the P2P port only.
- **Testnet faucet** added (`faucet/`): minimal Flask app, per-IP and
  per-address rate limiting, honeypot instead of external CAPTCHA. Found
  and fixed two bugs while smoke-testing: Flask-Limiter's rate-string
  parser silently no-ops on a fractional hour count (fixed by expressing
  the limit in whole minutes), and a port-5000 conflict (a stale process
  plus macOS's own AirPlay Receiver default) that made a "restart" look
  like it hadn't fixed anything when the old process was still serving
  requests.

See `PARAMETERS.md` §9 for what's still open before any public launch.

---

## Phase 3 — Desktop wallet builds (Windows, Linux, macOS)

### 2026-07-31

- **macOS `.dmg` built and verified end-to-end.** `macdeployqt` bundles the
  Qt frameworks into `CodexaCoin-Qt.app` (confirmed via `otool -L`: no more
  external Homebrew/Qt paths, only standard macOS system libraries), then
  `hdiutil` packages it with an `Applications` symlink into
  `CodexaCoin-Core-macOS.dmg` (~31MB, checksum-verified). Relaunched the
  bundled app directly to confirm it still initializes correctly after
  bundling. Scripted as `contrib/macdeploy/build_dmg.sh` (reusable, not a
  one-off manual sequence) — also prints the exact `codesign`/
  `notarytool`/`stapler` commands needed before public distribution
  (`PARAMETERS.md` §10; no Apple Developer ID certificate exists in this
  environment).
- **GitHub Actions release workflow added**
  (`.github/workflows/release.yml`): builds Linux (tarball + `.deb` via
  `fpm`), Windows (NSIS installer), and macOS (`.dmg`, native runner) on
  tag push, publishing a draft GitHub Release with all artifacts attached.
  Reuses the already-proven Ubuntu-runner + `depends/` cross-compilation
  matrix from the existing `build.yml` CI workflow rather than re-deriving
  build configuration. **Not run end-to-end** — needs an actual tag push
  to fully verify; the macOS leg is the only one independently verified
  locally this session.
- **Windows and Linux builds not produced locally** — genuine environment
  constraints, not toolchain problems, both documented in detail in
  `PARAMETERS.md` §9 item 9: Windows' mingw-w64 cross-compiler works fine
  (Boost/libevent built successfully via `depends/`) but the Qt 5.15.10
  source download reset mid-transfer from `download.qt.io` on two separate
  attempts, and the depends system's fallback mirror 404s for this exact
  file; Linux cross-compilation from a bare macOS host isn't supported by
  the depends system at all (it expects a pre-installed cross-compiler,
  matching Ubuntu's `apt-get` pattern — it doesn't build one from scratch,
  and none is available via Homebrew in a supported form). Both are
  expected to work fine on GitHub Actions' Ubuntu runners, which is what
  the release workflow actually relies on.
- **Qt UI staking controls added**, extending Blackcoin More's existing
  (and already fairly complete) staking UI rather than building from
  scratch — it already had a live status-bar icon
  (`updateStakingIcon()`, updated every second) and an
  encrypted-wallet-specific "unlock for staking" flow, but no general
  on/off control and no reward-amount estimate:
  - **"Enable Staking" toggle** (`bitcoingui.h`/`.cpp`): a checkable
    Settings-menu action. Checking it on an encrypted, locked wallet
    reuses the existing `AskPassphraseDialog::UnlockStaking` flow
    (reverting the checkbox if the user cancels); otherwise it calls
    `setEnabledStaking()` directly — including for turning staking *off*,
    which never needs to re-lock the wallet for spending. The checkbox
    stays in sync with actual state (e.g. if staking was toggled via the
    passphrase-dialog path instead) via `updateStakingIcon()`'s existing
    1-second timer, signal-blocked to avoid feedback loops.
  - **Expected monthly reward estimate** (`overviewpage.ui`/`.cpp`): a new
    "Est. monthly reward" row on the Overview page, computed from the
    current spendable balance and the `nStakeRewardAnnualBP` consensus
    parameter (simple, non-compounded — matches the "~1.14%/month" figure
    quoted elsewhere, the number users actually watch accrue, rather than
    the compounded annual figure). This is a UI-only estimate: it uses
    double-precision arithmetic (deliberately, not the 128-bit path
    `pos.cpp`'s actual reward formula uses — naive `int64` multiplication
    here would overflow for any realistically large balance) and doesn't
    account for per-UTXO maturity timing or the 60-day age cap, so it's
    documented as an estimate, never a guarantee, in its own tooltip.

See `PARAMETERS.md` §9/§10 for what's still open before any public launch.

---

## Phase 4 — Light-wallet backend (required for mobile)

### 2026-07-31

- **`electrumx-cac` added**, adapting
  [CoinBlack/electrumx-blk](https://github.com/CoinBlack/electrumx-blk)
  (Blackcoin's own ElectrumX fork) rather than Fulcrum — researched both
  first; Fulcrum has no generic altcoin/PoS transaction support at all
  (BTC/BCH/LTC-specific only), while electrumx-blk already ships a
  Blackcoin-specific transaction deserializer that correctly handles the
  PoS coinstake `nTime` field CAC inherits unchanged, and a
  version-conditional header-hash mixin that already matches this fork's
  real block-version behavior (every CAC block is `nVersion=7`). Added
  `CodexaCoin`/`CodexaCoinTestnet`/`CodexaCoinRegtest` coin-definition
  classes (genesis hash, RPC port, address prefixes from PARAMETERS.md);
  reused the existing Blackcoin transaction deserializer and daemon RPC
  wrapper unmodified since none of that logic needed to change.
- **Verified against a real node**: ran electrumx-cac against a local
  regtest `codexacoind` and confirmed it connects and correctly identifies
  the daemon via the new coin definition. Full end-to-end block indexing
  was not verified locally — both of electrumx's storage backends
  (leveldb/plyvel, rocksdb) failed to build/run on this specific
  development machine's macOS version (12.7.6, below Homebrew's supported
  tier for the rocksdb formula; plyvel hit a runtime ABI/symbol-visibility
  mismatch against Homebrew's leveldb) — an environment packaging issue,
  not a CAC-adaptation problem. The provided Docker image sidesteps it
  entirely via Debian's packaged leveldb.
- **Deployment scripts added** (`provisioning/electrumx/`): idempotent
  shell provisioning script (systemd service, Let's Encrypt via certbot
  standalone — electrumx has native TLS support, no reverse-proxy needed)
  and a Dockerfile (the recommended path given the local packaging issue
  above). Network-aware port ranges (mainnet/testnet/regtest each get
  distinct ports, not just distinct configs, so a misconfigured wallet
  can't silently connect to the wrong chain on a plausible port).
- **Mobile API gateway specified** (`docs/mobile-api.md`): REST/JSON
  endpoints for balance, UTXOs, history, transaction detail (including
  coin-age reward decoding for coinstake transactions), broadcast, and fee
  estimate, each mapped to the specific underlying Electrum-protocol call
  it wraps. Also specifies the Phase 6 staking-service endpoint shapes
  (custodial 6A: status/deposit/withdraw; cold-staking 6B:
  delegate/revoke) as a stable contract for Phase 5 mobile development,
  even though no staking backend exists yet. This is a specification
  only — the gateway service itself is Phase 5/6 implementation work.

See `PARAMETERS.md` §9/§11 for what's still open before any public launch.

---

## Phase 5 — Mobile wallet (Android + iOS)

### 2026-07-31

- **Flutter light wallet built** (`cac_wallet/`): BIP39 mnemonic
  create/restore, BIP32 HD derivation (`m/44'/<coin_type>'/0'/0/0`), hand-
  implemented Base58Check/bech32 address encoding checked against the real
  ground-truth addresses from `PARAMETERS.md` §3.1, and a from-scratch
  legacy P2PKH transaction signer (SIGHASH_ALL, low-S DER encoding) —
  built by hand rather than via a generic Bitcoin-family package because
  CAC's ordinary (non-coinstake) transactions use `nVersion=2`, which is
  wire-compatible with standard legacy Bitcoin serialization, making this
  a checkable, standard target rather than a CAC-specific format.
- **Full screen set implemented**: lock (biometric app-lock via
  `local_auth`, gated on app access not per-transaction signing — a
  documented simplification), onboarding (create/restore), home, receive
  (QR via `qr_flutter`), send (QR scan via `mobile_scanner`, manual entry,
  build-sign-broadcast flow), history, staking (status-display only, no
  on-device computation), and settings (network switch, wipe wallet with
  confirmation). Every network call goes through a single narrow
  `GatewayApi` client matching `docs/mobile-api.md`'s spec exactly; no
  gateway is actually deployed yet (Phase 4 was a specification only), so
  every screen degrades gracefully (not a crash) when a call fails.
- **Zero on-device staking, verified structurally**: no
  `WorkManager`/`BGTaskScheduler` registrations, no background isolates,
  no PoW/PoS logic anywhere in the Dart source — the staking screen is
  read-only display plus remote API calls only. Documented in full,
  including the exact Apple/Google policy this satisfies, in
  `docs/store-compliance.md`.
- **Flutter SDK version turned out to be a real macOS 12 compatibility
  wall** (current stable's Dart VM refuses to start on this OS) — worked
  around with an older stable release (3.19.6) rather than fighting the
  host OS. See `PARAMETERS.md` §12.1 for the full finding.
- **22/22 unit tests passing** (6 integration tests correctly skipped, no
  live gateway to test against), including a real ECDSA signature
  verification test proving the hand-rolled signer produces
  independently-verifiable, standard-format signatures, and address
  round-trip tests against Phase 1's real ground-truth addresses. `flutter
  analyze`: 0 issues.
- **Android verified for real, on-device**: built, installed, and
  launched on an emulator, confirmed via `logcat` (no crashes) and an
  on-device screenshot (`adb screencap`) showing the actual onboarding UI
  rendering correctly. Two environment issues found and fixed along the
  way (Gradle/Java 22 incompatibility; `mobile_scanner`'s minSdkVersion
  requirement) — see `PARAMETERS.md` §12.3.
- **iOS not verified this phase.** Xcode and the Simulator runtime work
  fine, but CocoaPods isn't installed and installing it on this machine
  triggers building LLVM from source — a multi-hour compile with no
  precompiled bottle available here, a disproportionate cost given
  Android already gives real, on-device confirmation of the entire shared
  Dart codebase. Documented, not silently skipped — see `PARAMETERS.md`
  §12.4.
- **Mainnet founder premine window (`PARAMETERS.md` §5) begun for real**,
  alongside this phase's mobile work: the actual mainnet genesis was
  mined in an earlier phase but block 1 onward had never been produced.
  Mining block 1 via the wallet's own `generatetoaddress` worked
  immediately. Mining further blocks with a proper multi-threaded miner
  (`cpuminer-opt`, built locally, `--algo=scrypt`) surfaced three real
  bugs in that generic mining tool's coinbase construction — none of them
  CAC consensus-code issues, all in the tool's assumptions about a
  "standard" Bitcoin-family chain that this fork's PoS-derived
  serialization doesn't quite match:
  1. **Coinbase `nVersion`**: the tool hardcodes `nVersion=1`, but CAC's
     `CTransaction` deserializer expects a legacy 4-byte `nTime` field for
     any `nVersion<2` (`transaction.h`) that the tool never emits,
     corrupting parsing. Fixed by patching the tool to emit `nVersion=2`
     (matching what CAC's own internal miner already produces).
  2. **Missing `vchBlockSig`**: `CBlock` serializes as `header + vtx +
     vchBlockSig` (`block.h`) — a PoS-chain field, empty for PoW blocks,
     but the empty-length byte still has to be present. The tool, having
     no concept of this field, never appended it, so the node's
     deserializer hit end-of-stream. Fixed by appending the one required
     byte.
  3. **BIP34 height encoding for heights 1–16**: CAC's `bad-cb-height`
     check compares against `CScript() << nHeight`, and Bitcoin Core's own
     `operator<<(int64_t)` special-cases heights 0 and 1–16 as a single
     `OP_N` opcode byte, not a length-prefixed push — which only matters
     for a brand-new chain's very first ~16 blocks. Bitcoin Core's own
     coinbase-building code (`node/miner.cpp`) also unconditionally
     appends a trailing `OP_0` after the height, satisfying the
     consensus-enforced ≥2-byte minimum coinbase scriptSig length even in
     the 1-byte-`OP_N` case; replicated the same convention in the
     patched miner. Found via a debug-only improvement to `submitblock`'s
     error message (`rpc/mining.cpp`) to include the actual
     `BlockValidationState::ToString()` reason instead of a generic
     string — a real diagnostic gap in code from an earlier phase, fixed
     as part of tracking this down.
  As of this writing mining is ongoing in the background toward block
  500; see `PARAMETERS.md` §5 for the design this is executing and §9 for
  its status as an open pre-launch TODO.

See `PARAMETERS.md` §12 for full details on what was and wasn't verified
this phase, and its open TODOs.

---

## Phase 6 — VPS staking service and web wallet

### 2026-08-01

- **`docs/mobile-api.md` implemented for real** (`vps-gateway/`) — Phase 4
  left it as a specification only; this phase built the actual Flask
  service, backed by direct `codexacoind` RPC (a watch-only descriptor
  wallet importing addresses on first use) rather than `electrumx-cac`,
  since Phase 4's Electrum backend remains blocked locally by the same
  macOS storage-packaging issue documented back then. mobile-api.md's
  own design already treats the backend as an internal detail behind the
  gateway, so this is a scoped substitution, not a contract change — see
  `PARAMETERS.md` §13.1 for the full reasoning and its real scaling
  limitation versus a proper indexed backend.
- **6A custodial staking pool implemented**: one dedicated on-chain UTXO
  per deposit (never consolidated), so the chain's own already-verified
  coin-age-proportional reward logic (§6) computes each depositor's
  reward correctly on its own — the pool only watches for a deposit's
  UTXO being staked and credits (reward − 5% pool fee), rather than
  reimplementing reward math itself (see §13.2). JWT-based account
  signup/login for the auth mobile-api.md left as "mechanism TBD".
- **Full lifecycle verified end-to-end against a real node on regtest**
  (chosen for controllable coin maturity): deposit → external funding →
  watcher detects it → node stakes it → watcher detects the resulting
  coinstake and computes the reward, matching the wallet's own reported
  amount exactly → 5% fee deducted exactly → status reflects it
  correctly → withdraw → status correctly zeroes out afterward. General
  wallet endpoints (balance/utxos/history/tx-detail/broadcast/
  fee-estimate) verified the same way, including a real `is_coinstake`/
  reward computation against an actual on-chain coinstake transaction.
- **Web wallet built** (`web-wallet/`): a static, bundler-free browser
  wallet using the `@noble`/`@scure` crypto libraries loaded directly as
  ES modules (chosen specifically because they're dependency-free and
  browser-native, unlike most general Bitcoin JS libraries which assume
  Node's `Buffer` and need a bundler) — `crypto.js` mirrors
  `cac_wallet/lib/crypto/*.dart` exactly (same algorithms, same byte
  layouts), so a recovery phrase restores identically on either wallet.
  Verified in a real browser, not just read for correctness: wallet
  creation produced a real, correctly-prefixed mainnet address; balance
  display, staking signup/login/status, and the deposit flow all worked
  against the live gateway.
- **Two real bugs found and fixed during that browser verification**:
  the gateway had no CORS headers at all, silently blocking every
  cross-origin request a browser-based wallet makes by definition (added
  `flask-cors`); and the staking pool's `ensure_*_wallet_loaded` helpers
  swallowed `loadwallet` failures unconditionally, producing a
  confusing "already exists" error instead of the real problem when a
  wallet was stuck from an earlier interrupted process — fixed to check
  `listwalletdir` and surface the actual failure. See `PARAMETERS.md`
  §13.4 for the full list, including three unrelated bugs found in an
  external mining tool while separately mining the founder premine
  window in parallel this phase (not bugs in this project's own code —
  see below).
- **6B (non-custodial cold-staking) deliberately not implemented.**
  The current codebase has no cold-staking script support at all
  (confirmed by searching the tree before writing anything). Rather than
  silently building a new consensus feature — a new opcode, new script
  validation rules, a real hard/soft-fork-shaped deployment decision —
  this phase specified what it would actually require in
  `PARAMETERS.md` §14, following this project's standing rule against
  inventing consensus changes without asking first, applied here to a
  whole feature rather than a single constant.
- **VPS deployment scripts written** (`provisioning/vps-gateway/`):
  systemd units for the gateway (behind gunicorn, not Flask's dev
  server) and a timer-driven staking-pool watcher pass, a Dockerfile,
  and an example nginx reverse-proxy config — same idempotent
  provisioning-script pattern as `provisioning/electrumx/` and
  `provisioning/seed-node/`.
- **Mainnet founder premine mining continued in parallel** (see Phase
  5's entry for how it started): building and fixing the multi-threaded
  external miner surfaced real bugs in that tool's assumptions about
  this fork's PoS-derived transaction/block format — all three
  documented in Phase 5's entry remain the complete list; no new mining
  bugs were found this phase, just continued background progress toward
  block 500.

See `PARAMETERS.md` §13/§14 for full details on what was and wasn't
verified this phase, its open TODOs, and the 6B cold-staking design
specification.

---

## Phase 7 — Block explorer, documentation, and launch readiness

### 2026-08-01

- **Block explorer built** (`explorer/`): public, read-only, no
  authentication or wallet keys — deliberately a separate service from
  `vps-gateway/`, a different trust boundary. Same direct-RPC backend
  approach as Phase 6 (`txindex=1`, already enabled and synced on this
  node, makes arbitrary block/tx lookup by hash/height/txid work
  natively), plus `scantxoutset` for stateless address balance/UTXO
  lookups that don't require importing every queried address into a
  wallet the way the gateway does. Same honest limitation stated
  up front: current balance/UTXOs only, no historical transaction list
  without a real index.
- **Verified in a real browser against the live mainnet node**: home
  page stats, block detail with prev/next navigation, transaction
  detail, and address search — balance exactly matched
  `utxo_count × 28,000,000 CAC` for the mining reward address. The
  transaction detail page incidentally re-confirmed, on real chain data,
  the BIP34 height-encoding fix made to the external mining tool in
  Phase 6 (visible in block 156's coinbase scriptSig).
- **A same-origin API-base bug caught before it shipped**: while writing
  the production nginx config, the frontend's default API base URL was
  changed from a hardcoded local dev address to a same-origin relative
  path — but the fix as first written double-prefixed every request
  path (`/api/api/stats`). Caught immediately by re-checking the actual
  `fetch()` call sites rather than assuming the change was correct, and
  re-verified in a real browser after fixing it.
- **Deployment scripts written** (`provisioning/explorer/`): systemd
  unit (stateless — no data directory, unlike the gateway's), Dockerfile,
  provisioning script, and nginx reverse-proxy example, same pattern as
  every other service in `provisioning/`.
- **Root-level `README.md` written** — did not exist before this phase.
  Project overview, a directory-by-directory map of every subsystem,
  and the cross-service architecture (which services talk to which,
  and why the explorer/gateway/electrumx split exists).
- **Final launch-readiness review** (`PARAMETERS.md` §15.3): every open
  item from §9 and every phase's own "what wasn't verified" notes,
  synthesized into one place and sorted into what's genuinely done, what
  still needs real work, and what's an external/administrative decision
  rather than a technical blocker. Nothing marked done without having
  actually been checked.
- **Founder premine mining continued in the background throughout this
  phase** (started Phase 5, bugs fixed in Phase 6) — at height 161/500
  as of this writing, including surviving a machine sleep/node-restart
  with no manual intervention needed (the external miner reconnected
  automatically). See `PARAMETERS.md` §15.2.

See `PARAMETERS.md` §15 for the block explorer writeup and the complete
final launch-readiness assessment.

---

## Post-launch-readiness feature additions

### 2026-08-01

Five further features scoped and approved via an open "what else should
we add?" pass with the project owner, none part of the original
7-phase spec:

- **Real dynamic fee estimation** (`vps-gateway/app.py`): replaced a
  hardcoded `FEE_RATE_SAT_VB` constant — empirically found to be 10x
  the node's real `mempoolminfee` floor — with a live heuristic driven
  by `getmempoolinfo()`'s actual `mempoolminfee` and mempool fullness.
  Verified live against the running node.
- **P2SH multisig wallet support** added to both `web-wallet/crypto.js`
  and `cac_wallet` (Dart): N-of-M bare multisig in P2SH, a minimal
  hand-rolled partial-signature-exchange proposal format. Verified via
  a real 2-of-3 create/sign/merge/finalize cycle with independent
  signature cross-checks in both languages; `cac_wallet`'s test suite
  grew from 22 to 24 passing tests.
- **Web Push notifications** added to `web-wallet` (new
  `vps-gateway/push.py`, `push_subscriptions` table, two new
  endpoints, `web-wallet/sw.js`), wired into deposit-confirmed and
  reward-credited events in `staking.py`. Browser notification
  permission is hard-denied in this dev environment (a real policy
  constraint); verified instead at the protocol level via a local
  capture server confirming correct VAPID-signed, `aes128gcm`-encrypted
  push requests.
- **Merchant checkout widget** (new `checkout-widget/`): embeddable ES
  module, no new backend endpoint, polls the existing address-balance
  endpoint to detect payment. Verified end-to-end on regtest with a
  real `sendtoaddress` payment correctly detected.
- **Explorer enhancements** (`explorer/app.py`, `explorer/app.js`): new
  `/api/richlist` and `/api/supply-series` endpoints, a hand-rolled
  inline SVG supply chart, a rich-list page, and a 20-second
  auto-refresh timer on the home route. Verified live in-browser: rich
  list balance exactly matched `303 × 28,000,000 CAC`, the chart
  rendered a correct monotonic-ascending line, and an instrumented
  `setInterval`/`clearInterval` check confirmed the refresh timer is
  created and cleared exactly once per navigation, with no leaks.
- **Two ideas deliberately deferred**, following the same precedent as
  Phase 6's 6B cold-staking deferral: on-chain/off-chain **governance**
  and **hardware wallet support**. Both need their own dedicated design
  review before implementation. See `PARAMETERS.md` §17.

See `PARAMETERS.md` §16-17 for the full writeup of all seven items
above.

---

## Founder premine window complete and checkpointed

### 2026-08-01

- **500-block founder premine window finished mining** on mainnet — the
  last remaining "in progress" item from Phase 7 (`PARAMETERS.md` §15.2).
  `audit_premine_supply.py` confirmed the total minted across blocks
  1–500 is exactly `14,000,000,000.00000000 CAC`, constant
  `28,000,000 CAC` per block, zero deviation.
- **Checkpoints frozen**: all 501 block hashes (genesis through block
  500) hardcoded into mainnet's `checkpointData` in `chainparams.cpp`
  (`PARAMETERS.md` §9 item 2, now done — see §5.4). The node was rebuilt
  and restarted with the new checkpoint data and came back up clean at
  the same height, `bestblockhash` matching the newly-hardcoded height-500
  checkpoint exactly.
- **Desktop app rebuilt with the final CAC logo**: `codexacoin-qt`
  recompiled against the regenerated icon set (see the branding update
  above), binary swapped into `CodexaCoin-Qt.app`, Qt framework rpaths
  re-fixed and the bundle re-signed, verified via a clean relaunch.
- **codexacoin.com website built and deployed**: a static pre-launch
  landing site (project overview, real consensus specs pulled directly
  from `PARAMETERS.md`, phase-by-phase roadmap) deployed to a VPS behind
  nginx with a real Let's Encrypt certificate (HTTP→HTTPS redirect,
  apex + `www` both covered). See `provisioning/website/README.md`.

---

## Fixed a chain-halting staking bug found live at height 500

### 2026-08-01

- **A third real staking bug, found the moment the premine window
  finished**: every wallet reported `getstakinginfo` weight `0` and the
  full 14,000,000,000 CAC premine as `"immature"` at height 500 — meaning
  nothing could ever stake, and since PoW is permanently disabled past
  block 500, nothing could ever produce block 501 either. A genuine
  chain-halting deadlock, live on mainnet.
- **Root cause**: `wallet/staking.cpp`'s coin selection for staking
  (`GetStakeWeight`, `AvailableCoinsForStaking`, `CreateCoinStake`) reused
  the wallet's generic "trusted balance" maturity check, which requires
  `nCoinbaseMaturity + 1` confirmations — one more than `pos.cpp`'s actual
  PoS validation rule (`>= nCoinbaseMaturity`), which was specifically
  designed (§5.2) to let the first post-premine block be staked the
  instant PoW ends. The wallet's own implementation was one confirmation
  too conservative and silently reintroduced the exact dead zone the
  design was supposed to prevent.
- **Fix**: added a staking-specific balance helper
  (`GetStakingBalance()`) that agrees with `pos.cpp`'s threshold instead
  of the wallet's generic one; removed the redundant, stricter
  `IsTxImmature()` gate from `AvailableCoinsForStaking`. Ordinary wallet
  balance display and spending are untouched — this only changes which
  coins the local wallet is willing to attempt staking with, not any
  consensus rule, so there's no fork risk.
- **Verified live**: staking weight went from `0` to exactly block 1's
  28,000,000 CAC the moment the fix was deployed; block 501 was produced
  within about a minute, correctly flagged as proof-of-stake, consuming
  block 1's coinbase as its stake input and paying a coin-age-proportional
  reward. See `PARAMETERS.md` §6.4 for the full writeup.

---

## Deployed the block explorer, then root-caused its P2P connectivity

### 2026-08-01

- **Block explorer deployed** to
  [codexacoin.com/blockexplorer](https://codexacoin.com/blockexplorer/),
  backed by its own headless `codexacoind` (no wallet, no keys) built
  from source on the VPS, since no Linux binary existed anywhere in this
  project yet. See `provisioning/explorer/README.md`.
- **A genuine repo gap found and fixed while building it**:
  `src/qt/Makefile`, `src/test/Makefile`, and `src/qt/test/Makefile` had
  never been committed to git since the original Phase 1 fork import —
  plain, hand-written pass-through Makefiles, invisible locally because
  macOS builds never re-run `autoreconf` and just reuse whatever
  `Makefile` is already sitting in the working tree. A clean checkout
  hits it immediately. Fixed by committing the three files.
- **P2P connectivity between the Mac's node and the VPS's node
  investigated and fixed.** Initially looked like a real bug in the
  codebase's connection-management code — every connection attempt
  seemed to vanish with no trace at all. Turned out to be a
  self-inflicted VPS configuration mistake, not a code bug: an arbitrary
  `maxconnections=8` set during initial provisioning caused Bitcoin
  Core's outbound-slot-reservation math to consume all 8 slots for
  outbound alone, leaving zero capacity for inbound connections — every
  inbound attempt was silently dropped as "full," and the actual log
  line explaining why was itself gated behind a debug category that
  wasn't enabled on the VPS side, which is what made it look like a
  silent, unexplained failure at first. Root-caused with `-debug=net`,
  `tcpdump`, and `strace` attached to the live process — the smoking gun
  was `accept() → setsockopt(TCP_NODELAY) → close()` with no `recv`/`read`
  ever called. Fixed by removing the `maxconnections` override (no code
  changes needed); verified immediately after with a full real-P2P sync
  and both nodes showing each other in `getpeerinfo`. See `PARAMETERS.md`
  §9 item 10 for the full diagnostic trail.

---

## All three wallets live: desktop, Android, and web

### 2026-08-01

- **macOS desktop wallet published**: rebuilt `CodexaCoin-Core-macOS.dmg`
  fresh (current binary, final logo/icon) and published it at
  `codexacoin.com/downloads/`. Still unsigned/unnotarized (no Apple
  Developer ID available in this environment, see `PARAMETERS.md` §10) —
  the site says so plainly rather than hiding it.
- **Android APK published**: built a real `--release` APK (not debug),
  fixed the same Gradle/JDK-17 mismatch documented in `PARAMETERS.md`
  §12.3, published at `codexacoin.com/downloads/`. Direct-install only,
  not on the Play Store.
- **Web wallet deployed for real**, with its own backend — this was the
  bigger piece:
  - Rebuilt the VPS's `codexacoind` with wallet support enabled
    (the explorer's build had deliberately used `--disable-wallet`),
    same binary now serving both the explorer and the gateway.
  - Created real `gateway` (watch-only) and `stakingpool` (holds real
    keys) wallets on it, matching the design in `PARAMETERS.md` §13.
  - Deployed `vps-gateway/` as a systemd service
    (`cac-gateway.service` + `cac-gateway-watcher.timer`), with a real,
    freshly-generated `GATEWAY_JWT_SECRET` — not a placeholder.
  - Deployed `web-wallet/`'s static frontend to `codexacoin.com/wallet/`.
    Fixed its `GATEWAY_URLS` default, which had pointed at
    `http://127.0.0.1:8080` (a local-dev-only value) instead of the
    same-origin convention `explorer/app.js` and
    `checkout-widget/checkout.js` already use — nginx proxies `/v1/` to
    the gateway at the site root, same pattern as the explorer's `/api/`.
  - **Verified live, not just "pages load"**: created a real wallet in
    the browser (real BIP39 mnemonic, a real derived address confirmed
    valid via the node's own `validateaddress`), confirmed its balance
    query actually round-tripped through nginx → gateway → node RPC, and
    exercised the staking-pool signup endpoint directly against the
    production JWT secret (then removed the test account from the
    database afterward).
- **Website updated** to match reality: badge changed from "Pre-launch"
  to "Early access," hero copy updated (premine complete, chain is
  staking live), new "Get a wallet" section linking all three, and the
  roadmap now shows the premine-mining and wallet-availability items as
  done.

---

## Website polish, self-attested signup fields, and a deferred referral feature

### 2026-08-01

- **Website visual polish**: hero glow, logo float animation, card/roadmap
  hover states, real button shadows, nav underline animation, and
  focus-visible outlines -- no structural or content changes.
- **Signup collects self-attested KYC fields** (full name, date of birth,
  national ID or passport number) -- explicitly not identity
  verification (no document check, no provider), both the API and the
  UI say so plainly. ID numbers are encrypted at rest via a new
  `GATEWAY_KYC_ENCRYPTION_KEY`; name/DOB stay plaintext. See
  `PARAMETERS.md` section 13.6 for the full reasoning, including why a
  from-scratch "real KYC" wasn't attempted.
- **Referral/airdrop reward requested, not built**: the funding source
  (newly minted supply, taken from the referred deposit, or paid from
  pool fees) was never pinned down, and this project's supply is
  otherwise fixed by design (premine + staking rewards only, no dev
  fund). Building a payout mechanism without deciding that first risked
  either breaking the fixed-supply model or a solvency problem for
  other users' custodial funds. See `PARAMETERS.md` section 13.6.

---

## Referral reward implemented, once the funding source was resolved

### 2026-08-01

- Follows up on the earlier entry deferring this feature. The funding
  question was resolved: 10% of a referred user's first deposit, paid
  from a dedicated `adminwallet` funded manually by the project owner —
  not newly minted CAC, not deducted from the referred user's deposit,
  and not drawn from the pool wallet holding other users' funds.
- `vps-gateway/referral.py`: referral codes generated at signup,
  crediting hooked into the existing deposit-watcher pass (bookkeeping
  ledger entry, not an immediate on-chain send), `/v1/referral/status`
  and `/v1/referral/withdraw` endpoints. Web wallet gained a referral
  code field at signup and a Referrals card showing your code, referred
  count, and a withdraw form.
- Verified the crediting logic and the withdraw endpoint's error path
  live, without moving any real funds (a real transfer is the project
  owner's action, not something to execute while verifying a feature) --
  confirmed exact 10% crediting, no double-credit on a repeat trigger,
  and a clean failure from the still-unfunded admin wallet with the
  credit correctly left available afterward. See `PARAMETERS.md`
  section 13.7 for the full writeup, including the admin wallet's
  receive address.

---

## Appendix A.5 staking-reward unit test suite

### 2026-08-02

- `codexacoin-core/src/test/pos_tests.cpp` (new, registered in
  `Makefile.test.include`): the formal unit test suite for
  `ComputeCoinAgeReward`/`CheckStakeKernelHash` called for by the spec's
  Appendix A.5, which had only ever been exercised via one real end-to-end
  regtest run (`PARAMETERS.md` §6.1) until now. Seven cases: the known
  regtest vector as a regression guard, zero/negative inputs, the age-cap
  plateau, confirmation the 128-bit `arith_uint256` path is actually
  exercised (not dead code) plus a forced-overflow test of the defensive
  int64 clamp, a fast deterministic full-simulated-year calibration (lands
  within 2 satoshis of the nominal annual rate on a 1,000,000 CAC input),
  and a statistical test confirming PoS kernel eligibility stays amount-only
  and uncorrelated with coin-age (3000 trials each at a 1-second vs.
  55-day age, ~50% pass rate either way).
- All seven cases pass under the project's real `make check` invocation.
  Running the full `test_codexacoin` binary unfiltered (not how `make
  check` actually works — each suite gets its own process) surfaces ~34
  unrelated pre-existing failures elsewhere in the suite, traced to a
  hardcoded 2020 mocktime being checked against the real system clock;
  reproduces identically with `pos_tests` excluded, so it predates this
  change and wasn't introduced by it. Left as-is (out of scope for this
  task) but documented in `PARAMETERS.md` §6.1a for whoever picks it up.
- See `PARAMETERS.md` §6, §6.1a, and §9 item 3 for the full writeup.

---

## Dedicated BIP32 extended-key version bytes

### 2026-08-02

- `kernel/chainparams.cpp`: all four networks (mainnet, testnet, signet,
  regtest) previously reused Bitcoin's own `EXT_PUBLIC_KEY`/`EXT_SECRET_KEY`
  version bytes verbatim, so `dumpwallet`/`listdescriptors` output started
  with Bitcoin's literal "xpub"/"xprv" -- indistinguishable at a glance from
  a real Bitcoin extended key. Chose CodexaCoin-specific bytes instead:
  mainnet extended keys now start `Czxx...`, testnet/signet/regtest start
  `DDxx...`. Not consensus-critical (display-only, no validation logic
  touches this), not a breaking change (no UI in this project currently
  serializes an extended key; old backup files stay valid regardless).
- Live-verified against a real, freshly-built `codexacoind`: created a
  descriptor wallet on an isolated mainnet node and confirmed
  `listdescriptors` actually returns the new `Czxx...`-prefixed extended
  pubkey, then repeated on regtest for the `DDxx...` family. See
  `PARAMETERS.md` section 6.4 for the full writeup, including why the
  `EXT_SECRET_KEY`/`dumpwallet` side couldn't be independently re-verified
  live in this build (no BDB/legacy wallet support) despite using the
  identical, already-verified encoding mechanism.
- Closes `PARAMETERS.md` section 9 item 5.

---

## Real Windows and Linux builds, GPG-signed and published

### 2026-08-02

- Asked directly how to handle the request to make downloads warning-free:
  paid code-signing certificates (Windows Authenticode, Apple notarization)
  need real purchases and business/identity verification this project
  can't do unilaterally. Decided: ship real Windows/Linux binaries now with
  GPG signing + SHA256 checksums (free, same scheme Bitcoin Core uses),
  revisit paid certificates later.
- **Windows** (mingw-w64, CLI only): found and fixed two real portability
  bugs that only surfaced on an actual cross-compile attempt -- ~50
  headers missing an explicit `<cstdint>` include (mingw's libstdc++
  doesn't transitively pull it in the way macOS's libc++ does), and a
  `libbitcoinconsensus` shared-library link conflict (fixed via
  `--disable-shared`). Produces real, working `codexacoind.exe`/
  `codexacoin-cli.exe`/etc.
- **Linux** (native Ubuntu 22.04 build inside Docker, full Qt GUI):
  live-verified, not just compiled -- ran the resulting `codexacoind`
  on regtest inside the container and got a real address back from
  `getnewaddress`.
- Generated a real GPG release-signing key, computed `SHA256SUMS` across
  all four release artifacts (macOS, Windows, Linux, Android), signed it,
  and published everything to `codexacoin.com/downloads/` alongside the
  public key. Verified all four checksums against the live server after
  upload. Website gained Windows/Linux wallet cards and a "Verifying a
  download" section explaining plainly that GPG/checksum verification
  proves authenticity but does not suppress OS security warnings -- only
  a paid certificate does that.
- See `PARAMETERS.md` section 10.1 for the full writeup, and section 9
  item 9 (now closed).

---

## Android: real gateway, working staking login/deposit/withdraw, and a launch-blocking crash fix

### 2026-08-03

- The Android app's gateway URL was still a placeholder (`api.codexacoin.
  example`) and its staking screen was fully stubbed despite the gateway
  endpoints existing since Phase 6 -- deposit/withdraw buttons just showed
  a "not live yet" snackbar, and the auth token was silently never sent
  with staking requests. Fixed: mainnet now points at the real
  `codexacoin.com/v1` backend (same one the web wallet uses), added
  login/signup mirroring web-wallet's exact contract (including the
  self-attested KYC fields), and rebuilt the staking screen with a real
  auth form and working deposit/withdraw.
- Found and fixed a real, previously-unknown bug along the way:
  `MainActivity` wasn't a `FragmentActivity`, which the biometric
  app-lock plugin requires -- every fresh install hit
  `no_fragment_activity` and was **permanently stuck on the lock screen**,
  unable to reach any other screen. Not related to this session's other
  changes; just never triggered before because nobody had run the app
  past onboarding with a real emulator/device credential enrolled.
- Verified on a real Android emulator: confirmed the crash is gone,
  created a real wallet through onboarding, and reached the rebuilt
  staking screen. Full deposit/withdraw click-through wasn't finished --
  the emulator became unstable partway through (unrelated to the code
  changes) -- documented honestly rather than claimed as done.
- See `PARAMETERS.md` section 12.6 for the full writeup, closing section
  12.5 item 2.

---

## Android staking verified live end-to-end; stale release APK republished

### 2026-08-03

- Verified the full auth/staking flow added yesterday against the real,
  live gateway (`codexacoin.com/v1`), not just statically: signed up a
  real test account, fetched staking status, requested a deposit address
  (real address returned, no funds moved), and attempted a withdraw
  (clean "exceeds available balance" error -- the safe way to verify that
  path without ever moving real funds). All four matched the exact
  request/response shapes the Dart client now sends. Pivoted to direct
  API testing after the Android emulator became unstable a third time
  across two fresh instances -- confirmed via `aapt2 dump badging` that
  the built APK's own manifest was correct throughout, so this was
  environment tooling instability, not an app defect.
- Cleaned up the test account and its one deposit-address row from the
  production gateway database immediately after verifying.
- Rebuilt and republished the Android release APK at
  `codexacoin.com/downloads/CodexaCoin-android.apk` -- the previous file
  there predated every fix from the day before (real gateway URL,
  working staking, the lock-screen crash fix), so anyone downloading the
  app before this point was getting a build that couldn't reach the
  backend and could get stuck on first launch. Regenerated and re-signed
  `SHA256SUMS`/`SHA256SUMS.asc` to match; verified against the live
  server.
- See `PARAMETERS.md` section 12.7 for the full writeup.

---

## Website content and design overhaul

### 2026-08-03

- Rewrote `website/index.html`/`style.css` for a more professional,
  investor-credible presentation, per explicit request. Every new claim
  ties to something already true and documented elsewhere in this
  project -- no hype copy, no invented statistics.
- New: a hero stats bar pulling real numbers (block height, difficulty)
  live from the explorer's `/api/stats` on page load; a credibility
  strip (audited premine, open source, GPG-signed releases, real
  running network); a "Why Proof-of-Stake" section; an "ecosystem"
  section linking the explorer, gateway, checkout widget, and the newly
  public GitHub repo; an explicit "What we won't tell you" section
  disclosing the project's actual early-stage risks (concentrated
  supply, no exchange listing, unsigned builds, not investment advice);
  and an FAQ.
- Kept the existing dark cyan/blue/gold visual language, added a
  live-updating status badge, icon-led cards, a primary/outline button
  hierarchy, and a dependency-free `<details>`-based FAQ accordion.
- Verified live: fetched stats match the deployed page, no console
  errors, and multi-column layouts confirmed via computed styles at
  both mobile and desktop widths.
- See `PARAMETERS.md` section 16.6 for the full writeup.

---

## First public GitHub repo, first real CI release, v0.1.0 draft published

### 2026-08-03

- Published the project to GitHub for the first time
  (`github.com/fakharnaqvi5313/codexacoin`, public, MIT) -- scanned
  tracked file contents for real secrets first (none found).
- Moved `release.yml` to the actual monorepo root (GitHub Actions never
  discovers workflows nested a directory down) and pushed tag `v0.1.0`.
  `linux-x86_64` and `windows-x86_64` built successfully on GitHub's own
  infrastructure for the first time ever. `macos-x86_64` got stuck queued
  76-90+ minutes on two separate attempts with no error and nothing else
  competing for a runner anywhere in the account -- un-gated
  `publish-release` from needing macOS so future releases aren't held
  hostage by that queue.
- Published a draft GitHub Release for `v0.1.0` with all four platform
  artifacts: the CI-built Linux tarball/`.deb` and Windows installer
  (downloaded directly rather than waiting on a full re-run), plus a
  freshly rebuilt-and-smoke-tested macOS `.dmg`.
- Added the three CI-built artifacts to the website's downloads page too,
  alongside the existing locally-built ones, framed as a second
  independently-built option rather than a replacement. Regenerated and
  re-signed `SHA256SUMS` to cover all seven hosted files.
- See `PARAMETERS.md` section 16.7 for the full writeup.

---

## Legal/policy pages added; Microsoft Store submission blocker found

### 2026-08-03

- Added Privacy Policy, Terms & Conditions (governing law: Pakistan),
  Risk Disclosure, AML/KYC Policy, and Acceptable Use Policy pages under
  `website/legal/`, linked from the site footer and both the web wallet's
  and Android app's signup forms. Every factual claim checked against
  what the code actually does (confirmed no cookies, no third-party
  trackers, before writing those sections that way) rather than using
  generic boilerplate.
- Investigated Microsoft Store submission for a Windows GUI wallet.
  Fetched Microsoft's current Store Policies directly rather than relying
  on memory: policies 10.8.3 and 10.2.6 both require a **Company**
  developer account for any app handling private keys/recovery phrases or
  cryptocurrency wallets -- confirmed with the user that their existing
  account is Individual, which Store policy explicitly disallows for this
  category (a hard certification rejection, not a soft risk). Converting
  requires real business verification with Microsoft that only the
  account owner can do.
- Proceeded with the account-type-independent prep work anyway: building
  an actual Windows GUI wallet via the depends system (the existing
  Windows build is CLI-only), including Qt this time -- the earlier
  attempt had skipped it because the Qt source download kept stalling
  mid-transfer.
- See `PARAMETERS.md` section 16.8 for the full writeup.

---

## First real Windows GUI wallet build

### 2026-08-03

- Achieved a genuine Windows GUI build (`codexacoin-qt.exe` bundled in the
  installer) for the first time, after the local macOS-hosted mingw Qt
  cross-compile hit a real, structural dead end (the host-tool build
  feeds macOS Clang flags to the mingw compiler, which rejects them --
  not fixable, just an unsupported combination).
- Fixed the real bug instead: GitHub Actions' `release.yml` Windows job
  never used `CONFIG_SITE` when calling `configure`, so it never found
  the Qt that `depends` already builds by default -- confirmed by reading
  `depends/config.site.in` directly. That's why the CI-built Windows
  artifact from the last release was CLI-only despite never disabling
  Qt. Fixed, then verified for real: extracted the resulting installer
  with `p7zip` (a `strings` search alone was misleading -- NSIS
  compresses its payload, so it looked empty even when genuinely not) and
  confirmed `codexacoin-qt.exe` (39.3MB) is really in there.
- Replaced the stale CLI-only Windows download on both the GitHub Release
  and the website with this real GUI build, and corrected the homepage
  copy that said Windows was "command-line only for now."
- Still blocked, same as before: real Microsoft Store submission needs
  the account owner to convert to a Company developer account.
- See `PARAMETERS.md` section 16.9 for the full writeup.

---

## DEX listing: chose Stellar, set up (unfunded) issuer infrastructure

### 2026-08-03

- Researched all three requested options (THORChain, Osmosis, Stellar
  DEX) plus XRPL as a close alternative before choosing. THORChain and
  Osmosis are both structurally blocked for a chain like CAC (no smart
  contracts, no IBC) regardless of budget -- THORChain requires its own
  node operators to adopt a new chain-client integration; Osmosis
  requires a purpose-built bridge, the kind of "another blockchain"
  representation explicitly asked to avoid if possible. Stellar's native
  DEX is genuinely near-zero-cost and permissionless, and has meaningfully
  more liquidity than XRPL's equivalent.
- Set up `stellar-issuer/`: generated the two Stellar keypairs (issuer +
  distributor) needed to issue a `CAC` asset, with secret seeds written
  only to a local gitignored file, never logged or committed; created a
  new, empty CAC-chain wallet (`stellar-reserve`) to eventually hold the
  backing reserve; wrote `setup_asset.py`, ready to run once funded.
- Deliberately did not fund the accounts, decide a reserve amount, or
  issue anything -- those are real financial commitments only the
  project owner should make, same standing rule already applied to the
  referral-pool funding decision.
- See `PARAMETERS.md` section 18 for the full writeup.

---

## DEX listing goes live: reserve funded, CAC issued on Stellar, initial offer placed

### 2026-08-03

- Project owner funded both Stellar accounts (issuer and distributor)
  with real XLM, and locked the reserve by sending 10,000,000 real CAC to
  the `stellar-reserve` wallet on the live mainnet node (confirmed
  on-chain, single UTXO, height 1004).
- Ran `setup_asset.py`: distributor established a trustline to the `CAC`
  asset and the issuer sent it the full 10,000,000 reserve-backed amount
  -- verified live via Horizon.
- Ran `place_sell_offer.py`: placed a resting DEX sell offer of 500,000
  CAC against XLM at the owner-chosen initial rate of 1 XLM = 14 CAC
  (price 1/14) -- verified live on Stellar's DEX as offer `1851427700`.
- Published `website/legal/proof-of-reserve.html`: fetches the real
  `stellar-reserve` CAC balance and the issued Stellar `CAC` supply live,
  client-side, from the CAC explorer API and Horizon respectively, and
  compares them -- so "backed 1:1" is independently checkable rather than
  a bare claim. Linked from the site footer and every legal page's nav.
- Added section 10 to `risk-disclosure.html` (`id="stellar-iou"`)
  disclosing the Stellar `CAC` asset's custodial/IOU nature, matching how
  the VPS gateway's custodial staking pool is disclosed in section 5 of
  the same page.
- As with every step in this sequence, all real transactions (funding,
  the CAC reserve transfer, issuing the asset, placing the DEX offer)
  were executed by the project owner directly, never by the assistant --
  each was independently verified afterward via read-only Horizon/CAC
  explorer API calls.
- Still open: locking the issuer account's master key weight to 0 (or
  multisig) to permanently cap further issuance, left for the project
  owner once the reserve amount is treated as final. See `PARAMETERS.md`
  section 18.1 for the full writeup.

---

## Seeded (and disclosed) initial chart history on the CAC/XLM pair

### 2026-08-03

- Placed one small round-trip trade -- a project-controlled "trader"
  account bought ~28 CAC for ~2 XLM against the distributor's resting
  offer, then sold it back for ~1.87 XLM -- so third-party chart viewers
  (stellar.expert etc.) show something other than a blank chart. Flagged
  up front that this is a wash trade (both sides project-controlled, not
  organic demand) before doing anything; owner chose to proceed with
  public disclosure rather than skip it or do it quietly.
- Hit `MANAGE_BUY_OFFER_CROSS_SELF` three times attempting the second
  leg -- Stellar rejects an account placing a buy offer that would cross
  its own resting sell offer. Diagnosed by decoding the failed
  transactions' `result_xdr`, not guessed. Fixed by bidding at 1/15
  instead of the original 1/14, a small bid/ask spread rather than an
  identical round-trip price.
- Both trades verified live on Horizon (tx `7de68167...`, buy,
  2026-08-03T13:37:16Z; tx `ef7f58e2...`, sell, 2026-08-03T13:46:08Z) --
  disclosed by name in a new section 3 of `proof-of-reserve.html` so
  nobody mistakes the resulting candle for real trading demand.
- See `PARAMETERS.md` section 18.2 for the full writeup, including the
  exact failure diagnosis.

---

## Scoped and started a Uniswap listing on Base (wrapped ERC-20)

### 2026-08-03

- Answered whether CAC shows on CoinGecko/CoinCodex (no) and what those
  platforms actually require (real tracked trading volume, not a form --
  confirmed CoinGecko's own listing terms have no fee/liquidity minimum
  published but do require the asset already trading somewhere tracked;
  GeckoTerminal indexes any Uniswap pool automatically with no
  application, which is the more realistic near-term path).
- Scoped Base vs. Arbitrum vs. Ethereum mainnet vs. BNB Chain and
  recommended Base -- gas is cheap everywhere now (mainnet ~$0.01-2/tx
  as of mid-2026), so the deciding factor was Coinbase's on-ramp making
  Base easiest for a zero-audience asset to reach real traders; BNB
  Chain ruled out since PancakeSwap, not Uniswap, dominates BSC volume.
  Owner delegated the final decision.
- Built `base-issuer/`: a fixed-supply ERC-20 (`CodexaCoinBase.sol`) with
  no owner and no mint function at all -- an improvement over the
  Stellar issuer, which still needs its master key locked separately to
  get the same guarantee. Deploy script and a Uniswap V2 pool-seeding
  script (`addLiquidityETH`, auto-creates the pair), sized at 0.05 ETH +
  7,400 CAC to imply roughly the same CAC price as the Stellar peg.
- Verified the Uniswap V2 Router02/Factory/WETH addresses on Base two
  ways: independently against BaseScan, and by calling the live
  Router02 contract's own `factory()`/`WETH()` functions and confirming
  they match -- stronger than trusting either source alone.
- Created the `base-reserve` CAC-chain wallet
  (`CYKfFa2cfXgKjcLBNPTNFNYBoiNsFfjZV1`) and generated the deployer/
  distributor EVM wallet
  (`0x744a7f868eBD6Ea933AE49AB8424873CE2894f77`) -- both safe, no-value-
  moved steps done directly. Funding, deployment, and pool creation are
  still the owner's actions, not yet done. See `PARAMETERS.md` section
  19 for the full writeup, including a local-fork tooling limitation
  hit (and worked around) while dry-running the scripts.

---

## Fixed two real Android mobile-wallet send bugs

### 2026-08-04

- Fixed "type 'Null' is not a subtype of type 'String' in type cast" when
  sending any amount: `send_screen.dart` read a `pubkey_hash` field off
  each UTXO returned by the gateway's `/address/<addr>/utxos` endpoint,
  but that endpoint only ever returns `txid`/`vout`/`value`/`height`/
  `confirmations` (`vps-gateway/app.py`) -- the field never existed, so
  the cast always failed on any real send attempt. The value doesn't
  need to come from the server at all: every UTXO fetched here belongs
  to this wallet's own single active address, so the pubkey hash is the
  same for all of them and can be computed locally from the wallet's own
  key -- exactly the pattern `web-wallet/app.js` already used correctly.
  Added `WalletService.activePubkeyHash()` and had the send screen use
  that instead of trusting a nonexistent API field.
- Fixed QR-code scanning on Android: `AndroidManifest.xml` never declared
  the `CAMERA` permission `mobile_scanner` requires, so the scanner
  either failed silently or never got real camera access. Added the
  permission (plus a non-required camera `<uses-feature>` so install
  isn't blocked on cameraless devices) and an `errorBuilder` on the scan
  screen so a future camera/permission failure shows a real message
  instead of a blank screen.
- Verified via `flutter analyze` (clean) and `flutter test` (all pass).
- Rebuilt the release APK and redeployed it to
  `codexacoin.com/downloads/CodexaCoin-android.apk`, replacing the old
  broken build; `SHA256SUMS`/`SHA256SUMS.asc` regenerated and re-signed
  to match. Local build needed `JAVA_HOME` pinned to JDK 17 (Gradle
  7.6.3 doesn't support the machine's default JDK 22).

---

## Added seven features to the web wallet

### 2026-08-04

- QR code on the receive screen; QR camera scanning on the send screen
  (with a real error message, not a blank screen, if camera access
  fails).
- Session PIN lock -- real PBKDF2 + AES-GCM encryption of the recovery
  phrase at rest via the Web Crypto API, not just a UI-level gate.
- Multisig (N-of-M) UI built on top of `crypto.js`'s already-complete
  but previously unexposed multisig primitives: create a shared
  address, propose a spend, sign sequentially across cosigners,
  finalize and broadcast.
- Transaction detail view (tap a history row for a full breakdown).
- Address book with labels, usable directly from the send screen.
- Multiple addresses per wallet -- "New address" derives the next BIP44
  index; balance/UTXOs/history combine across every address generated
  on that browser. Explicitly not full gap-limit address discovery --
  said so in-app.
- Extended `buildAndSignTransaction` to support a different signing key
  per input (needed once a send can span more than one address),
  backward compatible with every existing single-key call site.
- Found and fixed a real bug during testing: the Settings screen's
  PIN success/error messages were being set then immediately cleared
  by the same handler, never actually visible.
- Verified end to end in a real browser, not just read for correctness
  -- see `web-wallet/README.md`'s Verification section and
  `PARAMETERS.md` section 20 for the full account, including design
  decisions (why the PIN lock is real encryption, why multi-address
  isn't gap-limit discovery, why multisig signs sequentially rather
  than supporting parallel-copy merging).
- Deployed to `codexacoin.com/wallet/`, then re-verified QR and multisig
  directly against production (not just the local test): the receive
  QR canvas decodes back to the exact displayed address, and a live
  2-of-2 multisig address/signature round trip checked out. Test
  wallet's `localStorage`/`sessionStorage` cleared immediately after --
  see `PARAMETERS.md` section 20.4.

---

## Ported the web wallet's feature batch to the mobile app

### 2026-08-04

- Multisig UI (built directly on `crypto/transaction.dart`'s
  already-complete but previously unexposed multisig primitives),
  address book, transaction detail view, and multiple addresses per
  wallet with combined balance/history/UTXOs -- same designs as the
  web-wallet batch, translated to Flutter.
- Extended `buildAndSignTransaction` for per-input signing keys, same
  shape as the web-wallet change, backward compatible.
- Found and fixed two more real, previously-undiscovered bugs while
  reading the existing code: `send_screen.dart` never reversed a UTXO's
  txid hex to wire byte order (every real send would have referenced
  the wrong previous output and failed at broadcast), and
  `TxSummary`/`TxDetail` force-cast a `height` field to non-nullable
  `int` that the gateway genuinely returns as `null` for any pending
  transaction (would have crashed the History screen on any
  unconfirmed tx).
- Verified via `flutter analyze` (clean) and the full test suite (26
  tests, including a new targeted test for the per-input-key signing
  change and the pre-existing full multisig round-trip test, both
  passing). Live UI/simulator testing wasn't possible this time -- the
  iOS Simulator tool was stuck in a genuine crash-restart loop for the
  whole session, an environment issue, not a shortcut taken.
- Push notifications not built: needs a Firebase project (Android/FCM)
  and Apple Developer account (iOS/APNs), neither of which this session
  has access to or can create. Left for the project owner.
- Rebuilt and redeployed the release APK to
  `codexacoin.com/downloads/CodexaCoin-android.apk`; `SHA256SUMS`/
  `SHA256SUMS.asc` regenerated and re-signed. Full account, including
  the bug diagnoses, in `PARAMETERS.md` section 21.

---

## Added price, BIP21, explorer links, CSV export, watch-only, and QR
multisig sharing to both wallets

### 2026-08-09

- Live CAC/USD price estimate (Stellar DEX last-trade price x CoinGecko
  XLM/USD), clearly labelled as an estimate resting on thin DEX
  liquidity, not a reliable market price.
- BIP21 URI support (`codexacoin:<address>?amount=X`): the receive
  screen's QR now carries a requested amount when one is entered, and
  the send screen auto-splits a scanned or pasted BIP21 URI into
  address + amount. Falls back to plain-address behavior when the
  input isn't a BIP21 URI.
- One-tap block explorer links from the receive screen and transaction
  detail view/screen.
- CSV export of transaction history (web: browser download; mobile:
  native share sheet via `share_plus`).
- Watch-only address monitoring -- track any address's balance without
  holding its keys, kept as its own list separate from the address
  book (which is for addresses you send *to*, not monitor).
- QR-based multisig proposal sharing as an alternative to copy/paste,
  with a disclosed 1500-character size ceiling (same constant on both
  platforms) that fails closed with a clear message rather than
  generating an unscannable QR.
- Web-wallet verified live in-browser for all six features (real price
  fetch, BIP21 round trip, watch-only persistence, multisig QR round
  trip and oversized-proposal rejection, CSV escaping, explorer-link
  URLs). Mobile verified via `flutter analyze` (clean) and the full
  test suite (26 tests passing); live simulator testing wasn't possible
  this session, same standing iOS Simulator environment issue noted in
  the previous entry. Full account in `PARAMETERS.md` section 22.
- Rebuilt and redeployed the release APK to
  `codexacoin.com/downloads/CodexaCoin-android.apk`; `SHA256SUMS`/
  `SHA256SUMS.asc` regenerated and re-signed. Web wallet redeployed to
  `codexacoin.com/wallet/`.

---

## Added message signing, seed-phrase backup verification, dark mode,
xpub watch-only, fee-bumping, and a new-transaction banner to both
wallets

### 2026-08-09

- Message signing/verification (Bitcoin-style, matching
  `codexacoin-cli signmessage`/`verifymessage` exactly), so anyone can
  prove control of a P2PKH address without spending anything. Found and
  fixed a real bug while testing the mobile implementation's hand-rolled
  signature-recovery math: a hardcoded curve constant was two hex
  digits short, silently breaking every recovery attempt. Cross-checked
  the two independent implementations against each other with a real
  signature produced on one platform and verified on the other.
- Seed-phrase backup verification: a short quiz (3 random word
  positions, retyped from the phrase just shown) before wallet creation
  completes, on both platforms -- neither previously checked that a
  backup was actually correct.
- Dark/Light/System theming on both platforms (previously hardcoded to
  a single theme on each).
- xpub-based watch-only: export this wallet's account xpub, or import
  someone else's to derive and watch a chosen number of its addresses
  -- no private key involved. Verified with real cross-derivation
  checks (addresses via xpub match the same indices derived directly
  from the private key) and a cross-platform golden vector.
- Fee-bumping (RBF) for stuck sends: new sends now signal BIP125
  opt-in replaceability by default, and a "Bump fee" action on a
  pending self-sent transaction rebuilds it with a higher fee, taken
  from its own change output. Backed by a small local-only log of what
  each wallet itself sent (needed to safely rebuild the exact same
  inputs); fails closed with a specific reason when bumping isn't
  possible (no local record, no change output, or not enough change).
- A live "new transaction" banner -- but implemented differently per
  platform on purpose: web polls while Home/History is the open tab
  (a foreground browser timer, no bearing on app-store background-
  execution policy); the mobile app checks only on explicit refresh
  (opening a screen, pull-to-refresh), since `docs/store-compliance.md`
  prohibits any scheduled/periodic task in the Flutter project outright
  -- a real App Store/Play Store constraint, not a style choice. A
  deliberate, disclosed difference rather than a silently narrower port.
- Full account of the design decisions, the bug found and fixed, and
  how each feature was verified (including the specific cross-platform
  checks) in `PARAMETERS.md` section 23.
- Rebuilt and redeployed the release APK to
  `codexacoin.com/downloads/CodexaCoin-android.apk`; `SHA256SUMS`/
  `SHA256SUMS.asc` regenerated and re-signed. Web wallet redeployed to
  `codexacoin.com/wallet/`.

---

## Set up (unfunded) PancakeSwap listing infrastructure on BNB Smart Chain

### 2026-08-10

- Third listing venue, after Stellar and Base: a reserve-backed,
  fixed-supply wrapped BEP-20 (`bnb-issuer/`), mirroring
  `base-issuer/`'s no-owner/no-mint-function design.
- Deliberately quoted against USDT rather than BNB/WBNB: an AMM pool
  only holds the ratio between its two assets fixed, so pooling against
  a volatile native asset means the token's USD price drifts with that
  asset's own volatility, unrelated to the token itself. Quoting
  against USDT removes that -- explicitly documented as *not* making
  CAC a stablecoin, since its USDT price still floats with actual
  supply/demand.
- PancakeSwap V2 Router/Factory/WBNB/USDT addresses verified two
  independent ways (BscScan, and calling the Router's own
  `factory()`/`WETH()` view functions over public RPC) before use --
  caught a wrong remembered Factory address before it could reach a
  script, and confirmed USDT's decimals are 18 on BSC, not 6 like
  Ethereum's USDT.
- Deployer wallet and CAC-chain reserve wallet (`bnb-reserve`)
  generated; contract compiles. Awaiting funding (CAC to the reserve,
  BNB for gas, USDT for the pool) before deployment -- see
  `bnb-issuer/README.md`. Full design rationale in `PARAMETERS.md`
  section 24.

---

## Take the BNB Smart Chain PancakeSwap listing live; disclose it

### 2026-08-10

- Owner funded and deployed: `CodexaCoinBnb` (fixed-supply, no-owner,
  no-mint-function BEP-20) live at
  `0xd9bac2e48E090d42E5E71193D23e8efAAF9a054c`, and a CAC/USDT
  PancakeSwap V2 pool seeded at
  `0x610d052dFAFdBD0F8bA6D37Ec202e58e4Cb7de9a` (21.41008673 USDT +
  1712.8069384 CAC, implying exactly the $0.0125/CAC target price).
  Every number independently verified on-chain via direct `eth_call`s
  -- contract metadata, total supply, reserve balances, pool reserves
  -- not just taken from the deploy scripts' own success output.
- Extended `website/legal/proof-of-reserve.html` (now covers Stellar
  and BNB Chain, live-checked in-browser against both chains) and
  `risk-disclosure.html` (new §11) to disclose this third custodial
  liability, matching the existing Stellar disclosure pattern.
- Found and fixed a real bug while building the updated disclosure
  page: the explorer's address-lookup endpoint uses `scantxoutset`,
  which the node only allows one of at a time -- firing two concurrent
  lookups (as the new two-venue page did) made one of them fail with
  "Scan already in progress," rendering as a silent `NaN`. Fixed by
  sequencing the two lookups instead of firing them concurrently.
  Flagged the same underlying issue in both wallets' watch-only screens
  (which fire lookups for every watched address concurrently) as a
  separate follow-up, since it's pre-existing, already-shipped code
  outside this change's scope. Full account in `PARAMETERS.md` section
  24.

---

## Fixed a real concurrency bug in both wallets' watch-only balance lookups

### 2026-08-10

- Both wallets' watch-only screens fired a balance lookup for every
  watched address concurrently (no `await` between them). Fixed to
  fetch sequentially instead, on both web (`loadWatch()`) and mobile
  (`WatchScreen._load()`).
- The earlier note in this changelog (previous entry, taking BNB Chain
  live) guessed this was the same `scantxoutset` "Scan already in
  progress" bug the disclosure page hit. That guess was wrong: the
  watch-only screens go through a different backend service
  (`vps-gateway`, not the explorer) with a different failure mode --
  confirmed directly against the live gateway (two brand-new addresses
  looked up concurrently produced a 500 on one of them; the same two
  looked up sequentially both succeeded). Corrected in `PARAMETERS.md`
  section 25 rather than left standing.

---

## Verified the BNB Chain CAC contract's source code on BscScan

### 2026-08-10

- Submitted `bnb-issuer/contracts/CodexaCoinBnb.sol` for BscScan source
  verification (compiler v0.8.24+commit.e11b9ed9, optimizer on/200 runs,
  `paris` EVM target, MIT license -- all taken directly from
  `bnb-issuer/hardhat.config.js`, not re-guessed). BscScan reports an
  "Exact Match" against the deployed bytecode at
  `0xd9bac2e48E090d42E5E71193D23e8efAAF9a054c`.
- This closes the gap flagged in the previous BNB Chain disclosure: the
  proof-of-reserve page previously said the source was "not yet
  separately submitted for BscScan's own source verification" while a
  missing-logo investigation had separately surfaced that an earlier
  draft of that same page had claimed it *was* verified, before it
  actually was -- both now resolved together by making the underlying
  claim true. `website/legal/proof-of-reserve.html` updated to link the
  verified source directly instead of describing its status.
- This step (public source verification) is a prerequisite for the
  project owner's own separate BscScan "Verified Address" ownership
  claim, which requires signing with the deployer key and was
  explicitly left to them -- not performed here.

---

## Submitted BscScan token info, fixed a real logo-size bug, disclosed CAC/USDT trade history

### 2026-08-10

- With BscScan source verification (previous entry) and the project
  owner's own ownership claim both done, submitted BscScan's "Update
  Token Info" form (ticket #840112): official site/email, description,
  and a 32x32 SVG logo hosted at
  `website/assets/cac-logo-32.svg` (BscScan requires a link, not a
  direct upload).
- Cropping the logo for that submission surfaced an unrelated real bug:
  `website/assets/logo.png` was 2000x1361px / 2.3MB despite being
  rendered at 32x32px by CSS on every page -- fixed by replacing it
  with the same square crop, downsized to 256x256 (118KB, ~19x
  smaller). Verified locally before committing.
- Disclosed four small CAC/USDT PancakeSwap round-trip trades (same
  deployer/reserve wallet on both sides of each) in
  `website/legal/proof-of-reserve.html`, same treatment as the earlier
  Stellar CAC/XLM seed trade -- all four tx hashes independently
  verified against their on-chain receipts (confirmed real `Sync`/
  `Swap` events on the actual pool contract, confirmed success,
  cross-checked implied price) before writing up the disclosure,
  rather than taking the reported amounts on faith.
- BscScan's confirmation email noted their paid Priority Support and
  Featured Listing tiers have no published pricing (inquiry-only) --
  researched and reported honestly rather than guessing a number.

---

## Added the BNB Chain price source to both wallets' live price display

### 2026-08-10

- `web-wallet/price.js` and `cac_wallet/lib/services/price_service.dart`
  previously only checked Stellar's DEX for CAC's price. Extended both
  to also try the CAC/USDT PancakeSwap pool via GeckoTerminal's API
  first (falling back to Stellar), and to label the on-screen
  disclaimer with whichever source actually answered rather than
  hardcoding "Stellar DEX" -- both remain honest that this is thin,
  project-seeded liquidity, not a reliable market price.
- Verified, not just written: `flutter analyze` and the full test
  suite (40 tests) both clean, and `price.js` loaded directly in a
  browser against the live GeckoTerminal endpoint to confirm it
  actually returns the real pool price with the correct source label.

---

## Added a live USD estimate to the Send amount field

### 2026-08-10

- Both wallets' Send screens now show a live "~$X.XX estimated"
  value under the amount field as you type, using the same price
  source as the home balance (previous entry). Fetches the price once
  per screen visit rather than per keystroke -- every keystroke after
  that is a local multiplication, no repeated API calls.
- Verified in-browser for web-wallet: created a real (throwaway)
  wallet, typed an amount on the Send screen, and confirmed the
  estimate appeared with the correct source label, updated live as
  the amount changed, and cleared correctly when the field was
  emptied. `flutter analyze` and the full test suite (40 tests) clean
  for the mobile side.

---

## Added a "Buy / Sell CAC" button to the mobile home screen

### 2026-08-10

- New action button on `cac_wallet`'s home screen opens PancakeSwap's
  own swap UI externally, pre-filled for CAC/USDT, rather than adding
  any BNB Chain key management or DEX-execution logic to the wallet
  itself -- picked as the option that doesn't expand what the wallet
  custodies or is responsible for signing. Uses the same external-link
  pattern already used for "View on Explorer."
- Verified the exact URL in a browser first: PancakeSwap's swap page
  resolves it to "From: USDT (BNB Chain)" / "To: CAC (BNB Chain)"
  correctly pre-filled, not just that it loads. `flutter analyze` and
  the full test suite (40 tests) both clean.

---

## Added WalletConnect swap to the mobile wallet

### 2026-08-11

- New "Connect Wallet & Swap (WalletConnect)" screen in `cac_wallet`,
  alongside (not replacing) the external-link "Buy / Sell CAC" button.
  Pairs with the user's own external wallet app (MetaMask, Trust
  Wallet, etc.) via Reown AppKit, restricted to a BSC-only required
  namespace, and drives a PancakeSwap CAC<->USDT swap through it --
  the wallet still never holds a BSC key or signs anything itself;
  every transaction is built as unsigned calldata here and signed in
  the connected wallet app.
- New pure ABI-encoding module (`lib/services/pancake_swap.dart`) for
  the PancakeSwap Router calldata, decimal amount parsing/formatting,
  and slippage math -- fully unit-tested (15 new tests) without
  needing a live connection.
- Found and fixed a real Android toolchain conflict along the way:
  `reown_appkit` pulls in `appcheck` (wallet-detection) and
  `coinbase_wallet_sdk`, both of which needed newer Kotlin/AGP/minSdk
  than this project is pinned to. Pinned `appcheck` to the last
  release on the older toolchain rather than bumping the whole
  project's Kotlin/AGP/Gradle for it, and raised `minSdkVersion` from
  21 to 23 (Android 6.0) for `coinbase_wallet_sdk`'s requirement.
- Every BSC address involved (PancakeSwap Router, CAC, USDT) was
  re-verified against BscScan before use rather than trusted from
  memory -- worth calling out because a first recollection of the
  router address was in fact wrong (39 hex characters, not 40).
- `flutter analyze` and the full test suite (55 tests) clean; a real
  `flutter build apk --release` succeeds. Not verified in this
  environment: an actual WalletConnect pairing handshake or a real
  signed swap against a live external wallet -- needs real-device
  testing. See PARAMETERS.md section 31 for the full write-up.

---

## Added air-gapped offline signing (in place of Ledger/Trezor support)

### 2026-08-11

- Requested hardware wallet support; researched Ledger's and Trezor's
  current SDKs and coin-registration requirements first rather than
  assuming it was buildable. Both gate device signing behind an
  officially registered coin list -- Trezor's forum states they aren't
  accepting new coins at all right now, and Ledger's current docs
  don't confirm any path for an unregistered coin either. Neither is
  something this project can just apply its way past.
- Built the alternative that gets the same real security property
  (seed never touches an internet-connected device) without vendor
  approval: air-gapped signing between two instances of `cac_wallet`
  itself. An online, watch-only device (an xpub only, no seed) builds
  an unsigned spend and hands it off as QR/text; an offline device
  holding the seed (meant to stay in airplane mode) signs it and hands
  back a ready-to-broadcast raw transaction -- it has no broadcast
  button at all, keeping the two roles strictly separated. Not a
  BIP-174 PSBT implementation -- a minimal, purpose-built format, same
  spirit as this wallet's existing multisig proposal format, since
  both ends are always this same wallet's own code.
- New Home-screen actions "Offline Send" and "Sign Offline"; new pure
  module `lib/crypto/offline_signing.dart`.
- Unusually strong verification for this kind of feature: a test signs
  the same transaction both the normal way and via the offline path
  and asserts the raw output is **byte-for-byte identical** (possible
  because this wallet's ECDSA signing is already RFC6979-deterministic)
  -- not just "didn't crash," but "produced the exact same valid
  signature." Also tested: the safety check that refuses to sign an
  input that doesn't actually belong to the seed being used.
  `flutter analyze` and the full test suite (61 tests, 6 new) clean;
  a real `flutter build apk --release` succeeds. Not verified here: an
  actual two-device QR handoff and a broadcast of something genuinely
  signed on separate hardware -- needs real-device testing. See
  PARAMETERS.md section 32 for the full write-up.

---

## Added multi-recipient batch sends (both platforms)

### 2026-08-13

- Send screens on both `web-wallet` and `cac_wallet` now support
  several recipients in one transaction (one shared fee/change output
  instead of sending separately to each). Nothing changed at the
  signing layer -- both platforms' `buildAndSignTransaction()` already
  accepted an arbitrary outputs list; this was purely a UI and
  service-layer change (`WalletService.sendTransaction()` now takes a
  `List<SendRecipient>` on mobile; the web send form builds dynamic
  recipient rows instead of one fixed address/amount pair).
- Mobile: `flutter analyze` and the full test suite (61 tests) clean;
  a real `flutter build apk --release` succeeds.
- Web: no JS test suite exists for `web-wallet`, so verified directly
  in-browser -- add/remove recipient rows, the combined fiat total
  estimate, the address book's "Use" button correctly targeting the
  last-focused row, and the full send path executing cleanly. See
  PARAMETERS.md section 33 for the full write-up.

---

## Added native mobile push notifications for incoming payments

### 2026-08-13

- `cac_wallet` can now register a device to be notified when its
  active address receives a payment, even while the app is closed --
  the existing in-app "new transaction" banner only shows up while
  the app is already open. Uses Firebase Cloud Messaging, a different
  mechanism from web-wallet's existing Web Push/VAPID system (browser-
  only, no Flutter equivalent) and a new incoming-payment trigger
  (the existing gateway push system only covered staking deposit/
  reward events, not ordinary payments).
- New gateway endpoint `POST /v1/push/mobile/register` (no auth
  required, address-keyed -- same convention as the balance/utxo/
  history endpoints, not the account-keyed Web Push one), a new
  `mobile_push_registrations` table, and a new watcher step
  (`mobile_notify.py`) that detects a registered address's balance
  increasing and sends a push.
- Genuinely blocked on external credentials this assistant can't
  create (a Firebase project's service account key and app config
  values), same standing constraint as the Reown/WalletConnect project
  ID. Built and verified everything possible without them, designed to
  stay completely inert until they're supplied: `cac_wallet`
  initializes Firebase from Dart-side config values rather than
  `google-services.json`/the Android Gradle plugin specifically so
  adding this didn't require touching (or risk breaking) the already-
  working Android build before real credentials exist -- confirmed
  empirically with a real `flutter build apk --release`, not just
  assumed. `flutter analyze` clean. Gateway: new/changed Python files
  pass `py_compile` and import cleanly with the two new dependencies
  actually installed (not just assumed to resolve); the new endpoint's
  request validation and the watcher's empty-state path were both
  exercised directly. See PARAMETERS.md section 34 for the full
  write-up. (Deployed to the live gateway on 2026-08-13 alongside
  batch sends -- still fully inert pending real Firebase credentials.)

---

## Deployed batch sends and push notifications; direct on-chain PancakeSwap price

### 2026-08-13

- Deployed the above two features to production: synced
  `vps-gateway/` to `/opt/cac-gateway` (new pip deps installed, DB
  migration run, `cac-gateway.service` restarted), synced `web-wallet/`
  to `codexacoin.com/wallet/`, and published a freshly rebuilt release
  APK to `codexacoin.com/downloads/` with a regenerated GPG-signed
  `SHA256SUMS`. Verified live, not just "deployed": hit the new
  `/v1/push/mobile/register` endpoint against the real gateway and
  confirmed the row landed in (and was removable from) the actual
  production database; confirmed the live `price.js`/`app.js` being
  served match the new source; confirmed the live `SHA256SUMS` hash
  for the APK matches the local build byte-for-byte.
- Both wallets' CAC/USD price estimate now reads the CAC/USDT
  PancakeSwap V2 pool's reserves directly via a raw `eth_call` to
  `getReserves()` over a public BSC RPC endpoint, rather than only
  through GeckoTerminal's indexed API. GeckoTerminal and the existing
  Stellar DEX fallback remain as fallbacks if the direct RPC call
  fails. Verified the pair's `token0()`/`token1()` order and decimals
  on-chain before writing any code (rather than assuming), and
  confirmed the new code path in both a real browser (CORS actually
  works against the public RPC endpoint) and the mobile runtime,
  matching a hand-computed value from the same raw reserve data.

---

## Fixed bad-txns-fee-not-enough; adjustable fees; referral copy/history

### 2026-08-13

- **Fixed a live bug reported by a user**: sends were failing on-chain
  with `bad-txns-fee-not-enough`. Root cause: the node's consensus
  minimum fee (`CFeeRate::GetFee`) rounds up
  (`ceil(rate*size/1000)`); every client-side fee calculation on both
  platforms rounded down (floor/truncating division). Whenever
  `rate*size` wasn't an exact multiple of 1000 -- true for nearly
  every real transaction -- the wallet computed exactly 1 satoshi less
  than the network requires. Fixed all 8 fee-computation sites across
  both platforms (regular send, multisig propose, offline/air-gapped
  send, fee-bump). Verified by brute-forcing every vsize from 100-5000
  bytes against the exact consensus formula in both the Dart runtime
  and a real browser's JS engine -- zero mismatches after the fix.
- **Adjustable network fee**: the send screen on both platforms now
  shows the gateway's recommended sat/vB rate with +/- controls and a
  direct input, so a user can pay more than the recommendation if they
  want. Can't go lower -- this coin enforces a single fixed consensus
  minimum, not a real congestion market, so anything lower would just
  get rejected; the send handler re-fetches the current floor at send
  time and only honors an override that's still above it.
- **Referral code copy + history**: web wallet's referral card gained
  a Copy button and a history list (new `GET /v1/referral/history`)
  showing every referred user (masked email) and what they've earned,
  not just an aggregate count. Mobile gained a whole new `ReferralScreen`
  (previously mobile had no way to view/share your own code at all,
  only to enter someone else's at signup) with copy, share, the same
  history list, and a withdraw form.
- **Fixed a second, unrelated live bug found while testing the
  above**: `let txPollHandle` (the live new-tx-banner poller) was
  declared far below `boot()`, which can synchronously reach into
  `enterWallet()` and start polling before the module finishes
  evaluating top to bottom. Any user with an existing wallet and no
  PIN set hit a "Cannot access before initialization" TDZ error on
  every page load, which crashed `boot()` and left the whole UI blank.
  Moved the declaration earlier, before `boot()` is ever called.
- Deployed all of the above live: gateway restarted with the new
  endpoint (verified end-to-end against a real SQLite DB and the live
  auth-required response), web wallet redeployed to
  `codexacoin.com/wallet/`, and a freshly rebuilt release APK
  published to `codexacoin.com/downloads/` with a regenerated
  GPG-signed `SHA256SUMS`.

---

## Pre-fork history (inherited from Blackcoin More)

Everything above `## Phase 1` in this file is CodexaCoin's own history. The
inherited Blackcoin More changelog (covering the v26.2.x line this fork was
taken from) is preserved unmodified in `codexacoin-core/CHANGELOG.md`.
