// Copyright (c) 2010 Satoshi Nakamoto
// Copyright (c) 2009-2022 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <core_io.h>
#include <policy/feerate.h>
#include <policy/fees.h>
#include <rpc/protocol.h>
#include <rpc/request.h>
#include <rpc/server.h>
#include <rpc/server_util.h>
#include <rpc/util.h>
#include <txmempool.h>
#include <univalue.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <string>

namespace node {
struct NodeContext;
}

using node::NodeContext;

void RegisterFeeRPCCommands(CRPCTable& t)
{
    // No fee-estimation RPCs are registered here: FirstIslamicCoin has no
    // dynamic/smart fee estimator (see GetMinFee() in consensus/tx_verify.cpp
    // -- a flat, deterministic minimum fee replaces it), so estimatesmartfee
    // was dropped rather than left pointing at a mempool-based estimate this
    // chain doesn't compute. Kept as a no-op function since rpc/register.h
    // still calls it unconditionally alongside every other category.
    (void)t;
}
