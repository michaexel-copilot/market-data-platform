"""Management console — serves the single-page administration UI."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["console"])

_CONSOLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Market Data — Management Console</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; background: #f5f5f5; color: #1a1a1a; height: 100vh; display: flex; flex-direction: column; }

    /* ── Top bar ── */
    #TOP_BAR { background: #1a1a2e; color: #fff; padding: 12px 20px; display: flex; align-items: center; gap: 16px; }
    #TOP_BAR h1 { font-size: 1rem; font-weight: 600; letter-spacing: 0.05em; }

    /* ── SEG_ASSET_CLASS + ACT_BTN_LIST row ── */
    #TOP_BAR { justify-content: space-between; }
    #SEG_ASSET_CLASS { display: flex; gap: 4px; }
    #SEG_ASSET_CLASS button {
      padding: 6px 14px; border: 1px solid #444; border-radius: 4px;
      background: transparent; color: #ccc; cursor: pointer; font-size: 0.85rem;
    }
    #SEG_ASSET_CLASS button.active {
      background: #e94560; border-color: #e94560; color: #fff; font-weight: 600;
    }

    /* ── SEG_SOURCE_FILTER ── */
    #SEG_SOURCE_FILTER { display: flex; gap: 4px; margin-top: 6px; }
    #SEG_SOURCE_FILTER button {
      padding: 4px 12px; border: 1px solid #555; border-radius: 4px;
      background: transparent; color: #aaa; cursor: pointer; font-size: 0.78rem;
    }
    #SEG_SOURCE_FILTER button.active {
      background: #16213e; border-color: #a0c4ff; color: #a0c4ff; font-weight: 600;
    }

    /* ── ACT_BTN_LIST ── */
    #ACT_BTN_LIST { display: flex; gap: 8px; align-items: center; }
    #BTN_MIGRATE_FUNDAMENTALS {
      padding: 6px 14px; background: #f39c12; color: #fff;
      border: none; border-radius: 4px; cursor: pointer; font-size: 0.85rem; font-weight: 600;
    }
    #BTN_MIGRATE_FUNDAMENTALS:hover { background: #e67e22; }
    #BTN_MIGRATE_FUNDAMENTALS:disabled { background: #bbb; cursor: not-allowed; }

    /* ── Main layout ── */
    #MAIN_LAYOUT { display: flex; flex: 1; overflow: hidden; }

    /* ── PANE_INSTRUMENT_LIST ── */
    #PANE_INSTRUMENT_LIST {
      width: 260px; min-width: 200px; background: #fff;
      border-right: 1px solid #e0e0e0; display: flex; flex-direction: column; overflow: hidden;
    }
    #PANE_INSTRUMENT_LIST .list-top { flex-shrink: 0; }
    #PANE_INSTRUMENT_LIST .list-header {
      padding: 10px 14px; font-size: 0.75rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.08em; color: #888;
      border-bottom: 1px solid #eee;
    }
    #PANE_INSTRUMENT_LIST ul { list-style: none; flex: 1; overflow-y: auto; margin: 0; padding: 0; }
    #PANE_INSTRUMENT_LIST li.ITEM_INSTRUMENT {
      padding: 10px 14px; cursor: pointer; border-bottom: 1px solid #f0f0f0;
    }
    #PANE_INSTRUMENT_LIST li.ITEM_INSTRUMENT:hover { background: #f8f8f8; }
    #PANE_INSTRUMENT_LIST li.ITEM_INSTRUMENT.selected { background: #e8f0fe; border-left: 3px solid #1a73e8; }
    #PANE_INSTRUMENT_LIST li.ITEM_INSTRUMENT .ticker { font-weight: 600; font-size: 0.9rem; }
    #PANE_INSTRUMENT_LIST li.ITEM_INSTRUMENT .name { font-size: 0.78rem; color: #666; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    #PANE_INSTRUMENT_LIST .list-empty { padding: 20px 14px; color: #999; font-size: 0.85rem; }
    #INP_INSTRUMENT_FILTER {
      width: 100%; box-sizing: border-box; padding: 7px 10px;
      border: none; border-bottom: 1px solid #e0e0e0; font-size: 0.85rem;
      outline: none; background: #fafafa;
    }
    #INP_INSTRUMENT_FILTER:focus { background: #fff; border-bottom-color: #1a73e8; }

    /* ── PANE_CONTENT (right side) ── */
    #PANE_CONTENT { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

    /* ── ACTION_BAR ── */
    #ACTION_BAR {
      background: #fff; border-bottom: 1px solid #e0e0e0;
      padding: 10px 20px; display: flex; align-items: center; gap: 10px;
    }
    #BTN_UPDATE_FUNDAMENTALS {
      padding: 7px 16px; background: #1a73e8; color: #fff;
      border: none; border-radius: 4px; cursor: pointer; font-size: 0.85rem;
    }
    #BTN_UPDATE_FUNDAMENTALS:disabled { background: #bbb; cursor: not-allowed; }
    #BTN_UPDATE_OHLCV {
      padding: 7px 16px; background: #0f9d58; color: #fff;
      border: none; border-radius: 4px; cursor: pointer; font-size: 0.85rem;
    }
    #BTN_UPDATE_OHLCV:disabled { background: #bbb; cursor: not-allowed; }
    #DDL_OHLCV_PERIOD {
      padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px;
      font-size: 0.85rem; background: #fff;
    }
    #DDL_OHLCV_PERIOD:disabled { background: #f0f0f0; color: #aaa; cursor: not-allowed; }
    #INP_BEST_SMA_POS_USD {
      width: 120px; padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px;
      font-size: 0.85rem; background: #fff;
    }
    #INP_BEST_SMA_POS_USD:disabled { background: #f0f0f0; color: #aaa; cursor: not-allowed; }

    /* ── PANE_FUNDAMENTALS ── */
    #PANE_FUNDAMENTALS { flex: 1; overflow-y: auto; padding: 24px; }
    #PANE_FUNDAMENTALS .placeholder { color: #aaa; font-size: 0.95rem; margin-top: 40px; text-align: center; }
    #PANE_FUNDAMENTALS .error { color: #c00; font-size: 0.9rem; }
    #PANE_FUNDAMENTALS h2 { font-size: 1.1rem; margin-bottom: 16px; }
    #PANE_FUNDAMENTALS table { border-collapse: collapse; width: 100%; max-width: 600px; }
    #PANE_FUNDAMENTALS td { padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 0.88rem; }
    #PANE_FUNDAMENTALS td:first-child { font-weight: 600; color: #555; width: 40%; }
    #PANE_FUNDAMENTALS h3 { font-size: 0.9rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #888; margin: 24px 0 8px; }
    #PANE_FUNDAMENTALS .ohlcv-range-table th { padding: 6px 12px; font-size: 0.8rem; font-weight: 700; text-align: left; background: #f5f5f5; border-bottom: 2px solid #e0e0e0; }
    #PANE_FUNDAMENTALS .ohlcv-range-table td { width: auto; font-weight: normal; color: inherit; font-family: monospace; font-size: 0.83rem; }
    #PANE_FUNDAMENTALS .ohlcv-range-table td:first-child { font-weight: 700; color: #333; width: 60px; font-family: inherit; }
    #PANE_FUNDAMENTALS .avail-table th { padding: 6px 12px; font-size: 0.8rem; font-weight: 700; text-align: center; background: #f5f5f5; border-bottom: 2px solid #e0e0e0; }
    #PANE_FUNDAMENTALS .avail-table th:first-child { text-align: left; }
    #PANE_FUNDAMENTALS .avail-table td { text-align: center; width: auto; font-weight: normal; color: inherit; }
    #PANE_FUNDAMENTALS .avail-table td:first-child { text-align: left; font-weight: 700; font-family: monospace; }
    #PANE_FUNDAMENTALS .avail-yes { color: #1e7e34; }
    #PANE_FUNDAMENTALS .avail-no  { color: #bbb; }
    #PANE_FUNDAMENTALS .import-ok { color: #0f5132; background: #d1e7dd; border: 1px solid #badbcc; border-radius: 4px; padding: 8px 12px; font-size: 0.88rem; margin-bottom: 12px; }
  </style>
</head>
<body>

<div id="TOP_BAR">
  <h1>Market Data — Management Console</h1>
  <div id="SEG_ASSET_CLASS">
    <button data-class="crypto" class="active">Crypto</button>
    <button data-class="equity">Equity</button>
    <button data-class="etf">ETF</button>
    <button data-class="fx">FX</button>
    <button data-class="commodity">Commodity</button>
  </div>
  <div id="SEG_SOURCE_FILTER">
    <button data-source="eodhd" class="active">eodhd</button>
    <button data-source="hl" class="active">hl</button>
    <button data-source="yahoo-finance">yahoo-finance</button>
    <button data-source="cmc">cmc</button>
  </div>
  <div id="ACT_BTN_LIST">
    <button id="BTN_MIGRATE_FUNDAMENTALS">Migrate Fundamental Data</button>
  </div>
</div>

<div id="MAIN_LAYOUT">

  <div id="PANE_INSTRUMENT_LIST">
    <div class="list-top">
      <div class="list-header">Instruments</div>
      <input id="INP_INSTRUMENT_FILTER" type="text" placeholder="Filter instruments…" autocomplete="off">
    </div>
    <ul id="INSTRUMENT_LIST_UL"></ul>
  </div>

  <div id="PANE_CONTENT">
    <div id="ACTION_BAR">
      <button id="BTN_UPDATE_FUNDAMENTALS" disabled>Update Fundamental Data</button>
      <button id="BTN_UPDATE_OHLCV" disabled>Update OHLCV Data</button>
      <select id="DDL_OHLCV_PERIOD" disabled>
        <option value="1m">1m</option>
        <option value="5m">5m</option>
        <option value="1h">1h</option>
        <option value="1d" selected>1d</option>
        <option value="1w">1w</option>
        <option value="1mo">1mo</option>
        <option value="1y">1y</option>
      </select>
      <input id="INP_BEST_SMA_POS_USD" type="number" min="1" step="1" value="100" disabled>
      <button id="BTN_COMPUTE_BEST_SMA_V2" disabled>Compute BEST SMA Exit V1</button>
    </div>
    <div id="PANE_FUNDAMENTALS">
      <p class="placeholder">Select an instrument to view details</p>
    </div>
  </div>

</div>

<script>
  // ── State ──
  let selectedInstrumentId = null;
  let activeSources = new Set(['eodhd', 'hl']);

  // ── Element references ──
  let allLoadedInstruments = [];

  // ── Element references ──
  const segButtons        = document.querySelectorAll('#SEG_ASSET_CLASS button');
  const srcButtons        = document.querySelectorAll('#SEG_SOURCE_FILTER button');
  const listUl            = document.getElementById('INSTRUMENT_LIST_UL');
  const inpFilter         = document.getElementById('INP_INSTRUMENT_FILTER');
  const fundamentalsPane  = document.getElementById('PANE_FUNDAMENTALS');
  const btnFundamentals   = document.getElementById('BTN_UPDATE_FUNDAMENTALS');
  const btnOhlcv          = document.getElementById('BTN_UPDATE_OHLCV');
  const ddlPeriod         = document.getElementById('DDL_OHLCV_PERIOD');
  const inpBestSmaPosUsd  = document.getElementById('INP_BEST_SMA_POS_USD');
  const btnBestSmaV2      = document.getElementById('BTN_COMPUTE_BEST_SMA_V2');
  const btnMigrate        = document.getElementById('BTN_MIGRATE_FUNDAMENTALS');

  // ── Asset-class selector ──
  segButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      segButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedInstrumentId = null;
      setActionsEnabled(false);
      fundamentalsPane.innerHTML = '<p class="placeholder">Select an instrument to view details</p>';
      inpFilter.value = '';
      loadInstruments(btn.dataset.class);
    });
  });

  // ── Source-filter selector ──
  srcButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const src = btn.dataset.source;
      if (activeSources.has(src) && activeSources.size === 1) return; // keep at least one active
      if (activeSources.has(src)) {
        activeSources.delete(src);
        btn.classList.remove('active');
      } else {
        activeSources.add(src);
        btn.classList.add('active');
      }
      const activeClass = document.querySelector('#SEG_ASSET_CLASS button.active')?.dataset.class || 'crypto';
      loadInstruments(activeClass);
    });
  });

  // ── Load instrument list ──
  async function loadInstruments(assetClass) {
    listUl.innerHTML = '<li class="list-empty">Loading…</li>';
    try {
      let allItems = [];
      let page = 1;
      const sourcesParam = activeSources.size > 0 ? `&sources=${[...activeSources].join(',')}` : '';
      while (true) {
        const res = await fetch(`/v1/instruments?asset_class=${assetClass}&is_active=true&page_size=1000&page=${page}${sourcesParam}`);
        const data = await res.json();
        const items = data.items || [];
        allItems = allItems.concat(items);
        if (data.next_page == null) break;
        page = data.next_page;
      }
      listUl.innerHTML = '';
      if (allItems.length === 0) {
        allLoadedInstruments = [];
        listUl.innerHTML = activeSources.size > 0
          ? '<li class="list-empty">No instruments found. Run import-source-intersection to populate source data.</li>'
          : '<li class="list-empty">No instruments found</li>';
        return;
      }
      allLoadedInstruments = allItems;
      renderInstrumentList(allLoadedInstruments);
      // Auto-select BTC on first load
      const btcInst = allLoadedInstruments.find(i => (i.ticker || '').toUpperCase() === 'BTC');
      if (btcInst) {
        const btcLi = listUl.querySelector(`li[data-id="${CSS.escape(btcInst.instrument_id)}"]`);
        if (btcLi) btcLi.click();
      }
    } catch (e) {
      listUl.innerHTML = `<li class="list-empty">Error loading instruments</li>`;
    }
  }

  // ── Render filtered instrument list ──
  function renderInstrumentList(instruments) {
    listUl.innerHTML = '';
    if (instruments.length === 0) {
      listUl.innerHTML = '<li class="list-empty">No instruments found</li>';
      return;
    }
    instruments.forEach(inst => {
      const li = document.createElement('li');
      li.className = 'ITEM_INSTRUMENT';
      li.dataset.id = inst.instrument_id;
      li.innerHTML = `<div class="ticker">${escHtml(inst.ticker)}</div><div class="name">${escHtml(inst.full_name || '')}</div>`;
      li.addEventListener('click', () => selectInstrument(li, inst));
      listUl.appendChild(li);
    });
  }

  // ── Filter input handler ──
  inpFilter.addEventListener('input', () => {
    const q = inpFilter.value.trim().toLowerCase();
    const filtered = q
      ? allLoadedInstruments.filter(i =>
          (i.ticker || '').toLowerCase().includes(q) ||
          (i.full_name || '').toLowerCase().includes(q))
      : allLoadedInstruments;
    renderInstrumentList(filtered);
  });

  // ── Instrument selection ──
  function selectInstrument(li, inst) {
    document.querySelectorAll('#INSTRUMENT_LIST_UL .ITEM_INSTRUMENT').forEach(el => el.classList.remove('selected'));
    li.classList.add('selected');
    selectedInstrumentId = inst.instrument_id;
    setActionsEnabled(true);
    loadFundamentals(inst.instrument_id, inst.ticker, inst.full_name);
  }

  // ── Load fundamentals ──
  async function loadFundamentals(instrumentId, ticker, fullName) {
    fundamentalsPane.innerHTML = '<p class="placeholder">Loading…</p>';
    try {
      const [fundRes, availRes, matrixRes, bestSmaRes] = await Promise.all([
        fetch(`/v1/instruments/${instrumentId}/fundamentals`),
        fetch(`/v1/instruments/${instrumentId}/ohlcv-availability`),
        fetch(`/v1/instruments/${instrumentId}/ohlcv-data-available`),
        fetch(`/v1/trading-strategies/${instrumentId}/v2`),
      ]);
      if (!fundRes.ok) {
        fundamentalsPane.innerHTML = `<p class="error">Error loading fundamentals (HTTP ${fundRes.status})</p>`;
        return;
      }
      const data = await fundRes.json();
      const title = ticker ? `${escHtml(ticker)}${fullName ? ' — ' + escHtml(fullName) : ''}` : escHtml(instrumentId);
      const rows = Object.entries(data)
        .filter(([, v]) => v !== null && v !== undefined && typeof v !== 'object')
        .map(([k, v]) => `<tr><td>${escHtml(k)}</td><td>${escHtml(String(v))}</td></tr>`)
        .join('');

      // OHLCV time range section
      let ohlcvRangeHtml = '<p style="color:#999;font-size:0.85rem">No OHLCV data available.</p>';
      if (availRes.ok) {
        const availData = await availRes.json();
        const ivEntries = Object.entries(availData.intervals || {});
        if (ivEntries.length > 0) {
          const ivOrder = ['1m','5m','1h','1d','1w','4w','1mth','1y','1ytd'];
          ivEntries.sort(([a], [b]) => {
            const ai = ivOrder.indexOf(a), bi = ivOrder.indexOf(b);
            return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
          });
          const fmtTs = t => t ? t.slice(0,16).replace('T',' ') : '—';
          const ivRows = ivEntries.map(([iv, {first, last}]) =>
            `<tr><td>${escHtml(iv)}</td><td>${escHtml(fmtTs(first))}</td><td>${escHtml(fmtTs(last))}</td></tr>`
          ).join('');
          ohlcvRangeHtml = `<table class="ohlcv-range-table"><thead><tr><th>Interval</th><th>First</th><th>Last</th></tr></thead><tbody>${ivRows}</tbody></table>`;
        }
      }

      // OHLCV data available matrix section
      let ohlcvMatrixHtml = '';
      if (matrixRes.ok) {
        const matrixData = await matrixRes.json();
        const sources = Object.entries(matrixData.sources || {});
        if (sources.length > 0) {
          const ivCols = ['has_1m','has_5m','has_1h','has_1d'];
          const ivLabels = ['1m','5m','1h','1d'];
          const headerCols = ivLabels.map(l => `<th>${escHtml(l)}</th>`).join('');
          const matrixRows = sources.map(([src, flags]) => {
            const cells = ivCols.map(col =>
              `<td class="${flags[col] ? 'avail-yes' : 'avail-no'}">${flags[col] ? '✓' : '—'}</td>`
            ).join('');
            return `<tr><td>${escHtml(src)}</td>${cells}</tr>`;
          }).join('');
          ohlcvMatrixHtml = `<h3>OHLCV Data Available</h3><table class="avail-table"><thead><tr><th>Source</th>${headerCols}</tr></thead><tbody>${matrixRows}</tbody></table>`;
        }
      }

      // BEST SMA Exit V1 section
      let bestSmaV2Html = '<p style="color:#999;font-size:0.85rem">No BEST SMA Exit V1 data available.</p>';
      if (bestSmaRes.ok) {
        const bestSmaData = await bestSmaRes.json();
        const items = bestSmaData.items || [];
        if (items.length > 0) {
          const values = {};
          items.forEach(it => { values[it.indicator_name] = it.indicator_value; });
          const params = items[0].parameters || {};
          const computedAt = items[0].computed_at ? String(items[0].computed_at).slice(0, 19).replace('T', ' ') : '—';
          bestSmaV2Html = `
            <table class="ohlcv-range-table"><tbody>
              <tr><td>sma_low</td><td>${escHtml(String(values.sma_low ?? '—'))}</td></tr>
              <tr><td>sma_high</td><td>${escHtml(String(values.sma_high ?? '—'))}</td></tr>
              <tr><td>pos_usd</td><td>${escHtml(String(params.pos_usd ?? '—'))}</td></tr>
              <tr><td>computed_at</td><td>${escHtml(computedAt)}</td></tr>
            </tbody></table>
          `;
        }
      }

      fundamentalsPane.innerHTML =
        `<h2>${title}</h2><table>${rows}</table>` +
        `<div class="ohlcv-range-section"><h3>OHLCV Time Range</h3>${ohlcvRangeHtml}</div>` +
        (ohlcvMatrixHtml ? `<div class="ohlcv-matrix-section">${ohlcvMatrixHtml}</div>` : '') +
        `<div class="best-sma-v2-section"><h3>BEST SMA Exit V1</h3>${bestSmaV2Html}</div>`;
    } catch (e) {
      fundamentalsPane.innerHTML = `<p class="error">Error loading fundamentals: ${escHtml(e.message)}</p>`;
    }
  }

  // ── Enable/disable action bar ──
  function setActionsEnabled(enabled) {
    btnFundamentals.disabled = !enabled;
    btnOhlcv.disabled        = !enabled;
    ddlPeriod.disabled       = !enabled;
    inpBestSmaPosUsd.disabled = !enabled;
    btnBestSmaV2.disabled     = !enabled;
  }

  // ── BTN_UPDATE_FUNDAMENTALS stub ──
  btnFundamentals.addEventListener('click', () => {
    console.log(`[stub] BTN_UPDATE_FUNDAMENTALS clicked for ${selectedInstrumentId}`);
  });

  // ── BTN_UPDATE_OHLCV — import from local cache ──
  btnOhlcv.addEventListener('click', async () => {
    if (!selectedInstrumentId) return;
    const interval = ddlPeriod.value;
    btnOhlcv.disabled = true;
    btnOhlcv.textContent = 'Importing\u2026';
    try {
      const res = await fetch('/v1/admin/import-ohlcv-cache', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({instrument_id: selectedInstrumentId, interval}),
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = (data.detail) ? escHtml(String(data.detail)) : `HTTP ${res.status}`;
        _prependOhlcvMessage(`<p class="error">OHLCV import failed: ${msg}</p>`);
        return;
      }
      if (data.status === 'folder_not_found') {
        _prependOhlcvMessage(`<p class="error">Cache folder not found. Expected: ${escHtml(data.expected_path || '')}</p>`);
        return;
      }
      // Success
      _prependOhlcvMessage(`<p class="import-ok">Imported ${data.rows_imported} rows from cache.</p>`);
      // Refresh OHLCV sections
      _refreshOhlcvSections(selectedInstrumentId);
    } catch (e) {
      _prependOhlcvMessage(`<p class="error">OHLCV import failed: ${escHtml(e.message)}</p>`);
    } finally {
      btnOhlcv.disabled = false;
      btnOhlcv.textContent = 'Update OHLCV Data';
    }
  });

  // ── BTN_COMPUTE_BEST_SMA_V2 — compute enhanced BEST SMA strategy ──
  btnBestSmaV2.addEventListener('click', async () => {
    if (!selectedInstrumentId) return;
    const posUsd = Number(inpBestSmaPosUsd.value || '100');
    btnBestSmaV2.disabled = true;
    btnBestSmaV2.textContent = 'Computing…';
    try {
      const res = await fetch(`/v1/trading-strategies/${selectedInstrumentId}/compute-v2`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({pos_usd: posUsd}),
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = (data.error) ? escHtml(String(data.error)) : `HTTP ${res.status}`;
        _prependOhlcvMessage(`<p class="error">BEST SMA Exit V1 compute failed: ${msg}</p>`);
        return;
      }
      _prependOhlcvMessage('<p class="import-ok">BEST SMA Exit V1 computed successfully.</p>');
      _refreshBestSmaV2Section(selectedInstrumentId);
    } catch (e) {
      _prependOhlcvMessage(`<p class="error">BEST SMA Exit V1 compute failed: ${escHtml(e.message)}</p>`);
    } finally {
      btnBestSmaV2.disabled = false;
      btnBestSmaV2.textContent = 'Compute BEST SMA Exit V1';
    }
  });

  // Prepend a status message above existing fundamentals pane content
  function _prependOhlcvMessage(html) {
    const msg = document.createElement('div');
    msg.innerHTML = html;
    fundamentalsPane.insertBefore(msg.firstChild, fundamentalsPane.firstChild);
  }

  // Re-fetch and re-render only the OHLCV sections (range + matrix)
  async function _refreshOhlcvSections(instrumentId) {
    try {
      const [availRes, matrixRes] = await Promise.all([
        fetch(`/v1/instruments/${instrumentId}/ohlcv-availability`),
        fetch(`/v1/instruments/${instrumentId}/ohlcv-data-available`),
      ]);
      // Replace OHLCV Time Range section
      const rangeEl = fundamentalsPane.querySelector('.ohlcv-range-section');
      const matrixEl = fundamentalsPane.querySelector('.ohlcv-matrix-section');
      if (rangeEl && availRes.ok) {
        const availData = await availRes.json();
        const ivEntries = Object.entries(availData.intervals || {});
        if (ivEntries.length > 0) {
          const ivOrder = ['1m','5m','1h','1d','1w','4w','1mth','1y','1ytd'];
          ivEntries.sort(([a],[b]) => {
            const ai = ivOrder.indexOf(a), bi = ivOrder.indexOf(b);
            return (ai===-1?999:ai)-(bi===-1?999:bi);
          });
          const fmtTs = t => t ? t.slice(0,16).replace('T',' ') : '—';
          const ivRows = ivEntries.map(([iv,{first,last}]) =>
            `<tr><td>${escHtml(iv)}</td><td>${escHtml(fmtTs(first))}</td><td>${escHtml(fmtTs(last))}</td></tr>`
          ).join('');
          rangeEl.innerHTML = `<h3>OHLCV Time Range</h3><table class="ohlcv-range-table"><thead><tr><th>Interval</th><th>First</th><th>Last</th></tr></thead><tbody>${ivRows}</tbody></table>`;
        }
      }
      if (matrixEl && matrixRes.ok) {
        const matrixData = await matrixRes.json();
        const sources = Object.entries(matrixData.sources || {});
        if (sources.length > 0) {
          const ivCols = ['has_1m','has_5m','has_1h','has_1d'];
          const ivLabels = ['1m','5m','1h','1d'];
          const headerCols = ivLabels.map(l=>`<th>${escHtml(l)}</th>`).join('');
          const matrixRows = sources.map(([src,flags]) => {
            const cells = ivCols.map(col=>`<td class="${flags[col]?'avail-yes':'avail-no'}">${flags[col]?'\u2713':'\u2014'}</td>`).join('');
            return `<tr><td>${escHtml(src)}</td>${cells}</tr>`;
          }).join('');
          matrixEl.innerHTML = `<h3>OHLCV Data Available</h3><table class="avail-table"><thead><tr><th>Source</th>${headerCols}</tr></thead><tbody>${matrixRows}</tbody></table>`;
        }
      }
    } catch (_) { /* silent */ }
  }

  async function _refreshBestSmaV2Section(instrumentId) {
    try {
      const section = fundamentalsPane.querySelector('.best-sma-v2-section');
      if (!section) return;

      const res = await fetch(`/v1/trading-strategies/${instrumentId}/v2`);
      if (!res.ok) {
        section.innerHTML = '<h3>BEST SMA Exit V1</h3><p style="color:#999;font-size:0.85rem">No BEST SMA Exit V1 data available.</p>';
        return;
      }
      const data = await res.json();
      const items = data.items || [];
      if (items.length === 0) {
        section.innerHTML = '<h3>BEST SMA Exit V1</h3><p style="color:#999;font-size:0.85rem">No BEST SMA Exit V1 data available.</p>';
        return;
      }

      const values = {};
      items.forEach(it => { values[it.indicator_name] = it.indicator_value; });
      const params = items[0].parameters || {};
      const computedAt = items[0].computed_at ? String(items[0].computed_at).slice(0, 19).replace('T', ' ') : '—';
      section.innerHTML = `
        <h3>BEST SMA Exit V1</h3>
        <table class="ohlcv-range-table"><tbody>
          <tr><td>sma_low</td><td>${escHtml(String(values.sma_low ?? '—'))}</td></tr>
          <tr><td>sma_high</td><td>${escHtml(String(values.sma_high ?? '—'))}</td></tr>
          <tr><td>pos_usd</td><td>${escHtml(String(params.pos_usd ?? '—'))}</td></tr>
          <tr><td>computed_at</td><td>${escHtml(computedAt)}</td></tr>
        </tbody></table>
      `;
    } catch (_) { /* silent */ }
  }

  // ── BTN_MIGRATE_FUNDAMENTALS ──
  btnMigrate.addEventListener('click', async () => {
    btnMigrate.disabled = true;
    btnMigrate.textContent = 'Migrating…';
    fundamentalsPane.innerHTML = '<p class="placeholder">Running migration…</p>';
    try {
      const res = await fetch('/v1/admin/migrate-fundamentals', { method: 'POST' });
      if (!res.ok) {
        fundamentalsPane.innerHTML = `<p class="error">Migration failed (HTTP ${res.status})</p>`;
        return;
      }
      const data = await res.json();
      fundamentalsPane.innerHTML = `<p class="placeholder">Migration complete — ${data.promoted} instrument(s) promoted.</p>`;
      const activeClass = document.querySelector('#SEG_ASSET_CLASS button.active')?.dataset.class || 'crypto';
      loadInstruments(activeClass);
    } catch (e) {
      fundamentalsPane.innerHTML = `<p class="error">Migration error: ${escHtml(e.message)}</p>`;
    } finally {
      btnMigrate.disabled = false;
      btnMigrate.textContent = 'Migrate Fundamental Data';
    }
  });

  // ── Helpers ──
  function escHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  // ── Init ──
  loadInstruments('crypto');
</script>
</body>
</html>"""


@router.get("/console", response_class=HTMLResponse)
async def management_console() -> HTMLResponse:
    return HTMLResponse(content=_CONSOLE_HTML)
