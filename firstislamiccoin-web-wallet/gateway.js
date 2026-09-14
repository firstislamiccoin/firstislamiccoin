// HTTP client for the firstislamiccoin-staking-service gateway
// (../firstislamiccoin-staking-service/, Phase 6), matching
// ../firstislamiccoin-mobile/docs/mobile-api.md exactly -- mirrors
// firstislamiccoin-mobile/lib/services/gateway_api.dart.
export class GatewayError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

export class Gateway {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
  }

  async _get(path, { auth } = {}) {
    const headers = auth ? { Authorization: `Bearer ${auth}` } : {};
    const resp = await fetch(this.baseUrl + path, { headers });
    return this._decode(resp);
  }

  async _post(path, body, { auth } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (auth) headers.Authorization = `Bearer ${auth}`;
    const resp = await fetch(this.baseUrl + path, { method: "POST", headers, body: JSON.stringify(body) });
    return this._decode(resp);
  }

  async _decode(resp) {
    const data = await resp.json();
    if (!resp.ok) {
      const err = data.error || {};
      throw new GatewayError(err.code || "unknown-error", err.message || `Request failed (${resp.status})`);
    }
    return data;
  }

  networkStatus() { return this._get("/v1/network/status"); }
  balance(address) { return this._get(`/v1/address/${address}/balance`); }
  utxos(address) { return this._get(`/v1/address/${address}/utxos`); }
  history(address, limit = 50) { return this._get(`/v1/address/${address}/history?limit=${limit}`); }
  tx(txid) { return this._get(`/v1/tx/${txid}`); }
  broadcast(rawTxHex) { return this._post("/v1/tx/broadcast", { raw_tx_hex: rawTxHex }); }
  feeEstimate(targetBlocks = 6) { return this._get(`/v1/fee-estimate?target_blocks=${targetBlocks}`); }

  signup(email, password, kyc) { return this._post("/v1/auth/signup", { email, password, ...kyc }); }
  login(email, password) { return this._post("/v1/auth/login", { email, password }); }

  stakingStatus(token) { return this._get("/v1/staking/status", { auth: token }); }
  stakingDeposit(token, amountSatoshis) {
    return this._post("/v1/staking/deposit", { amount: String(amountSatoshis) }, { auth: token });
  }
  stakingWithdraw(token, amountSatoshis, toAddress) {
    return this._post("/v1/staking/withdraw", { amount: String(amountSatoshis), to_address: toAddress }, { auth: token });
  }

  pushVapidPublicKey() { return this._get("/v1/push/vapid-public-key"); }
  pushSubscribe(token, subscription) { return this._post("/v1/push/subscribe", subscription, { auth: token }); }

  referralStatus(token) { return this._get("/v1/referral/status", { auth: token }); }
  referralHistory(token) { return this._get("/v1/referral/history", { auth: token }); }
  referralWithdraw(token, toAddress) {
    return this._post("/v1/referral/withdraw", { to_address: toAddress }, { auth: token });
  }

  currentPrice() { return this._get("/v1/price"); }
  priceAlertsList(token) { return this._get("/v1/price-alerts/web", { auth: token }); }
  priceAlertsCreate(token, direction, thresholdUsd) {
    return this._post("/v1/price-alerts/web", { direction, threshold_usd: thresholdUsd }, { auth: token });
  }
  async priceAlertsDelete(token, alertId) {
    const headers = { Authorization: `Bearer ${token}` };
    const resp = await fetch(`${this.baseUrl}/v1/price-alerts/web/${alertId}`, { method: "DELETE", headers });
    return this._decode(resp);
  }
}
