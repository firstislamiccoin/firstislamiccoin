// Production default: empty string, so fetch() calls below (each of
// which already includes the "/api/..." prefix itself, e.g. "/api/stats")
// resolve same-origin -- meant to be reverse-proxied that way (see
// provisioning/explorer/nginx-example.conf in firstislamiccoin-infra) so
// the frontend and backend share an origin and need no CORS setup at all.
// Local development runs them on different ports (see README.md) --
// override via localStorage to a full origin like "http://127.0.0.1:8081"
// for that case, which is why CORS is still supported/enabled on the backend.
const API_BASE = localStorage.getItem("fic_explorer_api") || "";
const COIN = 100_000_000n;

function formatFic(fils) {
  const s = BigInt(fils);
  const neg = s < 0n;
  const abs = neg ? -s : s;
  const whole = abs / COIN;
  const frac = (abs % COIN).toString().padStart(8, "0");
  return `${neg ? "-" : ""}${whole.toLocaleString("en-US")}.${frac}`;
}

function formatTime(unixSeconds) {
  if (!unixSeconds) return "-";
  return new Date(unixSeconds * 1000).toISOString().replace("T", " ").replace(".000Z", " UTC");
}

function shorten(hash, n = 10) {
  if (!hash) return "-";
  return hash.length > n * 2 ? `${hash.slice(0, n)}…${hash.slice(-n)}` : hash;
}

async function api(path) {
  const resp = await fetch(API_BASE + path);
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || `Request failed (${resp.status})`);
  return data;
}

const app = document.getElementById("app");
const chainBadge = document.getElementById("chain-badge");

function render(html) {
  app.innerHTML = html;
}

function renderError(message) {
  render(`<div class="card error">${message}</div>`);
}

// ------------------------------------------------------------------ home

let homeRefreshTimer = null;
const HOME_REFRESH_MS = 20000;

function supplyChartSvg(points) {
  if (points.length < 2) return "";
  const w = 600, h = 140, pad = 8;
  const maxHeight = points[points.length - 1].height || 1;
  const maxSupply = BigInt(points[points.length - 1].total_supply_fils) || 1n;
  const minSupply = BigInt(points[0].total_supply_fils) || 0n;
  const span = maxSupply - minSupply || 1n;
  const coords = points.map((p) => {
    const x = pad + (p.height / maxHeight) * (w - 2 * pad);
    const frac = Number(((BigInt(p.total_supply_fils) - minSupply) * 1000n) / span) / 1000;
    const y = h - pad - frac * (h - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return `
    <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px;">
      <polyline points="${coords.join(" ")}" fill="none" stroke="#D4AF37" stroke-width="2" />
    </svg>`;
}

async function renderHome() {
  if (homeRefreshTimer) { clearInterval(homeRefreshTimer); homeRefreshTimer = null; }
  render('<div class="notice">Loading…</div>');
  try {
    const [stats, supply] = await Promise.all([api("/api/stats"), api("/api/supply-series")]);
    chainBadge.textContent = stats.chain;
    render(`
      <div class="stats-grid">
        <div class="stat-tile"><div class="label">Height</div><div class="value">${stats.height.toLocaleString("en-US")}</div></div>
        <div class="stat-tile"><div class="label">Difficulty</div><div class="value">${Number(stats.difficulty).toPrecision(4)}</div></div>
        <div class="stat-tile"><div class="label">Block reward</div><div class="value">${formatFic(stats.fixed_reward_fils)} + fees</div></div>
        <div class="stat-tile"><div class="label">Total supply</div><div class="value">${formatFic(stats.total_supply_fils)} FIC</div></div>
      </div>
      <div class="card">
        <div class="detail-row"><span class="k">Best block</span><span class="v mono"><a href="#/block/${stats.best_block_hash}">${shorten(stats.best_block_hash)}</a></span></div>
        <div class="detail-row"><span class="k">Chain</span><span class="v">${stats.chain}</span></div>
        <div class="detail-row"><span class="k">Genesis premine</span><span class="v">${formatFic(stats.premine_total_fils)} FIC</span></div>
        <div class="detail-row"><span class="k">Fixed reward per block</span><span class="v">${formatFic(stats.fixed_reward_fils)} FIC + fees</span></div>
        <div class="detail-row"><span class="k">Annual emission (constant)</span><span class="v">${formatFic(stats.annual_emission_fils)} FIC/yr</span></div>
      </div>
      <div class="card">
        <h3 style="margin-top:0">Total supply</h3>
        ${supplyChartSvg(supply.points)}
        <p class="notice">Exact at every height: premine + 10 FIC &times; blocks staked since genesis. See <a href="#/staking">staking stats</a> for emission detail.</p>
      </div>
      <div class="card">
        <a href="#/richlist">View rich list &rarr;</a>
      </div>
      <div class="card">
        <p class="notice">Enter a block height, block hash, transaction id, or address above to look it up.
        This page auto-refreshes every ${HOME_REFRESH_MS / 1000}s.</p>
      </div>
    `);
    homeRefreshTimer = setInterval(() => {
      if (location.hash === "" || location.hash === "#/") renderHome();
    }, HOME_REFRESH_MS);
  } catch (e) {
    renderError(e.message);
  }
}

// --------------------------------------------------------------- richlist

async function renderRichlist() {
  render('<div class="notice">Loading (this scans recent blocks, may take a moment)…</div>');
  try {
    const data = await api("/api/richlist?limit=25");
    render(`
      <div class="card">
        <h2 style="margin-top:0">Rich list</h2>
        <p class="notice">Computed from blocks ${data.scanned_from_height}&ndash;${data.scanned_to_height}${data.truncated ? " (older history not included -- see API note)" : ""}.</p>
        <table>
          <thead><tr><th>#</th><th>Address</th><th>Balance</th></tr></thead>
          <tbody>
            ${data.addresses.map((a, i) => `
              <tr>
                <td>${i + 1}</td>
                <td class="mono"><a href="#/address/${a.address}">${shorten(a.address, 14)}</a></td>
                <td>${formatFic(a.balance_fils)} FIC</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>
    `);
  } catch (e) {
    renderError(e.message);
  }
}

// --------------------------------------------------------------- staking

async function renderStaking() {
  render('<div class="notice">Loading…</div>');
  try {
    const s = await api("/api/staking-stats");
    render(`
      <div class="card">
        <h2 style="margin-top:0">Staking statistics</h2>
        <div class="detail-row"><span class="k">Current block reward</span><span class="v">${s.current_block_reward_fic} FIC + fees, fixed</span></div>
        <div class="detail-row"><span class="k">Annual emission</span><span class="v">${s.annual_emission_fic.toLocaleString("en-US")} FIC/yr</span></div>
        <div class="detail-row"><span class="k">Blocks/day (measured)</span><span class="v">${s.blocks_per_day ?? "-"} ${s.measured_over_blocks ? `(last ${s.measured_over_blocks} blocks)` : ""}</span></div>
        <div class="detail-row"><span class="k">Blocks/day (target)</span><span class="v">${s.target_blocks_per_day}</span></div>
        <div class="detail-row"><span class="k">Active stake weight</span><span class="v">not available</span></div>
        <div class="detail-row"><span class="k">Delegated (P2CS/cold) staking</span><span class="v">not built yet</span></div>
      </div>
      <div class="card">
        <p class="notice">${s.note}</p>
      </div>
    `);
  } catch (e) {
    renderError(e.message);
  }
}

// ----------------------------------------------------------------- block

async function renderBlock(ident) {
  render('<div class="notice">Loading…</div>');
  try {
    const b = await api(`/api/block/${ident}`);
    const badge = b.is_genesis
      ? '<span class="badge genesis">genesis</span>'
      : b.is_proof_of_stake ? '<span class="badge pos">PoS</span>' : '<span class="badge pow">PoW</span>';
    render(`
      <div class="card">
        <h2 style="margin-top:0">Block ${b.height} ${badge}</h2>
        <div class="detail-row"><span class="k">Hash</span><span class="v mono">${b.hash}</span></div>
        <div class="detail-row"><span class="k">Time</span><span class="v">${formatTime(b.time)}</span></div>
        <div class="detail-row"><span class="k">Difficulty</span><span class="v">${b.difficulty}</span></div>
        <div class="detail-row"><span class="k">Bits</span><span class="v mono">${b.bits}</span></div>
        <div class="detail-row"><span class="k">Merkle root</span><span class="v mono">${shorten(b.merkleroot)}</span></div>
        <div class="detail-row"><span class="k">Previous block</span><span class="v mono">${b.previousblockhash ? `<a href="#/block/${b.previousblockhash}">${shorten(b.previousblockhash)}</a>` : "-"}</span></div>
        <div class="detail-row"><span class="k">Next block</span><span class="v mono">${b.nextblockhash ? `<a href="#/block/${b.nextblockhash}">${shorten(b.nextblockhash)}</a>` : "(tip)"}</span></div>
      </div>
      <div class="card">
        <h3 style="margin-top:0">Transactions (${b.tx_count})</h3>
        <table>
          <thead><tr><th>Txid</th><th>Type</th><th>Outputs</th></tr></thead>
          <tbody>
            ${b.transactions.map((t) => `
              <tr>
                <td class="mono"><a href="#/tx/${t.txid}">${shorten(t.txid)}</a></td>
                <td>${t.is_coinbase ? `<span class="badge ${b.is_genesis ? "genesis" : "coinbase"}">${b.is_genesis ? "genesis" : "coinbase"}</span>` : t.is_coinstake ? '<span class="badge pos">coinstake</span>' : "transfer"}</td>
                <td>${formatFic(t.output_total_fils)} FIC</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>
    `);
  } catch (e) {
    renderError(e.message);
  }
}

// -------------------------------------------------------------------- tx

async function renderTx(txid) {
  render('<div class="notice">Loading…</div>');
  try {
    const t = await api(`/api/tx/${txid}`);
    const typeBadge = t.is_coinbase
      ? '<span class="badge coinbase">coinbase</span>'
      : t.is_coinstake
        ? '<span class="badge pos">coinstake</span>'
        : "transfer";
    render(`
      <div class="card">
        <h2 style="margin-top:0">Transaction ${typeBadge}</h2>
        <div class="detail-row"><span class="k">Txid</span><span class="v mono">${t.txid}</span></div>
        <div class="detail-row"><span class="k">Block</span><span class="v">${t.height !== null ? `<a href="#/block/${t.blockhash}">${t.height}</a>` : "unconfirmed"}</span></div>
        <div class="detail-row"><span class="k">Confirmations</span><span class="v">${t.confirmations}</span></div>
        <div class="detail-row"><span class="k">Time</span><span class="v">${formatTime(t.time)}</span></div>
        ${t.reward_fils !== null ? `<div class="detail-row"><span class="k">Staking reward (fixed + fees)</span><span class="v">${formatFic(t.reward_fils)} FIC</span></div>` : ""}
        ${t.reward_fees_fils !== null ? `<div class="detail-row"><span class="k">&nbsp;&nbsp;of which fees</span><span class="v">${formatFic(t.reward_fees_fils)} FIC</span></div>` : ""}
      </div>
      <div class="card">
        <h3 style="margin-top:0">Inputs (${t.vin.length})</h3>
        ${t.vin.map((vin) => vin.coinbase
          ? `<div class="detail-row"><span class="k">Coinbase</span><span class="v mono">${vin.coinbase}</span></div>`
          : `<div class="detail-row"><span class="k mono">${shorten(vin.txid)}:${vin.vout}</span><span class="v"></span></div>`
        ).join("")}
      </div>
      <div class="card">
        <h3 style="margin-top:0">Outputs (${t.vout.length})</h3>
        ${t.vout.map((vout) => `
          <div class="detail-row">
            <span class="k mono">${vout.scriptPubKey.address || vout.scriptPubKey.type || "(no address)"}</span>
            <span class="v">${formatFic(Math.round(vout.value * Number(COIN)))} FIC</span>
          </div>`).join("")}
      </div>
    `);
  } catch (e) {
    renderError(e.message);
  }
}

// --------------------------------------------------------------- address

async function renderAddress(address) {
  render('<div class="notice">Loading…</div>');
  try {
    const a = await api(`/api/address/${address}`);
    render(`
      <div class="card">
        <h2 style="margin-top:0">Address</h2>
        <div class="detail-row"><span class="k">Address</span><span class="v mono">${a.address}</span></div>
        <div class="detail-row"><span class="k">Balance</span><span class="v">${formatFic(a.balance_fils)} FIC</span></div>
        <div class="detail-row"><span class="k">UTXOs</span><span class="v">${a.utxo_count}</span></div>
      </div>
      <div class="card">
        <p class="notice">${a.note}</p>
      </div>
      <div class="card">
        <h3 style="margin-top:0">Unspent outputs</h3>
        <table>
          <thead><tr><th>Txid</th><th>Height</th><th>Value</th></tr></thead>
          <tbody>
            ${a.utxos.map((u) => `
              <tr>
                <td class="mono"><a href="#/tx/${u.txid}">${shorten(u.txid)}</a>:${u.vout}</td>
                <td>${u.height !== null ? `<a href="#/block/${u.height}">${u.height}</a>` : "-"}</td>
                <td>${formatFic(u.value_fils)} FIC ${u.is_coinbase_or_coinstake ? '<span class="badge coinbase">coinbase/stake</span>' : ""}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>
    `);
  } catch (e) {
    renderError(e.message);
  }
}

// ------------------------------------------------------------------ router

async function route() {
  const hash = location.hash.replace(/^#\/?/, "");
  const [kind, ...rest] = hash.split("/");
  const id = rest.join("/");
  if (kind !== "" && homeRefreshTimer) { clearInterval(homeRefreshTimer); homeRefreshTimer = null; }
  if (!kind) return renderHome();
  if (kind === "block") return renderBlock(id);
  if (kind === "tx") return renderTx(id);
  if (kind === "address") return renderAddress(id);
  if (kind === "richlist") return renderRichlist();
  if (kind === "staking") return renderStaking();
  renderError("Unknown page");
}

window.addEventListener("hashchange", route);
route();

// ------------------------------------------------------------------ search

async function doSearch() {
  const q = document.getElementById("search-input").value.trim();
  if (!q) return;
  try {
    const result = await api(`/api/search?q=${encodeURIComponent(q)}`);
    location.hash = `#/${result.type}/${result.id}`;
  } catch (e) {
    renderError(e.message);
  }
}
document.getElementById("search-btn").addEventListener("click", doSearch);
document.getElementById("search-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") doSearch();
});
