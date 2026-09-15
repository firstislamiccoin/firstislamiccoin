// Copyright (c) 2010 Satoshi Nakamoto
// Copyright (c) 2009-2021 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <kernel/chainparams.h>

#include <arith_uint256.h>
#include <chainparamsseeds.h>
#include <consensus/amount.h>
#include <consensus/merkle.h>
#include <consensus/params.h>
#include <hash.h>
#include <kernel/messagestartchars.h>
#include <logging.h>
#include <primitives/block.h>
#include <primitives/transaction.h>
#include <script/interpreter.h>
#include <script/script.h>
#include <uint256.h>
#include <util/chaintype.h>
#include <util/strencodings.h>

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <type_traits>
#include <vector>

/**
 * FirstIslamicCoin: the genesis coinbase message on every network. The em dash
 * is spelled as UTF-8 escapes so the bytes cannot depend on the compiler's
 * source character set. The phrase is 94 bytes, which makes the coinbase
 * scriptSig 99 of the 100 bytes consensus allows (consensus/tx_check.cpp).
 */
static const char* const FIC_GENESIS_TIMESTAMP = "FirstIslamicCoin 12/Sep/2026 \xe2\x80\x94 Bismillah, the first Shariah-conscious Proof-of-Stake network";
static constexpr uint32_t FIC_GENESIS_TIME = 1789171200; // 2026-09-12 00:00:00 UTC

/**
 * FirstIslamicCoin: the premine as nOutputs equal genesis outputs paying
 * premineScript. It is split so the chain can keep staking genesis outputs
 * until the first coinstake outputs mature -- see docs/genesis.md.
 */
static std::vector<CTxOut> GenesisPremineOutputs(const CScript& premineScript, CAmount nPremineTotal, unsigned int nOutputs = 1000)
{
    assert(nOutputs > 0 && nPremineTotal % nOutputs == 0);
    return std::vector<CTxOut>(nOutputs, CTxOut(nPremineTotal / nOutputs, premineScript));
}

static CScript P2PKHScript(const std::string& keyhash_hex)
{
    return CScript() << OP_DUP << OP_HASH160 << ParseHex(keyhash_hex) << OP_EQUALVERIFY << OP_CHECKSIG;
}

/**
 * Build the genesis block. FirstIslamicCoin: its coinbase outputs are the
 * premine and are spendable -- ConnectBlock() adds them to the UTXO set, and
 * IsStakeMature() exempts them from maturity. contrib/genesis/generate_genesis.py
 * serializes exactly this block to mine it.
 */
static CBlock CreateGenesisBlock(const std::vector<CTxOut>& premine, uint32_t nTime, uint32_t nNonce, uint32_t nBits, int32_t nVersion)
{
    CMutableTransaction txNew;
    txNew.nVersion = 1;
    txNew.nTime = nTime;
    txNew.vin.resize(1);
    txNew.vin[0].scriptSig = CScript() << 0 << CScriptNum(42) << std::vector<unsigned char>((const unsigned char*)FIC_GENESIS_TIMESTAMP, (const unsigned char*)FIC_GENESIS_TIMESTAMP + strlen(FIC_GENESIS_TIMESTAMP));
    txNew.vout = premine;

    CBlock genesis;
    genesis.nTime    = nTime;
    genesis.nBits    = nBits;
    genesis.nNonce   = nNonce;
    genesis.nVersion = nVersion;
    genesis.vtx.push_back(MakeTransactionRef(std::move(txNew)));
    genesis.hashPrevBlock.SetNull();
    genesis.hashMerkleRoot = BlockMerkleRoot(genesis);
    return genesis;
}

/**
 * Main network on which people trade goods and services.
 */
class CMainParams : public CChainParams {
public:
    CMainParams() {
        m_chain_type = ChainType::MAIN;
        consensus.signet_blocks = false;
        consensus.signet_challenge.clear();
        consensus.nMaxReorganizationDepth = 500;
        consensus.CSVHeight = 0; // fresh chain, active from genesis
        consensus.SegwitHeight = 0; // fresh chain, active from genesis
        consensus.MinBIP9WarningHeight = 0;
        consensus.powLimit = uint256S("00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.posLimit = uint256S("00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.posLimitV2 = uint256S("000000000000ffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.nTargetTimespan = 16 * 60; // 16 mins
        consensus.nTargetSpacingV1 = 60;
        consensus.nTargetSpacing = 64;
        consensus.fPowAllowMinDifficultyBlocks = false;
        consensus.fPowNoRetargeting = false;
        consensus.fPoSNoRetargeting = false;
        consensus.nRuleChangeActivationThreshold = 12000; // 80% of 15000
        consensus.nMinerConfirmationWindow = 15000; // nTargetTimespan / nTargetSpacing * 1000
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].bit = 28;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].nStartTime = Consensus::BIP9Deployment::NEVER_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].min_activation_height = 0; // No activation delay

        // Deployment of SegWit (BIP141, BIP143, and BIP147)
        // FirstIslamicCoin: this entry is what decides whether SegWit is enforced.
        // SegWit is a version-bits deployment in this tree, not a buried one, so
        // SegwitHeight above is never read. CAC left it NEVER_ACTIVE, which meant
        // witness programs were never script-checked in blocks (spendable by the
        // block producer with no signature), while the mempool refused properly
        // signed witness spends. Active from genesis on every network.
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].bit = 1;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].nStartTime = Consensus::BIP9Deployment::ALWAYS_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].min_activation_height = 0; // No activation delay

        // Deployment of Taproot (BIPs 340-342)
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].bit = 2;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nStartTime = Consensus::BIP9Deployment::ALWAYS_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].min_activation_height = 0; // No activation delay

        consensus.nProtocolV1RetargetingFixedTime = 1395631999;
        consensus.nProtocolV2Time = 1407053625;
        consensus.nProtocolV3Time = 1444028400;
        consensus.nProtocolV3_1Time = 1713938400;
        consensus.nLastPOWBlock = 0; // FirstIslamicCoin: proof-of-stake from block 1
        consensus.nStakeTimestampMask = 0xf; // 15
        consensus.nCoinbaseMaturity = 500; // also the minimum stake age: 500 blocks x 64 s, about 8.9 hours

        // FirstIslamicCoin supply: the premine is carried by the genesis coinbase,
        // then every staked block mints a fixed 10 FIC plus fees. Every value
        // here is documented in docs/tokenomics.md.
        consensus.nPremineTotal = CAmount{14'000'000'000} * COIN;
        consensus.nPowSubsidy = 0;
        consensus.nFixedStakeReward = 10 * COIN;
        consensus.nRewardHalvingInterval = 0; // disabled

        // Fresh chain, zeroed pending real chain work.
        consensus.nMinimumChainWork = uint256{};
        consensus.defaultAssumeValid = uint256{};

        /**
         * The message start string is designed to be unlikely to occur in normal data.
         * The characters are rarely used upper ASCII, not valid as UTF-8, and produce
         * a large 32-bit integer with any alignment.
         */
        pchMessageStart[0] = 0xf1;
        pchMessageStart[1] = 0x1c;
        pchMessageStart[2] = 0x51;
        pchMessageStart[3] = 0xa3;
        nDefaultPort = 19770;
        m_assumed_blockchain_size = 1;

        // FirstIslamicCoin: PLACEHOLDER premine recipient, pending the genesis
        // key ceremony (TODO-HUMAN). It pays BIP-341's "nothing up my sleeve"
        // point H, whose private key nobody knows, so this genesis block can
        // never bootstrap a chain -- and m_genesis_premine_placeholder makes the
        // node refuse to try. At the ceremony: replace the script, pick a launch
        // nTime, re-mine with contrib/genesis/generate_genesis.py and clear the
        // flag (docs/genesis.md).
        const CScript premineScript = CScript() << ParseHex("0250929b74c1a04954b78b4b6035e97a5e078a5a0f28ec96d547bfee9ace803ac0") << OP_CHECKSIG;
        m_genesis_premine_placeholder = true;
        genesis = CreateGenesisBlock(GenesisPremineOutputs(premineScript, consensus.nPremineTotal), FIC_GENESIS_TIME, 1669658, 0x1e0fffff, 7);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256S("0xbe7039971885efc3cb375ffb86200ab6964535dcd57c2cf9d8075522657afaeb"));
        assert(genesis.hashMerkleRoot == uint256S("0x098f41ec382356d32495c8db82e43d429f6c3d20a6ad8455a74cd99808d03e1a"));

        // Note that of those which support the service bits prefix, most only support a subset of
        // possible options.
        // This is fine at runtime as we'll fall back to using them as an addrfetch if they don't support the
        // service bits we want, but we should get them updated to support all service bits wanted by any
        // release ASAP to avoid it where possible.
        // FirstIslamicCoin: these names resolve (a real VPS -- see
        // docs/CHANGELOG-FIC.md's Phase 10 section), but nothing listens on
        // mainnet's P2P port there yet -- mainnet itself can't start until
        // the genesis key ceremony (m_genesis_premine_placeholder, TODO-HUMAN)
        // replaces the placeholder above.
        vSeeds.emplace_back("seed1.firstislamiccoin.com");
        vSeeds.emplace_back("seed2.firstislamiccoin.com");
        vSeeds.emplace_back("seed3.firstislamiccoin.com");

        base58Prefixes[PUBKEY_ADDRESS] = std::vector<unsigned char>(1,36);  // addresses start with F
        base58Prefixes[SCRIPT_ADDRESS] = std::vector<unsigned char>(1,28);  // addresses start with C
        base58Prefixes[SECRET_KEY] =     std::vector<unsigned char>(1,164);
        base58Prefixes[EXT_PUBLIC_KEY] = {0x04, 0x88, 0xB2, 0x1E}; // xpub
        base58Prefixes[EXT_SECRET_KEY] = {0x04, 0x88, 0xAD, 0xE4}; // xprv

        bech32_hrp = "fic";

        // FirstIslamicCoin: populated from the first mainnet seed nodes (Phase 3).
        vFixedSeeds.clear();

        fDefaultConsistencyChecks = false;
        m_is_mockable_chain = false;

        // FirstIslamicCoin: a new chain -- genesis is the only checkpoint until
        // real mainnet blocks exist to pin (docs/LAUNCH-RUNBOOK.md).
        checkpointData = {
            {
                {0, consensus.hashGenesisBlock},
            }
        };

        m_assumeutxo_data = {
            // TODO to be specified in a future patch.
        };

        chainTxData = ChainTxData{
            // Fresh chain, no transaction history yet.
            .nTime    = 0,
            .nTxCount = 0,
            .dTxRate  = 0,
        };
    }
};

/**
 * Testnet (v1): public test network which is reset from time to time.
 */
class CTestNetParams : public CChainParams {
public:
    CTestNetParams() {
        m_chain_type = ChainType::TESTNET;
        consensus.signet_blocks = false;
        consensus.signet_challenge.clear();
        consensus.nMaxReorganizationDepth = 500;
        consensus.CSVHeight = 0; // fresh chain, active from genesis
        consensus.SegwitHeight = 0; // fresh chain, active from genesis
        consensus.MinBIP9WarningHeight = 0;
        consensus.powLimit = uint256S("0000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.posLimit = uint256S("00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.posLimitV2 = uint256S("000000000000ffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.nTargetTimespan = 16 * 60; // 16 mins
        consensus.nTargetSpacingV1 = 60;
        consensus.nTargetSpacing = 64;
        consensus.fPowAllowMinDifficultyBlocks = true;
        consensus.fPowNoRetargeting = false;
        consensus.fPoSNoRetargeting = false;
        consensus.nRuleChangeActivationThreshold = 11250; // 75% for testchains
        consensus.nMinerConfirmationWindow = 15000; // nTargetTimespan / nTargetSpacing * 1000
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].bit = 28;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].nStartTime = Consensus::BIP9Deployment::NEVER_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].min_activation_height = 0; // No activation delay

        // Deployment of SegWit (BIP141, BIP143, and BIP147)
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].bit = 1;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].nStartTime = Consensus::BIP9Deployment::ALWAYS_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].min_activation_height = 0; // No activation delay

        // Deployment of Taproot (BIPs 340-342)
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].bit = 2;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nStartTime = Consensus::BIP9Deployment::ALWAYS_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].min_activation_height = 0; // No activation delay

        consensus.nProtocolV1RetargetingFixedTime = 1395631999;
        consensus.nProtocolV2Time = 1407053625;
        consensus.nProtocolV3Time = 1444028400;
        consensus.nProtocolV3_1Time = 1667779200;
        consensus.nLastPOWBlock = 0; // FirstIslamicCoin: proof-of-stake from block 1, as on mainnet
        consensus.nStakeTimestampMask = 0xf;
        consensus.nCoinbaseMaturity = 50; // also the minimum stake age: 50 blocks x 64 s, about 53 minutes

        // Mirrors mainnet's supply rules; testnet coins have no value.
        consensus.nPremineTotal = CAmount{14'000'000'000} * COIN;
        consensus.nPowSubsidy = 0;
        consensus.nFixedStakeReward = 10 * COIN;
        consensus.nRewardHalvingInterval = 0;

        consensus.nMinimumChainWork = uint256{};
        consensus.defaultAssumeValid = uint256{};

        pchMessageStart[0] = 0xf1;
        pchMessageStart[1] = 0x1c;
        pchMessageStart[2] = 0x54;
        pchMessageStart[3] = 0xb3;
        nDefaultPort = 29770;
        m_assumed_blockchain_size = 1;

        // FirstIslamicCoin: the testnet premine key lives outside the repository
        // (secrets/testnet-genesis-key.txt) for whoever bootstraps testnet.
        genesis = CreateGenesisBlock(GenesisPremineOutputs(P2PKHScript("8d153502ba477ca4b9d4fff3b51e6f4f2d86d6e1"), consensus.nPremineTotal), FIC_GENESIS_TIME, 8609, 0x1f00ffff, 7);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256S("0xa028f8ffcbbb97bde94e3acb508ec33caa80067dccfc077905a4c3acb18f7aed"));
        assert(genesis.hashMerkleRoot == uint256S("0xa6ef8928345ff177f6fbb0503c856a2100de24e3e7c63adcf2d4d6922c721641"));

        // FirstIslamicCoin: no testnet DNS seeds yet; Phase 2 nodes connect with
        // -addnode (TODO-HUMAN).
        vSeeds.clear();

        base58Prefixes[PUBKEY_ADDRESS] = std::vector<unsigned char>(1,111);
        base58Prefixes[SCRIPT_ADDRESS] = std::vector<unsigned char>(1,196);
        base58Prefixes[SECRET_KEY] =     std::vector<unsigned char>(1,239);
        base58Prefixes[EXT_PUBLIC_KEY] = {0x04, 0x35, 0x87, 0xCF}; // tpub
        base58Prefixes[EXT_SECRET_KEY] = {0x04, 0x35, 0x83, 0x94}; // tprv

        bech32_hrp = "tfic";

        vFixedSeeds.clear();

        fDefaultConsistencyChecks = false;
        m_is_mockable_chain = false;

        // Fresh chain -- checkpoints reset to genesis only.
        checkpointData = {
            {
                {0, consensus.hashGenesisBlock},
            }
        };

        m_assumeutxo_data = {
            // TODO to be specified in a future patch.
        };

        chainTxData = ChainTxData{
            // Fresh chain, no transaction history yet.
            .nTime    = 0,
            .nTxCount = 0,
            .dTxRate  = 0,
        };
    }
};

/**
 * Signet: test network with an additional consensus parameter (see BIP325).
 */
class SigNetParams : public CChainParams {
public:
    explicit SigNetParams(const SigNetOptions& options)
    {
        std::vector<uint8_t> bin;
        vSeeds.clear();

        if (!options.challenge) {
            bin = ParseHex("512103ad5e0edad18cb1f0fc0d28a3d4f1f3e445640337489abb10404f2d1e086be430210359ef5021964fe22d6f8e05b2463c9540ce96883fe3b278760f048f5189f2e6c452ae");

            /*
            vSeeds.emplace_back("seed.signet.bitcoin.sprovoost.nl.");

            // Hardcoded nodes can be removed once there are more DNS seeds
            vSeeds.emplace_back("178.128.221.177");
            vSeeds.emplace_back("v7ajjeirttkbnt32wpy3c6w3emwnfr3fkla7hpxcfokr3ysd3kqtzmqd.onion:38333");
            */

            vSeeds.clear();

            consensus.nMinimumChainWork = uint256S("0x00");
            consensus.defaultAssumeValid = uint256S("0x00");
            m_assumed_blockchain_size = 1;
            chainTxData = ChainTxData{
                // Data from RPC: getchaintxstats 4096 000000187d4440e5bff91488b700a140441e089a8aaea707414982460edbfe54
                .nTime    = 0,
                .nTxCount = 0,
                .dTxRate  = 0.0,
            };
        } else {
            bin = *options.challenge;
            consensus.nMinimumChainWork = uint256{};
            consensus.defaultAssumeValid = uint256{};
            m_assumed_blockchain_size = 0;
            chainTxData = ChainTxData{
                0,
                0,
                0,
            };
            LogPrintf("Signet with challenge %s\n", HexStr(bin));
        }

        if (options.seeds) {
            vSeeds = *options.seeds;
        }

        m_chain_type = ChainType::SIGNET;
        consensus.signet_blocks = true;
        consensus.signet_challenge.assign(bin.begin(), bin.end());
        consensus.nMaxReorganizationDepth = 500;
        consensus.CSVHeight = 1;
        consensus.SegwitHeight = 1;
        consensus.nTargetTimespan = 16 * 60; // 16 mins
        consensus.nTargetSpacingV1 = 64;
        consensus.nTargetSpacing = 64;
        consensus.fPowAllowMinDifficultyBlocks = false;
        consensus.fPowNoRetargeting = false;
        consensus.fPoSNoRetargeting = false;
        consensus.nRuleChangeActivationThreshold = 12000; // 80% of 15000
        consensus.nMinerConfirmationWindow = 15000; // nTargetTimespan / nTargetSpacing * 1000
        consensus.MinBIP9WarningHeight = 0;
        consensus.powLimit = uint256S("0000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.posLimit = uint256S("00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.posLimitV2 = uint256S("000000000000ffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].bit = 28;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].nStartTime = Consensus::BIP9Deployment::NEVER_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].min_activation_height = 0; // No activation delay

        // Deployment of SegWit (BIP141, BIP143, and BIP147); signet also needs a
        // witness commitment in every block for its block solution.
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].bit = 1;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].nStartTime = Consensus::BIP9Deployment::ALWAYS_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].min_activation_height = 0; // No activation delay

        // Activation of Taproot (BIPs 340-342)
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].bit = 2;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nStartTime = Consensus::BIP9Deployment::ALWAYS_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].min_activation_height = 0; // No activation delay

        consensus.nProtocolV1RetargetingFixedTime = 1707168541;
        consensus.nProtocolV2Time = 1707168542;
        consensus.nProtocolV3Time = 1707168543;
        consensus.nProtocolV3_1Time = 1707168544;
        consensus.nLastPOWBlock = 0x7fffffff; // signet blocks are signed proof-of-work
        consensus.nStakeTimestampMask = 0xf;
        consensus.nCoinbaseMaturity = 10;

        // FirstIslamicCoin: signet is not planned for launch. It shares the
        // testnet genesis block, so it carries the same premine.
        consensus.nPremineTotal = CAmount{14'000'000'000} * COIN;
        consensus.nPowSubsidy = 0;
        consensus.nFixedStakeReward = 10 * COIN;
        consensus.nRewardHalvingInterval = 0;

        // message start is defined as the first 4 bytes of the sha256d of the block script
        HashWriter h{};
        h << consensus.signet_challenge;
        uint256 hash = h.GetHash();
        std::copy_n(hash.begin(), 4, pchMessageStart.begin());

        nDefaultPort = 49770;

        genesis = CreateGenesisBlock(GenesisPremineOutputs(P2PKHScript("8d153502ba477ca4b9d4fff3b51e6f4f2d86d6e1"), consensus.nPremineTotal), FIC_GENESIS_TIME, 8609, 0x1f00ffff, 7);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256S("0xa028f8ffcbbb97bde94e3acb508ec33caa80067dccfc077905a4c3acb18f7aed"));
        assert(genesis.hashMerkleRoot == uint256S("0xa6ef8928345ff177f6fbb0503c856a2100de24e3e7c63adcf2d4d6922c721641"));

        vFixedSeeds.clear();

        m_assumeutxo_data = {};

        base58Prefixes[PUBKEY_ADDRESS] = std::vector<unsigned char>(1,111);
        base58Prefixes[SCRIPT_ADDRESS] = std::vector<unsigned char>(1,196);
        base58Prefixes[SECRET_KEY] =     std::vector<unsigned char>(1,239);
        base58Prefixes[EXT_PUBLIC_KEY] = {0x04, 0x35, 0x87, 0xCF}; // tpub
        base58Prefixes[EXT_SECRET_KEY] = {0x04, 0x35, 0x83, 0x94}; // tprv

        bech32_hrp = "tfic";

        fDefaultConsistencyChecks = false;
        m_is_mockable_chain = false;
    }
};

/**
 * Regression test: intended for private networks only. Has minimal difficulty to ensure that
 * blocks can be found instantly.
 */
class CRegTestParams : public CChainParams
{
public:
    explicit CRegTestParams(const RegTestOptions& opts)
    {
        m_chain_type = ChainType::REGTEST;
        consensus.signet_blocks = false;
        consensus.signet_challenge.clear();
        consensus.nMaxReorganizationDepth = 50;
        consensus.CSVHeight = 1;
        consensus.SegwitHeight = 1;
        consensus.MinBIP9WarningHeight = 0;
        consensus.powLimit = uint256S("7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.posLimit = uint256S("00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.posLimitV2 = uint256S("000000000000ffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.nTargetTimespan = 16 * 60; // 16 mins
        consensus.nTargetSpacingV1 = 64;
        consensus.nTargetSpacing = 1; // FirstIslamicCoin: 1-second regtest spacing
        consensus.fPowAllowMinDifficultyBlocks = true;
        consensus.fPowNoRetargeting = true;
        consensus.fPoSNoRetargeting = true;
        consensus.nRuleChangeActivationThreshold = 120; // 80% for regtest
        consensus.nMinerConfirmationWindow = 150; // Faster than normal for regtest (150 instead of 15000)
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].bit = 28;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].nStartTime = 0;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].min_activation_height = 0; // No activation delay

        // Deployment of SegWit (BIP141, BIP143, and BIP147)
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].bit = 1;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].nStartTime = Consensus::BIP9Deployment::ALWAYS_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT; // ignored for ALWAYS_ACTIVE
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].min_activation_height = 0; // No activation delay

        // Deployment of Taproot (BIPs 340-342)
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].bit = 2;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nStartTime = Consensus::BIP9Deployment::ALWAYS_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].min_activation_height = 0; // No activation delay

        consensus.nProtocolV1RetargetingFixedTime = 1395631999;
        consensus.nProtocolV2Time = 1407053625;
        consensus.nProtocolV3Time = 1444028400;
        consensus.nProtocolV3_1Time = 1713938400;
        // FirstIslamicCoin: regtest keeps a proof-of-work window so the upstream
        // functional test harness can mine blocks on demand. -lastpowblock=0
        // restores mainnet's proof-of-stake-from-block-1 rules; FIC's own
        // premine and reward tests run that way.
        consensus.nLastPOWBlock = 500;
        consensus.nStakeTimestampMask = 0; // any second is a valid stake time at 1-second spacing
        consensus.nCoinbaseMaturity = 10;

        consensus.nPremineTotal = CAmount{14'000'000'000} * COIN;
        consensus.nPowSubsidy = 28'000'000 * COIN; // test harness only; upstream CAC's regtest per-block amount
        consensus.nFixedStakeReward = 10 * COIN;
        consensus.nRewardHalvingInterval = 0;

        consensus.nMinimumChainWork = uint256{};
        consensus.defaultAssumeValid = uint256{};

        pchMessageStart[0] = 0xf1;
        pchMessageStart[1] = 0x1c;
        pchMessageStart[2] = 0x52;
        pchMessageStart[3] = 0xc3;
        nDefaultPort = 39770;
        m_assumed_blockchain_size = 0;

        for (const auto& [dep, height] : opts.activation_heights) {
            switch (dep) {
            /*
            case Consensus::BuriedDeployment::DEPLOYMENT_SEGWIT:
                consensus.SegwitHeight = int{height};
                break;
            */
            case Consensus::BuriedDeployment::DEPLOYMENT_CSV:
                consensus.CSVHeight = int{height};
                break;
            }
        }

        for (const auto& [deployment_pos, version_bits_params] : opts.version_bits_parameters) {
            consensus.vDeployments[deployment_pos].nStartTime = version_bits_params.start_time;
            consensus.vDeployments[deployment_pos].nTimeout = version_bits_params.timeout;
            consensus.vDeployments[deployment_pos].min_activation_height = version_bits_params.min_activation_height;
        }

        if (opts.last_pow_block) {
            consensus.nLastPOWBlock = *opts.last_pow_block;
        }

        // FirstIslamicCoin: the regtest premine key is public by design --
        // sha256("FirstIslamicCoin regtest genesis premine key"), also in
        // test/functional/test_framework/fic.py -- so tests can spend and stake it.
        genesis = CreateGenesisBlock(GenesisPremineOutputs(P2PKHScript("70e519799aeef0396b253b70a5f523d2fed89d64"), consensus.nPremineTotal), FIC_GENESIS_TIME, 3, 0x207fffff, 7);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256S("0x360afc3edc3e70f91452bbc7ece92fd4a18dbb9700aea612564636fadbd4e712"));
        assert(genesis.hashMerkleRoot == uint256S("0x8b2a04a50eefa5278f18e583eb1f03e965be9e6210bb5e9c406cf7010cd594c0"));

        vFixedSeeds.clear(); //!< Regtest mode doesn't have any fixed seeds.
        vSeeds.clear();
        vSeeds.emplace_back("dummySeed.invalid.");

        fDefaultConsistencyChecks = true;
        m_is_mockable_chain = true;

        checkpointData = {
            {
                {0, consensus.hashGenesisBlock},
            }
        };

        m_assumeutxo_data = {
            // FirstIslamicCoin: the UTXO set at height 510 of the unit-test chain --
            // TestChain100Setup's 500 blocks plus mineBlocks(10), as used by
            // validation_chainstatemanager_tests and validation_chainstate_tests.
            // Its 1510 coins include the 1000 spendable genesis premine outputs.
            // Regenerate from CreateUTXOSnapshot()'s txoutset_hash/nchaintx/base_hash
            // if that fixture's chain changes. Upstream's regtest entries were
            // meaningless for this genesis block; feature_assumeutxo.py would need
            // its own entry.
            {
                .height = 510,
                .hash_serialized = AssumeutxoHash{uint256S("0xd5de4dc7bed0e1def21c094cea1a77e62bb3c1256156ec0b5b9f536ae5b5a2a2")},
                .nChainTx = 511,
                .blockhash = uint256S("0xa067e50a2d85cd01a0ce0a167f53e8173f088670016366aae9bb33b4f90b3bb9")
            },
        };

        chainTxData = ChainTxData{
            0,
            0,
            0
        };

        base58Prefixes[PUBKEY_ADDRESS] = std::vector<unsigned char>(1,111);
        base58Prefixes[SCRIPT_ADDRESS] = std::vector<unsigned char>(1,196);
        base58Prefixes[SECRET_KEY] = std::vector<unsigned char>(1,239);
        base58Prefixes[EXT_PUBLIC_KEY] = {0x04, 0x35, 0x87, 0xCF}; // tpub
        base58Prefixes[EXT_SECRET_KEY] = {0x04, 0x35, 0x83, 0x94}; // tprv

        bech32_hrp = "rfic";
    }
};

std::unique_ptr<const CChainParams> CChainParams::SigNet(const SigNetOptions& options)
{
    return std::make_unique<const SigNetParams>(options);
}

std::unique_ptr<const CChainParams> CChainParams::RegTest(const RegTestOptions& options)
{
    return std::make_unique<const CRegTestParams>(options);
}

std::unique_ptr<const CChainParams> CChainParams::Main()
{
    return std::make_unique<const CMainParams>();
}

std::unique_ptr<const CChainParams> CChainParams::TestNet()
{
    return std::make_unique<const CTestNetParams>();
}
