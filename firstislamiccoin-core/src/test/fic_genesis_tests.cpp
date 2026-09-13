// Copyright (c) 2026 The FirstIslamicCoin developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.
//
// The genesis premine, and the network parameters FirstIslamicCoin launches
// with. A drift in any value the brand and chain-parameter tables pin down
// should fail here rather than at launch.

#include <chainparams.h>
#include <chainparamsbase.h>
#include <consensus/amount.h>
#include <consensus/params.h>
#include <deploymentstatus.h>
#include <kernel/messagestartchars.h>
#include <pos.h>
#include <primitives/block.h>
#include <test/util/setup_common.h>
#include <util/chaintype.h>
#include <validation.h>

#include <boost/test/unit_test.hpp>

#include <algorithm>
#include <memory>
#include <string>
#include <vector>

namespace {

const CAmount PREMINE{14'000'000'000 * COIN};
const size_t GENESIS_OUTPUTS{1'000};
const std::string FIC_PHRASE{"FirstIslamicCoin 12/Sep/2026 \xe2\x80\x94 Bismillah, the first Shariah-conscious Proof-of-Stake network"};

std::vector<std::unique_ptr<const CChainParams>> AllNetworks()
{
    std::vector<std::unique_ptr<const CChainParams>> networks;
    networks.push_back(CChainParams::Main());
    networks.push_back(CChainParams::TestNet());
    networks.push_back(CChainParams::SigNet({}));
    networks.push_back(CChainParams::RegTest({}));
    return networks;
}

} // namespace

BOOST_FIXTURE_TEST_SUITE(fic_genesis_tests, BasicTestingSetup)

BOOST_AUTO_TEST_CASE(genesis_carries_exact_premine)
{
    for (const auto& chain : AllNetworks()) {
        const Consensus::Params& params{chain->GetConsensus()};
        const CBlock& genesis{chain->GenesisBlock()};
        BOOST_CHECK_EQUAL(params.nPremineTotal, PREMINE);
        BOOST_CHECK_EQUAL(genesis.GetHash(), params.hashGenesisBlock);

        BOOST_REQUIRE_EQUAL(genesis.vtx.size(), 1U);
        const CTransaction& coinbase{*genesis.vtx[0]};
        BOOST_CHECK(coinbase.IsCoinBase());
        BOOST_REQUIRE_EQUAL(coinbase.vout.size(), GENESIS_OUTPUTS);

        CAmount total{0};
        for (const CTxOut& out : coinbase.vout) {
            BOOST_CHECK_EQUAL(out.nValue, PREMINE / GENESIS_OUTPUTS);
            BOOST_CHECK(!out.scriptPubKey.empty());
            BOOST_CHECK(!out.scriptPubKey.IsUnspendable());
            total += out.nValue;
        }
        BOOST_CHECK_EQUAL(total, PREMINE);
        BOOST_CHECK_EQUAL(GetBlockSubsidy(0, params), PREMINE);
    }
}

BOOST_AUTO_TEST_CASE(genesis_timestamp_phrase)
{
    const std::vector<unsigned char> phrase(FIC_PHRASE.begin(), FIC_PHRASE.end());
    for (const auto& chain : AllNetworks()) {
        const CScript& script_sig{chain->GenesisBlock().vtx[0]->vin[0].scriptSig};
        BOOST_CHECK_LE(script_sig.size(), 100U); // consensus/tx_check.cpp
        BOOST_CHECK(std::search(script_sig.begin(), script_sig.end(), phrase.begin(), phrase.end()) != script_sig.end());
    }
}

BOOST_AUTO_TEST_CASE(proof_of_stake_from_block_one)
{
    for (const auto& chain : {CChainParams::Main(), CChainParams::TestNet()}) {
        const Consensus::Params& params{chain->GetConsensus()};
        BOOST_CHECK_EQUAL(params.nLastPOWBlock, 0);
        BOOST_CHECK_EQUAL(params.nPowSubsidy, 0);
        BOOST_CHECK_EQUAL(GetBlockSubsidy(1, params, /*fProofOfStake=*/false), 0);
    }

    // Regtest keeps a PoW window for the test harness; -lastpowblock=0
    // reproduces the mainnet rules.
    BOOST_CHECK_GT(CChainParams::RegTest({})->GetConsensus().nLastPOWBlock, 0);
    CChainParams::RegTestOptions opts;
    opts.last_pow_block = 0;
    BOOST_CHECK_EQUAL(CChainParams::RegTest(opts)->GetConsensus().nLastPOWBlock, 0);
}

BOOST_AUTO_TEST_CASE(genesis_outputs_mature_immediately)
{
    const auto chain{CChainParams::Main()};
    const Consensus::Params& params{chain->GetConsensus()};

    BOOST_CHECK(IsStakeMature(/*nCoinHeight=*/0, /*nSpendHeight=*/1, params));
    BOOST_CHECK(IsStakeMature(0, 2, params));

    // Every other coin still needs nCoinbaseMaturity confirmations.
    BOOST_CHECK(!IsStakeMature(1, 2, params));
    BOOST_CHECK(!IsStakeMature(1, params.nCoinbaseMaturity, params));
    BOOST_CHECK(IsStakeMature(1, 1 + params.nCoinbaseMaturity, params));
}

// SegWit and Taproot are version-bits deployments in this tree: the deployment
// entry alone decides whether witness programs are script-checked in blocks.
// CAC left both NEVER_ACTIVE on mainnet and testnet, so native SegWit and
// Taproot outputs were spendable without a signature by whoever produced the
// block. They must be enforced from genesis on every network.
BOOST_AUTO_TEST_CASE(segwit_and_taproot_active_from_genesis)
{
    for (const auto& chain : AllNetworks()) {
        BOOST_TEST_CONTEXT(ChainTypeToString(chain->GetChainType())) {
            const Consensus::Params& params{chain->GetConsensus()};
            for (const auto dep : {Consensus::DEPLOYMENT_SEGWIT, Consensus::DEPLOYMENT_TAPROOT}) {
                BOOST_CHECK_EQUAL(params.vDeployments[dep].nStartTime, Consensus::BIP9Deployment::ALWAYS_ACTIVE);
                VersionBitsCache cache;
                BOOST_CHECK(DeploymentActiveAfter(/*pindexPrev=*/nullptr, params, dep, cache));
            }
        }
    }
}

// Mainnet and testnet set CSVHeight = 0 ("fresh chain, active from genesis"),
// unlike upstream, where a buried deployment is never active at height 0.
// ContextualCheckBlock() used to assert pindexPrev != nullptr as soon as it
// judged CSV active, then dereference it two lines later regardless of the
// assert -- both unconditionally true for the genesis block itself, whose
// pindexPrev is null by definition. AcceptBlock() calls ContextualCheckBlock()
// for every block on disk during -reindex, genesis included, which is how
// this was found: a real -reindex of a running testnet node crashed
// ("Assertion `pindexPrev != nullptr' failed") a few seconds in. A normal
// startup never reaches it, and regtest and signet (CSVHeight = 1) never
// trigger the condition, which is why it went undetected until an operator
// actually reindexed a mainnet/testnet-shaped chain.
BOOST_AUTO_TEST_CASE(csv_active_from_genesis_on_main_and_testnet)
{
    VersionBitsCache cache;
    BOOST_CHECK(DeploymentActiveAfter(/*pindexPrev=*/nullptr, CChainParams::Main()->GetConsensus(), Consensus::DEPLOYMENT_CSV, cache));
    BOOST_CHECK(DeploymentActiveAfter(/*pindexPrev=*/nullptr, CChainParams::TestNet()->GetConsensus(), Consensus::DEPLOYMENT_CSV, cache));
    // Contrast: regtest and signet don't hit this until height 1.
    BOOST_CHECK(!DeploymentActiveAfter(/*pindexPrev=*/nullptr, CChainParams::RegTest({})->GetConsensus(), Consensus::DEPLOYMENT_CSV, cache));
    BOOST_CHECK(!DeploymentActiveAfter(/*pindexPrev=*/nullptr, CChainParams::SigNet({})->GetConsensus(), Consensus::DEPLOYMENT_CSV, cache));
}

BOOST_AUTO_TEST_CASE(mainnet_genesis_is_placeholder_until_key_ceremony)
{
    BOOST_CHECK(CChainParams::Main()->GenesisPremineIsPlaceholder());
    BOOST_CHECK(!CChainParams::TestNet()->GenesisPremineIsPlaceholder());
    BOOST_CHECK(!CChainParams::SigNet({})->GenesisPremineIsPlaceholder());
    BOOST_CHECK(!CChainParams::RegTest({})->GenesisPremineIsPlaceholder());
}

BOOST_AUTO_TEST_CASE(network_parameters_match_spec)
{
    struct Expected {
        ChainType type;
        MessageStartChars magic;
        uint16_t p2p_port;
        uint16_t rpc_port;
        int maturity;
        int64_t spacing;
        unsigned char p2pkh;
        unsigned char p2sh;
        unsigned char wif;
        std::vector<unsigned char> xpub;
        std::vector<unsigned char> xprv;
        std::string hrp;
    };
    const std::vector<Expected> expected{
        {ChainType::MAIN, {0xF1, 0x1C, 0x51, 0xA3}, 19770, 19771, 500, 64, 36, 28, 164,
         {0x04, 0x88, 0xB2, 0x1E}, {0x04, 0x88, 0xAD, 0xE4}, "fic"},
        {ChainType::TESTNET, {0xF1, 0x1C, 0x54, 0xB3}, 29770, 29771, 50, 64, 111, 196, 239,
         {0x04, 0x35, 0x87, 0xCF}, {0x04, 0x35, 0x83, 0x94}, "tfic"},
        {ChainType::REGTEST, {0xF1, 0x1C, 0x52, 0xC3}, 39770, 39771, 10, 1, 111, 196, 239,
         {0x04, 0x35, 0x87, 0xCF}, {0x04, 0x35, 0x83, 0x94}, "rfic"},
    };

    for (const Expected& e : expected) {
        const auto chain{e.type == ChainType::MAIN    ? CChainParams::Main() :
                         e.type == ChainType::TESTNET ? CChainParams::TestNet() :
                                                        CChainParams::RegTest({})};
        BOOST_TEST_CONTEXT(ChainTypeToString(e.type)) {
            const Consensus::Params& params{chain->GetConsensus()};
            BOOST_CHECK(chain->MessageStart() == e.magic);
            BOOST_CHECK_EQUAL(chain->GetDefaultPort(), e.p2p_port);
            BOOST_CHECK_EQUAL(CreateBaseChainParams(e.type)->RPCPort(), e.rpc_port);
            BOOST_CHECK_EQUAL(params.nCoinbaseMaturity, e.maturity);
            BOOST_CHECK_EQUAL(params.nTargetSpacing, e.spacing);
            BOOST_CHECK_EQUAL(params.nFixedStakeReward, 10 * COIN);
            BOOST_CHECK(chain->Base58Prefix(CChainParams::PUBKEY_ADDRESS) == std::vector<unsigned char>{e.p2pkh});
            BOOST_CHECK(chain->Base58Prefix(CChainParams::SCRIPT_ADDRESS) == std::vector<unsigned char>{e.p2sh});
            BOOST_CHECK(chain->Base58Prefix(CChainParams::SECRET_KEY) == std::vector<unsigned char>{e.wif});
            BOOST_CHECK(chain->Base58Prefix(CChainParams::EXT_PUBLIC_KEY) == e.xpub);
            BOOST_CHECK(chain->Base58Prefix(CChainParams::EXT_SECRET_KEY) == e.xprv);
            BOOST_CHECK_EQUAL(chain->Bech32HRP(), e.hrp);
            BOOST_CHECK_EQUAL(chain->Checkpoints().mapCheckpoints.size(), 1U); // genesis only
        }
    }
}

BOOST_AUTO_TEST_SUITE_END()
