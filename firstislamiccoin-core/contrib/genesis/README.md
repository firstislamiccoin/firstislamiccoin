# Genesis mining tool

`generate_genesis.cpp` brute-forces the `nNonce` for a genesis block at a
given `(nTime, nBits)`, reusing the real `CreateGenesisBlock()` /
`FindGenesisBlock()` in `src/kernel/chainparams.cpp` — it does not
reimplement block or transaction serialization, so it cannot silently
disagree with the node about what a given genesis block actually hashes to.

Not wired into the autotools build (`Makefile.am`) — it's a one-off tool for
finalizing chain parameters, not a shipped binary. Build it manually after
building the main project (`./configure && make` from the repo root), then
compile and link against the resulting static libraries:

```bash
g++ -std=c++20 -I src -I src/config -DHAVE_CONFIG_H \
  -c contrib/genesis/generate_genesis.cpp -o /tmp/generate_genesis.o

g++ -std=c++20 /tmp/generate_genesis.o \
  src/.libs/libunivalue.a \
  src/libbitcoin_common.a \
  src/libbitcoin_util.a \
  src/libbitcoin_consensus.a \
  src/crypto/.libs/libbitcoin_crypto_base.a \
  src/crypto/.libs/libbitcoin_crypto_sse41.a \
  src/crypto/.libs/libbitcoin_crypto_avx2.a \
  src/crypto/.libs/libbitcoin_crypto_x86_shani.a \
  src/secp256k1/.libs/libsecp256k1.a \
  -lpthread \
  -o /tmp/generate_genesis
```

Usage:

```bash
/tmp/generate_genesis <network-label> <nTime> <nBits-hex>
# e.g.
/tmp/generate_genesis mainnet 1785326400 1e0fffff
```

Prints the mined `nNonce`, the resulting `hashGenesisBlock` /
`hashMerkleRoot`, and a ready-to-paste `CreateGenesisBlock(...)` +
`assert(...)` block for `kernel/chainparams.cpp`.

**Important:** proof-of-work is validated against `CBlockHeader::GetPoWHash()`
(scrypt) everywhere in this codebase, not `GetHash()` (SHA256d, and only for
`nVersion > 6` at that — see `primitives/block.cpp`). `FindGenesisBlock()`
already checks the right one; if you ever reimplement this logic elsewhere,
don't check `GetHash()` against the target or your genesis block will pass
local generation but fail `high-hash` the moment any node tries to load it.

See `PARAMETERS.md` §8 (repo root) for the currently-mined values for
mainnet/testnet/signet/regtest, and §9 for what's still a placeholder pending
real launch (the mainnet genesis here is already final; the *premine window*
mined on top of it is not — that's a separate, later mining ceremony).
