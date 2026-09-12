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

static CBlock CreateGenesisBlock(const char* pszTimestamp, const CScript& genesisOutputScript, uint32_t nTime, uint32_t nNonce, uint32_t nBits, int32_t nVersion, const CAmount& genesisReward)
{
    // Genesis block

    // MainNet:

    //CBlock(hash=000001faef25dec4fbcf906e6242621df2c183bf232f263d0ba5b101911e4563, ver=1, hashPrevBlock=0000000000000000000000000000000000000000000000000000000000000000, hashMerkleRoot=12630d16a97f24b287c8c2594dda5fb98c9e6c70fc61d44191931ea2aa08dc90, nTime=1393221600, nBits=1e0fffff, nNonce=164482, vtx=1, vchBlockSig=)
    //  Coinbase(hash=12630d16a9, nTime=1393221600, ver=1, vin.size=1, vout.size=1, nLockTime=0)
    //    CTxIn(COutPoint(0000000000, 4294967295), coinbase 00012a24323020466562203230313420426974636f696e2041544d7320636f6d6520746f20555341)
    //    CTxOut(empty)
    //  vMerkleTree: 12630d16a9

    // TestNet:

    //CBlock(hash=0000724595fb3b9609d441cbfb9577615c292abf07d996d3edabc48de843642d, ver=1, hashPrevBlock=0000000000000000000000000000000000000000000000000000000000000000, hashMerkleRoot=12630d16a97f24b287c8c2594dda5fb98c9e6c70fc61d44191931ea2aa08dc90, nTime=1393221600, nBits=1f00ffff, nNonce=216178, vtx=1, vchBlockSig=)
    //  Coinbase(hash=12630d16a9, nTime=1393221600, ver=1, vin.size=1, vout.size=1, nLockTime=0)
    //    CTxIn(COutPoint(0000000000, 4294967295), coinbase 00012a24323020466562203230313420426974636f696e2041544d7320636f6d6520746f20555341)
    //    CTxOut(empty)
    //  vMerkleTree: 12630d16a9

    CMutableTransaction txNew;
    txNew.nVersion = 1;
    txNew.nTime = nTime;
    txNew.vin.resize(1);
    txNew.vout.resize(1);
    txNew.vin[0].scriptSig = CScript() << 0 << CScriptNum(42) << std::vector<unsigned char>((const unsigned char*)pszTimestamp, (const unsigned char*)pszTimestamp + strlen(pszTimestamp));
    txNew.vout[0].nValue = genesisReward;

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
 * Build the genesis block. Note that the output of its generation
 * transaction cannot be spent since it did not originally exist in the
 * database.
 */
static CBlock CreateGenesisBlock(uint32_t nTime, uint32_t nNonce, uint32_t nBits, int32_t nVersion, const CAmount& genesisReward)
{
    // CodexaCoin genesis timestamp phrase: a verifiable, dated financial-news
    // headline (mirrors Bitcoin's own "Chancellor on brink of second bailout
    // for banks" convention). Kept short and quoted in full (not truncated)
    // to fit the 100-byte coinbase scriptSig consensus limit. See
    // PARAMETERS.md section 8 for the source.
    const char* pszTimestamp = "CNBC 29/Jul/2026 Fed meeting recap: July 2026";
    const CScript genesisOutputScript = CScript() << ParseHex("04678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5f") << OP_CHECKSIG;
    return CreateGenesisBlock(pszTimestamp, genesisOutputScript, nTime, nNonce, nBits, nVersion, genesisReward);
}

/**
 * CodexaCoin: brute-force nNonce for a genesis block satisfying nBits, reusing
 * the exact same CreateGenesisBlock() (same pszTimestamp, same output script)
 * every CChainParams subclass in this file already calls -- so there is no
 * separate reimplementation of the header/coinbase serialization to get
 * subtly wrong. Used by contrib tooling (see PARAMETERS.md section 8/9) to
 * regenerate genesis nTime/nNonce/hash whenever network params change.
 */
CBlock FindGenesisBlock(uint32_t nTime, uint32_t nBits, int32_t nVersion, const CAmount& genesisReward, uint32_t& nNonceOut)
{
    arith_uint256 bnTarget;
    bnTarget.SetCompact(nBits);
    for (uint32_t nonce = 0;; ++nonce) {
        CBlock block = CreateGenesisBlock(nTime, nonce, nBits, nVersion, genesisReward);
        // CodexaCoin/Blackcoin: proof-of-work is checked against
        // GetPoWHash() (scrypt), not GetHash() (SHA256d, and only for
        // nVersion > 6 at that -- see primitives/block.cpp). ConnectBlock's
        // CheckBlockHeader() calls CheckProofOfWork(block.GetPoWHash(), ...)
        // unconditionally, regardless of block version.
        if (UintToArith256(block.GetPoWHash()) <= bnTarget) {
            nNonceOut = nonce;
            return block;
        }
        if (nonce == std::numeric_limits<uint32_t>::max()) {
            throw std::runtime_error("FindGenesisBlock: exhausted nNonce range without finding a valid hash; try a different nTime");
        }
    }
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
        consensus.CSVHeight = 0; // CodexaCoin: fresh chain, active from genesis (no legacy history to preserve)
        consensus.SegwitHeight = 0; // CodexaCoin: fresh chain, active from genesis
        consensus.MinBIP9WarningHeight = 0;
        consensus.powLimit = uint256S("00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.posLimit = uint256S("00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.posLimitV2 = uint256S("000000000000ffffffffffffffffffffffffffffffffffffffffffffffffffff");
        consensus.nTargetTimespan = 16 * 60; // 16 mins
        consensus.nTargetSpacingV1 = 60;
        consensus.nTargetSpacing = 64; // CodexaCoin: unchanged from Blackcoin default (PARAMETERS.md)
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
        // CodexaCoin: fresh chain, SegWit active from genesis (SegwitHeight = 0 above);
        // this deployment entry is unused for buried deployments but left NEVER_ACTIVE
        // for cleanliness/consistency with the other version-bits slots.
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].bit = 1;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].nStartTime = Consensus::BIP9Deployment::NEVER_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].min_activation_height = 0; // No activation delay

        // Deployment of Taproot (BIPs 340-342)
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].bit = 2;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nStartTime = Consensus::BIP9Deployment::NEVER_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].min_activation_height = 0; // No activation delay

        consensus.nProtocolV1RetargetingFixedTime = 1395631999;
        consensus.nProtocolV2Time = 1407053625;
        consensus.nProtocolV3Time = 1444028400;
        consensus.nProtocolV3_1Time = 1713938400;
        consensus.nLastPOWBlock = 500; // CodexaCoin: founder premine window, see PARAMETERS.md section 5
        consensus.nStakeTimestampMask = 0xf; // 15
        consensus.nCoinbaseMaturity = 500;

        // CodexaCoin: 14,000,000,000 CAC premine, split evenly across the
        // 500-block PoW window above (28,000,000 CAC/block, exact, no
        // remainder). See PARAMETERS.md section 5.
        consensus.nPremineTotal = CAmount{14000000000} * COIN;
        // CodexaCoin: coin-age-proportional staking reward (PARAMETERS.md
        // section 6 / spec Appendix A). 1368 bp = 13.68%/yr = 1.14%/mo,
        // uncalibrated default pending the regtest maturity-drag test.
        consensus.nStakeRewardAnnualBP = 1368;
        consensus.nStakeRewardAgeCapSeconds = 60 * 24 * 60 * 60; // 60 days

        // CodexaCoin: fresh chain, zeroed pending real chain work (PARAMETERS.md
        // instruction: "Zero out chainTxData and nMinimumChainWork appropriately
        // for a new chain").
        consensus.nMinimumChainWork = uint256{};
        consensus.defaultAssumeValid = uint256{};

        /**
         * The message start string is designed to be unlikely to occur in normal data.
         * The characters are rarely used upper ASCII, not valid as UTF-8, and produce
         * a large 32-bit integer with any alignment.
         */
        pchMessageStart[0] = 0x74;
        pchMessageStart[1] = 0x80;
        pchMessageStart[2] = 0x2a;
        pchMessageStart[3] = 0xa6;
        nDefaultPort = 16210;
        m_assumed_blockchain_size = 1;

        // CodexaCoin: genesis mined by contrib/genesis/generate_genesis.cpp
        // (see PARAMETERS.md section 8). nNonce found by brute force against
        // GetPoWHash() (scrypt), not GetHash().
        genesis = CreateGenesisBlock(1785326400, 2473299, 0x1e0fffff, 7, 0);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256S("0xecf4dfc81beeb2a992ee169e1fc349144e48108d7a03f7fb6d619c2bd845038e"));
        assert(genesis.hashMerkleRoot == uint256S("0x089c9664d716a35a805093b15b0dd6e9f58e84ca21a176c2783a377d23ef6b22"));

        // Note that of those which support the service bits prefix, most only support a subset of
        // possible options.
        // This is fine at runtime as we'll fall back to using them as an addrfetch if they don't support the
        // service bits we want, but we should get them updated to support all service bits wanted by any
        // release ASAP to avoid it where possible.
        // CodexaCoin: TODO placeholders -- no real seed infrastructure exists
        // yet. See PARAMETERS.md section 9 / Phase 2 deliverables.
        vSeeds.emplace_back("seed1.codexacoin.example"); // TODO: stand up real seed node
        vSeeds.emplace_back("seed2.codexacoin.example"); // TODO: stand up real seed node

        base58Prefixes[PUBKEY_ADDRESS] = std::vector<unsigned char>(1,28);
        base58Prefixes[SCRIPT_ADDRESS] = std::vector<unsigned char>(1,63);
        base58Prefixes[SECRET_KEY] =     std::vector<unsigned char>(1,156);
        // CodexaCoin-specific BIP32 version bytes (PARAMETERS.md section 9
        // item 5): dumpwallet/listdescriptors "xpub"/"xprv" strings now read
        // "Czxt.../CzsJ..." instead of Bitcoin's own. Not consensus-critical
        // -- purely how a wallet backup file/descriptor string displays.
        base58Prefixes[EXT_PUBLIC_KEY] = {0x38, 0x86, 0x00, 0x00};
        base58Prefixes[EXT_SECRET_KEY] = {0x38, 0x84, 0x00, 0x00};

        bech32_hrp = "cac";

        // CodexaCoin: no fixed-seed IP list exists yet for a chain that
        // hasn't launched. Empty until Phase 2/7 seed infrastructure is live.
        vFixedSeeds.clear();

        fDefaultConsistencyChecks = false;
        m_is_mockable_chain = false;

        // CodexaCoin: the 500-block founder premine window (PARAMETERS.md
        // section 5) is now fully mined and frozen here as of 2026-08-01,
        // making it unreorgable for anyone who ever syncs from genesis.
        // Generated from a live getblockhash 0..500 scan against the real
        // mined chain (PARAMETERS.md section 9 TODO #2, now done).
        checkpointData = {
            {
                {0, consensus.hashGenesisBlock},
                {1, uint256S("0x25efc90ff657ec53e25352ab523c583b37ec100a31b1c88bbb8961b2e074654d")},
                {2, uint256S("0x6c0fa8a44152370086cafcd273da6cb85c73f2d1384bdf2797e844ad77751adf")},
                {3, uint256S("0x7dac0b3d40a13126fbb17e55b450bf5bd5db4db1be099cde69b9985d0540738e")},
                {4, uint256S("0xae866ac695f2f730923d08b88a210e8d799b9c0a4729617a71e2ce9d116b29e5")},
                {5, uint256S("0x5ba81f558f370a8d6844515c298897d9e4d66634c5f3e7f29a920583dac8292b")},
                {6, uint256S("0xf84425776426f0a21b68df474f39eeccd3579e37c81b728d641c0194ff732928")},
                {7, uint256S("0x99742a0d310f15c36a5fd3ac53e2ac94a441a56a59cd30e60c8c7ce948a289e7")},
                {8, uint256S("0xb1556bbdc9cc8c214e066fc21b8ed6b1d12e080b50027143d840c1ba27cf4731")},
                {9, uint256S("0x64ec3e3728bee9cd0b2fd197c8b4edcc10bb4041ad163c665e4c0c4a7dd89e98")},
                {10, uint256S("0x6bfb3c219d55cd716f9654ddd50fdc51f24f0838d34fc3f73f3c6b532fbecc81")},
                {11, uint256S("0x55086322e9960d09d527297b93a18d035ee51f8a2192546754da5a917bec3e41")},
                {12, uint256S("0x6689ed0fb0f1b9f6ca3e6b2760cb8947404ae019270d9911f6b09caaa8c47a3a")},
                {13, uint256S("0x96fe3f66a6c012e80910e82788709a439a483e4ae0da90be8cfc6b7ee659d823")},
                {14, uint256S("0xb44514fce00c295fc77edb1cbcb39d97f02143267e98f433febb4c31df9ccabf")},
                {15, uint256S("0x6ad6e4ba10fa8c60e97b7a1a6c54cf3195fc823ed6aa6c75a7daad9583a32831")},
                {16, uint256S("0xbe3e72705c672190359fe7cd7f0911c4300a177269a111841a3062a0e0f04729")},
                {17, uint256S("0xb4638a1b06c11c756583d55c04bc736625d0b630a1333d2a0be3d51bf2106492")},
                {18, uint256S("0x34f4efc108dbd0cab2a622cfcf8df6d39715a80b8a387d732f45504634e8efc5")},
                {19, uint256S("0x1fe071335610e636495a611490d6b1d75ae679305fa92f302c1cea9ba5346a01")},
                {20, uint256S("0xa893913630e0e631607ec43fffbc4491e8cfef05094e94fe7dbe87f4f1ee08a5")},
                {21, uint256S("0x80f5da81871d126ff3b70469ae7fe871efefa0dec1afb278879fca786d3d6ec5")},
                {22, uint256S("0x11b49e1c73d40f2becaff45ae1b63f498a2bc48455c00eeed9ad496699103bd8")},
                {23, uint256S("0xfc18e8b9e17117ce4b7ebad917b5bd6a71305332892def8574ecef2b833ae776")},
                {24, uint256S("0x7014c2d7323c3c382b462084e2bf6b70fdd0be683d1f31236b5a876762fb3429")},
                {25, uint256S("0x6952d94feb81b87788bed79889fd1dea2bcd31d9d8a5909b695d737d1883ed96")},
                {26, uint256S("0x844a62b1a22bf80e8ed6502b0b8b83367129f073d62efa9fd1a06da3e5d6f2e7")},
                {27, uint256S("0x731bee365eb050d0d55877da309a057d8af71599225caf485645b8698d626233")},
                {28, uint256S("0x53b529d199ce63dce110bf83fdf6452d3ef67e2a7606ed614aa07abd44386bcf")},
                {29, uint256S("0x51e06ca95fd5a652ff5ea3efc2a7ddc036c62adb6a79c0cc4a3cda1035cda18b")},
                {30, uint256S("0x8eb89dbc8a70cdebee846eb9d129902573c188f0c556ee2788079cff4b8eb665")},
                {31, uint256S("0xbff3f97f21f2926a8c4a5759b415271585e2cea9a1bdd1bc581e941bc78d1b10")},
                {32, uint256S("0xfd5a33071db63e976fa7cea43711e339dc33bbecae976658b87ea531ffdd1495")},
                {33, uint256S("0xd286c07bc8b9edb24cfd4f9605607854db13732b6a2b20948d93e35f99b1fe03")},
                {34, uint256S("0x101a73863ae339d8c074877f1fb8eab89dc7b9c1d2e069e6cd3f82015026dfc6")},
                {35, uint256S("0xc04f0a09400d62971ae1449a7246facbdb1df051022d2e4e4372c4f9f1d0fb5c")},
                {36, uint256S("0xed92fb797ef33c76e1450dcc5cc0ba66066d846ef0829a6fd1dc23d43e8fc024")},
                {37, uint256S("0xa5be455e82ae092abadb3533e5d53d985b6435aa19009b15f054f69dffd285b7")},
                {38, uint256S("0x1840a3bf53625b0af813e4527f2e59be8951e23d124c97479e732af4266118bc")},
                {39, uint256S("0x70040f9a5e5667e058b4859056067b5d0aea883a263ca267cd957c3cc936278c")},
                {40, uint256S("0x61cf40be4535d6867214b1e6316576aa7c3f35945aa18c07795c1b20971620e2")},
                {41, uint256S("0x27aa4bf0156854dd040f6f32492c5daa7ae7c7777f06ef6ba7a97b0b5db84208")},
                {42, uint256S("0x5c6a811d975e32c26992408cfa967e5223221a4a323097e486099465c5dee4e2")},
                {43, uint256S("0x063e03cf7eaeb20deef7781cd56b229dc7386338e0960a652819c44fa2e1e0a8")},
                {44, uint256S("0x8ce2c5075aeab14f6bbbdc4bf5a538fa0937e5e5f333b6e808b405af9a611ddd")},
                {45, uint256S("0x51d3bafac2cb1362276799207b6ea9d194a866de38ef7d0aa251550e3f9392d9")},
                {46, uint256S("0x1d9c9e73a83ebae1bd335b2d7f7f2704fbb0acb26a8cc701df6f7dff3767fd49")},
                {47, uint256S("0x647d229c1edbb6f7cebf8ba4b809ce3ffbbd4f3ada0804f1f65462b29295ce5a")},
                {48, uint256S("0x37c4499b9e262d64d5072142e0de0b0e8fa3f86024fdfe1e26549fa32c7e8a88")},
                {49, uint256S("0x3f029a3defca6833d74bf78961b12c01efdb15d0b0c8dd073e03b610809c6153")},
                {50, uint256S("0x0a8833770a8a10b301b1af27ded9d1c96bd7ecb620ca4be359c7ea997825368e")},
                {51, uint256S("0x3561878c5d160fcadfadfa105ab75487737403857bd8d72b7893f8706899e23e")},
                {52, uint256S("0xaa9359fe8655413e659a6f73cd119378cc7903850fefa1a18b0ad8e6e6f04536")},
                {53, uint256S("0x4a7ca3b02ab758a72fe6f86df3b282a3156423c098191cf5daa5d70c6a4e49e2")},
                {54, uint256S("0x1e2d33f96516d6a6745a89b49c7848fa9fe1500f60b4a8a9a55ffa434b5711be")},
                {55, uint256S("0x0aaa0871f1df5f6a6fb14255e794b1512f59d17ca6eb737aa1bba5d3077a7a21")},
                {56, uint256S("0x5b1d3d4a6bb6b0eadfd1ab0bc175002927b43c01d12ebfd6c7dbb33f0b3140a1")},
                {57, uint256S("0xf7b27f7feaa2ecfbfaeb1536be01a2d949339229642eaa86899e8b9dae07b893")},
                {58, uint256S("0xdb0c89cf4b98569a73c33a5514b49a02c39e7b155364ab00b0b8b1ae2ac66d6a")},
                {59, uint256S("0x920622af1e2aa44c492c6e30a352c76cb123f1c78180ca84f0831994118929ad")},
                {60, uint256S("0x8c79fc59b2844ea4b5414a85f5379154b2fb67a395dec566712d96781393642a")},
                {61, uint256S("0x59f43ef506793543ce93fdd9d66e11f65734aa2e3e0eb6bb2241fcd001d650e9")},
                {62, uint256S("0xfcd371b4e7d87769f7dce40aeee2cd0cc1ddf4f9db750fc72d589487d20a2e38")},
                {63, uint256S("0xfaf71a753e57a00cdcc559b947fcfc10c4a5f03642f24bc56b3ffff6b4c81662")},
                {64, uint256S("0xed66b7406473322bcee83fa003d9ba83263caba47217930c15456f1ecc978930")},
                {65, uint256S("0x61bcc8d92190701e68090f1d1d1f1906687b4edf79465d17d83db8c14e4cf539")},
                {66, uint256S("0xfaebaf11b57d674d5a360a74e76e857783c0350b4f3fbc99628319b428d896da")},
                {67, uint256S("0x45a91f6f2aa47274fe4cf9b6336db17953bf7bc93402ff9097db67dcca835310")},
                {68, uint256S("0x5adccc22ac9449cd36465b93096e751dc3aefbd0dc51c112d6d77ca498fccedc")},
                {69, uint256S("0x39f76370c52b8a4eac5abe1de9428d8b2aaec8ec5c0ab78d2318414c7ede912a")},
                {70, uint256S("0x554e752bdbf9783abcdd0821aa50bb9cbe449426f32076bdf53d1f03281c577f")},
                {71, uint256S("0xadf27fc2e123868195d77aa01709bae69a2c5d5e9b3fa90a9c1729579dbf6c1c")},
                {72, uint256S("0x5f4536d0e1b730a222bd8f4ab188f7f26c950318b8f6db5b239ba6cad7adc60f")},
                {73, uint256S("0x7e7cd8b111de7bae9a61f7c9218c3b6192b4fd6dfa44762bc5ecbedcc177c382")},
                {74, uint256S("0xd76f101de6ca86eb5dc9c6a16e4be3830e3d5dd9fa2e484ce28c5cef5bb075d7")},
                {75, uint256S("0xc2391d2b1d66b7101f0ea544ed6ba4abb93e0bf3b0d9f72e1cfa3f6fcd7a8a48")},
                {76, uint256S("0x37e485561b84ca8cd45502ba92f06266beeeb70c195b1f57911a06e57c8cfcb7")},
                {77, uint256S("0x89b3bcecb362d508a58d5d03de4a1cc6c10303bcb670ac5a87012bb11834d10d")},
                {78, uint256S("0xe1371c0748e0eb7b167525fc5ecf2bd86d8c5fce534bb649474fb9fdf33986bf")},
                {79, uint256S("0xbe6cdf9be77fe51c67f517534d198de0dfb8a661abdbfb4952f602790b442972")},
                {80, uint256S("0x34067612a408ba007782c1acc1e9184433dbdc34478665f50f60092e209e7ea3")},
                {81, uint256S("0x99cb5cc0e54af2ec341cc43e591ce461ab04aa439c333b9ed0b01a7fe50f2e0b")},
                {82, uint256S("0x29a210650ab755079d4ad7cdc4e578549da49ebacb367d526bd623ea6b6b807e")},
                {83, uint256S("0xc6d7ad2714d14c9a55d898414b56a3f0b45d0de693f46a9df673c4d019bbd0cf")},
                {84, uint256S("0x33b10b3e1bf1349c6028f2901601c16535d7a35c7a7773c975835fa6433ea9b2")},
                {85, uint256S("0xe63809466131cd3edf3ab5a1ae372c7848f78c0232f7a9387536e9083f4f9f5f")},
                {86, uint256S("0xe44edc7ad75a7650653111eb1ccad3f7c7d3f4258f245717aec5b022b8da7e02")},
                {87, uint256S("0x47d252bc65c75c70fb85816c7bc2bfec39c254efd2fbeac804c86a6934a6b68f")},
                {88, uint256S("0xc8841242803fb900edc25399f6b69da678aeee8674cbc58081ea3e3cfc3fe12f")},
                {89, uint256S("0xc87f9d31c4c17d1560fca3366cdcafde6afee350137333b95e33354c2aee62c5")},
                {90, uint256S("0x1cb71010e0c06cd222ca74d97017324a1164d54ba759d05ae9d7a94b36b37b10")},
                {91, uint256S("0x34cbc285c6cb3a169aa02f100c9429c6e246c96c4589e3a21df9f5a479bf6d24")},
                {92, uint256S("0xe2172002a1e686ee96cbb91d76c643faf6f4b44bb4f01aeb95a8a66ea8b63bf1")},
                {93, uint256S("0xef7e83738b2d02a1ee151d8f6604006355c11eb6d3bea40343ea3fe4324a3eae")},
                {94, uint256S("0x3107201a0cb45d817c29967432cc80dd967841f9d96ad9ff2020e751398a9cde")},
                {95, uint256S("0xd6fc67a6f0fa004089d8e22e39bb1babca648ed9b42156d6b43c303db14213ed")},
                {96, uint256S("0xb321e0721c209464334b23c406ce68f3dd6e729d52699d12b0d4555adbf59cca")},
                {97, uint256S("0x535b5760dfaaa287a5b6ee70050821e65e7226b65abbf775c61bdcbeaabf0cb9")},
                {98, uint256S("0x0e923dc44a77ded92a7f72718a95bb5cd6b065747d105663d5a4eea61829ff4c")},
                {99, uint256S("0xef18ac9e9b0c9808c5c654681490329c412ea0da94edca6aacfbc4eb47d5029f")},
                {100, uint256S("0x04fdbf3ffb7bcebcd91665e4ffa962db104d04a7de669a0d02aff88263d0307f")},
                {101, uint256S("0x404bc0ba3caa1858634de29cdbf99d9c40594b52f4166c57c92a01eeb9307382")},
                {102, uint256S("0xd7469eb627ef2e7b4e99674b199cda592a97bfebf0ace3d36f9cc3597d359423")},
                {103, uint256S("0x7b59d30ad29c8a17b4fdf7bb3b9ff06edbd8996325ad57c93e10fa89777a45aa")},
                {104, uint256S("0x3e7282e1b3844a084af1997f0fd3da0115d494ee3914c48829388d838e90b37b")},
                {105, uint256S("0x937edfb51bb5cc8a7c6de3670a98db7fbd5e62e45077ea84057563bc7d986d5e")},
                {106, uint256S("0x3f4d2f421973117191d924c1742921159043cdc487b18a1c37a3a32481e6833b")},
                {107, uint256S("0x625bbeaa48fffe21e9dd9fcd0d79c0bebc890e98e12c0eac07cb28eb14f07445")},
                {108, uint256S("0xe82b967a980376ddb1af263655bcf620b24fe8a7215dabab1efbd62f72521a8d")},
                {109, uint256S("0xfb15765e294b21685f3d0353ab37f9d1867550e6af492689626510f49c82a8a3")},
                {110, uint256S("0xdc594684ea5c873c8dc425d1a03e56be7e00af3c024e9eac171f1e1abde3a5ab")},
                {111, uint256S("0x6776efb2411210079f31da13da112722b5e17dc7ec0af6129f099115cf471fb7")},
                {112, uint256S("0x8fb73d4d78781867f159f449cdf54f4e7f4a455498fb7ca4947d6e1c89b2d746")},
                {113, uint256S("0x9244399883cc5c087df47a62433b6827e2fe71e3146556a39ce5978cc0743f58")},
                {114, uint256S("0xf389554138f9c7b2f848b94050dabda687cf5075358294211337ac2e6594552e")},
                {115, uint256S("0x8f68c558d87674e54b70f939d76662b1358c48167a977b61bb2f2dcb25025c13")},
                {116, uint256S("0x98172e4edd8b23630ec047765e15552306d017ff9563afad35dd12270bb945a1")},
                {117, uint256S("0x731852846c7afd30c1b57573cc56be691ec99469d71c0043061144eadcc884ff")},
                {118, uint256S("0x3874dd94f59d8b771a451443684deae167b16c9cd861de02ce389998b8edea1f")},
                {119, uint256S("0xe16aae5e68acffd5f89f1184ca0fcfe3f9ed616ec28e32e7889dc4a2487636e3")},
                {120, uint256S("0xbb1babb9015778158949d4e6492e385435f110efe4dc258509125b99e6b0b8ae")},
                {121, uint256S("0x2713b0537328d688b39719a6805581e1e55c0ace02f5709ae85a5a7abf2c73e6")},
                {122, uint256S("0x9ef2d39c540ccaff14513316c217b330b2c68f6582790c38c669c7ed4c306b43")},
                {123, uint256S("0x9aa48063d02916e9a06cf6c94f09b14644801bca5392ed8ae270baa7644965e2")},
                {124, uint256S("0x0dfa0c25552607e0131b517272b2506b742caad8dc647e9ec1accf72ae86fcdc")},
                {125, uint256S("0x4b340170e440f5d710e5fe14e9ef5d6a33d5f6349cddef5685d33b4709b495e0")},
                {126, uint256S("0x2df24108040bb284bd30a3308c84a21f62ed2684c01533ef71e9e5474fd54fb3")},
                {127, uint256S("0x7658abd1f6ece1e4c7f0b9ee09845b5c8cec1e61f6fe35e2ad8028b317775b67")},
                {128, uint256S("0xa5aa7d2e2d0b1c31f6aa1bc70d1a779c266d664b085c4df22c24424fd0cd22c4")},
                {129, uint256S("0xac28b1bdd2a7ada7d43bd4d43f0347d651cb004dea3cd3aefd27d24800742aab")},
                {130, uint256S("0x73a87396fd3f94a1fb81c2c84aa6387a01df15a443044c95e32643c3caab5436")},
                {131, uint256S("0x999fdb2985663957ba0bd282e2db11ef5305372723737c92778739e577b1ddc4")},
                {132, uint256S("0xc8c8e596925ccbe17705c8e317a0035b070fd214ac1bd045e4fd54d8cb32e6ea")},
                {133, uint256S("0xa0abcc96ba9df439e1fda20f1190d0aad84c002def99b56b23ca06b01bf29a19")},
                {134, uint256S("0xda081bde48ee13bf02311f64bfaba3c49711055dc58ddd96a16c64654a83a9ab")},
                {135, uint256S("0xf6d557c22e256983d7339bcd4143f3720758f06c7a7ec1fa45c0df8d79cc0ea2")},
                {136, uint256S("0x1864d1f32d2aa98e8140ec084a97aca9482349f4d1b54c9a9292faac5ae0b067")},
                {137, uint256S("0x700a22abb11df0f07d28f50e28b86edb12ca37a6d7a0df913708b06976d1d8f0")},
                {138, uint256S("0x5c9cd3b471f79e695234bd3e1f42b649e36bd1266f1debbfe7454b57bbbd2d8b")},
                {139, uint256S("0x163732d557d4198145ad4c05829b0a57a20556258b9880f76e80a11e4b857e5a")},
                {140, uint256S("0x5c04ff07bf2d99d220693fa18b9a22d3250888e34db0bd97e787587066587fcb")},
                {141, uint256S("0x6e59db940c1c38844b451298cd537973e6da6aea795c944ea96bec3bf17cb119")},
                {142, uint256S("0x553d8b03d3cf343d22a785407a0fff3974e5111b6eda64a4601fb09790412616")},
                {143, uint256S("0xe1be8c31a0c4b484b75b020e1ae7d2dfe386e751f1dc3782edfeaecce9c72f84")},
                {144, uint256S("0xf211e06a593d8dd4c69c6bcffa04ccbd2540fedc414e08032d5e21fa21ee71bb")},
                {145, uint256S("0x48ec1c3d0d726835ced873c0132143993318fb11aaa80a3a4f518f3323fdb208")},
                {146, uint256S("0x2821eeedae3f5d027af5987292142d49943fba8731f418fe545877f9d8776b0c")},
                {147, uint256S("0x1e1d7edc49f4228872b82d728c85a57eab0537429666ec60cb5c47d169e5f383")},
                {148, uint256S("0xb90a60715a85d055f8d588e618134faa81a104e6d301600f9b5af691cd4f233c")},
                {149, uint256S("0x85307694073e5bae8ba3c4a70d4c5fc4b270c259b3fae875b022a247209bbd72")},
                {150, uint256S("0xecccd65deacdd2a0d2ed268a16fcf7c4f1e40c3a3814e00fe442e5110295ccb1")},
                {151, uint256S("0x282af9e2829509aaeccd7a57bbd953bdf72c649b03cfd9640a2212aea907726b")},
                {152, uint256S("0x9f101ad4acdfeb09f608a9977a0cea3401382a51d2e233d01d5680ba5a8e53da")},
                {153, uint256S("0xe240f52ccff7e7def895a2989bd1c5d2ae4627f26d806b9141ad0a36128dd03a")},
                {154, uint256S("0x095dbc7de39dbdf14a822e3fddeafe93d1892fe54ea3bc575c7a801d42683d58")},
                {155, uint256S("0xb28231aca9fe0d52f84200df015854f361adb1ccfd5f3a7e6d8faea4ae7d5cea")},
                {156, uint256S("0x5b31b121d1d4a37897180058be76f3625e2b4f7271d228e0f7db6e41a468cf9a")},
                {157, uint256S("0xf6abc4fb830333e202721b62bc916ba3e56fb67cc01c41f4dddba6f2101cd823")},
                {158, uint256S("0xafc3e3fcd32d6a6c488c25e99254e8860104a3de496b742bcd1a8d611dbbee53")},
                {159, uint256S("0x56d689dc557069ec1b7f8c1e45779d08fdd44d217f32f96bec67574b6aafcd31")},
                {160, uint256S("0x4f1463c42949582687981e880db323948cd82d402f9ec82cc3d77b5b1768caf1")},
                {161, uint256S("0x1020f62a55e35612c5246df6195444cc68a0af0801ef3cd3c4ce22f75131430b")},
                {162, uint256S("0xd8e2b2a5d56ef14832529e5efae6ed19acb60e39d23b2a0ca411c7ede5c25a1e")},
                {163, uint256S("0x637ec8a38a0a9584b672b09e82fa7621ab55d8d45c76e594f618b94dd112e0c3")},
                {164, uint256S("0xffbc7f2b132328490c20f0ad8b973d6a774a6bd580f84bb416bfbb35e6b90280")},
                {165, uint256S("0x1e0a87b867cb208e5a18d922665ac7c6045be8171e01970ba923773447c9f2ba")},
                {166, uint256S("0x1c8f2666515e96e26efff11f08ad66c79e6be396328904e5f9bac26fda60aca1")},
                {167, uint256S("0xf975dd3e7d8feb9c1c74c5a268a5715301d03ac08fae616a8942c806846797de")},
                {168, uint256S("0x905f69d898a03c8affff7e4e98fa5177d988a2cdf9d8742c6b0b3f851f0af1a2")},
                {169, uint256S("0x67a4dfb1da8fd26983e1336260550c90dfeb5c8846b02f68ee6d3c42382c17a7")},
                {170, uint256S("0x76cdda71152409751ceec1616c89da5dce40f1e4573c2844d945ef5b7e06671c")},
                {171, uint256S("0xe09d90ab09c8841ae101a1b3683a7f77ceec784bdcc00a3e47e3a56e5ac9eb88")},
                {172, uint256S("0xb761fd2bb6ee0fd9965d351af8a0b5df1c00151fbd903bdffbd9c705e12397c6")},
                {173, uint256S("0x312e1f9b9b88bfbb9c9670a8a2df470adf1515678782c77ecfc2e47fdd4b7e7c")},
                {174, uint256S("0xe7655bf7c42c93698a97eadb358df0d12f254ae91d4e21c86898b2ad0744fb61")},
                {175, uint256S("0xf5a970ab4864b0b5cdca975e65ea45aa26177fa20996ad3afd50b754fd611d67")},
                {176, uint256S("0xabaa7a63efd1de3647aa51802fe8dd4f03d926af1f25b4dff42e7830a799944f")},
                {177, uint256S("0x99e77cf63ba23087df89f3e9f115177741de535bfca3f19c5456122fd585570c")},
                {178, uint256S("0x9e09afa71828906fb2d311a94a4d5a5f57ba2fe1a9e9c3a9f7c459d606c954bb")},
                {179, uint256S("0xff858349bd193b508c6cf2971803f28162bfd0d9199f358cdc4f3854834e74ac")},
                {180, uint256S("0x4e8762de0cba43a301363665aa2e240ee1e2645570fc92630331c55a463636df")},
                {181, uint256S("0x7cc8f0f27147fc94c2d8727e6dc481c0b5c98a9ba271accaa9fb4a46c909e285")},
                {182, uint256S("0x0fe6998f13a54c8a72cb8dc5acd801906f8b3ebd95ae94173a350f5060ae90fc")},
                {183, uint256S("0xcb8b145d6856481a1bb49bc20c777ab827a124ed12afebc14ab4cf415cbeb73e")},
                {184, uint256S("0xcf7a79d7d987fa195298c2055d072b882c074414dbae3b109c0740b9f1cf2635")},
                {185, uint256S("0x17650b31a6a2b5697ec7281bd175b29b13d65235a5b12ad4fc2f468d26042165")},
                {186, uint256S("0x52a51c98bbb236664e0e1cc01181f6c7a61db91862245c677f140753e2c34f38")},
                {187, uint256S("0x4c5e8f84955e0bd2b4d728963f22697bedbf829db094a9bc899e3cfd42ca07a0")},
                {188, uint256S("0x530643eaf9d38f5d04eb1f9d80bee364f99c0082ce51d9c055f335d1a6135352")},
                {189, uint256S("0xbceaacc173fd6b3f549c00f971ebb760454ef2fd3716756608e332de11c858f2")},
                {190, uint256S("0x8b177fb2834585b696a8fdf430b55b02fb0b7b6967fc48a4a7f49c26cc39a0b4")},
                {191, uint256S("0xd5f4e793e0d6630e3f0dca1feab8e047ccb7d80180a8ee7859d61c3d1f45afcc")},
                {192, uint256S("0xcc24a41d339b124d68ac50273bcf3bbf293c9291526808218db50c9985d2a02d")},
                {193, uint256S("0x0f913879d3b3f88ee590586d65bae1956bbc7f5c1c15a9ae58182f495463eef8")},
                {194, uint256S("0x0ea956520bb76eeb32968204c2842957aef58e6df8f0b9e4f120b0bd0337a586")},
                {195, uint256S("0xe39857c82576dcff257abc660607c930126cc43b953fc4c8372e7e9b2aaae369")},
                {196, uint256S("0xc7d526caa869d4380b37b9055f033131808105de5a18aaa47d793fc2edf655a6")},
                {197, uint256S("0xcdb0f3aefec970ac3ff52df7ab496093f69a82cc09511f6e170e95eb4eaa83e6")},
                {198, uint256S("0x39a26afdf0acb2850326315b6a0b8953f0e94341204bab9e0e1b27f284b3ed33")},
                {199, uint256S("0x4f3536e08ac0d5c31912ba7a1a128211324f8b505ed6267d0a6f72773f723388")},
                {200, uint256S("0xc532c194a5933293f3fad800fac9222760ee722f660acf748a01f10295850c07")},
                {201, uint256S("0xbc3147154317ef3308a9f0da864d9aa9933b845d3010f1a254158bbd435165c6")},
                {202, uint256S("0x9555b4445e816cc4c5c95b9e2152ad0bdb8b2fa4c00e90c31caa8a63b8bc044d")},
                {203, uint256S("0x58ee7941187dfa1126ff8f2965e19d8534d29434370399d82cb456c199d87a28")},
                {204, uint256S("0x8273333e0d3ed98b477f7fe5ee5b0483aaed1582a40619b94927449f2077fb64")},
                {205, uint256S("0x01f6e94c9b4a5c980096159cd146eb65b572f139bfab5ad0011f6ccf607f0d52")},
                {206, uint256S("0x8b9a53911c41913f846e3ff6b0427b172e30be08ae7679aed5586e246cd0619b")},
                {207, uint256S("0xed816baa67de0edf65b88753928876f2760ea1d9d6f83403394358151198211c")},
                {208, uint256S("0xf3e1ba33b7506bdf98a803ecbef923a5a3583338d4a7fceca8541c4bf8896319")},
                {209, uint256S("0xfb560e4caba617c122e1d89d39a593d664079473b747c277cb9cfc81c4fda9a1")},
                {210, uint256S("0x35c9e34dbeed7a36e06d2ce7050248341b16e54326e9a92c4179c0a2e9c92af4")},
                {211, uint256S("0x1aad6f503c9f329fca676b4259cc27ae553116a82dbd692ee39f0a301230a8a6")},
                {212, uint256S("0xf29581fa86b91170a26dedd8bf686885f2a01c5ceaf268a41563b89e07e327e7")},
                {213, uint256S("0xf510326cf7ae738a5f3c5dfd380660225ebc6ca7393adc794c06e2b31b164435")},
                {214, uint256S("0xf079fd6a0ee155d752ab2c04e5b8fa12beb556a7c752b461e51b6925dfc09af1")},
                {215, uint256S("0x6caffad2a6d766299b8e4dbed5f029531aef213dffbdb941bb85dba912c14735")},
                {216, uint256S("0xf27e835aba6395a63be43924f0f7c405d21e0c4ed05669ea868e0da61ffaf8c0")},
                {217, uint256S("0x594ffc6eaeece62a0a621c6bbe8d48bbb995e74885c5423806e31c5c74defb5a")},
                {218, uint256S("0xc0bbc26a732bbbc1cecd2aa4a4285612160705c82200018427a8f3b499c7781e")},
                {219, uint256S("0x595f093157650c9a1846ee69fe84d04155f707a3258027548790cf1c0048f5a8")},
                {220, uint256S("0xdae16dc1c57653b28402567a7962b43eedede16aef7ec58cbcdf74f61b83bae0")},
                {221, uint256S("0x5ebb391e11681a084c1837356c1bed8fac1e0799850dcdfa24862d5aee7121ea")},
                {222, uint256S("0x58f401f8e3f6bb064eff72ddc251e5452045de211f95b3f20b7637caa0ef2ee8")},
                {223, uint256S("0x63bca06b3246bb0c892c2c23ab9b4659c1406f658f41d75a19a5b3490cc057b1")},
                {224, uint256S("0xd216995068bd4ce9ae4547bfe73fe21123b51d884949f450e0bd033e8d167a24")},
                {225, uint256S("0x32aa50b27fd8dce551cda96c0f32a903bd23e6cafb88036726ab4b38dcd6308e")},
                {226, uint256S("0x1385b926485ab5a3e7a1e307270af15d205d6bdeff177b23f37e09b867ce6997")},
                {227, uint256S("0x0f74b4141bcd08bcbe8082e27c7cb7096c957d60904e0613dead4c3d593a895d")},
                {228, uint256S("0xbcd464c5aa3009535331718509f01cbfad207c126178fd3bad134827764132bc")},
                {229, uint256S("0x5b1f41cc82676c3fcbbe088fe485064dfd1186224ceda3cc26d3ebd51e59f4f9")},
                {230, uint256S("0x7e01ced9b145681116e60756eb8112b114809623731eba8b093a49522d65817d")},
                {231, uint256S("0x84d80ed2c2efdf4ac6f536cd0d20e0919d96350d784184895468d05d6e26ad12")},
                {232, uint256S("0x36f045d0609570669088dbcbdafaf4e6a8defc23b0a5d641fbf4e3756440b147")},
                {233, uint256S("0xa2c15d3cfa8f2298f82b98e692e8f7a928bf931e3ce4d1dbee7f557ee508141c")},
                {234, uint256S("0x84eaf07b67689a0f2afd478344bf4c986b710d81d1799479b69760555397f941")},
                {235, uint256S("0x320ccf06fae1c7e0b0bbd1d060e2261ac248135baa03b1a92f30d390c3994a2b")},
                {236, uint256S("0x460a0f4b2fae0f045fdfdb718fd99015fabad7f22c0c349f50861b4297c1461a")},
                {237, uint256S("0xb11966e04dfc210ec29f6c90d1de0190f7deea5953324045cb57a2d5c60bc640")},
                {238, uint256S("0x54aae485f63f07f640d7da5edcc25d5b16d85fd7b33cfcd566c01464b7595fce")},
                {239, uint256S("0x4616ce8458f70e3c203e8facad9e7dbb7dd75bce4ab30a42fc88012bbb8686b3")},
                {240, uint256S("0x815931e93abd686102432ed56fb02cbb4c57d107c7ba10a3b56edaad1b73479e")},
                {241, uint256S("0xe9ce15230ee0dd7a022d27553e150324e0b33b1983242b404c902268adcbf4fb")},
                {242, uint256S("0xa33859aade60bbd349dd35aff2b523f9a0c6aedb368b3ab5f08e60e72abd279c")},
                {243, uint256S("0xbf2fc2039ae3fc4de2df9d84b56770675a5c0c5dac910618db61ba89d84d3bc1")},
                {244, uint256S("0x09b555df737d0801cabd1b6a370a72facba799ed2c0c079075e2a98e25a6c353")},
                {245, uint256S("0xc9df4c8ec7debae1b6e12859d5e8b4ce0e939d7d023e8843d2b0ccbb8f93ab0b")},
                {246, uint256S("0xcd307f94e29295116a353103e98b51d55a0d8092adba0246afab1137721caf01")},
                {247, uint256S("0x13cb45b53154acca7693ae3ea069b620fd86d47e8b0600a08da543c6aa72badd")},
                {248, uint256S("0x1c482174f5f160e58ab43866fff49ef1afe38926728e20bc6784b2db06fbd00d")},
                {249, uint256S("0x540509668eec94f55f1ff26338de8ac70307f7eca7e64041a7e296cf70e38f33")},
                {250, uint256S("0x55d90e323bd7a02c4ccb7a2463917620017b835b7f762a10d2149f3d92fe43fe")},
                {251, uint256S("0xa88d997bcfaac83a5bf51465451e6a295d9e929b66e3c173b9ec8e658b731812")},
                {252, uint256S("0xd3e45d8679780b32ff9ba26c604bbef1dd6360c8a4be382047b4b34ffe1483a3")},
                {253, uint256S("0xb33f4f9428f78e1dbd522930fd02bfe4927e9e2d923befc4fcf7588f03a6cd98")},
                {254, uint256S("0xedd5e3b03940c392899fc6f777775985b84e666c04f06d3b60dea290ff5205e0")},
                {255, uint256S("0x5928846ae2f7bebbe2d918eccd602dbf1581261fbcf22c043ae4b13ca343654e")},
                {256, uint256S("0xedeef6f0e03b0680cc6cdeed993db4cbc422a79e8a9a1f74d9d948cf50316e90")},
                {257, uint256S("0xe10dc9485c41e64491bbadf7e1636e54ca7fe0c4005628a042017583d25b5d65")},
                {258, uint256S("0x46af6c56fca26850feb80d082bf2ecf1abd7ae631cc6b0deea9d9674a8fafd68")},
                {259, uint256S("0xa9b0356ddbb2d330e6745de307c0f2d8cf268aee3313ab2c6f9a3213fedf158f")},
                {260, uint256S("0x58685492897eb74b37ffaec8c0e8654d848b7d174a430f1a4256c077a2fe7107")},
                {261, uint256S("0x45a5b502aa941b2ab25f802be0b9a3ccaeb36e6dd19f050c27917fc5a68eedac")},
                {262, uint256S("0x8093ae94a1c89c29524b6df53943b71d4af0e4d1f2e0f592e94f4f61836ec06d")},
                {263, uint256S("0x5922ebd66e9784db729addceafb54f6c30c61540f423d78a4a2c1c9b21ed231e")},
                {264, uint256S("0x8e866abd009979196554522f481337da615806e7b12839fb629ee32a5917efef")},
                {265, uint256S("0x7de5587adb39981b975bcb2685405126194f3c26620845b343123fd21c4b2ebc")},
                {266, uint256S("0xa7d309370d4d2bcd5c7a209e2ec53b0d95adc83054a77a02f70c59859e77f51b")},
                {267, uint256S("0x25569f16b11c60fa8578e4b2c7e7e6cf775f16fe1c81a400f2171e6a88d795c1")},
                {268, uint256S("0x7e1786fa643f09a7f84f61a914c8a8de5bc5b6bf690febb95c6bd85f7edabc87")},
                {269, uint256S("0x93fce722f8e1e296ed3145fd8cbd3b2f774157614a48dfe86430042d793d2e48")},
                {270, uint256S("0x7ad7122df9c6b6d600c6f38a845e4ffcf762444fe175b908a3ee041cd635d7bd")},
                {271, uint256S("0xaf7cc05be9ae156d03dc337630f99044a79a62c956c2cc77e313d938ad737521")},
                {272, uint256S("0xa0ec6aee0a174a650410494f0d9c6071c49cf73a775f832225f2ff9a350455c5")},
                {273, uint256S("0xeee3208acde7c3578aa5279bdc01d6e05de484489f37fb7303b71be678405036")},
                {274, uint256S("0x36e2286378d2280206a5789e6236725cfc3b7ec386f2eff3a5f22ac56fbc74bf")},
                {275, uint256S("0x4a1aecbaaad81a6d0a26eca167076972862b2ce75d1a556e0b8e4209ddd9796e")},
                {276, uint256S("0xd4d5c6979dee04cbaeddc467c2fab069262373cced6ccedc040a69361303134e")},
                {277, uint256S("0xe3a8a0188b600dbc9e29016e244390663783c446c12a99e3b73e56be6d82b972")},
                {278, uint256S("0x5d72df51628ba35f7805656d1f0d290374f2cb2872b7fce5d31ab9bcf83515c2")},
                {279, uint256S("0x7ff85b4a5b194ba577aa4397b6564fef0383be177ca8dad9924c97f926185bf8")},
                {280, uint256S("0xc7c54cd1095cf31983a1a18ae4c82d2aab1a9e69150e2157751479fcc2960ffc")},
                {281, uint256S("0xbb205a2e712b303ffb8456e2e02ae9f89009722cd450a7af92675798824c3d78")},
                {282, uint256S("0x0e4fb9939eea927a326c9c80ce96fd9461d05cb9ff4c0166dfd0c20d60a7d379")},
                {283, uint256S("0x9022126e9195367f9fccbc9990ac64c9a274bb1b4f37e458efbcfd1e6c3530e1")},
                {284, uint256S("0x1a01b6dcadb1188d71831266802ce7990a3a28d3125f278e6e136354456678ad")},
                {285, uint256S("0xb3639571e1c30b0525245736fbf249fc4e1c1e80ec16db75d4490b83995adfd6")},
                {286, uint256S("0xc91c014c6a3897a0c3fff58f2f471da37bfead804fe79657d5ba688ad8cf3f0c")},
                {287, uint256S("0x3c7976b4716d3b1a9554888bb8da6ccde3eaf832cc1eb1db2a30bea2b06cb286")},
                {288, uint256S("0x06c1bd1cec2337ed1370ff5555a85db0a8af3cce30875fb6c92cc4e011811399")},
                {289, uint256S("0x9b78d5507c7c5410af82b443fcaa2159399f6f812fde774d42c91f2aba09e72b")},
                {290, uint256S("0x7b7a9c9d6fea42fcf1045a88997206b63a85297c0128fe8d618619efc03bfc1b")},
                {291, uint256S("0xe70103cbbb049d7a1de3756b424a1e11454583b2bd517dc3ca1be5d5f2744c5d")},
                {292, uint256S("0xb212beee8c93421b99888eebd2279f5a87581df26c88b8820db4f3051861e9a8")},
                {293, uint256S("0x64bd1a68a4f3ce4455449768e2c24421a06226cf3fbc35d04160013467846a3d")},
                {294, uint256S("0xdc4b57a9eaa3452aef61562e69ed2739b6ca50d9cf950fb3a9a5649d98ec47b5")},
                {295, uint256S("0xaff04b03bbb0a639cc4880b47844c262b6d91e13edd06e69214caa3f04592ad7")},
                {296, uint256S("0xf9e9abbc8cc33d40e52f9455dc474faf88f50c688ee238db502b8a3ef411daf9")},
                {297, uint256S("0xd7841b5a0ff18dfa7d2bede4f2d804875a512142f6c6f7f7b29b49e3adebefee")},
                {298, uint256S("0x62a4e049db08c8eadef358e2bbd22009f9b67bdc664e76b5fe4d4b9ef79fd4a9")},
                {299, uint256S("0xa802ddcc87b94ba1ba0c348312e5b74a38af2c7dc489cd982f0c589163eda386")},
                {300, uint256S("0x12cfea1191376c98778bd7d7434632cd631278ac135a2bcecaa96a8e717d708b")},
                {301, uint256S("0x63fba7fcd18aaaf7656920dd64d4c42891ff545313897179d74730bb0a70668b")},
                {302, uint256S("0x30cb64be7269fcf669f045af4c5c4562437fd69096a9ea1a78a884dcec54a9c9")},
                {303, uint256S("0x4d2b71e5a66374fcc2a435c228c349fcaa808a39b47e569abc7f0f10b2bcd4cb")},
                {304, uint256S("0x8e452f1c340d5030afc2c5bafd2460035a1a363f9ab25f7bd03415bb72fedf92")},
                {305, uint256S("0xd076221fad693114848199aac11315ff1e9844d88669d765d8e090338fc438b7")},
                {306, uint256S("0x31baad013287c1726815e28e0cabb1d3571237103e2c4b41e77b55f1cb04646a")},
                {307, uint256S("0x5396253047c3aa7d3a0901afd64acfaf0c2c0756cc01be98f6f3d528447f88d7")},
                {308, uint256S("0x6ef8daa9f85852bdd015702dd4ee6676ff893e8d41f7dc1025cb2127d5386029")},
                {309, uint256S("0x23c4cf475e18e12ed15e7cf35c5bd697201bdd021c378e668d50f74e26ff3f54")},
                {310, uint256S("0xab7b5b2371eb2aa591ba8548c80622384afed36bd4a42d000110a11f5a5ff6e2")},
                {311, uint256S("0x173e951dc179b4a7413bfbd25fa11bf4c9cc6cb4fa75bb6ca19aa53ac7916162")},
                {312, uint256S("0x8619cbab0d1a4a6e68043be98bf5f076dd1a58f57f6051855f79acce4dd1582e")},
                {313, uint256S("0x087ae34de849ec5775fb39469094607b67f6b2dfc5866b1f6fc29240019f5769")},
                {314, uint256S("0xb8cf30c2d84368ea76a04c5356b4d0d10a65e637de59eb66bc99bfb99071ff22")},
                {315, uint256S("0xb2374921cc4e30b97a391cf7a024fd9081f93063c34cab56b2b964e9d8d72430")},
                {316, uint256S("0x9279a555885b36e0030ebfb6fbbc90b66f5e850007ee4bcec9a6ae507cfc78d1")},
                {317, uint256S("0xe6b1839ea9b488ebef97c9a0828fdaa9805d24a3853c74075e12b65a78c0b1b5")},
                {318, uint256S("0x9d562567ea021fbc1a9cb884735d3fe8219b1b961af6d9d87917b59a7a05e2f7")},
                {319, uint256S("0x2a0ec08641189b3d718559932d6f9e1821727b87e9ff8e12268a6ed9e15806ac")},
                {320, uint256S("0xd055bbd146d84a8b8cdfe99e762d0dbad6dd93a4c7b49ad7e08f4615441644cf")},
                {321, uint256S("0x18ad5fc5b1fda6ec13d30760df756b10a258dc531325b1e982c351d466324bfb")},
                {322, uint256S("0xd6eb5081af98c2292d46baa4be14b63e963434c4b3ac8915760fb3a7741b0193")},
                {323, uint256S("0x2523572a966c8365ed2cf3c7103863fa3acf75f6f8503d7edce71594f34ee7b9")},
                {324, uint256S("0xd424040f2de515178e857cf904dc2078fce2031550f6ecb1d789dde0cb599397")},
                {325, uint256S("0x9232c4a6b6780a69e9bff7ab7db046771c48374a605c7b5bda1bf0d0edea2033")},
                {326, uint256S("0xbd7e1b3372dfda664db94814c63aea75f04decbf14c7e638751b67107e296aa4")},
                {327, uint256S("0x637004f44494470388377960bbd836b358e91f81542bfcb6eb17d2ec84c11ff3")},
                {328, uint256S("0x3c6bfbb177b633bfa35807ce9931ff12949492c8a1a43e53b8704574ecfa8986")},
                {329, uint256S("0x02fcdc930e565d22078826f36831a6becaf94a6be4a87cc70a95f65152de8abe")},
                {330, uint256S("0x672211cbb02c5321617ae5893cd2ba2250010125fe454db5b30c63a561ecf663")},
                {331, uint256S("0x0151e56b148343b03fac123a6841f5582b4ff736da527792d2c1de2b87db8c15")},
                {332, uint256S("0x0ad2d0add0ad2532396366598f68db7df2405da1c28d536017db5c8eaa21754c")},
                {333, uint256S("0x09a71324b875adccf4690071af51bc7ce266f83b1225f871055edb469ff5c752")},
                {334, uint256S("0xbc0dc276bc0dcc1e5103748c54c3084094a1b378b62a41d17e240d2a7eed07d2")},
                {335, uint256S("0xd7562f5b36d5178bc60a57b11bed41e61edcba50af6e317d69a01b71fddf0443")},
                {336, uint256S("0x3981c5f79d181f99ff610f6869d77a6edd457ec8035287dda131ef8ab1d1cc52")},
                {337, uint256S("0x078b11293aa9e90780927f136a50c28ea6a4aa8345daacb2a9a49bb11cc2f44e")},
                {338, uint256S("0x6f3c59e06f5c1de686371e7dc60479925b634543f2db6cc5565f9462d3a8849d")},
                {339, uint256S("0x70355c27030eb019d00add68eeae504b7cf99cc0ca3d7549b1bf5faae4b60f46")},
                {340, uint256S("0x3f2bde9a1fd87e362e8a0e80c42f7bae08c0c45990dadeb333fee7dc2391e0fa")},
                {341, uint256S("0x26aebfb09422e309b049d2089fd4b4b10130f12e9addd3fe24a81eb75d78a3e7")},
                {342, uint256S("0x9a32943c2983a078dea888b113d2c0b355d52499ee5da1f0ea02a9c7925cbb01")},
                {343, uint256S("0xc60b1ec1488eb193e9823877564ecd1567500aaacbfaffd69bcec4cf3dc9e66f")},
                {344, uint256S("0xae5e4db471d0f35640a810f4e5124b53b13b420dce4b118b7bc62d9f098b55e8")},
                {345, uint256S("0x7481607f8bc5faea39fcbccb3df91892e6571b36427cf29e02b3279f6cf7f777")},
                {346, uint256S("0xebe84232d24b15cd0bd48e5111d246bcf441078386ffbae1ba56f822dbbac796")},
                {347, uint256S("0xbdb3766298609771e02d756db0e1d0fd8778418bb53ab41f5e6fd8d1864bf883")},
                {348, uint256S("0x218cd01287cceed2128a3f7869942156bfd8bf8465b4a647c578e4013c89c79e")},
                {349, uint256S("0x6c1b14b03107b62a61c5b64333c1f7d716cbbfad1723d7c216962858eb5936c8")},
                {350, uint256S("0x4ccacc0e1a70cc3d1323f5abd6ab9b539eb2616c26ba4c3f68e8a2bb684845ff")},
                {351, uint256S("0xa0304959354dea6949e6e35920d6b60cc4711afa8ec34024278319f189dcaeb7")},
                {352, uint256S("0x3bf46960c2f5a5f796431f242ad43b0317ffa9384188d8a288314c3890c208b4")},
                {353, uint256S("0x67fed402eee95153708a84416467a48b00e96b54fed04d603fa9f1688abe6eb8")},
                {354, uint256S("0xf055c34b882a5bd7d50e4e7726acf80fa8a1fe057c4213745f558c595508a6bc")},
                {355, uint256S("0xce399f4990ccf38e0c10aa92bf4a2c044133fbff3d693ede169d35ffda99744c")},
                {356, uint256S("0xae091b7bc568818c6285571cc5caf798129e7b5b4f05ad2e9ceabb763b7f1c76")},
                {357, uint256S("0xa00c48f717a82615c49cea2584ee966e0b7a2e40f84d1f63345cbc5d3f378e0b")},
                {358, uint256S("0xe6ddc78f522d5b513e154e617c182c0e2d80ee310acae9b9d1066def01862e96")},
                {359, uint256S("0xb6fafccf1b8bdc830e7f4815b47dcf4699802c3e04ac77dd63617ccccbe1e629")},
                {360, uint256S("0x6ecc0ba0035526f57417f9e20a14e1a3b36051b31524ff4780507ce79411cb0e")},
                {361, uint256S("0x6648b5ec3ab9b01023b67db764dadc9b9644dd13bd8e1419df70ea7af5a1f96c")},
                {362, uint256S("0x6180e2776338cd59efdd33ea99c1ffba1288eda1856df0089236096431697d81")},
                {363, uint256S("0xaf1c7757f7647c1ed6fee98b0ee89072b85e95c1680bc56bd4524483fd1b1c80")},
                {364, uint256S("0x0c1b38f596997910519fd5bdc2f2e670b7d829ee455e00c0b048d136d01b2f9e")},
                {365, uint256S("0xf55a0b907924393c14f5c748b822be9bb8d33973fa7844a0bc686cc0115d1e4c")},
                {366, uint256S("0xa1e79978086168fb7e311429f9096ae8fea6a7759217ff909573359c2ea3a289")},
                {367, uint256S("0xcaed31265d52a210c7dca95f20ce9f4ba5a9b821e923cb10db9200f6e634fa6a")},
                {368, uint256S("0x7f532572c40e4107937f0d0bc03f21e818bf7c92da23703d4cd7ba6090c2fa9f")},
                {369, uint256S("0xd055fc00cd39fc9112df20d207c1b78d84ea652d22d28e8119a92a6e4b762180")},
                {370, uint256S("0x0faae9ffb061519cf2b431c2ff6da4c3c2022ea15d3e67c9a60bbbf8455ad7e6")},
                {371, uint256S("0x3805a98c988b1c7c08140ef186790c67aa7fa78358b9d4c2cb68a782950e9033")},
                {372, uint256S("0x3ca6e8996ddabbb09298f11174d1851977b5e43bf196655b133861a0a9bf2298")},
                {373, uint256S("0x05c58019c25ce901f0bfc5e174190af08c0ba25ab83505cbfe16f8973b2dbcb3")},
                {374, uint256S("0x849d451e2b8587ae2d0ed318031e5c544e194f4054a90c47d5926be85ab82a9a")},
                {375, uint256S("0x57b8af4437bd9e38d435769bc30101f07c51c56ea05ff272b1b2d76eefd8d0bb")},
                {376, uint256S("0x4fff6f038cf6d67c9f1552113779fe8ded2a32310b5df1d0235f84da8786474a")},
                {377, uint256S("0x978ace14fdecc1143cafa0e9200e99ec166c46b043a8d23c75f69d0e75587a30")},
                {378, uint256S("0x6d630479d64f19b995775b6486c0a84fb5eac2d874e96e926717cad18ae8bca7")},
                {379, uint256S("0xda5a642d5a16b475065c50f363d786bf43a9cae8903890b455c7f30a0a8b86af")},
                {380, uint256S("0xd462a27801929ee7511d34ba8a91c32c1239e6bf0b07b651b91727562831126e")},
                {381, uint256S("0x0c5fe47f7d9cdce1bde5fbb308aca14dad8e118fbe697b3ebdd9b8af70f8a47d")},
                {382, uint256S("0xcefc2186bc0f14dcf91c3bcd68a3370c71326851ed9e9c20fbe7275cfdde6d25")},
                {383, uint256S("0xa1b22b9b0379c538d75801a8a51c657df67488e53c691750db8514314bd50c53")},
                {384, uint256S("0x5daf4029c5d36f0c4d6290c18cdaeef99dba0b3f354a685b0d2f24e05065fe0d")},
                {385, uint256S("0xccafbd24b26a1f57084db6652b609e5f7a381f8b0da9103d9ff3f6515908d21f")},
                {386, uint256S("0xf85d3a507c7a48154085f74ff5f2d8394a99addd3e8f6857465669726617cf0f")},
                {387, uint256S("0x1ecaf579e749d45fc090ae1ad84727fe14dbccc6d730e43dd3649b488692d373")},
                {388, uint256S("0x05cbb19d429ee186d3ad5b8479b71b0d72f5c56aa4697f4cf4d7e8bab4cffabf")},
                {389, uint256S("0x28450241ab2af4098696273c5b8b3a0e09b88c862ff8dc2bb5c2a1a7c46290de")},
                {390, uint256S("0x57a557e8661d01e4848ce3ab08473e185d9a2d76c3652d2ad68f6a4bfe545b44")},
                {391, uint256S("0xbd808a2b0d958afeee11bcdf506c2613e16f93fac0ea2de6aa2014f25616df47")},
                {392, uint256S("0x5916856b54d09de9c3c68013f981691d84c631b7bb96564d9e6ecf46bf016c78")},
                {393, uint256S("0xb4793adc33ac7da508ff928f049beca54070d5510984cf015271dcbf45c8b415")},
                {394, uint256S("0xa275bdeaac8fa6769f2bc4f5078b938beaeaeb771c6081bd997ab7c7087ff2bd")},
                {395, uint256S("0x41cab0af56fce90dfb4929af7bfa4957ea6f1782f81876d4b71bda13577d9bee")},
                {396, uint256S("0xfadd872b05da31cd37ecd931cd2f87aceac3ebdbd5ce27039e0645bf8308818d")},
                {397, uint256S("0xf8e069866e9aa27acc4d7c1bca03ef4c2ed8ad3c211e031663fab2ff435818a1")},
                {398, uint256S("0x85a1ce34e622c6fa2e59618c79a5190d149b0d45a643b87d0c649c4c85868afa")},
                {399, uint256S("0xb387fd8d2e4c37fd8fb5e5f05b6ee6a369d9f1fbb61a8e757241f151da8256c0")},
                {400, uint256S("0xfb7dfe404bcf6b9a11146dbe9798e24105933810890598e9b4a273acccfdc622")},
                {401, uint256S("0x7f22637112f70c554fb67912d60999c235a9998cb411c207e542887ba33e57de")},
                {402, uint256S("0xc2afb31f70c8dc4323bdf4c7f5d4d94fffeec53a480c18ca262a17f5bcf2a678")},
                {403, uint256S("0xac1fdfb84839d5e2d0dbf8a0659cc83293a70ca5f5b3f768413e6949c5ad2943")},
                {404, uint256S("0x2a6509afc4e74da1ad7a2f93a90c07e372a2e87389b4072c68edbe92ad79b55d")},
                {405, uint256S("0x896361dd11c93c2b6a454b7456befa12a2e735c71cc2e72ab14061d3aa5b9c39")},
                {406, uint256S("0x1dcc1c529073a86eb5add4d474318aff541d3b0553c179f7df7cac50cb323f30")},
                {407, uint256S("0x0d017d594477a75daf641c24d27a1bd663dd857351a04aeb4858c78668eb88b5")},
                {408, uint256S("0x7f82b7dba2f46ff3fb16a48b2a46486460586b627894b559682b0f1e86380474")},
                {409, uint256S("0xa56c83ebc43a76c3d636e91b943752bcbd45a41d9ca8f98f70ea1d60b03454ce")},
                {410, uint256S("0x553094bf92efa3e202ae6c95b6208304ee078dab90a04f7c37945ac56caa41b6")},
                {411, uint256S("0x93ec909c53b7cefff2a7b170196ae0bdc362a00d71778b62f39d00230c0e364b")},
                {412, uint256S("0x3226d1c6bf0c6e2096da8891b80ad5a7ffb9655c0c8c8ce6b3b3dc13e7da1e76")},
                {413, uint256S("0xbeb71812ce84b2fb54dfbb7ad65694febc192ec1266d5f24850990842cb48246")},
                {414, uint256S("0x2e7c9c8f599c3fe47fb06f7022cbc8e7e04d2b080f43717af1a68b37f0ef6e65")},
                {415, uint256S("0x673ecd2a9b2a2a7ce145759359c8f5d53f3d3964098abbff808853101280444c")},
                {416, uint256S("0xbeb0ccfe4203c84be693988ab9bddc56c0e16f73ee8a8d3460837b40978c5767")},
                {417, uint256S("0xaf31c4a36588a3c8d6a80fafb93e1c4e242e8d2f53aeae22688a316c331dec45")},
                {418, uint256S("0x313c82cb19172777bf7763622037b51c93d76fb4f92c282dd50af270c6a8cd4d")},
                {419, uint256S("0xc1f3eae11f231c0726c1a6e77cda1836ccf46bf9a864fe71014bd3647e4d7428")},
                {420, uint256S("0xa4b758553ab20c5f9d8a75fb40209921d647850792a28294666761626f6f6c23")},
                {421, uint256S("0x854da6480b06661c90fb6cfc795e05deb473e04e8cb0c92ff3540500206d9f17")},
                {422, uint256S("0x7adc310f430633ed8b00fcd393efb72304f3197704867c1449fee7182c7bfa76")},
                {423, uint256S("0x5d7f95e38868fed54a0410a887eaa3989cd796107fd8c346a4891a6ed92840ad")},
                {424, uint256S("0xd9a45c2918ec5f133c57fe1a71f8f325f8c6a38c350f4af28884d962f5a9eec5")},
                {425, uint256S("0x34f53e04b4ead785dbf14cc88b017ee6adb644a66e18e2d2fdce904f0f87092c")},
                {426, uint256S("0x8f19088653542880240db461e4796e2bf8f1023b3c485c7501a3043da61b82be")},
                {427, uint256S("0x1e95bdabf3e70295960ecefe098577f470c5dc3765a43f1821d98927605e2e9d")},
                {428, uint256S("0xc25eba1f9e04e6d8e619e31f1296bd39575641f88b5ad774ca3778951788ee84")},
                {429, uint256S("0x9f6d9b1574ec00812f380dc50e1d59fa809b6f47365db1ebaecda10087c38e7e")},
                {430, uint256S("0x4db985559c389ec6d0c0c1404a0617bed0c611470e17294fd1d630a293eca40e")},
                {431, uint256S("0x45b80784bb50eef7e065109eb68c68375ca46fc12f127a24dab18d67543401c2")},
                {432, uint256S("0x29eb6b572aac9d91385fb81218d7c68aa6a4befaac87990b6fc938e3eb6d01e1")},
                {433, uint256S("0x21bdc2d74ecf287fd6d809316a9f6471cb053350f829c7083a503d09952a1ccc")},
                {434, uint256S("0x7dc4508bff0e2df5380ec96c40c4fb1cd07a4cfd1fc19a111ef2a57b38d8eb09")},
                {435, uint256S("0x4e18e2c3dc577a1fae7040e1a47f1d6f44b0ddeb24dd4d239b5087e425dfd94c")},
                {436, uint256S("0xb5f9478069d45da37abf0b7e11fc42c3a3e40407ffd13c0f00fc58dda66487da")},
                {437, uint256S("0x47fa125d60e74416a748917e2b88d187daad94e4b9d96c6ca41e3bc7401241d0")},
                {438, uint256S("0x37fa4bfa847239fe3a743abdc87a3cc4b79b37bbfb9d8caff1041f35c1846854")},
                {439, uint256S("0x1aa18e744b35d098bb74429600fb1b3d36d1f26df15708e578f0200810e6d6d1")},
                {440, uint256S("0x32409dabc58d3c8733a3eacdf04c4a9b74e7974e784e051336a0d9a49a2b98b8")},
                {441, uint256S("0x48cb4bf34ae55b5cf1ed3804473193141f66f861caee98e57fbb6696987f2919")},
                {442, uint256S("0xdddda756b6eb5cf60f4430d791db5c684b884423e33bd184c67074266d10e6b4")},
                {443, uint256S("0x9fb3bb18c1aedb99b153f19ecc30c5caa85739a6d009fae682e2af414a199d25")},
                {444, uint256S("0x88cad8d48c4224b3a38324ba41472993e365cdcc4de90433b756d73023f48d29")},
                {445, uint256S("0xc33b0ea7a3d02d65e133cd4c99c59a8f6fbe48b9a0ea41f95ea9232aef0bb673")},
                {446, uint256S("0x238066e83fa519760cb4dbb433650830ed66c8c8b47ae94bd29ad94811e54b3b")},
                {447, uint256S("0xa3ab24f5ecd850e7f5c49597ec3d0e7963e50b8be7c0cdc88ab2260585fff126")},
                {448, uint256S("0x4b0040f9e77de06d3759f105b9fa31e622b18a0e942f97a5892b07ce7041db12")},
                {449, uint256S("0x09e69d00a7dfaafeca236006db25e25b4028b430bcbae11f6e71c25fe53f795e")},
                {450, uint256S("0x139c8f02594d0fb55f352de79697bf177bcab0c7eca63e6d792802ade681ab4f")},
                {451, uint256S("0x85264f70ea228c4f31dc1872adcba25a222726cf4405180b623468749caa6fc0")},
                {452, uint256S("0x55d076f9cde54bb6632676dfcdfa849245d2b6fad3dcb0952b7e429f44c9cfe9")},
                {453, uint256S("0xdd6816c6080835fb677ea7f9567a1796d87215cf69300bc6297de7f5cde412a5")},
                {454, uint256S("0x6275fe60191b5f396e6f7d823fa4ccffa4d3b04474022736e755ad7bfe04d55d")},
                {455, uint256S("0x98c1ba2f2e1ce103be714ac1e29c963b016ce335bd68a5ec12b4ee8c39523992")},
                {456, uint256S("0x98343726babf349fef3daab37fac685fd969433be1de2864556e0064439ad8bb")},
                {457, uint256S("0x8457be7a31bbcf83159c48962c3f4f6fa8920211a67738c8bd073c336ad01cbd")},
                {458, uint256S("0xece7a7b7c430b9ef3b6d4305db70b4b4791f7ed02597460aee9833efa0ec56d1")},
                {459, uint256S("0xe1ddad21575e599e5cbdfabb4fb8b53db73c4281fff82d1bd6ea44a4ffc1e6b2")},
                {460, uint256S("0x1f95f0a646b2ff3a07127a595b0118ac7459b6afcf55d8ab6714128a53d347b4")},
                {461, uint256S("0x4d68da1704289b4dd3ee3fc00c2f71bce2b89c54773d908783f98f06a5bc5bf3")},
                {462, uint256S("0x1a529b9fea7845853dfcc0eeb183fad5c94fba803dad8bbe91fbdc07c9a0a8f1")},
                {463, uint256S("0x2b0ac16ddb658653f19b68d0eb0c21eaed8f95e9e23f92cec5b5cc81de4496b5")},
                {464, uint256S("0xccd248ace67dfc471ec766a88a87712e9c0d6f9c59caf265d7ffde91d0731d4a")},
                {465, uint256S("0x51dc7c12328445a130b93859f7e92f8b36cbdf9540ac64b5474ce10e25f221a0")},
                {466, uint256S("0x904eb1d904995de58d6fd2a9f8318540467bbfd64eaecf8a8eeba2f12e5f0d25")},
                {467, uint256S("0x39077d89cdb6f5d183fcb8ce12cdf250bc54ca878951a4b6a55aef647c89148a")},
                {468, uint256S("0xf68e53b2937f468fc3dd46ae443910aa5664fdd71b0683b6a8f7d182ed7340ab")},
                {469, uint256S("0x6f2072998e2fabb86604726e41e4eb66ee079eae7165a85addb6ba1956a0540f")},
                {470, uint256S("0xf6634b1f88c0f5bc833371e7036c91a671a00899b8b6b82a71131b516395329a")},
                {471, uint256S("0xab51e28655015e772812b695821333c055b2ed629a02d2f0607ca38fad2e90ea")},
                {472, uint256S("0x45098ad84eb356f488032219ccdae067652b1368b00cb21a9a3ed0e4160dacce")},
                {473, uint256S("0xac4bb31080239af0b60ae7ae52f24670341891d35452f24420d54c881ffce6de")},
                {474, uint256S("0x04a368df09871d3f4f0d55eb4a1b15aa002c2864ecdeed15d2654e1ca545b8b2")},
                {475, uint256S("0x9c74ce54b019d0adb669d51e7cee46df0ac8ae2bc20344f0b2df4bbdb3396693")},
                {476, uint256S("0x77e6d2bad3d3f7e481856c17a363962e5c79ef966902d1c39c39035dd195625e")},
                {477, uint256S("0xe7577dbfc439ccb2c765897355f84664c43fc38a52a12284311051a15b6f01fb")},
                {478, uint256S("0xcfcd20b5e8c0dcc49c68c87c4548bf461df6e6f76854a94eac75bd39474d72cd")},
                {479, uint256S("0xebdd3f102762d14959e486fb2450dab1005d892bd18ce28e134cfcfecd1fc315")},
                {480, uint256S("0x3882673c172c10b2ab8112ac575fb8e47d8d48ba675e47aa2ec60d170f2dd8af")},
                {481, uint256S("0xdfc86cb4fdfe9af806e33493af94a806a860eb438348e9f987f04f933f4d406c")},
                {482, uint256S("0x4d8fcdeb3c2212513507946758c2f32bacd61ee1dbe2d6f465fd736bfdd42899")},
                {483, uint256S("0x7700c247937b0db94ad2bb20e5d2a3ae2e6e1c37d1a71d38f1660ec0aa675e65")},
                {484, uint256S("0xf2945e9e3c4826b65b5db76ff494d22bd2961b8e3f126db93b470cbd3b918f14")},
                {485, uint256S("0xe2aeb9bd60eab83e02725d600302bb43f2d86e85d6db1807c4d7c276ea7e4547")},
                {486, uint256S("0x8fbb68a81387ba783278c182d0c3dae8f63cd89a07ca46cc776bc9cb137e0300")},
                {487, uint256S("0x4066d8c8dd7ac27b9a83f8721ac5736fafd2eea5d4449172f964cc95f4222b07")},
                {488, uint256S("0x15a35f9004d2ac7c1d47ff1593d37a69a8cb7895940266cf0a9a69d9a3fdb456")},
                {489, uint256S("0x9e48c8d4bdacb1751bb5d57921c62b3b83077606c7d1a3078cb09b30312afd68")},
                {490, uint256S("0x8f7118675943b98b59de6501251301f07f51acf1eabfd105e4c9ed92aeffee62")},
                {491, uint256S("0x72b71c0510c7a49b5cc9cf682027490e89c7d156b30ccc2ec10f07c7e9571e39")},
                {492, uint256S("0xd10eebf2ad6e87093543ee9fadea2bcab4a2b26b2074011b0334494833629bab")},
                {493, uint256S("0xbacd10922ba9aea980c78c84e341f030e698f19e2fb239c3c5abc0038032d7d0")},
                {494, uint256S("0x60b26f5452b148ebc8bd79ff9412980f87e799c9b9e9b87a6540713947c6a74d")},
                {495, uint256S("0x5eed6509c2c436b6b4418e9ede8ab022be95bb785aef4b9d54f7de3fcc901039")},
                {496, uint256S("0x2ddcc0a48f4f959e70922f5af9d3bf33461a86c2ab813e67e79191a54510a8bf")},
                {497, uint256S("0x543e2c91b24ef54e6ad6efa6767f1a87ff5c7ecd1e7d0842718bf019ceca76fc")},
                {498, uint256S("0xefb83964f72f32dc1daa0e969f325bdd7eed0f466ac13635dcdcc4011b4b04f8")},
                {499, uint256S("0x0fb22109c070733832f438b3511093c4581251a3a4937508d79e6dc605086dbc")},
                {500, uint256S("0x7bc52a2e188cfce4e473070998bc0066e226e4a016bbf576a6d2ac167dd389a2")},
            }
        };

        m_assumeutxo_data = {
            // TODO to be specified in a future patch.
        };

        chainTxData = ChainTxData{
            // CodexaCoin: zeroed, no real chain exists yet (PARAMETERS.md instruction)
            .nTime    = 0,
            .nTxCount = 0,
            .dTxRate  = 0,
        };

        // CodexaCoin: no dev fund address generated yet -- TODO before
        // mainnet launch. Left empty (dev fund donation feature stays
        // disabled by default; see wallet/staking.cpp isDevFundEnabled).
        vDevFundAddress = {};
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
        consensus.CSVHeight = 0; // CodexaCoin: fresh chain, active from genesis
        consensus.SegwitHeight = 0; // CodexaCoin: fresh chain, active from genesis
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
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].nStartTime = Consensus::BIP9Deployment::NEVER_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].min_activation_height = 0; // No activation delay

        // Deployment of Taproot (BIPs 340-342)
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].bit = 2;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nStartTime = Consensus::BIP9Deployment::NEVER_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].min_activation_height = 0; // No activation delay

        consensus.nProtocolV1RetargetingFixedTime = 1395631999;
        consensus.nProtocolV2Time = 1407053625;
        consensus.nProtocolV3Time = 1444028400;
        consensus.nProtocolV3_1Time = 1667779200;
        consensus.nLastPOWBlock = 500; // CodexaCoin: founder premine window (mirrors mainnet), see PARAMETERS.md section 5
        consensus.nStakeTimestampMask = 0xf;
        consensus.nCoinbaseMaturity = 10; // Fast maturity for testing; window (500) stays >= this, so no staking-eligibility gap (see PARAMETERS.md section 5.2)

        consensus.nPremineTotal = CAmount{14000000000} * COIN; // CodexaCoin: mirrors mainnet for test parity; testnet coins are worthless
        consensus.nStakeRewardAnnualBP = 1368;
        consensus.nStakeRewardAgeCapSeconds = 60 * 24 * 60 * 60; // 60 days

        consensus.nMinimumChainWork = uint256{};
        consensus.defaultAssumeValid = uint256{};

        pchMessageStart[0] = 0xc1;
        pchMessageStart[1] = 0x02;
        pchMessageStart[2] = 0x7e;
        pchMessageStart[3] = 0x3b;
        nDefaultPort = 26210;
        m_assumed_blockchain_size = 1;

        // CodexaCoin: genesis mined by contrib/genesis/generate_genesis.cpp.
        genesis = CreateGenesisBlock(1785326400, 73100, 0x1f00ffff, 7, 0);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256S("0x719ff8d5c4773340ff014d12c0bbc623aa6fc2abc2b4ecd6dc7e93ef4f609b95"));
        assert(genesis.hashMerkleRoot == uint256S("0x089c9664d716a35a805093b15b0dd6e9f58e84ca21a176c2783a377d23ef6b22"));

        // Note that of those which support the service bits prefix, most only support a subset of
        // possible options.
        // This is fine at runtime as we'll fall back to using them as an addrfetch if they don't support the
        // service bits we want, but we should get them updated to support all service bits wanted by any
        // release ASAP to avoid it where possible.
        // CodexaCoin: TODO placeholders -- see PARAMETERS.md section 9 / Phase 2.
        vSeeds.emplace_back("testnet-seed1.codexacoin.example"); // TODO: stand up real testnet seed node
        vSeeds.emplace_back("testnet-seed2.codexacoin.example"); // TODO: stand up real testnet seed node

        base58Prefixes[PUBKEY_ADDRESS] = std::vector<unsigned char>(1,111);
        base58Prefixes[SCRIPT_ADDRESS] = std::vector<unsigned char>(1,196);
        base58Prefixes[SECRET_KEY] =     std::vector<unsigned char>(1,239);
        // CodexaCoin-specific BIP32 version bytes, shared across all
        // non-mainnet networks (see the CMainParams comment above).
        base58Prefixes[EXT_PUBLIC_KEY] = {0x39, 0x86, 0x00, 0x00};
        base58Prefixes[EXT_SECRET_KEY] = {0x39, 0x84, 0x00, 0x00};

        bech32_hrp = "tcac";

        // CodexaCoin: no fixed-seed IP list exists yet.
        vFixedSeeds.clear();

        fDefaultConsistencyChecks = false;
        m_is_mockable_chain = false;

        // CodexaCoin: fresh chain -- checkpoints reset to genesis only.
        checkpointData = {
            {
                {0, consensus.hashGenesisBlock},
            }
        };

        m_assumeutxo_data = {
            // TODO to be specified in a future patch.
        };

        chainTxData = ChainTxData{
            // CodexaCoin: zeroed, no real chain exists yet
            .nTime    = 0,
            .nTxCount = 0,
            .dTxRate  = 0,
        };

        // CodexaCoin: no dev fund address generated yet -- TODO before testnet launch.
        vDevFundAddress = {};
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

        // Activation of Taproot (BIPs 340-342)
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].bit = 2;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nStartTime = Consensus::BIP9Deployment::NEVER_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].min_activation_height = 0; // No activation delay

        consensus.nProtocolV1RetargetingFixedTime = 1707168541;
        consensus.nProtocolV2Time = 1707168542;
        consensus.nProtocolV3Time = 1707168543;
        consensus.nProtocolV3_1Time = 1707168544;
        consensus.nLastPOWBlock = 0x7fffffff; // CodexaCoin: no premine window on signet
        consensus.nStakeTimestampMask = 0xf;
        consensus.nCoinbaseMaturity = 10;

        consensus.nPremineTotal = 0;
        consensus.nStakeRewardAnnualBP = 1368;
        consensus.nStakeRewardAgeCapSeconds = 60 * 24 * 60 * 60; // 60 days

        // message start is defined as the first 4 bytes of the sha256d of the block script
        HashWriter h{};
        h << consensus.signet_challenge;
        uint256 hash = h.GetHash();
        std::copy_n(hash.begin(), 4, pchMessageStart.begin());

        nDefaultPort = 46210;

        // CodexaCoin: genesis mined by contrib/genesis/generate_genesis.cpp.
        // Same (nTime, nBits) as testnet by choice -- not consensus-relevant
        // since magic bytes/ports keep the networks from ever interoperating,
        // but noted in PARAMETERS.md as a minor cosmetic overlap.
        genesis = CreateGenesisBlock(1785326400, 73100, 0x1f00ffff, 7, 0);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256S("0x719ff8d5c4773340ff014d12c0bbc623aa6fc2abc2b4ecd6dc7e93ef4f609b95"));
        assert(genesis.hashMerkleRoot == uint256S("0x089c9664d716a35a805093b15b0dd6e9f58e84ca21a176c2783a377d23ef6b22"));

        vFixedSeeds.clear();

        m_assumeutxo_data = {};

        base58Prefixes[PUBKEY_ADDRESS] = std::vector<unsigned char>(1,111);
        base58Prefixes[SCRIPT_ADDRESS] = std::vector<unsigned char>(1,196);
        base58Prefixes[SECRET_KEY] =     std::vector<unsigned char>(1,239);
        // CodexaCoin-specific BIP32 version bytes, shared across all
        // non-mainnet networks (see the CMainParams comment above).
        base58Prefixes[EXT_PUBLIC_KEY] = {0x39, 0x86, 0x00, 0x00};
        base58Prefixes[EXT_SECRET_KEY] = {0x39, 0x84, 0x00, 0x00};

        bech32_hrp = "tcac";

        fDefaultConsistencyChecks = false;
        m_is_mockable_chain = false;

        vDevFundAddress = {};
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
        consensus.nTargetSpacing = 64;
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
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].nTimeout = 0;
        consensus.vDeployments[Consensus::DEPLOYMENT_SEGWIT].min_activation_height = 0; // No activation delay

        // Deployment of Taproot (BIPs 340-342)
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].bit = 2;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nStartTime = Consensus::BIP9Deployment::NEVER_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].min_activation_height = 0; // No activation delay

        consensus.nProtocolV1RetargetingFixedTime = 1395631999;
        consensus.nProtocolV2Time = 1407053625;
        consensus.nProtocolV3Time = 1444028400;
        consensus.nProtocolV3_1Time = 1713938400;
        // CodexaCoin: founder premine window enabled on regtest too (unlike
        // upstream Blackcoin's regtest, which never leaves PoW) so the
        // premine + coin-age PoS reward path can actually be exercised
        // end-to-end in tests. See PARAMETERS.md section 5.
        consensus.nLastPOWBlock = 500;
        consensus.nStakeTimestampMask = 0xf;
        consensus.nCoinbaseMaturity = 10;

        consensus.nPremineTotal = CAmount{14000000000} * COIN;
        consensus.nStakeRewardAnnualBP = 1368;
        consensus.nStakeRewardAgeCapSeconds = 60 * 24 * 60 * 60; // 60 days

        consensus.nMinimumChainWork = uint256{};
        consensus.defaultAssumeValid = uint256{};

        pchMessageStart[0] = 0x17;
        pchMessageStart[1] = 0xe4;
        pchMessageStart[2] = 0xb9;
        pchMessageStart[3] = 0x4c;
        nDefaultPort = 36210;
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

        // CodexaCoin: genesis mined by contrib/genesis/generate_genesis.cpp
        // (trivial on regtest's near-maximal powLimit -- nonce=1).
        genesis = CreateGenesisBlock(1785326400, 1, 0x207fffff, 7, 0);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256S("0x66a3b7f4db8f62053c717aab1d5ff9fa8cfed4f7b27f2583b438ee8f4c9c12d1"));
        assert(genesis.hashMerkleRoot == uint256S("0x089c9664d716a35a805093b15b0dd6e9f58e84ca21a176c2783a377d23ef6b22"));

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
            // CodexaCoin: Blackcoin's regtest assumeutxo snapshot hashes are
            // meaningless for a different genesis/chain; cleared pending
            // CAC-specific regeneration if assumeutxo functional tests are
            // exercised (test/functional/feature_assumeutxo.py).
        };

        chainTxData = ChainTxData{
            0,
            0,
            0
        };

        base58Prefixes[PUBKEY_ADDRESS] = std::vector<unsigned char>(1,111);
        base58Prefixes[SCRIPT_ADDRESS] = std::vector<unsigned char>(1,196);
        base58Prefixes[SECRET_KEY] = std::vector<unsigned char>(1,239);
        // CodexaCoin-specific BIP32 version bytes, shared across all
        // non-mainnet networks (see the CMainParams comment above).
        base58Prefixes[EXT_PUBLIC_KEY] = {0x39, 0x86, 0x00, 0x00};
        base58Prefixes[EXT_SECRET_KEY] = {0x39, 0x84, 0x00, 0x00};

        bech32_hrp = "cacrt";

        vDevFundAddress = {};
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
