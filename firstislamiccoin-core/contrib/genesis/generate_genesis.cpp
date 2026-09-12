// CodexaCoin genesis-mining tool.
//
// Reuses kernel::FindGenesisBlock() (see src/kernel/chainparams.cpp), which
// calls the exact same CreateGenesisBlock() every CChainParams subclass
// already uses -- so this tool cannot silently disagree with the real node
// about what the genesis block for a given (nTime, nBits, nVersion, reward)
// actually is. It only brute-forces nNonce and prints the result; nothing
// about block/transaction serialization is reimplemented here.
//
// Not wired into the autotools build (Makefile.am) as a shipped binary --
// it's a one-off tool run during parameter finalization, then its output is
// pasted into kernel/chainparams.cpp. Build manually after the main build:
//
//   c++ -std=c++20 -I src -I src/config $(pkg-config --cflags libevent) \
//       contrib/genesis/generate_genesis.cpp \
//       src/kernel/libbitcoinkernel-*.a ...  (see contrib/genesis/README.md)
//
// Usage: generate_genesis <network> <nTime> <nBits-hex>
//   network: mainnet | testnet | regtest | signet   (only used for the printed label)

#include <kernel/chainparams.h>
#include <consensus/amount.h>
#include <util/strencodings.h>
#include <util/translation.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

const std::function<std::string(const char*)> G_TRANSLATION_FUN = nullptr;

int main(int argc, char** argv)
{
    if (argc != 4) {
        std::fprintf(stderr, "Usage: %s <network-label> <nTime> <nBits-hex>\n", argv[0]);
        std::fprintf(stderr, "Example: %s mainnet 1785456000 1e0fffff\n", argv[0]);
        return 1;
    }

    const std::string label = argv[1];
    const uint32_t nTime = static_cast<uint32_t>(std::strtoul(argv[2], nullptr, 10));
    const uint32_t nBits = static_cast<uint32_t>(std::strtoul(argv[3], nullptr, 16));
    // CodexaCoin: must be 7, not Bitcoin-derived default of 1 -- see
    // PARAMETERS.md section 8 (CheckBlockHeader rejects nVersion < 7 once
    // IsProtocolV2() is true, which it is for any 2026 genesis timestamp
    // given Blackcoin's inherited protocol-version thresholds are all ~2014-2024).
    const int32_t nVersion = 7;
    const CAmount genesisReward = 0;

    std::printf("Mining genesis for %s: nTime=%u nBits=0x%08x ...\n", label.c_str(), nTime, nBits);

    uint32_t nNonce = 0;
    CBlock genesis = FindGenesisBlock(nTime, nBits, nVersion, genesisReward, nNonce);

    std::printf("  nTime          = %u\n", nTime);
    std::printf("  nNonce         = %u\n", nNonce);
    std::printf("  nBits          = 0x%08x\n", nBits);
    std::printf("  hashGenesisBlock = 0x%s\n", genesis.GetHash().ToString().c_str());
    std::printf("  hashMerkleRoot   = 0x%s\n", genesis.hashMerkleRoot.ToString().c_str());
    std::printf("\n  genesis = CreateGenesisBlock(%uu, %uu, 0x%08x, 1, 0);\n", nTime, nNonce, nBits);
    std::printf("  consensus.hashGenesisBlock = genesis.GetHash();\n");
    std::printf("  assert(consensus.hashGenesisBlock == uint256S(\"0x%s\"));\n", genesis.GetHash().ToString().c_str());
    std::printf("  assert(genesis.hashMerkleRoot == uint256S(\"0x%s\"));\n", genesis.hashMerkleRoot.ToString().c_str());

    return 0;
}
