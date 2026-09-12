// Copyright (c) 2014-2023 The Blackcoin developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef FIRSTISLAMICCOIN_WALLET_RPC_STAKING_H
#define FIRSTISLAMICCOIN_WALLET_RPC_STAKING_H

#include <span.h>

class CRPCCommand;

namespace wallet {
Span<const CRPCCommand> GetStakingRPCCommands();
} // namespace wallet

#endif // FIRSTISLAMICCOIN_WALLET_RPC_STAKING_H
