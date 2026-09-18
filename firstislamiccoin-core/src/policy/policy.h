// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2022 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOIN_POLICY_POLICY_H
#define BITCOIN_POLICY_POLICY_H

#include <consensus/amount.h>
#include <consensus/consensus.h>
#include <primitives/transaction.h>
#include <script/interpreter.h>
#include <script/solver.h>

#include <cstdint>
#include <string>

class CCoinsViewCache;
class CFeeRate;
class CScript;

/** Default for -blockmaxweight, which controls the range of block weights the mining code will create **/
static constexpr unsigned int DEFAULT_BLOCK_MAX_WEIGHT{MAX_BLOCK_WEIGHT - 4000};
/** Default for -blockmintxfee, which sets the minimum feerate for a transaction in blocks created by mining code **/
static constexpr unsigned int DEFAULT_BLOCK_MIN_TX_FEE{100000};
/** The maximum weight for transactions we're willing to relay/mine */
static constexpr int32_t MAX_STANDARD_TX_WEIGHT{400000};
/** The minimum non-witness size for transactions we're willing to relay/mine: one larger than 64  */
static constexpr unsigned int MIN_STANDARD_TX_NONWITNESS_SIZE{65};
/** Maximum number of signature check operations in an IsStandard() P2SH script */
static constexpr unsigned int MAX_P2SH_SIGOPS{15};
/** The maximum number of sigops we're willing to relay/mine in a single tx */
static constexpr unsigned int MAX_STANDARD_TX_SIGOPS_COST{MAX_BLOCK_SIGOPS_COST/5};
/** Default for -bytespersigop */
static constexpr unsigned int DEFAULT_BYTES_PER_SIGOP{20};
/** Default for -permitbaremultisig */
static constexpr bool DEFAULT_PERMIT_BAREMULTISIG{true};
/** The maximum number of witness stack items in a standard P2WSH script */
static constexpr unsigned int MAX_STANDARD_P2WSH_STACK_ITEMS{100};
/** The maximum size in bytes of each witness stack item in a standard P2WSH script */
static constexpr unsigned int MAX_STANDARD_P2WSH_STACK_ITEM_SIZE{80};
/** The maximum size in bytes of each witness stack item in a standard BIP 342 script (Taproot, leaf version 0xc0) */
static constexpr unsigned int MAX_STANDARD_TAPSCRIPT_STACK_ITEM_SIZE{80};
/** The maximum size in bytes of a standard witnessScript */
static constexpr unsigned int MAX_STANDARD_P2WSH_SCRIPT_SIZE{3600};
/** The maximum size of a standard ScriptSig */
static constexpr unsigned int MAX_STANDARD_SCRIPTSIG_SIZE{1650};
/** The maximum size in bytes of witness input stack items */
static const unsigned int MAX_STANDARD_WITNESS_SIZE{100000};
/** Min feerate for defining dust.
 * Changing the dust limit changes which transactions are
 * standard and should be done with care and ideally rarely. It makes sense to
 * only increase the dust limit after prior releases were already not creating
 * outputs below the new threshold */
static constexpr unsigned int DUST_RELAY_TX_FEE{100000};
/** Default for -minrelaytxfee, minimum relay fee for transactions */
static constexpr unsigned int DEFAULT_MIN_RELAY_TX_FEE{100000};
/** Default for -limitancestorcount, max number of in-mempool ancestors */
static constexpr unsigned int DEFAULT_ANCESTOR_LIMIT{25};
/** Default for -limitancestorsize, maximum kilobytes of tx + all in-mempool ancestors */
static constexpr unsigned int DEFAULT_ANCESTOR_SIZE_LIMIT_KVB{101};
/** Default for -limitdescendantcount, max number of in-mempool descendants */
static constexpr unsigned int DEFAULT_DESCENDANT_LIMIT{25};
/** Default for -limitdescendantsize, maximum kilobytes of in-mempool descendants */
static constexpr unsigned int DEFAULT_DESCENDANT_SIZE_LIMIT_KVB{101};
/** Default for -datacarrier */
static const bool DEFAULT_ACCEPT_DATACARRIER = true;
/**
 * Default setting for -datacarriersize. 220 bytes of data, +1 for OP_RETURN,
 * +2 for the pushdata opcodes.
 */
static const unsigned int MAX_OP_RETURN_RELAY = 223;
/**
 * An extra transaction can be added to a package, as long as it only has one
 * ancestor and is no larger than this. Not really any reason to make this
 * configurable as it doesn't materially change DoS parameters.
 */
static constexpr unsigned int EXTRA_DESCENDANT_TX_SIZE_LIMIT{10000};


/**
 * Mandatory script verification flags that all new transactions must comply with for
 * them to be valid. Failing one of these tests may trigger a DoS ban;
 * see CheckInputScripts() for details.
 *
 * Note that this does not affect consensus validity; see GetBlockScriptFlags()
 * for that.
 */
// FirstIslamicCoin: CHECKSEQUENCEVERIFY, WITNESS and TAPROOT added --
// inherited from an older Bitcoin Core snapshot (via the CodexaCoin import)
// that predates upstream promoting CHECKSEQUENCEVERIFY from
// standardness-only to mandatory once permanently active (confirmed needed:
// feature_csv_activation.py expects a negative-locktime CSV violation to be
// treated as ban-worthy), and that was simply missing WITNESS and TAPROOT
// outright (current upstream Bitcoin Core's MANDATORY_SCRIPT_VERIFY_FLAGS
// includes both; this fork's inherited snapshot predates that).
//
// Without WITNESS/TAPROOT here, CheckInputScripts()'s "was this only a
// standard-but-not-mandatory-flag failure?" fallback (validation.cpp) treats
// ANY genuine witness/taproot consensus failure as though it would also fail
// without that flag -- which trivially "succeeds" instead, since witness and
// taproot verification both short-circuit to success when their flag is
// absent (see the SCRIPT_VERIFY_TAPROOT comment in the
// STANDARD_SCRIPT_VERIFY_FLAGS block below) -- and so mis-reports it as
// TX_NOT_STANDARD ("non-mandatory-script-verify-flag") instead of
// TX_CONSENSUS with the actual error. This isn't merely cosmetic: it also
// feeds the P2P DoS-ban logic (TX_CONSENSUS is ban-worthy, TX_NOT_STANDARD
// isn't). GetBlockScriptFlags() always includes WITNESS once segwit is
// active (which, on this fork, is from genesis), so ConnectBlock's flags
// (used for actual block consensus validation, independent of this list)
// virtually always overlap with WITNESS -- meaning without it here, this
// mis-wrapping wasn't taproot-specific at all, it would happen for *any*
// genuine consensus script failure hit via submitblock under -par=1 (the
// single-threaded/synchronous script-check path). Confirmed via
// feature_taproot.py's test_spenders phase (submitblock's error for a bad
// Schnorr signature hashtype came back as generic
// "non-mandatory-script-verify-flag (...)" instead of "Invalid Schnorr
// signature hash type", first with TAPROOT missing here, then again --
// merely with a different offending bit -- with WITNESS still missing).
//
// TAPROOT and WITNESS were previously handled inconsistently: TAPROOT was
// simply never added (predating this file's FIC-specific history entirely),
// while WITNESS was added once, then deliberately reverted specifically
// because p2p_orphan_handling.py's witness-stripped-relay scenario appeared
// to need it excluded to avoid banning the relaying peer. That reasoning
// didn't hold up: PolicyScriptChecks() (validation.cpp) has its own
// dedicated `!tx.HasWitness()` re-check, independent of this list, that
// reclassifies a pure witness-stripped rejection as TX_WITNESS_STRIPPED, and
// net_processing.cpp explicitly exempts TX_WITNESS_STRIPPED from ban-scoring
// regardless of whether WITNESS is MANDATORY here -- confirmed by rerunning
// p2p_orphan_handling.py after this change; it still passes.
static constexpr unsigned int MANDATORY_SCRIPT_VERIFY_FLAGS{SCRIPT_VERIFY_P2SH |
                                                             SCRIPT_VERIFY_DERKEY |
                                                             SCRIPT_VERIFY_DERSIG |
                                                             SCRIPT_VERIFY_LOW_S |
                                                             SCRIPT_VERIFY_NULLDUMMY |
                                                             SCRIPT_VERIFY_CHECKLOCKTIMEVERIFY |
                                                             SCRIPT_VERIFY_CHECKSEQUENCEVERIFY |
                                                             SCRIPT_VERIFY_WITNESS |
                                                             SCRIPT_VERIFY_TAPROOT};

/**
 * Standard script verification flags that standard transactions will comply
 * with. However we do not ban/disconnect nodes that forward txs violating
 * the additional (non-mandatory) rules here, to improve forwards and
 * backwards compatability.
 */
// FirstIslamicCoin: SCRIPT_VERIFY_TAPROOT added -- this list already had the
// taproot-adjacent DISCOURAGE_UPGRADABLE_TAPROOT_VERSION/DISCOURAGE_OP_SUCCESS
// flags but was missing the base SCRIPT_VERIFY_TAPROOT gate itself (inherited
// unmodified from the CodexaCoin import). Without it, interpreter.cpp's taproot
// witness verification short-circuits to an automatic pass
// (`if (!(flags & SCRIPT_VERIFY_TAPROOT)) return set_success(...)`) during
// PolicyScriptChecks (mempool/relay-time validation), so any witness
// targeting a taproot output -- including ones using unknown leaf versions or
// OP_SUCCESS opcodes that should be rejected as non-standard -- was silently
// accepted into the mempool. Block consensus validity was never affected:
// GetBlockScriptFlags() already adds SCRIPT_VERIFY_TAPROOT independently for
// block connection. Confirmed via feature_taproot.py's test_spenders phase
// (an unkver/bigpush spender expected to be rejected with -26 non-standard
// was instead accepted).
static constexpr unsigned int STANDARD_SCRIPT_VERIFY_FLAGS{MANDATORY_SCRIPT_VERIFY_FLAGS |
                                                             SCRIPT_VERIFY_STRICTENC |
                                                             SCRIPT_VERIFY_MINIMALDATA |
                                                             SCRIPT_VERIFY_DISCOURAGE_UPGRADABLE_NOPS |
                                                             SCRIPT_VERIFY_CLEANSTACK |
                                                             SCRIPT_VERIFY_MINIMALIF |
                                                             SCRIPT_VERIFY_NULLFAIL |
                                                             SCRIPT_VERIFY_CHECKSEQUENCEVERIFY |
                                                             SCRIPT_VERIFY_WITNESS |
                                                             SCRIPT_VERIFY_DISCOURAGE_UPGRADABLE_WITNESS_PROGRAM |
                                                             SCRIPT_VERIFY_WITNESS_PUBKEYTYPE |
                                                             SCRIPT_VERIFY_CONST_SCRIPTCODE |
                                                             SCRIPT_VERIFY_TAPROOT |
                                                             SCRIPT_VERIFY_DISCOURAGE_UPGRADABLE_TAPROOT_VERSION |
                                                             SCRIPT_VERIFY_DISCOURAGE_OP_SUCCESS |
                                                             SCRIPT_VERIFY_DISCOURAGE_UPGRADABLE_PUBKEYTYPE};

/** For convenience, standard but not mandatory verify flags. */
static constexpr unsigned int STANDARD_NOT_MANDATORY_VERIFY_FLAGS{STANDARD_SCRIPT_VERIFY_FLAGS & ~MANDATORY_SCRIPT_VERIFY_FLAGS};

/** Used as the flags parameter to sequence and nLocktime checks in non-consensus code. */
static constexpr unsigned int STANDARD_LOCKTIME_VERIFY_FLAGS{LOCKTIME_VERIFY_SEQUENCE};

CAmount GetDustThreshold(const CTxOut& txout, const CFeeRate& dustRelayFee);

bool IsDust(const CTxOut& txout, const CFeeRate& dustRelayFee);

bool IsStandard(const CScript& scriptPubKey, const std::optional<unsigned>& max_datacarrier_bytes, TxoutType& whichType, const bool witnessEnabled = false);


// Changing the default transaction version requires a two step process: first
// adapting relay policy by bumping TX_MAX_STANDARD_VERSION, and then later
// allowing the new transaction version in the wallet/RPC.
static constexpr decltype(CTransaction::nVersion) TX_MAX_STANDARD_VERSION{2};

/**
* Check for standard transaction types
* @return True if all outputs (scriptPubKeys) use only standard transaction forms
*/
bool IsStandardTx(const CTransaction& tx, const std::optional<unsigned>& max_datacarrier_bytes, bool permit_bare_multisig, const CFeeRate& dust_relay_fee, std::string& reason, const bool witnessEnabled = false);
/**
* Check for standard transaction types
* @param[in] mapInputs       Map of previous transactions that have outputs we're spending
* @return True if all inputs (scriptSigs) use only standard transaction forms
*/
bool AreInputsStandard(const CTransaction& tx, const CCoinsViewCache& mapInputs);
/**
* Check if the transaction is over standard P2WSH resources limit:
* 3600bytes witnessScript size, 80bytes per witness stack element, 100 witness stack elements
* These limits are adequate for multisignatures up to n-of-100 using OP_CHECKSIG, OP_ADD, and OP_EQUAL.
*
* Also enforce a maximum stack item size limit and no annexes for tapscript spends.
*/
bool IsWitnessStandard(const CTransaction& tx, const CCoinsViewCache& mapInputs);

/** Compute the virtual transaction size (weight reinterpreted as bytes). */
int64_t GetVirtualTransactionSize(int64_t nWeight, int64_t nSigOpCost, unsigned int bytes_per_sigop);
int64_t GetVirtualTransactionSize(const CTransaction& tx, int64_t nSigOpCost, unsigned int bytes_per_sigop);
int64_t GetVirtualTransactionInputSize(const CTxIn& tx, int64_t nSigOpCost, unsigned int bytes_per_sigop);

static inline int64_t GetVirtualTransactionSize(const CTransaction& tx)
{
    return GetVirtualTransactionSize(tx, 0, 0);
}

static inline int64_t GetVirtualTransactionInputSize(const CTxIn& tx)
{
    return GetVirtualTransactionInputSize(tx, 0, 0);
}

#endif // BITCOIN_POLICY_POLICY_H
