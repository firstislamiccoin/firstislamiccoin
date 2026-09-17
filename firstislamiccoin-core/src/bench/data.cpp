// Copyright (c) 2019-2021 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <bench/data.h>

#include <node/context.h>
#include <primitives/transaction.h>
#include <script/script.h>
#include <streams.h>
#include <sync.h>
#include <test/util/mining.h>
#include <test/util/script.h>
#include <txmempool.h>
#include <validation.h>
#include <validationinterface.h>

#include <cassert>

namespace benchmark {
namespace data {

#include <bench/data/block413567.raw.h>
const std::vector<uint8_t> block413567{std::begin(block413567_raw), std::end(block413567_raw)};

std::vector<uint8_t> GenerateSampleBlock(const node::NodeContext& node)
{
    // Mine enough blocks for a few coinbases to mature (regtest's real
    // consensus.nCoinbaseMaturity, kernel/chainparams.cpp), well inside the
    // regtest proof-of-work ceiling (consensus.nLastPOWBlock = 500).
    constexpr size_t NUM_SETUP_BLOCKS{15};
    constexpr size_t NUM_SPEND_TXS{5};

    CScriptWitness witness;
    witness.stack.push_back(WITNESS_STACK_ELEM_OP_TRUE);

    std::vector<COutPoint> coinbases;
    coinbases.reserve(NUM_SETUP_BLOCKS);
    for (size_t i{0}; i < NUM_SETUP_BLOCKS; ++i) {
        coinbases.push_back(MineBlock(node, P2WSH_OP_TRUE));
    }

    {
        LOCK(::cs_main);
        for (size_t i{0}; i < NUM_SPEND_TXS; ++i) {
            CMutableTransaction tx;
            tx.vin.emplace_back(coinbases.at(i));
            tx.vin.back().scriptWitness = witness;
            tx.vout.emplace_back(100000, P2WSH_OP_TRUE);
            const auto txr{MakeTransactionRef(tx)};
            const MempoolAcceptResult res{node.chainman->ProcessTransaction(txr)};
            assert(res.m_result_type == MempoolAcceptResult::ResultType::VALID);
        }
    }

    // Mine one more block; BlockAssembler pulls the transactions just
    // submitted from the mempool, so the result has a coinbase plus several
    // real spending transactions -- representative content for benchmarking
    // deserialization/CheckBlock/JSON-conversion speed.
    auto block{PrepareBlock(node, P2WSH_OP_TRUE)};
    auto valid{MineBlock(node, block)};
    assert(!valid.IsNull());

    CDataStream ss(SER_NETWORK);
    ss << TX_WITH_WITNESS(*block);
    std::vector<uint8_t> result(ss.size());
    memcpy(result.data(), ss.data(), ss.size());
    return result;
}

} // namespace data
} // namespace benchmark
