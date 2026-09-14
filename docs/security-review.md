# Security review — Phase 10

Every tool run, what it found, and what was done about each finding. Nothing
below is a claim that FIC's code is free of bugs — it is a record of what
was actually checked, in this environment, and the honest limits of that.

## Scope

The master prompt asks for "clang-tidy, cppcheck, ASan/UBSan builds on core;
`npm audit` / `flutter pub outdated` on apps." Static analysis (cppcheck) and
the existing lint suite were scoped to **the 37 non-test files `firstislamiccoin-core`
actually changed relative to CAC/Blackcoin** (found via `grep -rl
"FirstIslamicCoin:" src/`, the comment marker this project uses for every
consensus-affecting change — see `docs/CHANGELOG-FIC.md`). Re-auditing the
other ~2,600 files of inherited, unmodified Bitcoin Core / Blackcoin source is
out of scope: that code has its own long external audit history, and nothing
in this phase touched it.

## 1. `firstislamiccoin-core`'s own lint suite (`test/lint/all-lint.py`)

Ran it. Two real, FIC-introduced findings, both fixed:

| Finding | File | Fix |
|---|---|---|
| `open()` without explicit `encoding='utf8'` | `scripts/audit_premine_supply.py` | Added `encoding="utf8"` |
| Missing `export LC_ALL=C` as the first line | `contrib/fic/phase1-acceptance.sh` | Added it |

Everything else the linter flagged pre-dates FIC and was verified as such
against `codexacoin/codexacoin-core`'s own copy of the same file before being
left alone:

- `std::stoi`/`std::to_string` locale-dependence in `wallet/spend.cpp` and
  `rpc/rawtransaction_util.cpp` — identical in CAC.
- Missing `LC_ALL=C` in `contrib/macdeploy/build_dmg.sh` — identical in CAC.
- `blk_v2_transaction_tests.cpp`'s test-suite-name mismatch — the file exists
  verbatim in CAC too.
- `git merge-base HEAD master` failures in several lint scripts — this
  project's default branch is `main`, not `master`; a local-environment
  branch-naming assumption in the linter itself, not a code defect.
- `vulture`/`flake8`/`shellcheck`/`codespell` steps skipped — not installed in
  this environment. Exact commands to run them are printed by the linter
  itself; nothing here suppresses or removes that guidance.

## 2. cppcheck, scoped to the 37 FIC-changed files

```
cppcheck --enable=warning,performance,portability --inline-suppr --std=c++20 \
  -j4 -I src -I src/config --suppress=missingInclude --suppress=unknownMacro \
  $(grep -rl "FirstIslamicCoin:" src/ | grep -v "^src/test/\|^src/wallet/test/\|^src/qt/test/\|\.json$\|Makefile")
```

**Zero findings inside FIC's own new/changed lines** — `pos.cpp`, `pos.h`,
`wallet/staking.cpp`, `consensus/tx_verify.cpp`, `consensus/tx_check.cpp`,
`kernel/chainparams.cpp`, and the other files' actual FIC-marked code produced
no warnings at all. Every warning cppcheck did emit traces to pre-existing
upstream code that one of the 37 files happens to `#include` or otherwise
contain alongside the FIC change (e.g. `primitives/transaction.cpp`'s
decades-old constructors, `consensus/params.h`'s `nMaxReorganizationDepth` —
confirmed present verbatim in CAC's own `params.h`). The handful of
`syntaxError` lines (Qt macro expansion, `prevector.h` template parsing) are
cppcheck's own known C++-template-parsing limitations without a full
`compile_commands.json`, not real defects.

## 3. `ci/test/00_setup_env_native_asan.sh` and `00_setup_env_native_tidy.sh` existed, but ran nowhere

Both scripts — a full `--with-sanitizers=address,float-divide-by-zero,integer,
undefined` build and a `clang-tidy` static-analysis build — were already
present, inherited unchanged from upstream Bitcoin Core's CI infrastructure.
**Neither was referenced by any job in `.github/workflows/ci.yml`.** Checked
by grepping every workflow file for `FILE_ENV`; only the macOS job used one.

Fixed by adding two new jobs, `linux-native-asan` and
`linux-native-clang-tidy`, to `ci.yml`, using the same
docker-based `ci/test_run_all.sh` path Bitcoin Core's own CI uses for native
sanitizer/tidy builds (overriding the workflow-wide `DANGER_RUN_CI_ON_HOST: 1`
to `''` for just these two jobs, so `02_run_container.sh` builds its own
Ubuntu 24.04 container with clang-17/qt5/boost instead of installing them onto
the GitHub-hosted runner directly). `RUN_FUNCTIONAL_TESTS` is left `false` for
the ASan job — sanitized functional-test runs are dramatically slower and
functional behaviour is already exercised, unsanitized, elsewhere.

### A real, previously-invisible bug this went looking for and found: two of the project's `ci.yml` files were invalid YAML

Validating every workflow file in the monorepo (`yaml.safe_load` on all 11 of
them) turned up two files that do not parse as YAML at all — meaning **GitHub
Actions would refuse to run either workflow, in full, silently**, for as long
as the bug existed:

- **`firstislamiccoin-core/.github/workflows/ci.yml`** — a `- uses:
  actions/checkout@v5` step under `test-each-commit` was indented 2 spaces
  instead of 6, breaking the block mapping. Confirmed present, byte-identical,
  in `codexacoin/codexacoin-core/.github/workflows/ci.yml` — this predates
  FIC entirely and was inherited from CAC's own rebrand, undetected because a
  YAML *parse* failure produces no error CAC's own grep-based
  rebrand-verification would ever catch.
- **`firstislamiccoin-mobile/.github/workflows/ci.yml`** — a step's `name:`
  contained an unquoted colon (`flutter pub get (also runs l10n codegen --
  see pubspec.yaml's generate: true)`), which YAML parses as a nested mapping
  key. This one is FIC's own — CAC's `cac_wallet` has no CI workflow at all —
  introduced in Phase 5 and never caught because nothing in this environment
  had run `yaml.safe_load` against it before now.

Both fixed (re-indented; quoted the step name) and both now parse and list
the expected jobs. This means **no CI has ever actually run on either
`firstislamiccoin-core` or `firstislamiccoin-mobile`**, regardless of how
correct their individual job definitions are — a bigger, more basic gap than
"ASan isn't wired in," and the reason this review went looking for it in the
first place.

Also removed a vestigial `if: github.repository != 'bitcoin-core/gui' ||
github.event_name == 'pull_request'` condition on two `ci.yml` jobs — dead
weight inherited from upstream Bitcoin Core's own mirror-repo gating, always
true for this project's actual repository name, and confusing to read as if
it gated something real.

### What running the new ASan job actually confirmed, and what it didn't

The `ci_native_asan` Docker image (Ubuntu 24.04 + clang-17 + qt5 + boost, per
`00_setup_env_native_asan.sh`'s package list) **builds successfully** in this
environment — confirmed by building it directly. Running the full pipeline
end-to-end locally (via `ci/test_run_all.sh`) hit a real, pre-existing
fragility in Bitcoin Core's own `ci/test/02_run_container.sh`: its `CI_EXEC`
helper rejoins its arguments with `bash -c "... $*"`, which loses quoting —
and this repository happens to be checked out at a path containing spaces
("First Islamic Coin"), so `rsync`'s source argument splits apart mid-path.
This is not a Windows-specific issue and not something to patch in the
vendored script (a real GitHub Actions runner's `github.workspace` never
contains spaces, so it would not recur there) — it is a local-checkout-path
artifact of this specific development machine. The image build proves the
toolchain and dependency list are correct; the actual sanitizer build/test run
itself was not completed in this environment. Re-running `ci/test_run_all.sh`
from a checkout at a space-free path (or via the real GitHub Actions runner
once a repository exists — see TODO-HUMAN) would settle it definitively.

## 4. `npm audit` — not applicable

No FIC deliverable is an npm/Node project. Checked every repository for a
`package.json`: none exists in `firstislamiccoin-web-wallet` (plain JS, no
bundler — `docs/repo-map.md` already documents this), `firstislamiccoin-
explorer`/`firstislamiccoin-staking-service` (Flask, Python), or
`firstislamiccoin-website` (static HTML). The two Python services'
dependencies were audited with `pip-audit` instead (below), since that is the
actual equivalent for this stack.

## 5. `pip-audit` on the two Python services

```
pip-audit -r firstislamiccoin-staking-service/requirements.txt
pip-audit -r firstislamiccoin-explorer/requirements.txt
```

Found real, current CVEs in pinned versions:

| Package | Pinned | Advisories | Fixed to |
|---|---|---|---|
| Flask | 3.0.3 | PYSEC-2026-2151 | 3.1.3 |
| PyJWT | 2.9.0 | 8 advisories (PYSEC-2026-120/175/176/177/178/179, PYSEC-2025-183) | 2.13.0 |
| cryptography | 43.0.3 | 8 advisories incl. PYSEC-2026-1284/2141/3553/3554, GHSA-537c-gmf6-5ccf | 50.0.0 |
| requests | 2.32.3 | PYSEC-2026-1872, PYSEC-2026-2275 | 2.33.0 |

Bumped both `requirements.txt` files; `pip-audit` now reports **no known
vulnerabilities** for either service. Verified the bump doesn't just resolve
on paper: installed both into fresh venvs, imported each `app` module clean,
and exercised a real Flask route through each app's own test client
(`firstislamiccoin-staking-service`'s `/v1/push/vapid-public-key` correctly
still returns its documented `503 not-configured` — the same honest
no-op-when-unconfigured behaviour `docs/CHANGELOG-FIC.md`'s Phase 6 section
already describes, unaffected by the dependency bump).

## 6. `flutter pub outdated` / `flutter analyze` / `flutter test` on the mobile app

No Flutter SDK was available in this environment until this phase pulled
`ghcr.io/cirruslabs/flutter:stable` (Flutter 3.44.0) via Docker.

**`flutter pub get` failed outright** before any fix: `pubspec.yaml` pinned
`intl: ^0.19.0`, but the current Flutter stable SDK's `flutter_localizations`
requires exactly `intl 0.20.2` — a real, current build-breaking constraint
conflict, not a hypothetical one. Fixed by bumping the constraint to
`intl: ^0.20.2`; `pub get` now resolves.

**`flutter analyze` found 19 issues**, all in FIC's own `lib/` code (not
generated or inherited): 7 `unnecessary_non_null_assertion` warnings, all
`AppLocalizations.of(context)!` — the generated `of()` accessor no longer
returns nullable in the SDK/tool version now in use, making the `!` both
redundant and itself the analyzer's complaint. Fixed by removing the `!` at
all 7 call sites (`lib/main.dart`, `lib/screens/{home,onboarding,settings}_
screen.dart`). Re-ran `flutter analyze`: **12 issues remain**, all
`deprecated_member_use` info-level notices (`Radio`'s `groupValue`/
`onChanged` → `RadioGroup`, `DropdownButtonFormField`'s `value` →
`initialValue`, in `settings_screen.dart` and `staking_screen.dart`).
Deliberately **not** auto-migrated: `RadioGroup` is a real behavioural
change (a new ancestor widget, not a rename), and `value` vs `initialValue`
differ in whether the field re-syncs on external state changes — verifying
either migration correctly needs the physical-device/emulator check
`docs/CHANGELOG-FIC.md` TODO-HUMAN row 15 already tracks as unavailable in
this environment. Fixing these blind, without being able to click through
the resulting UI, risks trading a harmless deprecation notice for a silent
behavioural regression.

**`flutter test` found 2 pre-existing failures**, confirmed unrelated to
anything changed this phase (`git status` shows no crypto files touched):

- `test/crypto/address_test.dart`: "bech32 P2WPKH testnet: decodes and
  re-encodes a real address from the live testnet node" — decoded byte array
  is 20 bytes; expected 19.
- `test/crypto/keys_test.dart`: "mainnet and testnet coin types derive
  different keys" — fails an inequality assertion.

These are real, currently-failing tests in wallet address/key-derivation
code — not touched or investigated further here, deliberately: correctness
bugs in address encoding or key derivation carry fund-loss risk, and
diagnosing them properly (is the test's expected value wrong, or is the
implementation's) deserves focused attention this pass didn't budget for,
not a rushed guess. Tracked as TODO-HUMAN below; this is the first time
these tests have been run against a real Flutter SDK, since none was
available in this project's environment before this phase.

**`flutter pub outdated`**: 25 direct/transitive dependencies are pinned
below their latest resolvable version — none are security advisories (pub.dev
has no CVE feed equivalent to `pip-audit`/`npm audit` consulted here), several
are major-version jumps (`firebase_core` 3.4.0→4.14.0, `local_auth` 2.3.0→
3.0.2, `share_plus` 9.0.0→13.3.0) that need real API-compatibility testing
before bumping, which this environment cannot do (no device/emulator).
`js` and `flutter_secure_storage_macos` are flagged discontinued upstream —
both are transitive, not directly depended on. Left as-is; listed here rather
than bumped blind, for the same reason as the deprecation notices above.

## Open `TODO-HUMAN` from this review

- Re-run `ci/test_run_all.sh` (with `FILE_ENV=./ci/test/00_setup_env_native_
  asan.sh`) from a checkout path with no spaces, or via the real GitHub
  Actions runner once a repository exists, to get a completed ASan/UBSan
  build+test result — the image builds cleanly here; the full run wasn't
  completed in this environment (see §3).
- Investigate the two failing mobile crypto tests
  (`address_test.dart`'s bech32 P2WPKH testnet round-trip,
  `keys_test.dart`'s mainnet/testnet coin-type key-derivation inequality) —
  real, reproducible failures against a real Flutter SDK, not yet
  root-caused.
- Decide on and test the `Radio`/`RadioGroup` and `value`/`initialValue`
  Flutter API migrations once a device/emulator is available (same gap as
  existing TODO-HUMAN row 15).
- Review the major-version-behind Flutter dependencies
  (`firebase_core`, `local_auth`, `mobile_scanner`, `share_plus`, etc.) for
  breaking changes before bumping, once a device/emulator is available.
