// FirstIslamicCoin web wallet crypto layer.
//
// Mirrors firstislamiccoin-mobile/lib/crypto/{address,keys,transaction}.dart
// exactly (same algorithms, same byte layouts) so the web and mobile
// wallets are interchangeable -- a recovery phrase created on one restores
// identically on the other. Uses the noble/scure crypto libraries
// (dependency-free, browser-native, no Buffer polyfill needed, no bundler
// required) rather than a general-purpose Bitcoin library, for the same
// reason address.dart gives for hand-rolling: checkable against the real
// ground-truth values in docs/genesis.md and firstislamiccoin-core's own
// chainparams.cpp, not hidden behind a library's own address-encoding
// assumptions.
import * as bip39 from "https://cdn.jsdelivr.net/npm/@scure/bip39@1.3.0/+esm";
import { wordlist } from "https://cdn.jsdelivr.net/npm/@scure/bip39@1.3.0/wordlists/english/+esm";
import { HDKey } from "https://cdn.jsdelivr.net/npm/@scure/bip32@1.4.0/+esm";
import * as secp from "https://cdn.jsdelivr.net/npm/@noble/secp256k1@2.1.0/+esm";
import { sha256 } from "https://cdn.jsdelivr.net/npm/@noble/hashes@1.4.0/sha256/+esm";
import { ripemd160 } from "https://cdn.jsdelivr.net/npm/@noble/hashes@1.4.0/ripemd160/+esm";
import { hmac } from "https://cdn.jsdelivr.net/npm/@noble/hashes@1.4.0/hmac/+esm";

secp.etc.hmacSha256Sync = (key, ...msgs) => hmac(sha256, key, secp.etc.concatBytes(...msgs));

const B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

// bip32Versions: the conventional BIP32 extended-key version bytes
// (mainnet/testnet Bitcoin's own), used purely as a well-known
// serialization container for this wallet's own account xpub -- see
// deriveAccountXpub/deriveXpubAddress below. Not a claim of interop
// with generic Bitcoin tooling (FIC's own p2pkhVersion is what actually
// gets applied when deriving an address from one of these xpubs).
//
// bip44CoinType is 9770 on BOTH networks -- unlike most coins (and unlike
// CAC, which followed SLIP-44 convention and used testnet index 1), FIC's
// own chainparams work established 9770 uniformly; see
// docs/CHANGELOG-FIC.md and firstislamiccoin-mobile/lib/config/network_config.dart.
export const NETWORKS = {
  mainnet: {
    p2pkhVersion: 36, p2shVersion: 28, wifVersion: 164, bech32Hrp: "fic", bip44CoinType: 9770,
    bip32Versions: { private: 0x0488ade4, public: 0x0488b21e },
  },
  testnet: {
    p2pkhVersion: 111, p2shVersion: 196, wifVersion: 239, bech32Hrp: "tfic", bip44CoinType: 9770,
    bip32Versions: { private: 0x04358394, public: 0x043587cf },
  },
};

function bytesToHex(bytes) {
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function hexToBytes(hex) {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
  return out;
}

function doubleSha256(bytes) {
  return sha256(sha256(bytes));
}

export function hash160(bytes) {
  return ripemd160(sha256(bytes));
}

function base58checkEncode(payload) {
  const checksum = doubleSha256(payload).slice(0, 4);
  const full = new Uint8Array(payload.length + 4);
  full.set(payload);
  full.set(checksum, payload.length);
  let leadingZeros = 0;
  while (leadingZeros < full.length && full[leadingZeros] === 0) leadingZeros++;
  let num = 0n;
  for (const b of full) num = num * 256n + BigInt(b);
  let out = "";
  while (num > 0n) {
    const rem = num % 58n;
    num /= 58n;
    out = B58_ALPHABET[Number(rem)] + out;
  }
  return "1".repeat(leadingZeros) + out;
}

function base58checkDecode(str) {
  let num = 0n;
  for (const ch of str) {
    const idx = B58_ALPHABET.indexOf(ch);
    if (idx < 0) throw new Error("Invalid base58 character");
    num = num * 58n + BigInt(idx);
  }
  let bytes = [];
  while (num > 0n) {
    bytes.unshift(Number(num % 256n));
    num /= 256n;
  }
  let leadingZeros = 0;
  while (leadingZeros < str.length && str[leadingZeros] === "1") leadingZeros++;
  const full = new Uint8Array(leadingZeros + bytes.length);
  full.set(bytes, leadingZeros);
  const payload = full.slice(0, full.length - 4);
  const checksum = full.slice(full.length - 4);
  const expected = doubleSha256(payload).slice(0, 4);
  if (!expected.every((b, i) => b === checksum[i])) throw new Error("Bad checksum");
  return payload;
}

// -- bech32, per BIP173 --
const BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l";
function bech32Polymod(values) {
  const GEN = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3];
  let chk = 1;
  for (const v of values) {
    const top = chk >>> 25;
    chk = ((chk & 0x1ffffff) << 5) ^ v;
    for (let i = 0; i < 5; i++) if ((top >>> i) & 1) chk ^= GEN[i];
  }
  return chk;
}
function bech32HrpExpand(hrp) {
  const out = [];
  for (const c of hrp) out.push(c.charCodeAt(0) >>> 5);
  out.push(0);
  for (const c of hrp) out.push(c.charCodeAt(0) & 31);
  return out;
}
function bech32CreateChecksum(hrp, data) {
  const values = bech32HrpExpand(hrp).concat(data).concat([0, 0, 0, 0, 0, 0]);
  const mod = bech32Polymod(values) ^ 1;
  const ret = [];
  for (let p = 0; p < 6; p++) ret.push((mod >>> (5 * (5 - p))) & 31);
  return ret;
}
function convertBits(data, fromBits, toBits, pad) {
  let acc = 0, bits = 0;
  const ret = [];
  const maxv = (1 << toBits) - 1;
  for (const value of data) {
    if (value < 0 || value >> fromBits !== 0) throw new Error("Invalid data for bit conversion");
    acc = (acc << fromBits) | value;
    bits += fromBits;
    while (bits >= toBits) {
      bits -= toBits;
      ret.push((acc >>> bits) & maxv);
    }
  }
  if (pad) {
    if (bits > 0) ret.push((acc << (toBits - bits)) & maxv);
  } else if (bits >= fromBits || ((acc << (toBits - bits)) & maxv) !== 0) {
    throw new Error("Invalid padding in bit conversion");
  }
  return ret;
}
function bech32Encode(hrp, data) {
  const combined = data.concat(bech32CreateChecksum(hrp, data));
  return hrp + "1" + combined.map((d) => BECH32_CHARSET[d]).join("");
}
function bech32Decode(bech) {
  const pos = bech.lastIndexOf("1");
  const hrp = bech.slice(0, pos);
  const data = [];
  for (const c of bech.slice(pos + 1, -6)) data.push(BECH32_CHARSET.indexOf(c));
  return { hrp, data };
}

export function p2pkhAddress(pubkeyHash20, network) {
  const payload = new Uint8Array(21);
  payload[0] = network.p2pkhVersion;
  payload.set(pubkeyHash20, 1);
  return base58checkEncode(payload);
}

export function p2shAddress(scriptHash20, network) {
  const payload = new Uint8Array(21);
  payload[0] = network.p2shVersion;
  payload.set(scriptHash20, 1);
  return base58checkEncode(payload);
}

export function p2wpkhAddress(pubkeyHash20, network) {
  const program = convertBits(Array.from(pubkeyHash20), 8, 5, true);
  return bech32Encode(network.bech32Hrp, [0].concat(program));
}

export const AddressType = { p2pkh: "p2pkh", p2sh: "p2sh", p2wpkh: "p2wpkh" };

export function decodeAddress(address, network) {
  if (address.toLowerCase().startsWith(network.bech32Hrp + "1")) {
    const { hrp, data } = bech32Decode(address);
    if (hrp !== network.bech32Hrp) throw new Error("Address is for a different network");
    const witnessVersion = data[0];
    const program = convertBits(data.slice(1), 5, 8, false);
    if (witnessVersion !== 0 || program.length !== 20) throw new Error("Unsupported witness version/program length");
    return { type: AddressType.p2wpkh, hash: new Uint8Array(program) };
  }
  const decoded = base58checkDecode(address);
  if (decoded.length !== 21) throw new Error("Invalid Base58Check address length");
  const version = decoded[0];
  const payload = decoded.slice(1);
  if (version === network.p2pkhVersion) return { type: AddressType.p2pkh, hash: payload };
  if (version === network.p2shVersion) return { type: AddressType.p2sh, hash: payload };
  throw new Error(`Address version byte ${version} does not match this network`);
}

// -- BIP39 / BIP32 --
export function generateMnemonic() {
  return bip39.generateMnemonic(wordlist, 128);
}
export function isValidMnemonic(mnemonic) {
  return bip39.validateMnemonic(mnemonic, wordlist);
}
export async function deriveKey({ mnemonic, network, index = 0, passphrase = "", change = false }) {
  const seed = await bip39.mnemonicToSeed(mnemonic, passphrase);
  const root = HDKey.fromMasterSeed(seed);
  const path = `m/44'/${network.bip44CoinType}'/0'/${change ? 1 : 0}/${index}`;
  const node = root.derive(path);
  return { privateKey: node.privateKey, publicKey: node.publicKey };
}

// Exports this wallet's account-level extended public key ("xpub"),
// derived at m/44'/coinType'/0' -- the standard BIP44 "account" depth,
// one level above the external/change chains. Lets someone else (or
// this same wallet restored on another device, without its private
// key) derive and watch this wallet's addresses' balances without ever
// seeing a private key -- see deriveXpubAddress below, and the "locally
// generated, not gap-limit discovery" scoping note there.
export async function deriveAccountXpub({ mnemonic, network, passphrase = "" }) {
  const seed = await bip39.mnemonicToSeed(mnemonic, passphrase);
  const root = HDKey.fromMasterSeed(seed, network.bip32Versions);
  const account = root.derive(`m/44'/${network.bip44CoinType}'/0'`);
  return account.publicExtendedKey;
}

// Derives external-chain address #index from an imported account xpub,
// via BIP32 public (non-hardened) child derivation -- no private key
// involved anywhere in this call. Throws if `xpub` doesn't decode for
// `network` (e.g. testnet xpub imported while on mainnet -- the version
// bytes won't match) or is otherwise malformed. Like this wallet's
// existing multi-address support, watching from an xpub derives a
// fixed, caller-chosen count of addresses rather than scanning for a
// gap limit -- said explicitly in the UI.
export function deriveXpubAddress({ xpub, network, index }) {
  const node = HDKey.fromExtendedKey(xpub, network.bip32Versions);
  const child = node.derive(`m/0/${index}`);
  return p2pkhAddress(hash160(child.publicKey), network);
}

// -- legacy P2PKH transaction building/signing (mirrors transaction.dart) --
export function p2pkhScriptPubKey(pubkeyHash20) {
  return new Uint8Array([0x76, 0xa9, 0x14, ...pubkeyHash20, 0x88, 0xac]);
}
export function p2shScriptPubKey(scriptHash20) {
  return new Uint8Array([0xa9, 0x14, ...scriptHash20, 0x87]);
}
export function p2wpkhScriptPubKey(pubkeyHash20) {
  return new Uint8Array([0x00, 0x14, ...pubkeyHash20]);
}

function varInt(n) {
  if (n < 0xfd) return new Uint8Array([n]);
  const b = new Uint8Array(n <= 0xffff ? 3 : n <= 0xffffffff ? 5 : 9);
  const view = new DataView(b.buffer);
  if (n <= 0xffff) { b[0] = 0xfd; view.setUint16(1, n, true); }
  else if (n <= 0xffffffff) { b[0] = 0xfe; view.setUint32(1, n, true); }
  else { b[0] = 0xff; view.setBigUint64(1, BigInt(n), true); }
  return b;
}
function u32le(n) {
  const b = new Uint8Array(4);
  new DataView(b.buffer).setUint32(0, n, true);
  return b;
}
function u64le(n) {
  const b = new Uint8Array(8);
  new DataView(b.buffer).setBigUint64(0, BigInt(n), true);
  return b;
}
function concatBytes(...arrs) {
  const total = arrs.reduce((n, a) => n + a.length, 0);
  const out = new Uint8Array(total);
  let off = 0;
  for (const a of arrs) { out.set(a, off); off += a.length; }
  return out;
}

function serializeTx(version, inputs, outputs, locktime) {
  const parts = [u32le(version), varInt(inputs.length)];
  for (const inp of inputs) {
    parts.push(inp.prevTxid, u32le(inp.prevVout), varInt(inp.scriptSig.length), inp.scriptSig, u32le(inp.sequence ?? 0xffffffff));
  }
  parts.push(varInt(outputs.length));
  for (const out of outputs) {
    parts.push(u64le(out.valueSatoshis), varInt(out.scriptPubKey.length), out.scriptPubKey);
  }
  parts.push(u32le(locktime));
  return concatBytes(...parts);
}

function legacySighash({ inputs, outputs, inputIndex, subscript, locktime }) {
  const blanked = inputs.map((inp, i) => ({
    prevTxid: inp.prevTxid,
    prevVout: inp.prevVout,
    scriptSig: i === inputIndex ? subscript : new Uint8Array(0),
    sequence: inp.sequence,
  }));
  const preimage = serializeTx(2, blanked, outputs, locktime);
  const withType = concatBytes(preimage, u32le(1));
  return doubleSha256(withType);
}

function derEncodeSignature(sig) {
  // low-S already enforced by @noble/secp256k1's signing (normalizeS default true)
  function encodeInt(bigintVal) {
    let hex = bigintVal.toString(16);
    if (hex.length % 2) hex = "0" + hex;
    let bytes = hexToBytes(hex);
    if (bytes[0] & 0x80) bytes = concatBytes(new Uint8Array([0]), bytes);
    return concatBytes(new Uint8Array([0x02, bytes.length]), bytes);
  }
  const rEnc = encodeInt(sig.r);
  const sEnc = encodeInt(sig.s);
  return concatBytes(new Uint8Array([0x30, rEnc.length + sEnc.length]), rEnc, sEnc);
}

// inputs: [{txid: Uint8Array(32, internal order), vout, valueSatoshis, pubkeyHash: Uint8Array(20),
//           privateKey?, publicKeyCompressed?, sequence?}] -- an input's own
// privateKey/publicKeyCompressed (needed once a wallet can spend UTXOs
// sitting at more than one derived address in the same transaction)
// override the single global privateKey/publicKeyCompressed arguments
// below, which stay as the default for every input that doesn't specify
// its own -- existing single-key callers are unaffected. `sequence`
// defaults to 0xfffffffd (BIP125 opt-in replace-by-fee signal, any value
// below 0xfffffffe) rather than the plain 0xffffffff every send used
// before this default existed -- this is what makes "bump fee" possible
// later, since the node's inherited Bitcoin Core mempool policy only
// allows a conflicting replacement transaction when the original
// signalled replaceability this way. A transaction built before this
// default existed did not signal it and can't be bumped through
// standard replacement -- see the bumpFee logic in app.js.
// outputs: [{scriptPubKey: Uint8Array, valueSatoshis}]
export function buildAndSignTransaction({ inputs, outputs, privateKey, publicKeyCompressed, locktime = 0 }) {
  if (inputs.length === 0) throw new Error("No inputs provided");
  const txInputs = inputs.map((u) => ({
    prevTxid: u.txid, prevVout: u.vout, scriptSig: new Uint8Array(0),
    sequence: u.sequence ?? 0xfffffffd,
  }));
  for (let i = 0; i < inputs.length; i++) {
    const inputPrivateKey = inputs[i].privateKey ?? privateKey;
    const inputPublicKey = inputs[i].publicKeyCompressed ?? publicKeyCompressed;
    const subscript = p2pkhScriptPubKey(inputs[i].pubkeyHash);
    const sighash = legacySighash({ inputs: txInputs, outputs, inputIndex: i, subscript, locktime });
    const sig = secp.sign(sighash, inputPrivateKey);
    const derSig = derEncodeSignature(sig);
    const sigWithType = concatBytes(derSig, new Uint8Array([0x01]));
    txInputs[i].scriptSig = concatBytes(
      new Uint8Array([sigWithType.length]), sigWithType,
      new Uint8Array([inputPublicKey.length]), inputPublicKey
    );
  }
  return serializeTx(2, txInputs, outputs, locktime);
}

// -- N-of-M P2SH multisig --
//
// Standard Bitcoin-family bare multisig inside P2SH: no new consensus
// feature needed (unlike P2CS cold-staking, which doesn't exist in
// firstislamiccoin-core at all -- see docs/CHANGELOG-FIC.md's TODO-HUMAN
// table) --
// OP_CHECKMULTISIG is already valid, standard script this chain accepts
// unchanged, inherited from the Bitcoin/Blackcoin lineage.
//
// A single wallet instance only ever holds one signer's key, so spending
// a multisig UTXO needs an out-of-band "proposal" object that signers
// pass to each other (however they like -- email, a shared file, a
// future dedicated coordination endpoint) until enough signatures are
// collected. This is a minimal, from-scratch version of what BIP174
// (PSBT) formalizes for general use -- scoped down to exactly what this
// wallet's single-input-type (legacy P2PKH-family) signer already needs,
// not a general PSBT implementation.

const OP_CHECKMULTISIG = 0xae;

function opN(n) {
  if (n < 1 || n > 16) throw new Error("OP_N only supports 1..16");
  return 0x50 + n;
}

// pubkeysCompressed: array of Uint8Array(33), in the fixed order all
// cosigners must agree on ahead of time (order determines both the
// resulting address AND the required signature order when spending).
export function createMultisigRedeemScript(m, pubkeysCompressed) {
  if (m < 1 || m > pubkeysCompressed.length) throw new Error("m must be between 1 and the number of pubkeys");
  if (pubkeysCompressed.length > 16) throw new Error("at most 16 pubkeys supported (OP_N range)");
  const parts = [new Uint8Array([opN(m)])];
  for (const pk of pubkeysCompressed) {
    if (pk.length !== 33) throw new Error("Only compressed (33-byte) pubkeys are supported");
    parts.push(new Uint8Array([pk.length]), pk);
  }
  parts.push(new Uint8Array([opN(pubkeysCompressed.length), OP_CHECKMULTISIG]));
  return concatBytes(...parts);
}

export function multisigAddress(redeemScript, network) {
  return p2shAddress(hash160(redeemScript), network);
}

// inputs: [{txid, vout, valueSatoshis, redeemScript}] -- redeemScript
// may differ per input if spending from more than one multisig address
// in the same transaction, though the common case is all inputs sharing
// one address/script.
export function createMultisigProposal({ inputs, outputs, locktime = 0 }) {
  return {
    version: 2,
    locktime,
    inputs: inputs.map((i) => ({
      txid: bytesToHex(i.txid), vout: i.vout, valueSatoshis: i.valueSatoshis,
      redeemScript: bytesToHex(i.redeemScript),
    })),
    outputs: outputs.map((o) => ({ scriptPubKey: bytesToHex(o.scriptPubKey), valueSatoshis: o.valueSatoshis })),
    // signatures[i] is a map of pubkeyHex -> derSigHex for input i, built
    // up as each cosigner calls signMultisigProposal.
    signatures: inputs.map(() => ({})),
  };
}

function proposalToTxInputsOutputs(proposal) {
  const txInputs = proposal.inputs.map((i) => ({
    prevTxid: hexToBytes(i.txid), prevVout: i.vout, scriptSig: new Uint8Array(0),
  }));
  const outputs = proposal.outputs.map((o) => ({
    scriptPubKey: hexToBytes(o.scriptPubKey), valueSatoshis: o.valueSatoshis,
  }));
  return { txInputs, outputs };
}

// Mutates and returns `proposal` with this signer's signature added for
// every input whose redeemScript this pubkey actually appears in (a
// no-op for inputs this key isn't a cosigner on, so the same call is
// safe to make across a batch of inputs from different multisig setups).
export function signMultisigProposal(proposal, privateKey, publicKeyCompressed) {
  const { txInputs, outputs } = proposalToTxInputsOutputs(proposal);
  const pubkeyHex = bytesToHex(publicKeyCompressed);
  for (let i = 0; i < proposal.inputs.length; i++) {
    const redeemScript = hexToBytes(proposal.inputs[i].redeemScript);
    if (!scriptContainsPubkey(redeemScript, publicKeyCompressed)) continue;
    // For OP_CHECKMULTISIG the subscript is the redeem script itself
    // (not a P2PKH scriptPubKey the way ordinary spends use) -- the
    // classic Bitcoin signing rule for bare-multisig-in-P2SH.
    const sighash = legacySighash({ inputs: txInputs, outputs, inputIndex: i, subscript: redeemScript, locktime: proposal.locktime });
    const sig = secp.sign(sighash, privateKey);
    const derSig = derEncodeSignature(sig);
    proposal.signatures[i][pubkeyHex] = bytesToHex(concatBytes(derSig, new Uint8Array([0x01])));
  }
  return proposal;
}

function scriptContainsPubkey(redeemScript, pubkeyCompressed) {
  const needle = bytesToHex(pubkeyCompressed);
  const hex = bytesToHex(redeemScript);
  return hex.includes(needle);
}

// Combines signatures collected across independently-signed copies of
// the same proposal (e.g. two cosigners who each ran
// signMultisigProposal on their own copy) into one.
export function mergeMultisigProposals(proposals) {
  const merged = JSON.parse(JSON.stringify(proposals[0]));
  for (const p of proposals.slice(1)) {
    for (let i = 0; i < merged.signatures.length; i++) {
      Object.assign(merged.signatures[i], p.signatures[i]);
    }
  }
  return merged;
}

function parsePubkeysInOrder(redeemScript) {
  // Walk the script's push opcodes to recover pubkeys in their original
  // script order -- required because OP_CHECKMULTISIG's signature-
  // matching is order-sensitive (signatures must appear in the same
  // relative order as their pubkeys in the script).
  const pubkeys = [];
  let i = 1; // skip leading OP_m
  while (i < redeemScript.length) {
    const opcode = redeemScript[i];
    if (opcode >= 1 && opcode <= 75) {
      pubkeys.push(bytesToHex(redeemScript.slice(i + 1, i + 1 + opcode)));
      i += 1 + opcode;
    } else {
      break; // hit OP_n / OP_CHECKMULTISIG -- done
    }
  }
  return pubkeys;
}

// Once enough signatures are collected (per proposal.inputs[i]'s
// redeemScript's own m-of-n), assembles the final scriptSig for each
// input and returns the serialized, broadcast-ready raw transaction.
// Throws if any input is still short of its required signature count.
export function finalizeMultisigTransaction(proposal) {
  const { txInputs, outputs } = proposalToTxInputsOutputs(proposal);
  for (let i = 0; i < proposal.inputs.length; i++) {
    const redeemScript = hexToBytes(proposal.inputs[i].redeemScript);
    const m = redeemScript[0] - 0x50;
    const pubkeysInOrder = parsePubkeysInOrder(redeemScript);
    const collected = proposal.signatures[i];
    const orderedSigs = pubkeysInOrder.map((pk) => collected[pk]).filter(Boolean);
    if (orderedSigs.length < m) {
      throw new Error(`Input ${i} has ${orderedSigs.length} signature(s), needs ${m}`);
    }
    const sigsToUse = orderedSigs.slice(0, m).map(hexToBytes);
    // OP_0 dummy element (the historical OP_CHECKMULTISIG off-by-one
    // bug that's now a fixed, standard part of the script format -- one
    // extra stack item is always consumed and discarded) + each
    // signature push + the redeem script push.
    const parts = [new Uint8Array([0x00])];
    for (const sig of sigsToUse) parts.push(new Uint8Array([sig.length]), sig);
    parts.push(varInt(redeemScript.length), redeemScript);
    txInputs[i].scriptSig = concatBytes(...parts);
  }
  return serializeTx(proposal.version, txInputs, outputs, proposal.locktime);
}

// Given a locally-recorded sent-tx entry (see app.js's recordSentTx) and
// a target total fee, rebuilds and signs a replacement transaction that
// spends the exact same inputs and pays every non-change output the
// same amount, only shrinking the change output by the fee increase.
// Throws if there's no change output to shrink, or not enough change to
// absorb the increase -- fails closed rather than guessing at a
// fallback (e.g. pulling in an extra input) for either case.
// record: {inputs: [{txid, vout, valueSatoshis}], outputs: [{scriptPubKeyHex, valueSatoshis, isChange}], feeSatoshis}
// inputKeys[i] (a {privateKey, publicKeyCompressed} pair) must correspond to record.inputs[i].
export function buildBumpFeeTransaction({ record, newFeeSatoshis, inputKeys }) {
  const changeOutputIndex = record.outputs.findIndex((o) => o.isChange);
  if (changeOutputIndex === -1) {
    throw new Error("This transaction has no change output to reduce -- can't bump its fee automatically here.");
  }
  const feeIncrease = newFeeSatoshis - record.feeSatoshis;
  const changeOutput = record.outputs[changeOutputIndex];
  const newChangeValue = changeOutput.valueSatoshis - feeIncrease;
  if (newChangeValue <= 0) {
    throw new Error("Not enough change left to cover a higher fee.");
  }
  const inputs = record.inputs.map((inp, i) => ({
    txid: hexToBytes(inp.txid).reverse(),
    vout: inp.vout,
    valueSatoshis: inp.valueSatoshis,
    pubkeyHash: hash160(inputKeys[i].publicKeyCompressed),
    privateKey: inputKeys[i].privateKey,
    publicKeyCompressed: inputKeys[i].publicKeyCompressed,
  }));
  const outputs = record.outputs.map((o, i) => ({
    scriptPubKey: hexToBytes(o.scriptPubKeyHex),
    valueSatoshis: i === changeOutputIndex ? newChangeValue : o.valueSatoshis,
  }));
  const rawTx = buildAndSignTransaction({ inputs, outputs });
  const newOutputs = record.outputs.map((o, i) =>
    i === changeOutputIndex ? { ...o, valueSatoshis: newChangeValue } : o
  );
  return { rawTx, newOutputs };
}

export { bytesToHex, hexToBytes, varInt, concatBytes };
