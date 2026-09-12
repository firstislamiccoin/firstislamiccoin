FirstIslamicCoin Core
=====================

![FirstIslamicCoin](fic_logo.png)

https://firstislamiccoin.com

What is FirstIslamicCoin?
-------------------------

FirstIslamicCoin (FIC) is a proof-of-stake digital currency. People who hold
FIC keep a node online and take turns producing blocks; whoever produces a
block receives **a fixed 10 FIC plus that block's transaction fees**. The
reward does not depend on how much is staked or for how long — a larger stake
only wins blocks more often — so there is no rate of return on a balance
anywhere in the protocol.

The design choices behind this, and the open questions it raises, are explained
in plain English in [`docs/shariah-compliance.md`](../docs/shariah-compliance.md).
That document is not a fatwa; no Shariah board has reviewed FIC yet.

What is FirstIslamicCoin Core?
------------------------------

FirstIslamicCoin Core is the reference node software: `firstislamiccoind`,
`firstislamiccoin-cli`, `firstislamiccoin-tx`, `firstislamiccoin-wallet` and the
`firstislamiccoin-qt` desktop wallet. It connects to the FirstIslamicCoin
peer-to-peer network, fully validates blocks and transactions, and can stake.

It is derived from Bitcoin Core by way of Blackcoin More and CAC. What changed
from CAC, and why, is in [`docs/CHANGELOG-FIC.md`](../docs/CHANGELOG-FIC.md).

**Status: pre-launch.** There is no mainnet yet. The mainnet genesis block pays
its premine to a placeholder pending the genesis key ceremony, and the node
refuses to run mainnet until it is replaced.

Network at a glance
-------------------

| | Mainnet | Testnet | Regtest |
|---|---|---|---|
| Block reward | 10 FIC + fees | 10 tFIC + fees | 10 + fees |
| Target block spacing | 64 s | 64 s | 1 s |
| Coin maturity / minimum stake age | 500 blocks | 50 blocks | 10 blocks |
| P2P / RPC port | 19770 / 19771 | 29770 / 29771 | 39770 / 39771 |
| Addresses | `F…`, `C…`, `fic1…` | `m…`/`n…`, `tfic1…` | `m…`/`n…`, `rfic1…` |
| Proof of work after genesis | none | none | window for tests; `-lastpowblock=0` for none |

Supply is 14,000,000,000 FIC in the genesis block plus 10 FIC per block. Every
constant is in [`docs/tokenomics.md`](../docs/tokenomics.md); the genesis blocks
are described in [`docs/genesis.md`](../docs/genesis.md).

Building
--------

See `doc/build-unix.md`, `doc/build-osx.md` and `doc/build-windows.md`. In short,
on Linux:

```bash
./autogen.sh
./configure --with-sqlite=yes --without-bdb
make -j"$(nproc)"
```

Testing
-------

Unit tests run with `make check`; FIC's own consensus tests are the
`fic_reward_tests`, `fic_genesis_tests` and `pos_tests` suites.

Functional tests run with `test/functional/test_runner.py`. FIC's own are
`feature_fic_genesis_premine.py`, `feature_fic_fixed_reward.py` and
`feature_pos_reorg.py`.

To check a running node's supply against the consensus rules end to end:

```bash
scripts/audit_premine_supply.py --rpcport 39771
```

License
-------

FirstIslamicCoin Core is released under the terms of the MIT license, and keeps
the copyright notices of every project it derives from. See [COPYING](COPYING)
or https://opensource.org/licenses/MIT.
