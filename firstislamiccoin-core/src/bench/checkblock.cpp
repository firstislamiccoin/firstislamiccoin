// Copyright (c) 2016-2022 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <bench/bench.h>
#include <bench/data.h>

#include <chainparams.h>
#include <common/args.h>
#include <consensus/validation.h>
#include <streams.h>
#include <util/chaintype.h>
#include <validation.h>
#include <test/util/setup_common.h>

// These are the two major time-sinks which happen after we have fully received
// a block off the wire, but before we can relay the block on to peers using
// compact block relay.

static void DeserializeBlockTest(benchmark::Bench& bench)
{
    // FirstIslamicCoin: block413567 (a real vanilla-Bitcoin block) can never
    // deserialize correctly here -- see bench/data.h's GenerateSampleBlock.
    const auto testing_setup = MakeNoLogFileContext<const TestingSetup>(ChainType::REGTEST);
    const auto sample_block = benchmark::data::GenerateSampleBlock(testing_setup->m_node);
    CDataStream stream(sample_block, SER_NETWORK);
    std::byte a{0};
    stream.write({&a, 1}); // Prevent compaction

    bench.unit("block").run([&] {
        CBlock block;
        stream >> TX_WITH_WITNESS(block);
        bool rewound = stream.Rewind(sample_block.size());
        assert(rewound);
    });
}

static void DeserializeAndCheckBlockTest(benchmark::Bench& bench)
{
    // FirstIslamicCoin: regtest, not mainnet -- see bench/data.h's
    // GenerateSampleBlock (also explains why block413567 isn't used here).
    ArgsManager bench_args;
    const auto chainParams = CreateChainParams(bench_args, ChainType::REGTEST);
    const auto testing_setup = MakeNoLogFileContext<const TestingSetup>(ChainType::REGTEST);
    Chainstate& chainstate = testing_setup->m_node.chainman->ActiveChainstate();
    const auto sample_block = benchmark::data::GenerateSampleBlock(testing_setup->m_node);

    CDataStream stream(sample_block, SER_NETWORK);
    std::byte a{0};
    stream.write({&a, 1}); // Prevent compaction

    bench.unit("block").run([&] {
        CBlock block; // Note that CBlock caches its checked state, so we need to recreate it here
        stream >> TX_WITH_WITNESS(block);
        bool rewound = stream.Rewind(sample_block.size());
        assert(rewound);

        BlockValidationState validationState;
        bool checked = CheckBlock(block, validationState, chainParams->GetConsensus(), chainstate);
        assert(checked);
    });
}

BENCHMARK(DeserializeBlockTest, benchmark::PriorityLevel::HIGH);
BENCHMARK(DeserializeAndCheckBlockTest, benchmark::PriorityLevel::HIGH);
