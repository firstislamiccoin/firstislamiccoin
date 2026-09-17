// Copyright (c) 2011-2022 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <bench/bench.h>
#include <consensus/validation.h>
#include <crypto/sha256.h>
#include <node/miner.h>
#include <random.h>
#include <test/util/mining.h>
#include <test/util/script.h>
#include <test/util/setup_common.h>
#include <txmempool.h>
#include <validation.h>


#include <vector>

static void AssembleBlock(benchmark::Bench& bench)
{
    const auto test_setup = MakeNoLogFileContext<const TestingSetup>();

    CScriptWitness witness;
    witness.stack.push_back(WITNESS_STACK_ELEM_OP_TRUE);

    // Collect some loose transactions that spend the coinbases of our mined blocks
    // FirstIslamicCoin: regtest only accepts proof-of-work up to height 500
    // (consensus.nLastPOWBlock, kernel/chainparams.cpp) -- every block here is
    // mined via MineBlock()'s PoW loop, so mining NUM_BLOCKS must leave the
    // chain tip at height <= 500. The bench.run() lambda below builds (but
    // never connects) a candidate block on top of that tip without advancing
    // it, so leaving one block of headroom (tip at 499, candidates targeting
    // height 500) covers every iteration. coinbaseMaturity lowered to match
    // regtest's real consensus.nCoinbaseMaturity (10) rather than upstream's
    // unrelated 500; it only needs to exceed the real maturity rule, not
    // equal it.
    constexpr size_t NUM_BLOCKS{499};
    constexpr size_t coinbaseMaturity{10};
    std::array<CTransactionRef, NUM_BLOCKS - coinbaseMaturity + 1> txs;
    for (size_t b{0}; b < NUM_BLOCKS; ++b) {
        CMutableTransaction tx;
        tx.vin.emplace_back(MineBlock(test_setup->m_node, P2WSH_OP_TRUE));
        tx.vin.back().scriptWitness = witness;
        // FirstIslamicCoin: DUST_RELAY_TX_FEE (policy.h) is 100000 fils/kvB
        // here, ~33x vanilla Bitcoin's default 3000 sat/kvB, so the dust
        // threshold scales the same way -- upstream's 1337 sat output
        // cleared it there but falls below it here (rejected as dust).
        tx.vout.emplace_back(100000, P2WSH_OP_TRUE);
        if (NUM_BLOCKS - b >= coinbaseMaturity)
            txs.at(b) = MakeTransactionRef(tx);
    }
    {
        LOCK(::cs_main);

        for (const auto& txr : txs) {
            const MempoolAcceptResult res = test_setup->m_node.chainman->ProcessTransaction(txr);
            assert(res.m_result_type == MempoolAcceptResult::ResultType::VALID);
        }
    }

    bench.run([&] {
        PrepareBlock(test_setup->m_node, P2WSH_OP_TRUE);
    });
}
static void BlockAssemblerAddPackageTxns(benchmark::Bench& bench)
{
    FastRandomContext det_rand{true};
    auto testing_setup{MakeNoLogFileContext<TestChain100Setup>()};
    testing_setup->PopulateMempool(det_rand, /*num_transactions=*/1000, /*submit=*/true);
    node::BlockAssembler::Options assembler_options;
    assembler_options.test_block_validity = false;

    bench.run([&] {
        PrepareBlock(testing_setup->m_node, P2WSH_OP_TRUE, assembler_options);
    });
}

BENCHMARK(AssembleBlock, benchmark::PriorityLevel::HIGH);
BENCHMARK(BlockAssemblerAddPackageTxns, benchmark::PriorityLevel::LOW);
