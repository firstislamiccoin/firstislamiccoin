// Copyright (c) 2019 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOIN_BENCH_DATA_H
#define BITCOIN_BENCH_DATA_H

#include <cstdint>
#include <vector>

namespace node {
struct NodeContext;
} // namespace node

namespace benchmark {
namespace data {

extern const std::vector<uint8_t> block413567;

// FirstIslamicCoin: block413567 is a real, historical vanilla-Bitcoin block.
// It can never pass CheckBlock()/deserialize correctly under this chain's
// rules -- FIC's proof-of-work algorithm (scrypt) differs from Bitcoin's
// (SHA256d) entirely, on top of the nVersion<2 wire-format difference (see
// primitives/transaction.h). Benchmarks that need a real, currently-valid
// block (not just an opaque byte buffer) call this instead: it mines a
// small regtest chain via the same test/util/mining.h utilities the unit
// tests use, includes a few real spending transactions in the final block,
// and returns that block's network serialization. Requires an already
// running TestingSetup(ChainType::REGTEST) (mainnet can't be used here --
// FIC requires proof-of-stake from block 1, and PoS block construction
// needs a funded staking wallet, well beyond what a benchmark fixture
// should set up).
std::vector<uint8_t> GenerateSampleBlock(const node::NodeContext& node);

} // namespace data
} // namespace benchmark

#endif // BITCOIN_BENCH_DATA_H
