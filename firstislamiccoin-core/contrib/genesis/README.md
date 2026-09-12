# Genesis mining tool

`generate_genesis.py` builds a FirstIslamicCoin genesis block and brute-forces
its `nNonce`. The coinbase carries the whole premine as equal, spendable
outputs; see [`docs/genesis.md`](../../../docs/genesis.md) for why it is split
and for the values currently pinned in `src/kernel/chainparams.cpp`.

It needs only Python 3.8+ with OpenSSL's `hashlib.scrypt`. No build is
required, unlike the C++ `generate_genesis.cpp` inherited from upstream CAC,
which it replaces.

## Trusting the output

The script reimplements transaction and header serialization, so it proves
itself before it is used:

```bash
python3 contrib/genesis/generate_genesis.py --self-test
```

This rebuilds upstream CAC's three live genesis blocks and Blackcoin's mainnet
genesis from their published parameters, and checks the merkle root, header
hash and scrypt proof of work of each.

The node checks the result too: `chainparams.cpp` `assert()`s every network's
genesis hash and merkle root at startup, so a wrong value cannot ship quietly.

## Usage

```bash
python3 contrib/genesis/generate_genesis.py \
  --network regtest --time 1789171200 --bits 207fffff \
  --script 76a91470e519799aeef0396b253b70a5f523d2fed89d6488ac
```

| Option | Default | |
|---|---|---|
| `--script` | *(required)* | premine output `scriptPubKey`, hex |
| `--outputs` | `1000` | number of equal premine outputs |
| `--premine` | `14000000000` | total premine, whole coins |
| `--time` | `1789171200` | genesis `nTime` |
| `--bits` | `1e0fffff` | compact target, hex |
| `--phrase` | FIC timestamp phrase | coinbase message |
| `--nonce` | — | verify a known nonce instead of mining |
| `--workers` | CPU count | mining processes |

It prints `nNonce`, `hashGenesisBlock` and `hashMerkleRoot` to paste into
`chainparams.cpp`.

## Three traps, all inherited and all real

1. **`nVersion` must be 7.** `CheckBlockHeader()` rejects `nVersion < 7` once
   `IsProtocolV2()` holds, which it does for any 2026 timestamp.
2. **Proof of work is checked against `GetPoWHash()` (scrypt), never
   `GetHash()`.** For `nVersion > 6`, `GetHash()` is SHA256d.
3. **The coinbase `scriptSig` may be at most 100 bytes**
   (`consensus/tx_check.cpp`). The FIC phrase encodes to 99; the tool refuses
   anything over the limit.
