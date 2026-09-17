// Copyright (c) 2016-2022 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <bench/bench.h>
#include <bench/data.h>

#include <rpc/blockchain.h>
#include <streams.h>
#include <test/util/setup_common.h>
#include <util/chaintype.h>
#include <validation.h>

#include <univalue.h>

namespace {

struct TestBlockAndIndex {
    // FirstIslamicCoin: regtest, not mainnet -- see bench/data.h's
    // GenerateSampleBlock (also explains why block413567 isn't used here).
    const std::unique_ptr<const TestingSetup> testing_setup{MakeNoLogFileContext<const TestingSetup>(ChainType::REGTEST)};
    CBlock block{};
    uint256 blockHash{};
    CBlockIndex blockindex{};

    TestBlockAndIndex()
    {
        const auto sample_block = benchmark::data::GenerateSampleBlock(testing_setup->m_node);
        CDataStream stream(sample_block, SER_NETWORK);
        std::byte a{0};
        stream.write({&a, 1}); // Prevent compaction

        stream >> TX_WITH_WITNESS(block);

        blockHash = block.GetHash();
        blockindex.phashBlock = &blockHash;
        blockindex.nBits = block.nBits;
    }
};

} // namespace

static void BlockToJsonVerbose(benchmark::Bench& bench)
{
    TestBlockAndIndex data;
    bench.run([&] {
        auto univalue = blockToJSON(data.testing_setup->m_node.chainman->m_blockman, data.block, &data.blockindex, &data.blockindex, TxVerbosity::SHOW_DETAILS_AND_PREVOUT);
        ankerl::nanobench::doNotOptimizeAway(univalue);
    });
}

BENCHMARK(BlockToJsonVerbose, benchmark::PriorityLevel::HIGH);

static void BlockToJsonVerboseWrite(benchmark::Bench& bench)
{
    TestBlockAndIndex data;
    auto univalue = blockToJSON(data.testing_setup->m_node.chainman->m_blockman, data.block, &data.blockindex, &data.blockindex, TxVerbosity::SHOW_DETAILS_AND_PREVOUT);
    bench.run([&] {
        auto str = univalue.write();
        ankerl::nanobench::doNotOptimizeAway(str);
    });
}

BENCHMARK(BlockToJsonVerboseWrite, benchmark::PriorityLevel::HIGH);
