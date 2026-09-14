import * as fic from "./crypto.js";
import { Gateway, GatewayError } from "./gateway.js";
import * as qr from "./qr.js";
import * as storage from "./storage.js";
import { signMessage, verifyMessage } from "./message.js";

// Production default: empty string, so Gateway's fetch(this.baseUrl + path)
// calls resolve against the page's own origin (see explorer/app.js and
// checkout-widget/checkout.js for the identical convention) -- override via
// localStorage for local dev against a gateway on a different origin/port.
const GATEWAY_URLS = {
  mainnet: localStorage.getItem("fic_gateway_url_mainnet") || "",
  testnet: localStorage.getItem("fic_gateway_url_testnet") || "",
};
const COIN = 100_000_000n;

const state = {
  network: localStorage.getItem("fic_network") || "mainnet",
  mnemonic: null, // decrypted in-memory only once unlocked; never re-persisted in plain text if a PIN is set
  addressIndices: [], // every address index this wallet has generated on this browser, this network
  activeIndex: 0, // which index is shown as "current" on Receive / used for change outputs
  keys: {}, // index -> {privateKey, publicKey}
  addresses: {}, // index -> address string
  gateway: null,
  stakeToken: sessionStorage.getItem("fic_stake_token") || null,
  qrScanHandle: null,
  sendFeeMinRate: null, // BigInt, the gateway's own recommended/minimum rate, fetched fresh per screen visit
  sendFeeRateOverride: null, // BigInt or null -- null means "use the recommended rate"
};

function refreshGateway() {
  state.gateway = new Gateway(GATEWAY_URLS[state.network]);
  document.getElementById("network-badge").textContent = state.network;
}
refreshGateway();

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Parses a `firstislamiccoin:<address>[?amount=X&label=Y]` URI (BIP21-style).
// Returns just the address unchanged if given a bare address instead of
// a URI, so callers can pass either through this same function.
function parseBip21(text) {
  const trimmed = text.trim();
  if (!trimmed.toLowerCase().startsWith("firstislamiccoin:")) return { address: trimmed, amount: null };
  const withoutScheme = trimmed.slice("firstislamiccoin:".length);
  const [address, query] = withoutScheme.split("?");
  let amount = null;
  if (query) {
    const params = new URLSearchParams(query);
    const amountStr = params.get("amount");
    if (amountStr) amount = parseFloat(amountStr);
  }
  return { address, amount };
}

function formatFic(satoshis) {
  const s = BigInt(satoshis);
  const whole = s / COIN;
  const frac = (s % COIN).toString().padStart(8, "0");
  return `${whole}.${frac}`;
}

// ------------------------------------------------------------- addresses

function addressIndicesStorageKey() {
  return `fic_address_indices_${state.network}`;
}
function loadAddressIndices() {
  const raw = localStorage.getItem(addressIndicesStorageKey());
  const parsed = raw ? JSON.parse(raw) : null;
  return parsed && parsed.length ? parsed : [0];
}
function saveAddressIndices() {
  localStorage.setItem(addressIndicesStorageKey(), JSON.stringify(state.addressIndices));
}

async function ensureKey(index) {
  if (state.keys[index]) return state.keys[index];
  const network = fic.NETWORKS[state.network];
  const key = await fic.deriveKey({ mnemonic: state.mnemonic, network, index });
  state.keys[index] = key;
  state.addresses[index] = fic.p2pkhAddress(fic.hash160(key.publicKey), network);
  return key;
}

// Derives every address this wallet has generated so far on this browser
// for the current network. This is *not* BIP44 gap-limit discovery --
// it only knows about indices this browser itself has generated (via
// "New address" on the Receive screen), tracked locally in localStorage.
// A phrase restored fresh on a new browser starts back at just index 0;
// it does not scan for addresses used elsewhere. Balance, UTXOs, and
// history are combined across every known index.
async function deriveAllKnownAddresses() {
  state.addressIndices = loadAddressIndices();
  for (const idx of state.addressIndices) await ensureKey(idx);
  if (!state.addressIndices.includes(state.activeIndex)) {
    state.activeIndex = state.addressIndices[state.addressIndices.length - 1];
  }
}

function activeAddress() {
  return state.addresses[state.activeIndex];
}

async function gatherAllUtxos() {
  const all = [];
  for (const idx of state.addressIndices) {
    const resp = await state.gateway.utxos(state.addresses[idx]);
    for (const u of resp.utxos) all.push({ ...u, _index: idx });
  }
  return all;
}

// ------------------------------------------------------------- screens

function showScreen(name) {
  document.querySelectorAll(".screen").forEach((el) => el.classList.remove("active"));
  document.getElementById(`screen-${name}`).classList.add("active");
  document.querySelectorAll(".tabbar button").forEach((b) => b.classList.toggle("active", b.dataset.screen === name));
  if (name === "home") loadHome();
  if (name === "send") { loadAddressBook(); loadSendAmountFiat(); loadSendFeeRate(); }
  if (name === "receive") loadReceive();
  if (name === "history") loadHistory();
  if (name === "staking") loadStaking();
  if (name === "multisig") loadMultisig();
  if (name === "watch") loadWatch();
  if (name === "settings") loadSettings();
  // Only polls while Home or History is the visible screen, and only
  // while a wallet is actually unlocked -- see checkForNewTx. Not
  // background work: the interval is cleared the moment the user
  // navigates elsewhere, same as this being a plain tab getting closed
  // would stop it. Distinct from mobile's "no background work" rule
  // (docs/store-compliance.md), which is about the OS process
  // continuing after the app itself is closed -- a foreground browser
  // tab timer has no equivalent to disclose there.
  if (name === "home" || name === "history") startTxPolling();
  else stopTxPolling();
}

document.querySelectorAll(".tabbar button").forEach((btn) => {
  btn.addEventListener("click", () => showScreen(btn.dataset.screen));
});

// ------------------------------------------------------------ onboarding

async function enterWallet() {
  await deriveAllKnownAddresses();
  document.getElementById("screen-onboarding").classList.remove("active");
  document.getElementById("lock-overlay").style.display = "none";
  document.getElementById("tabbar").style.display = "flex";
  showScreen("home");
}

document.getElementById("btn-create-wallet").addEventListener("click", () => {
  const mnemonic = fic.generateMnemonic();
  document.getElementById("new-mnemonic").textContent = mnemonic;
  document.getElementById("new-mnemonic-card").style.display = "block";
  document.getElementById("btn-create-wallet").style.display = "none";
  document.getElementById("btn-show-restore").style.display = "none";
  state._pendingMnemonic = mnemonic;
});

document.getElementById("confirm-written").addEventListener("change", (e) => {
  document.getElementById("btn-mnemonic-continue").disabled = !e.target.checked;
});

document.getElementById("btn-mnemonic-continue").addEventListener("click", () => {
  showMnemonicQuiz(state._pendingMnemonic);
});

// Picks 3 random distinct word positions and asks the user to retype them,
// so a mistyped or skipped word in the backup is caught here rather than
// the first time it's actually needed.
function showMnemonicQuiz(mnemonic) {
  const words = mnemonic.split(" ");
  const indices = [];
  while (indices.length < 3) {
    const i = Math.floor(Math.random() * words.length);
    if (!indices.includes(i)) indices.push(i);
  }
  indices.sort((a, b) => a - b);
  const fieldsEl = document.getElementById("mnemonic-quiz-fields");
  fieldsEl.innerHTML = "";
  for (const i of indices) {
    const label = document.createElement("label");
    label.className = "field-label";
    label.textContent = `Word #${i + 1}`;
    const input = document.createElement("input");
    input.className = "quiz-word-input";
    input.dataset.index = String(i);
    input.autocomplete = "off";
    input.spellcheck = false;
    fieldsEl.appendChild(label);
    fieldsEl.appendChild(input);
  }
  document.getElementById("mnemonic-quiz-error").textContent = "";
  document.getElementById("new-mnemonic-card").style.display = "none";
  document.getElementById("mnemonic-quiz-card").style.display = "block";
}

document.getElementById("btn-quiz-back").addEventListener("click", () => {
  document.getElementById("mnemonic-quiz-card").style.display = "none";
  document.getElementById("new-mnemonic-card").style.display = "block";
});

document.getElementById("btn-quiz-verify").addEventListener("click", async () => {
  const words = state._pendingMnemonic.split(" ");
  const inputs = document.querySelectorAll("#mnemonic-quiz-fields .quiz-word-input");
  let allCorrect = true;
  for (const input of inputs) {
    const idx = Number(input.dataset.index);
    if (input.value.trim().toLowerCase() !== words[idx]) allCorrect = false;
  }
  const errEl = document.getElementById("mnemonic-quiz-error");
  if (!allCorrect) {
    errEl.textContent = "One or more words don't match. Check your written-down phrase and try again.";
    return;
  }
  errEl.textContent = "";
  state.mnemonic = state._pendingMnemonic;
  localStorage.setItem("fic_mnemonic", state.mnemonic);
  state.addressIndices = [0];
  saveAddressIndices();
  document.getElementById("mnemonic-quiz-card").style.display = "none";
  await enterWallet();
});

document.getElementById("btn-show-restore").addEventListener("click", () => {
  document.getElementById("restore-card").style.display = "block";
});

document.getElementById("btn-restore-confirm").addEventListener("click", async () => {
  const mnemonic = document.getElementById("restore-mnemonic").value.trim();
  const errEl = document.getElementById("restore-error");
  if (!fic.isValidMnemonic(mnemonic)) {
    errEl.textContent = "Invalid recovery phrase.";
    return;
  }
  errEl.textContent = "";
  state.mnemonic = mnemonic;
  localStorage.setItem("fic_mnemonic", mnemonic);
  state.addressIndices = [0];
  saveAddressIndices();
  await enterWallet();
});

// ------------------------------------------------------------- app lock

// Declared here (not down by the polling functions that use it, in the
// "live new-tx banner" section below) because boot() -- called a few
// lines down -- can synchronously reach into enterWallet() and start
// polling before this module has finished evaluating top to bottom.
// `let` bindings are in the temporal dead zone until their own
// declaration line runs, so leaving this next to startTxPolling()
// further down the file threw "Cannot access 'txPollHandle' before
// initialization" for any user with an existing wallet and no PIN set
// (the boot() path that calls enterWallet() synchronously).
let txPollHandle = null;

async function boot() {
  if (storage.isPinSet()) {
    document.getElementById("lock-overlay").style.display = "flex";
    return;
  }
  state.mnemonic = localStorage.getItem("fic_mnemonic") || null;
  if (state.mnemonic) await enterWallet();
}
boot();

document.getElementById("btn-unlock").addEventListener("click", async () => {
  const pin = document.getElementById("lock-pin").value;
  const errEl = document.getElementById("lock-error");
  errEl.textContent = "";
  try {
    const blob = storage.loadEncryptedBlob();
    state.mnemonic = await storage.decryptMnemonic(blob, pin);
    document.getElementById("lock-pin").value = "";
    await enterWallet();
  } catch (e) {
    errEl.textContent = "Incorrect PIN.";
  }
});
document.getElementById("lock-pin").addEventListener("keydown", (e) => {
  if (e.key === "Enter") document.getElementById("btn-unlock").click();
});

// -------------------------------------------------------------------- home

async function loadHome() {
  const errEl = document.getElementById("home-error");
  errEl.textContent = "";
  document.getElementById("home-address").textContent = activeAddress();
  document.getElementById("home-address-count").textContent =
    state.addressIndices.length > 1 ? `Balance combined across ${state.addressIndices.length} addresses` : "";
  try {
    let total = 0n;
    for (const idx of state.addressIndices) {
      const balance = await state.gateway.balance(state.addresses[idx]);
      total += BigInt(balance.confirmed) + BigInt(balance.unconfirmed);
    }
    document.getElementById("home-balance").textContent = `${formatFic(total)} FIC`;
    // No fiat value shown -- unlike CodexaCoin, FIC has no wrapped token
    // or DEX listing on any chain to source a price from at all (see
    // docs/CHANGELOG-FIC.md's Decision 3). #home-fiat-value stays
    // permanently empty rather than fabricating a number.
  } catch (e) {
    errEl.textContent = e instanceof GatewayError ? e.message : `Could not reach the network: ${e}`;
  }
}

// -------------------------------------------------------------------- send
//
// Supports sending to several recipients in a single transaction (a
// "batch send" -- one shared fee/change output instead of one
// transaction per recipient). Recipient rows are built dynamically
// into #send-recipients rather than a single fixed pair of inputs --
// see recipientRowHtml/wireRecipientRow below. crypto.js's
// buildAndSignTransaction already accepts an arbitrary outputs list,
// so nothing there needed to change for this.

let sendRecipientIdCounter = 0;
state.activeSendRecipientId = null; // which row's address field was last focused -- see the address-book "Use" handler

function recipientRowHtml(id) {
  return `<div class="recipient-row" data-recipient-id="${id}">
    <div class="recipient-header">
      <label class="field-label">Destination address</label>
      <button class="danger remove-recipient-btn" type="button" data-remove-recipient="${id}">Remove</button>
    </div>
    <div class="row">
      <input class="recipient-address" placeholder="F..." />
      <button class="secondary qr-scan-btn" type="button" title="Scan QR code">Scan</button>
    </div>
    <label class="field-label">Amount (FIC)</label>
    <input class="recipient-amount" type="number" step="0.00000001" />
  </div>`;
}

function wireRecipientRow(row) {
  const id = row.dataset.recipientId;
  const addressInput = row.querySelector(".recipient-address");
  const amountInput = row.querySelector(".recipient-amount");

  addressInput.addEventListener("focus", () => {
    state.activeSendRecipientId = id;
  });
  // Also handles a pasted firstislamiccoin: URI (not just a scanned one) --
  // same parseBip21 either way.
  addressInput.addEventListener("change", (e) => {
    const { address, amount } = parseBip21(e.target.value);
    if (address !== e.target.value) {
      e.target.value = address;
      if (amount != null) amountInput.value = amount;
    }
  });
  amountInput.addEventListener("focus", () => {
    state.activeSendRecipientId = id;
  });
  amountInput.addEventListener("input", updateSendAmountFiat);

  row.querySelector(".qr-scan-btn").addEventListener("click", () => {
    openQrScanner((text) => {
      const { address, amount } = parseBip21(text);
      addressInput.value = address;
      if (amount != null) amountInput.value = amount;
    });
  });
  row.querySelector(".remove-recipient-btn").addEventListener("click", () => {
    row.remove();
    updateRecipientRemoveButtons();
    updateSendAmountFiat();
  });
}

function updateRecipientRemoveButtons() {
  const rows = document.querySelectorAll(".recipient-row");
  rows.forEach((row) => {
    row.querySelector(".remove-recipient-btn").style.display = rows.length > 1 ? "" : "none";
  });
}

function addRecipientRow() {
  const id = sendRecipientIdCounter++;
  const container = document.getElementById("send-recipients");
  const wrapper = document.createElement("div");
  wrapper.innerHTML = recipientRowHtml(id);
  const row = wrapper.firstElementChild;
  container.appendChild(row);
  if (state.activeSendRecipientId == null) state.activeSendRecipientId = String(id);
  wireRecipientRow(row);
  updateRecipientRemoveButtons();
}

function resetSendRecipients() {
  document.getElementById("send-recipients").innerHTML = "";
  sendRecipientIdCounter = 0;
  state.activeSendRecipientId = null;
  addRecipientRow();
}

document.getElementById("btn-add-recipient").addEventListener("click", addRecipientRow);
addRecipientRow(); // start with one row

document.getElementById("btn-send-confirm").addEventListener("click", async () => {
  const errEl = document.getElementById("send-error");
  const okEl = document.getElementById("send-success");
  errEl.textContent = "";
  okEl.textContent = "";

  const rows = Array.from(document.querySelectorAll(".recipient-row"));
  const recipients = [];
  for (const row of rows) {
    const address = row.querySelector(".recipient-address").value.trim();
    const amountFic = parseFloat(row.querySelector(".recipient-amount").value);
    if (!address || !amountFic || amountFic <= 0) {
      errEl.textContent = "Enter a destination address and a positive amount for every recipient.";
      return;
    }
    recipients.push({ address, amountSatoshis: BigInt(Math.round(amountFic * 1e8)) });
  }

  try {
    const network = fic.NETWORKS[state.network];
    const destOutputs = recipients.map((r) => {
      const decoded = fic.decodeAddress(r.address, network);
      let scriptPubKey;
      if (decoded.type === fic.AddressType.p2pkh) scriptPubKey = fic.p2pkhScriptPubKey(decoded.hash);
      else if (decoded.type === fic.AddressType.p2sh) scriptPubKey = fic.p2shScriptPubKey(decoded.hash);
      else scriptPubKey = fic.p2wpkhScriptPubKey(decoded.hash);
      return { scriptPubKey, valueSatoshis: Number(r.amountSatoshis) };
    });
    const amountTotalSatoshis = recipients.reduce((sum, r) => sum + r.amountSatoshis, 0n);

    const allUtxos = await gatherAllUtxos();
    const feeResp = await state.gateway.feeEstimate();
    const minRate = BigInt(feeResp.fee_rate_sat_per_vbyte);
    state.sendFeeMinRate = minRate; // keep in sync in case it drifted since the screen loaded
    // Use the user's chosen rate only if it's still above the current
    // floor -- protects against a stale override surviving a floor
    // increase and getting rejected again.
    const feeRate = state.sendFeeRateOverride != null && state.sendFeeRateOverride > minRate ? state.sendFeeRateOverride : minRate;

    // Output count scales with recipient count now (N destinations + 1
    // change), not the fixed 2 a single-recipient send always had.
    const outputCount = recipients.length + 1;
    let totalIn = 0n;
    const chosen = [];
    for (const u of allUtxos) {
      chosen.push(u);
      totalIn += BigInt(u.value);
      // Re-estimated as inputs accumulate, scaled by input count -- rougher
      // than real dynamic fee estimation (this gateway has none, a known
      // limitation noted in mobile-api.md section 4).
      const estimatedVsize = BigInt(10 + chosen.length * 148 + outputCount * 34);
      // feeRate is already satoshis-per-vbyte (gateway.js's fee-estimate
      // response, fee_rate_sat_per_vbyte -- see app.py's fee_estimate,
      // which converts mempoolminfee's BTC/kvB all the way down to
      // sat/vbyte itself) -- so the fee is feeRate * vsize directly, no
      // further /1000 "per-kvB" conversion. CAC's original web-wallet had
      // exactly this extra /1000 here (a leftover from treating feeRate
      // as sat/kvB, which it never was on either chain's gateway), making
      // every send pay 1000x less fee than intended. Harmless on CAC,
      // which has no consensus-level minimum-fee check -- a real,
      // send-blocking bug here, since firstislamiccoin-core does enforce
      // one (see consensus/tx_verify.cpp's GetMinFee). Found live: a real
      // send against a real regtest node came back bad-txns-fee-not-enough
      // even after manually overriding the fee rate to 50x the floor.
      const feeSatoshis = feeRate * estimatedVsize;
      if (totalIn >= amountTotalSatoshis + feeSatoshis) break;
    }
    const finalVsize = BigInt(10 + chosen.length * 148 + outputCount * 34);
    const feeSatoshis = feeRate * finalVsize;
    if (totalIn < amountTotalSatoshis + feeSatoshis) {
      errEl.textContent = `Insufficient funds: have ${formatFic(totalIn)}, need ${formatFic(amountTotalSatoshis + feeSatoshis)}`;
      return;
    }
    const change = totalIn - amountTotalSatoshis - feeSatoshis;
    const changeKey = await ensureKey(state.activeIndex);
    const changeHash = fic.hash160(changeKey.publicKey);
    const outputs = [...destOutputs];
    if (change > 0n) outputs.push({ scriptPubKey: fic.p2pkhScriptPubKey(changeHash), valueSatoshis: Number(change) });

    const inputs = chosen.map((u) => {
      const key = state.keys[u._index];
      return {
        txid: fic.hexToBytes(u.txid).reverse(), // wire order is internal (reversed from display hex)
        vout: u.vout,
        valueSatoshis: Number(u.value),
        pubkeyHash: fic.hash160(key.publicKey),
        privateKey: key.privateKey,
        publicKeyCompressed: key.publicKey,
      };
    });

    const rawTx = fic.buildAndSignTransaction({ inputs, outputs });
    const result = await state.gateway.broadcast(fic.bytesToHex(rawTx));
    okEl.textContent = `Broadcast: ${result.txid}`;
    recordSentTx(result.txid, {
      inputs: chosen.map((u) => ({ txid: u.txid, vout: u.vout, valueSatoshis: Number(u.value), derivationIndex: u._index })),
      outputs: outputs.map((o, i) => ({
        scriptPubKeyHex: fic.bytesToHex(o.scriptPubKey),
        valueSatoshis: o.valueSatoshis,
        isChange: change > 0n && i === outputs.length - 1,
        changeIndex: change > 0n && i === outputs.length - 1 ? state.activeIndex : undefined,
      })),
      feeSatoshis: Number(feeSatoshis),
    });
    resetSendRecipients();
    updateSendAmountFiat();
  } catch (e) {
    errEl.textContent = e instanceof GatewayError ? e.message : String(e);
  }
});

// --------------------------------------------------------- fee bumping

// Local-only record of what this wallet itself sent, kept purely so
// "bump fee" can rebuild the exact same transaction later with a higher
// fee. Only ever covers sends made from
// this browser after this feature shipped (buildAndSignTransaction's
// sequence default changed at the same time -- see crypto.js); older
// sends, and sends made from a different browser/device, don't have a
// local record and can't be bumped through this UI.
function loadSentTxLog() {
  const raw = localStorage.getItem("fic_sent_tx_log");
  return raw ? JSON.parse(raw) : {};
}
function saveSentTxLog(log) {
  localStorage.setItem("fic_sent_tx_log", JSON.stringify(log));
}
function recordSentTx(txid, record) {
  const log = loadSentTxLog();
  log[txid] = record;
  saveSentTxLog(log);
}

// Rebuilds and rebroadcasts `txid` (a transaction this wallet itself
// sent, per the local log) with a higher fee taken out of its own
// change output. Throws with a clear, specific reason rather than
// guessing at a fallback for any case this can't handle -- the actual
// rebuild/reduce-change math lives in crypto.js's buildBumpFeeTransaction
// (pure, independently testable), this just supplies the fee target and
// re-derived keys and handles the network calls.
async function bumpFee(txid) {
  const log = loadSentTxLog();
  const record = log[txid];
  if (!record) {
    throw new Error("No local record of this transaction -- it was either sent from a different device/browser, or before this feature existed. Can't bump its fee here.");
  }
  const feeResp = await state.gateway.feeEstimate();
  const feeRate = BigInt(feeResp.fee_rate_sat_per_vbyte);
  const estimatedVsize = BigInt(10 + record.inputs.length * 148 + record.outputs.length * 34);
  // feeRate is already sat/vbyte -- see the identical note on the send
  // handler's own fee calculation above.
  const rateBasedFee = Number(feeRate * estimatedVsize);
  // Must be a *meaningfully* higher fee, not just technically higher
  // (BIP125 rule 4 requires paying for the replacement's own bandwidth
  // too) -- take whichever is larger of "fresh rate estimate" and "50%
  // more than before".
  const newFeeSatoshis = Math.max(rateBasedFee, Math.round(record.feeSatoshis * 1.5));

  const inputKeys = [];
  for (const inp of record.inputs) {
    const key = await ensureKey(inp.derivationIndex);
    inputKeys.push({ privateKey: key.privateKey, publicKeyCompressed: key.publicKey });
  }
  const { rawTx, newOutputs } = fic.buildBumpFeeTransaction({ record, newFeeSatoshis, inputKeys });
  const result = await state.gateway.broadcast(fic.bytesToHex(rawTx));

  const log2 = loadSentTxLog();
  delete log2[txid];
  log2[result.txid] = { inputs: record.inputs, outputs: newOutputs, feeSatoshis: newFeeSatoshis, replacesTxid: txid };
  saveSentTxLog(log2);
  return result.txid;
}

// ------------------------------------------------------------- QR scanning

// Shared by the send screen's address scanner and the multisig screen's
// proposal scanner -- same camera overlay, different destination for the
// decoded text.
function openQrScanner(onResult) {
  document.getElementById("qr-scan-overlay").style.display = "flex";
  document.getElementById("qr-scan-error").textContent = "";
  const video = document.getElementById("qr-video");
  const canvas = document.getElementById("qr-scan-canvas");
  state.qrScanHandle = qr.startQrScanner({
    video,
    canvas,
    onResult: (text) => {
      onResult(text);
      closeQrScan();
    },
    onError: () => {
      document.getElementById("qr-scan-error").textContent =
        "Could not access the camera. Check that this site has camera permission in your browser settings.";
    },
  });
}
function closeQrScan() {
  if (state.qrScanHandle) state.qrScanHandle.stop();
  state.qrScanHandle = null;
  document.getElementById("qr-scan-overlay").style.display = "none";
  document.getElementById("qr-video").srcObject = null;
}
document.getElementById("btn-qr-scan-cancel").addEventListener("click", closeQrScan);

// -------------------------------------------------------------- address book

function loadAddressBookEntries() {
  const raw = localStorage.getItem("fic_address_book");
  return raw ? JSON.parse(raw) : [];
}
function saveAddressBookEntries(entries) {
  localStorage.setItem("fic_address_book", JSON.stringify(entries));
}
function renderAddressBook() {
  const entries = loadAddressBookEntries();
  const listEl = document.getElementById("address-book-list");
  if (entries.length === 0) {
    listEl.innerHTML = '<p class="notice">No saved addresses yet.</p>';
    return;
  }
  listEl.innerHTML = entries
    .map(
      (e, i) => `
    <div class="book-row">
      <div class="book-info">
        <div class="book-label">${escapeHtml(e.label)}</div>
        <div class="book-address mono">${escapeHtml(e.address)}</div>
      </div>
      <button class="secondary" type="button" data-use="${i}">Use</button>
      <button class="danger" type="button" data-remove="${i}">Remove</button>
    </div>`
    )
    .join("");
  listEl.querySelectorAll("[data-use]").forEach((btn) => {
    btn.addEventListener("click", () => {
      // Fills whichever recipient row's address field was last focused
      // (falling back to the first row if none was, or it's since been
      // removed) -- there's no single fixed address field to target
      // anymore now that a send can have several recipients.
      const targetRow =
        document.querySelector(`.recipient-row[data-recipient-id="${state.activeSendRecipientId}"]`) ||
        document.querySelector(".recipient-row");
      if (targetRow) targetRow.querySelector(".recipient-address").value = entries[Number(btn.dataset.use)].address;
    });
  });
  listEl.querySelectorAll("[data-remove]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.dataset.remove);
      const updated = loadAddressBookEntries();
      updated.splice(idx, 1);
      saveAddressBookEntries(updated);
      renderAddressBook();
    });
  });
}
function loadAddressBook() {
  renderAddressBook();
}
document.getElementById("btn-book-add").addEventListener("click", () => {
  const label = document.getElementById("new-book-label").value.trim();
  const address = document.getElementById("new-book-address").value.trim();
  if (!label || !address) return;
  const entries = loadAddressBookEntries();
  entries.push({ label, address });
  saveAddressBookEntries(entries);
  document.getElementById("new-book-label").value = "";
  document.getElementById("new-book-address").value = "";
  renderAddressBook();
});

// ----------------------------------------------------------------- receive

async function loadReceive() {
  document.getElementById("receive-address").textContent = activeAddress();
  document.getElementById("receive-request-amount").value = "";
  await refreshReceiveQr();
  renderAddressList();
}
// BIP21-style URI (firstislamiccoin:<address>[?amount=X]) so a requested amount
// travels with the QR itself rather than needing to be communicated
// separately -- falls back to a bare address when no amount is set, same
// as before this feature existed.
async function refreshReceiveQr() {
  const amount = document.getElementById("receive-request-amount").value.trim();
  const amountNum = parseFloat(amount);
  const uri = amountNum > 0 ? `firstislamiccoin:${activeAddress()}?amount=${amountNum}` : activeAddress();
  await qr.renderQr(document.getElementById("receive-qr"), uri);
}
document.getElementById("receive-request-amount").addEventListener("input", refreshReceiveQr);

// No fiat estimate shown on the send screen -- see loadHome's identical
// note: FIC has no exchange listing to source a price from. #send-amount-fiat
// is left permanently empty rather than fabricating a number; kept as a
// named no-op (not just deleted) since showScreen still calls it, and
// updateSendAmountFiat still needs to drive updateSendFeeEstimate on every
// amount-field keystroke.
function loadSendAmountFiat() {}
function updateSendAmountFiat() {
  updateSendFeeEstimate();
}

// Adjustable network fee. Defaults to the gateway's own recommended rate
// (its floor). Users can raise it (e.g. wanting to be extra safe), but
// can't go below it -- this coin enforces a single fixed consensus
// minimum fee rate, not a real congestion-based market (see
// mobile-api.md section 4), so anything lower would just get the
// transaction rejected; the control clamps there instead of offering a
// choice that can't actually work.
async function loadSendFeeRate() {
  try {
    const feeResp = await state.gateway.feeEstimate();
    state.sendFeeMinRate = BigInt(feeResp.fee_rate_sat_per_vbyte);
    state.sendFeeRateOverride = null;
    const input = document.getElementById("send-fee-rate");
    input.min = state.sendFeeMinRate.toString();
    input.value = state.sendFeeMinRate.toString();
  } catch (e) {
    // Same "network unreachable" reality as loadHome's balance fetch --
    // leave the fee row empty rather than throwing; the send button's own
    // handler will surface a real error if the user actually tries to send.
    state.sendFeeMinRate = null;
  }
  updateSendFeeEstimate();
}
function effectiveSendFeeRate() {
  return state.sendFeeRateOverride ?? state.sendFeeMinRate ?? 0n;
}
function updateSendFeeEstimate() {
  const el = document.getElementById("send-fee-estimate");
  if (!el) return;
  if (state.sendFeeMinRate == null) {
    el.textContent = "";
    return;
  }
  const rate = effectiveSendFeeRate();
  const rowCount = document.querySelectorAll(".recipient-row").length || 1;
  const outputCount = rowCount + 1;
  // Single-input estimate for display only -- the real send picks
  // however many inputs it actually needs at confirm time. Same "no real
  // dynamic fee estimation" caveat as the rest of this gateway's fee
  // handling (mobile-api.md section 4).
  const roughVsize = BigInt(10 + 148 + outputCount * 34);
  const roughFee = rate * roughVsize; // rate is already sat/vbyte, see the send handler's note
  el.textContent = `~${formatFic(roughFee)} FIC for a single-input send (scales up with more inputs/recipients) -- recommended: ${state.sendFeeMinRate} sat/vB`;
}
function setSendFeeRate(rate) {
  if (state.sendFeeMinRate == null) return;
  const ceiling = state.sendFeeMinRate * 50n;
  const clamped = rate < state.sendFeeMinRate ? state.sendFeeMinRate : rate > ceiling ? ceiling : rate;
  state.sendFeeRateOverride = clamped === state.sendFeeMinRate ? null : clamped;
  document.getElementById("send-fee-rate").value = clamped.toString();
  updateSendFeeEstimate();
}
document.getElementById("btn-fee-decrease").addEventListener("click", () => setSendFeeRate(effectiveSendFeeRate() - 10n));
document.getElementById("btn-fee-increase").addEventListener("click", () => setSendFeeRate(effectiveSendFeeRate() + 10n));
document.getElementById("btn-fee-reset").addEventListener("click", () => setSendFeeRate(state.sendFeeMinRate ?? 0n));
document.getElementById("send-fee-rate").addEventListener("change", (e) => {
  const parsed = parseInt(e.target.value, 10);
  if (!isFinite(parsed) || parsed <= 0) {
    setSendFeeRate(state.sendFeeMinRate ?? 0n);
    return;
  }
  setSendFeeRate(BigInt(parsed));
});

document.getElementById("btn-view-on-explorer").addEventListener("click", () => {
  window.open(`https://explorer.firstislamiccoin.com/#/address/${activeAddress()}`, "_blank", "noopener");
});
function renderAddressList() {
  const listEl = document.getElementById("address-list");
  listEl.innerHTML = state.addressIndices
    .map(
      (idx) => `
    <div class="addr-row ${idx === state.activeIndex ? "current" : ""}">
      <span class="mono addr-info">${state.addresses[idx]}</span>
      <button class="secondary" type="button" data-select="${idx}">${idx === state.activeIndex ? "Current" : "Use"}</button>
    </div>`
    )
    .join("");
  listEl.querySelectorAll("[data-select]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      state.activeIndex = Number(btn.dataset.select);
      await loadReceive();
    });
  });
}
document.getElementById("btn-new-address").addEventListener("click", async () => {
  const nextIndex = Math.max(...state.addressIndices) + 1;
  state.addressIndices.push(nextIndex);
  saveAddressIndices();
  await ensureKey(nextIndex);
  state.activeIndex = nextIndex;
  await loadReceive();
});
document.getElementById("btn-copy-address").addEventListener("click", () => {
  navigator.clipboard.writeText(activeAddress());
});

// ----------------------------------------------------------------- history

// Shared by loadHistory's render and the background-while-open new-tx
// check below, so there's exactly one place that knows how to combine
// per-address history into one deduplicated, sorted list.
async function fetchCombinedHistory() {
  const seen = new Set();
  const allTxs = [];
  for (const idx of state.addressIndices) {
    const resp = await state.gateway.history(state.addresses[idx]);
    for (const t of resp.transactions) {
      if (seen.has(t.txid)) continue;
      seen.add(t.txid);
      allTxs.push(t);
    }
  }
  allTxs.sort((a, b) => (b.height ?? Infinity) - (a.height ?? Infinity));
  return allTxs;
}

async function loadHistory() {
  const listEl = document.getElementById("history-list");
  listEl.innerHTML = '<p class="notice">Loading...</p>';
  try {
    const allTxs = await fetchCombinedHistory();
    state._lastHistory = allTxs;
    seenTxids(allTxs);
    if (allTxs.length === 0) {
      listEl.innerHTML = '<p class="notice">No transactions yet.</p>';
      return;
    }
    listEl.innerHTML = allTxs
      .map(
        (t) =>
          `<div class="tx-row mono" data-txid="${t.txid}">${t.txid}<br><span class="notice">${t.height ? `Height ${t.height}` : "Pending"}</span></div>`
      )
      .join("");
    listEl.querySelectorAll(".tx-row").forEach((row) => {
      row.addEventListener("click", () => openTxDetail(row.dataset.txid));
    });
  } catch (e) {
    listEl.innerHTML = `<p class="error">${e instanceof GatewayError ? e.message : "Could not reach the network."}</p>`;
  }
}

// ------------------------------------------------- live new-tx banner

function seenTxids(txs) {
  if (!state._seenTxids) state._seenTxids = new Set();
  for (const t of txs) state._seenTxids.add(t.txid);
}

function startTxPolling() {
  stopTxPolling();
  txPollHandle = setInterval(checkForNewTx, 30000);
}
function stopTxPolling() {
  if (txPollHandle) {
    clearInterval(txPollHandle);
    txPollHandle = null;
  }
}

// Polls only while Home/History is the visible screen (see showScreen)
// and only while unlocked. The very first check after unlock just seeds
// state._seenTxids silently (existing transactions aren't "new") --
// only a check that finds txids beyond an already-seeded set shows the
// banner. Errors are swallowed: this is a best-effort convenience, not
// a user-initiated action, so a flaky network shouldn't surface an
// error the user didn't ask to see.
async function checkForNewTx() {
  if (!state.mnemonic) return;
  try {
    const allTxs = await fetchCombinedHistory();
    if (!state._seenTxids) {
      seenTxids(allTxs);
      return;
    }
    const newOnes = allTxs.filter((t) => !state._seenTxids.has(t.txid));
    seenTxids(allTxs);
    if (newOnes.length > 0) showNewTxBanner(newOnes.length);
  } catch {
    // silent -- see comment above
  }
}

function showNewTxBanner(count) {
  const banner = document.getElementById("new-tx-banner");
  document.getElementById("new-tx-banner-text").textContent =
    count === 1 ? "1 new transaction" : `${count} new transactions`;
  banner.style.display = "flex";
}
document.getElementById("btn-new-tx-dismiss").addEventListener("click", () => {
  document.getElementById("new-tx-banner").style.display = "none";
});
document.getElementById("new-tx-banner-text").addEventListener("click", () => {
  document.getElementById("new-tx-banner").style.display = "none";
  showScreen("history");
});

// Exports the summary fields already on screen (txid, height/status, fee)
// -- not the full detail (inputs/outputs) for every transaction, which
// would mean one extra gateway call per row. A reasonable scope cut for
// what a CSV export is normally used for (a quick record, not a full
// audit trail).
document.getElementById("btn-export-csv").addEventListener("click", () => {
  const txs = state._lastHistory || [];
  if (txs.length === 0) return;
  const rows = [["txid", "status", "height", "fee_satoshis"]];
  for (const t of txs) {
    rows.push([t.txid, t.height && t.height > 0 ? "confirmed" : "pending", t.height ?? "", t.fee ?? ""]);
  }
  const csv = rows.map((r) => r.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `firstislamiccoin-history-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
});

async function openTxDetail(txid) {
  document.getElementById("tx-detail-overlay").style.display = "flex";
  document.getElementById("btn-tx-detail-explorer").onclick = () => {
    window.open(`https://explorer.firstislamiccoin.com/#/tx/${txid}`, "_blank", "noopener");
  };
  const bumpBtn = document.getElementById("btn-tx-detail-bump-fee");
  const bumpErrEl = document.getElementById("tx-detail-bump-error");
  const bumpOkEl = document.getElementById("tx-detail-bump-success");
  bumpBtn.style.display = "none";
  bumpErrEl.textContent = "";
  bumpOkEl.textContent = "";
  const bodyEl = document.getElementById("tx-detail-body");
  bodyEl.innerHTML = '<p class="notice">Loading...</p>';
  try {
    const tx = await state.gateway.tx(txid);
    if (!tx.height && loadSentTxLog()[txid]) {
      bumpBtn.style.display = "block";
      bumpBtn.onclick = async () => {
        bumpErrEl.textContent = "";
        bumpOkEl.textContent = "";
        bumpBtn.disabled = true;
        try {
          const newTxid = await bumpFee(txid);
          bumpOkEl.textContent = `Rebroadcast with a higher fee: ${newTxid}`;
          bumpBtn.style.display = "none";
        } catch (e) {
          bumpErrEl.textContent = e.message || "Could not bump fee.";
        } finally {
          bumpBtn.disabled = false;
        }
      };
    }
    const rows = [];
    rows.push(["Txid", tx.txid]);
    rows.push(["Status", tx.height ? `Confirmed, height ${tx.height} (${tx.confirmations} confirmations)` : "Pending"]);
    if (tx.is_coinstake && tx.reward_satoshis != null) {
      rows.push(["Type", "Staking reward (coinstake)"]);
      rows.push(["Reward", `${formatFic(tx.reward_satoshis)} FIC`]);
    }
    for (const vin of tx.vin) {
      rows.push(["Input", vin.coinbase ? "coinbase" : `${vin.txid.slice(0, 16)}...:${vin.vout}`]);
    }
    for (const vout of tx.vout) {
      const addr = vout.scriptPubKey?.address || vout.scriptPubKey?.addresses?.[0] || "(non-standard output)";
      rows.push(["Output", `${addr}: ${vout.value} FIC`]);
    }
    bodyEl.innerHTML = rows
      .map(([k, v]) => `<div class="kv-row"><span>${escapeHtml(k)}</span><span class="mono">${escapeHtml(String(v))}</span></div>`)
      .join("");
  } catch (e) {
    bodyEl.innerHTML = `<p class="error">${e instanceof GatewayError ? e.message : "Could not load transaction."}</p>`;
  }
}
document.getElementById("btn-tx-detail-close").addEventListener("click", () => {
  document.getElementById("tx-detail-overlay").style.display = "none";
});

// ----------------------------------------------------------------- staking

function stakingLoggedIn() {
  return !!state.stakeToken;
}

async function loadStaking() {
  document.getElementById("staking-auth-card").style.display = stakingLoggedIn() ? "none" : "block";
  document.getElementById("staking-status-card").style.display = stakingLoggedIn() ? "block" : "none";
  document.getElementById("push-card").style.display = stakingLoggedIn() && "serviceWorker" in navigator && "PushManager" in window ? "block" : "none";
  document.getElementById("price-alerts-card").style.display = stakingLoggedIn() && "serviceWorker" in navigator && "PushManager" in window ? "block" : "none";
  document.getElementById("staking-actions-card").style.display = stakingLoggedIn() ? "block" : "none";
  document.getElementById("referral-card").style.display = stakingLoggedIn() ? "block" : "none";
  if (!stakingLoggedIn()) return;
  loadPriceAlerts();
  try {
    const status = await state.gateway.stakingStatus(state.stakeToken);
    document.getElementById("stat-delegated").textContent = `${formatFic(status.delegated_amount)} FIC`;
    document.getElementById("stat-rewards").textContent = `${formatFic(status.accrued_rewards)} FIC`;
    document.getElementById("stat-rate").textContent = `${status.effective_monthly_rate_bp / 100}% / month`;
    document.getElementById("stat-fee").textContent = `${status.pool_fee_bp / 100}%`;
  } catch (e) {
    if (e instanceof GatewayError && e.code === "unauthorized") {
      state.stakeToken = null;
      sessionStorage.removeItem("fic_stake_token");
      loadStaking();
      return;
    }
  }
  try {
    const ref = await state.gateway.referralStatus(state.stakeToken);
    document.getElementById("stat-referral-code").textContent = ref.referral_code;
    document.getElementById("stat-referral-count").textContent = ref.referred_count;
    document.getElementById("stat-referral-available").textContent = `${formatFic(ref.available_satoshis)} FIC`;
  } catch (e) {
    // Non-fatal -- staking status above already handles auth expiry; a
    // referral-status hiccup shouldn't block the rest of the screen.
  }
  try {
    const { referrals } = await state.gateway.referralHistory(state.stakeToken);
    const listEl = document.getElementById("referral-history-list");
    if (!referrals.length) {
      listEl.innerHTML = `<p class="notice">No referrals yet.</p>`;
    } else {
      listEl.innerHTML = referrals
        .map((r) => {
          const joined = new Date(r.joined_at * 1000).toLocaleDateString();
          let status;
          if (r.amount_satoshis == null) status = "no funded deposit yet";
          else if (r.withdrawn) status = `${formatFic(r.amount_satoshis)} FIC earned (withdrawn)`;
          else status = `${formatFic(r.amount_satoshis)} FIC earned (available)`;
          return `<div class="stat-row"><span>${escapeHtml(r.referred_email_masked)} (joined ${joined})</span><span>${escapeHtml(status)}</span></div>`;
        })
        .join("");
    }
  } catch (e) {
    // Non-fatal, same reasoning as the referral-status fetch above.
  }
}

document.getElementById("btn-referral-copy").addEventListener("click", async () => {
  const code = document.getElementById("stat-referral-code").textContent;
  if (!code || code === "-") return;
  const btn = document.getElementById("btn-referral-copy");
  try {
    await navigator.clipboard.writeText(code);
    const original = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = original; }, 1500);
  } catch (e) {
    // Clipboard API can be unavailable (non-HTTPS, permissions) -- the
    // code is already visible as selectable text, so this is a
    // convenience, not the only way to get it.
  }
});

async function stakeAuth(action) {
  const errEl = document.getElementById("stake-auth-error");
  errEl.textContent = "";
  const email = document.getElementById("stake-email").value.trim();
  const password = document.getElementById("stake-password").value;
  try {
    let result;
    if (action === "login") {
      result = await state.gateway.login(email, password);
    } else {
      const kyc = {
        full_name: document.getElementById("stake-full-name").value.trim(),
        date_of_birth: document.getElementById("stake-dob").value,
        id_type: document.getElementById("stake-id-type").value,
        id_number: document.getElementById("stake-id-number").value.trim(),
        referral_code: document.getElementById("stake-referral-code").value.trim(),
      };
      result = await state.gateway.signup(email, password, kyc);
    }
    state.stakeToken = result.token;
    sessionStorage.setItem("fic_stake_token", result.token);
    loadStaking();
  } catch (e) {
    errEl.textContent = e instanceof GatewayError ? e.message : String(e);
  }
}
document.getElementById("btn-stake-login").addEventListener("click", () => stakeAuth("login"));
document.getElementById("btn-stake-signup").addEventListener("click", () => stakeAuth("signup"));

document.getElementById("btn-stake-deposit").addEventListener("click", async () => {
  const amountFic = parseFloat(document.getElementById("deposit-amount").value);
  const resultEl = document.getElementById("deposit-result");
  if (!amountFic || amountFic <= 0) return;
  document.getElementById("staking-action-error").textContent = "";
  try {
    const amountSatoshis = Math.round(amountFic * 1e8);
    const result = await state.gateway.stakingDeposit(state.stakeToken, amountSatoshis);
    resultEl.textContent = `Send funds to: ${result.deposit_address}`;
  } catch (e) {
    resultEl.textContent = "";
    document.getElementById("staking-action-error").textContent = e instanceof GatewayError ? e.message : String(e);
  }
});

document.getElementById("btn-stake-withdraw").addEventListener("click", async () => {
  const errEl = document.getElementById("staking-action-error");
  const okEl = document.getElementById("staking-action-success");
  errEl.textContent = "";
  okEl.textContent = "";
  const amountFic = parseFloat(document.getElementById("withdraw-amount").value);
  const toAddress = document.getElementById("withdraw-address").value.trim();
  if (!amountFic || amountFic <= 0 || !toAddress) {
    errEl.textContent = "Enter an amount and destination address.";
    return;
  }
  try {
    const amountSatoshis = Math.round(amountFic * 1e8);
    const result = await state.gateway.stakingWithdraw(state.stakeToken, amountSatoshis, toAddress);
    okEl.textContent = `Withdrawal broadcast: ${result.txid}`;
    loadStaking();
  } catch (e) {
    errEl.textContent = e instanceof GatewayError ? e.message : String(e);
  }
});

document.getElementById("btn-referral-withdraw").addEventListener("click", async () => {
  const errEl = document.getElementById("referral-action-error");
  const okEl = document.getElementById("referral-action-success");
  errEl.textContent = "";
  okEl.textContent = "";
  const toAddress = document.getElementById("referral-withdraw-address").value.trim();
  if (!toAddress) {
    errEl.textContent = "Enter a destination address.";
    return;
  }
  try {
    const result = await state.gateway.referralWithdraw(state.stakeToken, toAddress);
    okEl.textContent = `Withdrawal broadcast: ${result.txid}`;
    loadStaking();
  } catch (e) {
    errEl.textContent = e instanceof GatewayError ? e.message : String(e);
  }
});

// ------------------------------------------------------------ web push

// Converts the VAPID public key from the base64url encoding the Web
// Push spec transmits it in to the raw Uint8Array PushManager.subscribe
// actually wants.
function urlBase64ToUint8Array(base64url) {
  const padding = "=".repeat((4 - (base64url.length % 4)) % 4);
  const base64 = (base64url + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

document.getElementById("btn-enable-push").addEventListener("click", async () => {
  const errEl = document.getElementById("push-error");
  const okEl = document.getElementById("push-success");
  errEl.textContent = "";
  okEl.textContent = "";
  try {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      errEl.textContent = "Notification permission was not granted.";
      return;
    }
    const { public_key: vapidPublicKey } = await state.gateway.pushVapidPublicKey();
    const registration = await navigator.serviceWorker.register("./sw.js");
    await navigator.serviceWorker.ready;
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
      });
    }
    await state.gateway.pushSubscribe(state.stakeToken, subscription.toJSON());
    okEl.textContent = "Notifications enabled.";
  } catch (e) {
    errEl.textContent = e instanceof GatewayError ? e.message : String(e);
  }
});

// ------------------------------------------------------------ price alerts
//
// Delivered through the same push_subscriptions a logged-in user already
// has from "Enable notifications" above -- there is no separate opt-in
// step, just add a threshold. One-shot: the gateway's watcher marks an
// alert triggered the first time its condition is met and never re-fires
// it (see vps-gateway/price_alerts.py), so a fired alert simply stops
// appearing in the list below rather than showing as "done".
async function loadPriceAlerts() {
  const currentEl = document.getElementById("price-alerts-current");
  try {
    const { usd_per_fic } = await state.gateway.currentPrice();
    currentEl.textContent = `Current price: ~$${usd_per_fic.toLocaleString("en-US", { maximumFractionDigits: 6 })}`;
  } catch (e) {
    currentEl.textContent = "Current price: unavailable right now";
  }
  const listEl = document.getElementById("price-alert-list");
  try {
    const { alerts } = await state.gateway.priceAlertsList(state.stakeToken);
    const pending = alerts.filter((a) => !a.triggered_at);
    if (!pending.length) {
      listEl.innerHTML = `<p class="notice">No alerts set.</p>`;
    } else {
      listEl.innerHTML = pending
        .map(
          (a) =>
            `<div class="stat-row"><span>Price goes ${a.direction} $${a.threshold_usd}</span>` +
            `<button class="secondary" data-alert-id="${a.id}" data-action="delete-price-alert">Remove</button></div>`
        )
        .join("");
      listEl.querySelectorAll('[data-action="delete-price-alert"]').forEach((btn) => {
        btn.addEventListener("click", async () => {
          try {
            await state.gateway.priceAlertsDelete(state.stakeToken, btn.dataset.alertId);
            loadPriceAlerts();
          } catch (e) {
            document.getElementById("price-alert-error").textContent =
              e instanceof GatewayError ? e.message : String(e);
          }
        });
      });
    }
  } catch (e) {
    // Non-fatal, same reasoning as the referral-status fetch above.
  }
}

document.getElementById("btn-price-alert-add").addEventListener("click", async () => {
  const errEl = document.getElementById("price-alert-error");
  errEl.textContent = "";
  const direction = document.getElementById("price-alert-direction").value;
  const threshold = parseFloat(document.getElementById("price-alert-threshold").value);
  if (!threshold || threshold <= 0) {
    errEl.textContent = "Enter a USD price to alert at.";
    return;
  }
  try {
    await state.gateway.priceAlertsCreate(state.stakeToken, direction, threshold);
    document.getElementById("price-alert-threshold").value = "";
    loadPriceAlerts();
  } catch (e) {
    errEl.textContent = e instanceof GatewayError ? e.message : String(e);
  }
});

// ----------------------------------------------------------------- multisig
//
// UI on top of crypto.js's already-complete multisig primitives (see the
// comment above createMultisigRedeemScript there). Proposals are signed
// sequentially -- cosigner A signs the pasted-in JSON, copies the result
// to cosigner B, B pastes and signs the same object, and so on -- which
// is enough to reach any m-of-n threshold without needing an explicit
// "combine independently-signed copies" step (crypto.js's
// mergeMultisigProposals exists for that parallel-signing case but isn't
// wired into this UI; a deliberate scope cut, not an oversight).
//
// Index 0's key is used as this wallet's multisig identity, regardless of
// which address is "active" on the Receive screen -- a cosigner set
// should be built against a stable key, not one that changes every time
// someone taps "New address".

async function loadMultisig() {
  const key = await ensureKey(0);
  document.getElementById("my-pubkey").textContent = fic.bytesToHex(key.publicKey);
}

document.getElementById("btn-ms-create").addEventListener("click", async () => {
  const errEl = document.getElementById("ms-create-error");
  errEl.textContent = "";
  document.getElementById("ms-create-result").style.display = "none";
  try {
    const key = await ensureKey(0);
    const lines = document
      .getElementById("ms-pubkeys")
      .value.trim()
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    const cosignerPubkeys = lines.map((hex) => fic.hexToBytes(hex));
    const allPubkeys = [key.publicKey, ...cosignerPubkeys];
    const m = parseInt(document.getElementById("ms-m").value, 10);
    const redeemScript = fic.createMultisigRedeemScript(m, allPubkeys);
    const network = fic.NETWORKS[state.network];
    const address = fic.multisigAddress(redeemScript, network);
    document.getElementById("ms-redeem-script").textContent = fic.bytesToHex(redeemScript);
    document.getElementById("ms-address").textContent = address;
    document.getElementById("ms-create-result").style.display = "block";
    document.getElementById("ms-propose-address").value = address;
    document.getElementById("ms-propose-redeem").value = fic.bytesToHex(redeemScript);
  } catch (e) {
    errEl.textContent = String(e.message || e);
  }
});

document.getElementById("btn-ms-propose").addEventListener("click", async () => {
  const errEl = document.getElementById("ms-propose-error");
  errEl.textContent = "";
  try {
    const address = document.getElementById("ms-propose-address").value.trim();
    const redeemScriptHex = document.getElementById("ms-propose-redeem").value.trim();
    const toAddress = document.getElementById("ms-propose-to").value.trim();
    const amountFic = parseFloat(document.getElementById("ms-propose-amount").value);
    if (!address || !redeemScriptHex || !toAddress || !amountFic || amountFic <= 0) {
      errEl.textContent = "Fill in every field.";
      return;
    }
    const redeemScript = fic.hexToBytes(redeemScriptHex);
    const network = fic.NETWORKS[state.network];
    const decoded = fic.decodeAddress(toAddress, network);
    let outScript;
    if (decoded.type === fic.AddressType.p2pkh) outScript = fic.p2pkhScriptPubKey(decoded.hash);
    else if (decoded.type === fic.AddressType.p2sh) outScript = fic.p2shScriptPubKey(decoded.hash);
    else outScript = fic.p2wpkhScriptPubKey(decoded.hash);
    const amountSatoshis = BigInt(Math.round(amountFic * 1e8));

    const utxoResp = await state.gateway.utxos(address);
    const feeResp = await state.gateway.feeEstimate();
    const feeRate = BigInt(feeResp.fee_rate_sat_per_vbyte);

    let totalIn = 0n;
    const chosen = [];
    for (const u of utxoResp.utxos) {
      chosen.push(u);
      totalIn += BigInt(u.value);
      // Multisig scriptSigs run much larger than a plain P2PKH spend (one
      // DER signature per required cosigner, plus the redeem script
      // itself pushed in full) -- deliberately generous rather than
      // precise, the same "no real dynamic fee estimation" limitation
      // noted for the ordinary send flow above.
      const estimatedVsize = BigInt(10 + chosen.length * (redeemScript.length + 150) + 2 * 34);
      // feeRate is already sat/vbyte -- see the send handler's identical note.
      const feeSatoshis = feeRate * estimatedVsize;
      if (totalIn >= amountSatoshis + feeSatoshis) break;
    }
    const finalVsize = BigInt(10 + chosen.length * (redeemScript.length + 150) + 2 * 34);
    const feeSatoshis = feeRate * finalVsize;
    if (totalIn < amountSatoshis + feeSatoshis) {
      errEl.textContent = `Insufficient funds at this address: have ${formatFic(totalIn)}, need ${formatFic(amountSatoshis + feeSatoshis)}`;
      return;
    }
    const change = totalIn - amountSatoshis - feeSatoshis;
    const outputs = [{ scriptPubKey: outScript, valueSatoshis: Number(amountSatoshis) }];
    if (change > 0n) outputs.push({ scriptPubKey: fic.p2shScriptPubKey(fic.hash160(redeemScript)), valueSatoshis: Number(change) });

    const inputs = chosen.map((u) => ({
      txid: fic.hexToBytes(u.txid).reverse(),
      vout: u.vout,
      valueSatoshis: Number(u.value),
      redeemScript,
    }));
    const proposal = fic.createMultisigProposal({ inputs, outputs });
    document.getElementById("ms-proposal-json").value = JSON.stringify(proposal, null, 2);
  } catch (e) {
    errEl.textContent = String(e.message || e);
  }
});

document.getElementById("btn-ms-sign").addEventListener("click", async () => {
  const errEl = document.getElementById("ms-sign-error");
  const okEl = document.getElementById("ms-sign-success");
  errEl.textContent = "";
  okEl.textContent = "";
  try {
    const key = await ensureKey(0);
    const proposal = JSON.parse(document.getElementById("ms-proposal-json").value);
    fic.signMultisigProposal(proposal, key.privateKey, key.publicKey);
    document.getElementById("ms-proposal-json").value = JSON.stringify(proposal, null, 2);
    okEl.textContent = "Signed with your key. Send this JSON to the next cosigner, or finalize if enough signatures are collected.";
  } catch (e) {
    errEl.textContent = String(e.message || e);
  }
});

document.getElementById("btn-ms-broadcast").addEventListener("click", async () => {
  const errEl = document.getElementById("ms-sign-error");
  const okEl = document.getElementById("ms-sign-success");
  errEl.textContent = "";
  okEl.textContent = "";
  try {
    const proposal = JSON.parse(document.getElementById("ms-proposal-json").value);
    const rawTx = fic.finalizeMultisigTransaction(proposal);
    const result = await state.gateway.broadcast(fic.bytesToHex(rawTx));
    okEl.textContent = `Broadcast: ${result.txid}`;
  } catch (e) {
    errEl.textContent = e instanceof GatewayError ? e.message : String(e.message || e);
  }
});

// QR is a convenience for handing a proposal to another device -- not a
// replacement for the JSON textarea, which still works for anything a
// QR can't hold. ~1500 chars is a conservative cutoff for reliable
// scanning at a reasonable QR size/zoom, well under the encoder's own
// hard limit -- a multi-signature proposal with several inputs can
// exceed it, so this fails closed with a clear message rather than
// silently producing an unscannable QR.
const MS_QR_MAX_CHARS = 1500;
document.getElementById("btn-ms-show-qr").addEventListener("click", async () => {
  const errEl = document.getElementById("ms-qr-error");
  errEl.textContent = "";
  const json = document.getElementById("ms-proposal-json").value.trim();
  if (!json) {
    errEl.textContent = "Nothing to show -- paste or create a proposal first.";
    return;
  }
  if (json.length > MS_QR_MAX_CHARS) {
    errEl.textContent = `This proposal is too large for a reliable QR code (${json.length} characters). Share the JSON text directly instead.`;
    return;
  }
  document.getElementById("ms-qr-overlay").style.display = "flex";
  await qr.renderQr(document.getElementById("ms-qr-canvas"), json);
});
document.getElementById("btn-ms-qr-close").addEventListener("click", () => {
  document.getElementById("ms-qr-overlay").style.display = "none";
});
document.getElementById("btn-ms-scan-qr").addEventListener("click", () => {
  openQrScanner((text) => {
    document.getElementById("ms-proposal-json").value = text;
  });
});

// ------------------------------------------------------------- watch-only

function loadWatchList() {
  const raw = localStorage.getItem("fic_watch_list");
  return raw ? JSON.parse(raw) : [];
}
function saveWatchList(entries) {
  localStorage.setItem("fic_watch_list", JSON.stringify(entries));
}

async function loadWatch() {
  const entries = loadWatchList();
  const listEl = document.getElementById("watch-list");
  if (entries.length === 0) {
    listEl.innerHTML = '<p class="notice">No watched addresses yet.</p>';
    return;
  }
  listEl.innerHTML = entries
    .map(
      (e, i) => `
    <div class="book-row">
      <div class="book-info">
        <div class="book-label">${escapeHtml(e.label)}</div>
        <div class="book-address mono">${escapeHtml(e.address)}</div>
        <div class="notice small" id="watch-balance-${i}">Loading balance...</div>
      </div>
      <button class="secondary" type="button" data-explorer="${i}">Explorer</button>
      <button class="danger" type="button" data-remove="${i}">Remove</button>
    </div>`
    )
    .join("");
  listEl.querySelectorAll("[data-remove]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.dataset.remove);
      const updated = loadWatchList();
      updated.splice(idx, 1);
      saveWatchList(updated);
      loadWatch();
    });
  });
  listEl.querySelectorAll("[data-explorer]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const address = entries[Number(btn.dataset.explorer)].address;
      window.open(`https://explorer.firstislamiccoin.com/#/address/${address}`, "_blank", "noopener");
    });
  });
  // Sequential, not Promise.all/forEach-with-async -- the explorer's
  // balance lookup runs a scantxoutset RPC, which the node only allows
  // one of at a time. Firing these concurrently made the loser of the
  // race fail with "Scan already in progress" and show a false
  // "Could not fetch balance" for an address that was actually fine.
  for (let i = 0; i < entries.length; i++) {
    const el = document.getElementById(`watch-balance-${i}`);
    try {
      const balance = await state.gateway.balance(entries[i].address);
      const total = BigInt(balance.confirmed) + BigInt(balance.unconfirmed);
      el.textContent = `${formatFic(total)} FIC`;
    } catch (err) {
      el.textContent = "Could not fetch balance";
    }
  }
}
document.getElementById("btn-show-xpub").addEventListener("click", async () => {
  const btn = document.getElementById("btn-show-xpub");
  const outEl = document.getElementById("my-xpub-output");
  if (outEl.style.display !== "none") {
    outEl.style.display = "none";
    return;
  }
  btn.disabled = true;
  try {
    const network = fic.NETWORKS[state.network];
    outEl.value = await fic.deriveAccountXpub({ mnemonic: state.mnemonic, network });
    outEl.style.display = "block";
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("btn-watch-xpub-add").addEventListener("click", () => {
  const errEl = document.getElementById("watch-xpub-error");
  errEl.textContent = "";
  const label = document.getElementById("watch-xpub-label").value.trim();
  const xpub = document.getElementById("watch-xpub-input").value.trim();
  const count = Math.max(1, Math.min(50, Number(document.getElementById("watch-xpub-count").value) || 0));
  if (!label || !xpub) {
    errEl.textContent = "Enter a label and an xpub.";
    return;
  }
  try {
    const network = fic.NETWORKS[state.network];
    const groupId = xpub.slice(-8);
    const entries = loadWatchList();
    for (let i = 0; i < count; i++) {
      const address = fic.deriveXpubAddress({ xpub, network, index: i });
      entries.push({ label: `${label} #${i}`, address, xpubGroup: groupId });
    }
    saveWatchList(entries);
    document.getElementById("watch-xpub-label").value = "";
    document.getElementById("watch-xpub-input").value = "";
    loadWatch();
  } catch (e) {
    errEl.textContent = e.message || "Could not derive addresses from this xpub.";
  }
});

document.getElementById("btn-watch-add").addEventListener("click", () => {
  const label = document.getElementById("watch-label").value.trim();
  const address = document.getElementById("watch-address").value.trim();
  if (!label || !address) return;
  const entries = loadWatchList();
  entries.push({ label, address });
  saveWatchList(entries);
  document.getElementById("watch-label").value = "";
  document.getElementById("watch-address").value = "";
  loadWatch();
});

// ---------------------------------------------------------------- settings

// Called both when the Settings screen is freshly entered (clears any
// stale message from a previous visit) and after set/remove-PIN actions
// (must NOT clear the message those actions just set -- see
// refreshLockCardVisibility for the action-safe version of this).
function loadSettings() {
  refreshLockCardVisibility();
  document.getElementById("lock-settings-error").textContent = "";
  document.getElementById("lock-settings-success").textContent = "";
  refreshThemeButtons();
  refreshMsgSignAddressList();
}

function refreshMsgSignAddressList() {
  const sel = document.getElementById("msg-sign-address");
  sel.innerHTML = "";
  for (const idx of state.addressIndices) {
    const opt = document.createElement("option");
    opt.value = String(idx);
    opt.textContent = state.addresses[idx] || `(address #${idx})`;
    sel.appendChild(opt);
  }
  sel.value = String(state.activeIndex);
}

document.getElementById("btn-msg-sign").addEventListener("click", async () => {
  const errEl = document.getElementById("msg-sign-error");
  const resultEl = document.getElementById("msg-sign-result");
  errEl.textContent = "";
  resultEl.style.display = "none";
  const idx = Number(document.getElementById("msg-sign-address").value);
  const message = document.getElementById("msg-sign-input").value;
  if (!message) {
    errEl.textContent = "Enter a message to sign.";
    return;
  }
  try {
    const key = await ensureKey(idx);
    const signature = signMessage(key.privateKey, message);
    document.getElementById("msg-sign-output").value = signature;
    resultEl.style.display = "block";
  } catch (e) {
    errEl.textContent = e.message || "Could not sign message.";
  }
});

document.getElementById("btn-msg-verify").addEventListener("click", () => {
  const errEl = document.getElementById("msg-verify-error");
  const okEl = document.getElementById("msg-verify-success");
  errEl.textContent = "";
  okEl.textContent = "";
  const address = document.getElementById("msg-verify-address").value.trim();
  const message = document.getElementById("msg-verify-message").value;
  const signature = document.getElementById("msg-verify-signature").value.trim();
  if (!address || !signature) {
    errEl.textContent = "Enter an address and a signature to verify.";
    return;
  }
  try {
    const network = fic.NETWORKS[state.network];
    const valid = verifyMessage(address, signature, message, network);
    if (valid) okEl.textContent = "Valid signature -- this address signed this exact message.";
    else errEl.textContent = "Invalid signature -- does not match this address/message.";
  } catch (e) {
    errEl.textContent = e.message || "Could not verify signature.";
  }
});

// "system" (the default, no override) tracks the OS/browser preference
// via style.css's prefers-color-scheme media query; "dark"/"light" pin
// it explicitly via the data-theme attribute (see the inline script in
// index.html's <head> for why that's applied before first paint).
function applyTheme(choice) {
  if (choice === "dark" || choice === "light") {
    localStorage.setItem("fic_theme", choice);
    document.documentElement.dataset.theme = choice;
  } else {
    localStorage.removeItem("fic_theme");
    delete document.documentElement.dataset.theme;
  }
  refreshThemeButtons();
}
function refreshThemeButtons() {
  const current = localStorage.getItem("fic_theme") || "system";
  document.getElementById("btn-theme-system").classList.toggle("active", current === "system");
  document.getElementById("btn-theme-dark").classList.toggle("active", current === "dark");
  document.getElementById("btn-theme-light").classList.toggle("active", current === "light");
}
document.getElementById("btn-theme-system").addEventListener("click", () => applyTheme("system"));
document.getElementById("btn-theme-dark").addEventListener("click", () => applyTheme("dark"));
document.getElementById("btn-theme-light").addEventListener("click", () => applyTheme("light"));
function refreshLockCardVisibility() {
  const pinSet = storage.isPinSet();
  document.getElementById("lock-not-set").style.display = pinSet ? "none" : "block";
  document.getElementById("lock-is-set").style.display = pinSet ? "block" : "none";
}

document.getElementById("btn-set-pin").addEventListener("click", async () => {
  const errEl = document.getElementById("lock-settings-error");
  const okEl = document.getElementById("lock-settings-success");
  errEl.textContent = "";
  okEl.textContent = "";
  const pin = document.getElementById("set-pin").value;
  const confirmPin = document.getElementById("set-pin-confirm").value;
  if (pin.length < 4) {
    errEl.textContent = "PIN must be at least 4 characters.";
    return;
  }
  if (pin !== confirmPin) {
    errEl.textContent = "PINs don't match.";
    return;
  }
  await storage.setPin(state.mnemonic, pin);
  document.getElementById("set-pin").value = "";
  document.getElementById("set-pin-confirm").value = "";
  okEl.textContent = "PIN set. Your recovery phrase is now encrypted at rest.";
  refreshLockCardVisibility();
});

document.getElementById("btn-lock-now").addEventListener("click", () => {
  state.mnemonic = null;
  state.keys = {};
  state.addresses = {};
  document.getElementById("tabbar").style.display = "none";
  document.querySelectorAll(".screen").forEach((el) => el.classList.remove("active"));
  document.getElementById("lock-overlay").style.display = "flex";
});

document.getElementById("btn-remove-pin").addEventListener("click", () => {
  storage.removePin(state.mnemonic);
  document.getElementById("lock-settings-success").textContent = "PIN removed; recovery phrase is now stored in plain text.";
  document.getElementById("lock-settings-error").textContent = "";
  refreshLockCardVisibility();
});

async function switchNetwork(net) {
  state.network = net;
  localStorage.setItem("fic_network", net);
  refreshGateway();
  state.keys = {};
  state.addresses = {};
  await deriveAllKnownAddresses();
  showScreen("home");
}
document.getElementById("btn-net-mainnet").addEventListener("click", () => switchNetwork("mainnet"));
document.getElementById("btn-net-testnet").addEventListener("click", () => switchNetwork("testnet"));

document.getElementById("btn-wipe-wallet").addEventListener("click", () => {
  if (!confirm("This deletes your recovery phrase from this browser. If you have not backed it up, any funds will be permanently unrecoverable. Continue?")) return;
  localStorage.removeItem("fic_mnemonic");
  localStorage.removeItem("fic_mnemonic_encrypted");
  localStorage.removeItem("fic_address_indices_mainnet");
  localStorage.removeItem("fic_address_indices_testnet");
  localStorage.removeItem("fic_address_book");
  sessionStorage.removeItem("fic_stake_token");
  location.reload();
});
