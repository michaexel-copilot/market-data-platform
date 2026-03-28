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
    #BTN_IMPORT_KRAKEN_1H {
      padding: 7px 16px; background: #e67e22; color: #fff;
      border: none; border-radius: 4px; cursor: pointer; font-size: 0.85rem;
    }
    #BTN_IMPORT_KRAKEN_1H:disabled { background: #bbb; cursor: not-allowed; }
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

    /* ── NAV_TABS ── */
    #NAV_TABS { display: flex; gap: 4px; }
    #NAV_TABS button {
      padding: 6px 16px; border: 1px solid #444; border-radius: 4px;
      background: transparent; color: #ccc; cursor: pointer; font-size: 0.85rem;
    }
    #NAV_TABS button.active {
      background: #e94560; border-color: #e94560; color: #fff; font-weight: 600;
    }

    /* ── PANE_SCHEDULER ── */
    #PANE_SCHEDULER { flex: 1; overflow-y: auto; padding: 24px; display: none; }
    #PANE_SCHEDULER h2 { font-size: 1.1rem; margin-bottom: 16px; }
    #PANE_SCHEDULER table { border-collapse: collapse; width: 100%; max-width: 560px; }
    #PANE_SCHEDULER th { padding: 8px 12px; font-size: 0.8rem; font-weight: 700; text-align: left; background: #f5f5f5; border-bottom: 2px solid #e0e0e0; }
    #PANE_SCHEDULER td { padding: 10px 12px; border-bottom: 1px solid #eee; font-size: 0.88rem; }
    #PANE_SCHEDULER td:first-child { font-family: monospace; font-weight: 600; }
    #PANE_SCHEDULER .btn-toggle {
      padding: 4px 14px; border: none; border-radius: 4px;
      cursor: pointer; font-size: 0.82rem; font-weight: 600;
    }
    #PANE_SCHEDULER .btn-toggle.enabled  { background: #0f9d58; color: #fff; }
    #PANE_SCHEDULER .btn-toggle.disabled { background: #ccc;    color: #555; }
    #PANE_SCHEDULER .sched-status { font-size: 0.82rem; color: #888; margin-top: 12px; }
  </style>
</head>
<body>

<div id="TOP_BAR">
  <h1>Market Data — Management Console</h1>
  <div id="NAV_TABS">
    <button id="BTN_NAV_INSTRUMENTS" class="active">Instruments</button>
    <button id="BTN_NAV_SCHEDULER">Scheduler</button>
  </div>
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
    <div id="PANE_SCHEDULER">
      <h2>Scheduler Jobs</h2>
      <table id="SCHED_TABLE">
        <thead><tr><th>Job ID</th><th>Status</th><th>Action</th></tr></thead>
        <tbody id="SCHED_TBODY"></tbody>
      </table>
      <p class="sched-status" id="SCHED_STATUS"></p>
    </div>
    <div id="ACTION_BAR">
      <button id="BTN_UPDATE_FUNDAMENTALS" disabled>Update Fundamental Data</button>
      <button id="BTN_UPDATE_OHLCV" disabled>Update OHLCV Data</button>
      <button id="BTN_IMPORT_KRAKEN_1H" disabled>Import Kraken 1h</button>
    </div>
    <div id="PANE_FUNDAMENTALS">
      <p class="placeholder">Select an instrument to view details</p>
    </div>
  </div>

</div>

<script>
  // ── State ──
  let selectedInstrumentId = null;
  let selectedTicker = null;
  let activeSources = new Set(['eodhd', 'hl']);
  let activeTab = 'instruments'; // 'instruments' | 'scheduler'

  // ── Element references ──
  let allLoadedInstruments = [];

  // ── NAV_TABS ──
  const btnNavInstruments = document.getElementById('BTN_NAV_INSTRUMENTS');
  const btnNavScheduler   = document.getElementById('BTN_NAV_SCHEDULER');
  const paneInstrumentList = document.getElementById('PANE_INSTRUMENT_LIST');
  const paneContent       = document.getElementById('PANE_CONTENT');
  const paneScheduler     = document.getElementById('PANE_SCHEDULER');
  const actionBar         = document.getElementById('ACTION_BAR');
  const paneInstruments   = document.getElementById('PANE_FUNDAMENTALS');
  const segAssetClass     = document.getElementById('SEG_ASSET_CLASS');
  const segSourceFilter   = document.getElementById('SEG_SOURCE_FILTER');
  const actBtnList        = document.getElementById('ACT_BTN_LIST');

  function switchTab(tab) {
    activeTab = tab;
    if (tab === 'scheduler') {
      btnNavInstruments.classList.remove('active');
      btnNavScheduler.classList.add('active');
      paneInstrumentList.style.display = 'none';
      actionBar.style.display = 'none';
      paneInstruments.style.display = 'none';
      segAssetClass.style.display = 'none';
      segSourceFilter.style.display = 'none';
      actBtnList.style.display = 'none';
      paneScheduler.style.display = 'block';
      loadSchedulerJobs();
    } else {
      btnNavScheduler.classList.remove('active');
      btnNavInstruments.classList.add('active');
      paneInstrumentList.style.display = '';
      actionBar.style.display = '';
      paneInstruments.style.display = '';
      segAssetClass.style.display = '';
      segSourceFilter.style.display = '';
      actBtnList.style.display = '';
      paneScheduler.style.display = 'none';
    }
  }

  btnNavInstruments.addEventListener('click', () => switchTab('instruments'));
  btnNavScheduler.addEventListener('click',   () => switchTab('scheduler'));

  // ── Scheduler pane ──
  async function loadSchedulerJobs() {
    const tbody = document.getElementById('SCHED_TBODY');
    const status = document.getElementById('SCHED_STATUS');
    tbody.innerHTML = '<tr><td colspan="3">Loading…</td></tr>';
    status.textContent = '';
    try {
      const res = await fetch('/v1/admin/scheduler/jobs');
      if (!res.ok) { tbody.innerHTML = `<tr><td colspan="3">Error loading jobs (HTTP ${res.status})</td></tr>`; return; }
      const jobs = await res.json();
      renderSchedulerJobs(jobs);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="3">Error: ${escHtml(e.message)}</td></tr>`;
    }
  }

  function renderSchedulerJobs(jobs) {
    const tbody = document.getElementById('SCHED_TBODY');
    tbody.innerHTML = '';
    jobs.forEach(job => {
      const tr = document.createElement('tr');
      const statusText = job.enabled ? 'Enabled' : 'Disabled';
      const btnClass   = job.enabled ? 'enabled' : 'disabled';
      const btnLabel   = job.enabled ? 'Disable' : 'Enable';
      tr.innerHTML =
        `<td>${escHtml(job.job_id)}</td>` +
        `<td>${escHtml(statusText)}</td>` +
        `<td><button class="btn-toggle ${btnClass}" data-job="${escHtml(job.job_id)}" data-enabled="${job.enabled}">${escHtml(btnLabel)}</button></td>`;
      tbody.appendChild(tr);
    });
    tbody.querySelectorAll('.btn-toggle').forEach(btn => {
      btn.addEventListener('click', () => toggleSchedulerJob(btn));
    });
  }

  async function toggleSchedulerJob(btn) {
    const jobId = btn.dataset.job;
    const currentlyEnabled = btn.dataset.enabled === 'true';
    const action = currentlyEnabled ? 'disable' : 'enable';
    const status = document.getElementById('SCHED_STATUS');
    btn.disabled = true;
    status.textContent = '';
    try {
      const res = await fetch(`/v1/admin/scheduler/jobs/${encodeURIComponent(jobId)}/${action}`, { method: 'POST' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        status.textContent = `Error: ${data.detail || 'HTTP ' + res.status}`;
        btn.disabled = false;
        return;
      }
      const data = await res.json();
      status.textContent = `${escHtml(jobId)} ${data.enabled ? 'enabled' : 'disabled'}.`;
      loadSchedulerJobs();
    } catch (e) {
      status.textContent = `Error: ${escHtml(e.message)}`;
      btn.disabled = false;
    }
  }

  // ── Element references ──
  const segButtons        = document.querySelectorAll('#SEG_ASSET_CLASS button');
  const srcButtons        = document.querySelectorAll('#SEG_SOURCE_FILTER button');
  const listUl            = document.getElementById('INSTRUMENT_LIST_UL');
  const inpFilter         = document.getElementById('INP_INSTRUMENT_FILTER');
  const fundamentalsPane  = document.getElementById('PANE_FUNDAMENTALS');
  const btnFundamentals   = document.getElementById('BTN_UPDATE_FUNDAMENTALS');
  const btnOhlcv          = document.getElementById('BTN_UPDATE_OHLCV');
  const btnKrakenImport   = document.getElementById('BTN_IMPORT_KRAKEN_1H');
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
    selectedTicker = inst.ticker;
    setActionsEnabled(true);
    loadFundamentals(inst.instrument_id, inst.ticker, inst.full_name);
    loadKrakenStatus(inst.ticker);
  }

  // ── Load fundamentals ──
  async function loadFundamentals(instrumentId, ticker, fullName) {
    fundamentalsPane.innerHTML = '<p class="placeholder">Loading…</p>';
    try {
      const [fundRes, availRes, matrixRes] = await Promise.all([
        fetch(`/v1/instruments/${instrumentId}/fundamentals`),
        fetch(`/v1/instruments/${instrumentId}/ohlcv-availability`),
        fetch(`/v1/instruments/${instrumentId}/ohlcv-data-available`),
      ]);
      if (!fundRes.ok) {
        fundamentalsPane.innerHTML = `<p class="error">Error loading fundamentals (HTTP ${fundRes.status})</p>`;
        return;
      }
      const data = await fundRes.json();
      const title = ticker ? `${escHtml(ticker)}${fullName ? ' — ' + escHtml(fullName) : ''}` : escHtml(instrumentId);
      const rows = Object.entries(data)
        .filter(([k, v]) => k !== 'launch_date' && v !== null && v !== undefined && typeof v !== 'object')
        .map(([k, v]) => `<tr><td>${escHtml(k)}</td><td>${escHtml(String(v))}</td></tr>`)
        .join('');
      const launchDateRow = data.launch_date
        ? `<tr><td>Launch Date</td><td>${escHtml(String(data.launch_date))}</td></tr>`
        : '';

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

      fundamentalsPane.innerHTML =
        `<h2>${title}</h2><table>${rows}${launchDateRow}</table>` +
        `<div class="ohlcv-range-section"><h3>OHLCV Time Range</h3>${ohlcvRangeHtml}</div>` +
        (ohlcvMatrixHtml ? `<div class="ohlcv-matrix-section">${ohlcvMatrixHtml}</div>` : '');
    } catch (e) {
      fundamentalsPane.innerHTML = `<p class="error">Error loading fundamentals: ${escHtml(e.message)}</p>`;
    }
  }

  // ── Enable/disable action bar ──
  function setActionsEnabled(enabled) {
    btnFundamentals.disabled = !enabled;
    btnOhlcv.disabled        = !enabled;
    if (!enabled) {
      btnKrakenImport.disabled = true;
      btnKrakenImport.textContent = 'Import Kraken 1h';
    }
  }

  // ── Load Kraken 1h status for ACTION_BAR button ──
  async function loadKrakenStatus(ticker) {
    btnKrakenImport.disabled = true;
    btnKrakenImport.textContent = 'Checking…';
    try {
      const res = await fetch(`/v1/instruments/${encodeURIComponent(ticker)}/kraken-1h-status`);
      if (!res.ok) { btnKrakenImport.textContent = 'Import Kraken 1h'; return; }
      const data = await res.json();
      if (!data.has_file) {
        btnKrakenImport.textContent = 'No Kraken File';
        btnKrakenImport.disabled = true;
      } else if (data.already_imported) {
        btnKrakenImport.textContent = 'Re-import Kraken 1h';
        btnKrakenImport.disabled = false;
      } else {
        btnKrakenImport.textContent = 'Import Kraken 1h';
        btnKrakenImport.disabled = false;
      }
    } catch (_) {
      btnKrakenImport.textContent = 'Import Kraken 1h';
      btnKrakenImport.disabled = true;
    }
  }

  // ── BTN_IMPORT_KRAKEN_1H ──
  btnKrakenImport.addEventListener('click', async () => {
    if (!selectedTicker) return;
    btnKrakenImport.disabled = true;
    btnKrakenImport.textContent = 'Importing…';
    try {
      const res = await fetch(`/v1/instruments/${encodeURIComponent(selectedTicker)}/import-kraken-1h`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) {
        _prependOhlcvMessage(`<p class="error">Kraken import failed: ${escHtml(data.detail || 'HTTP ' + res.status)}</p>`);
        btnKrakenImport.textContent = 'Import Kraken 1h';
        btnKrakenImport.disabled = false;
        return;
      }
      const from = data.gap_closed_from ? data.gap_closed_from.slice(0, 10) : '?';
      const to   = data.gap_closed_to   ? data.gap_closed_to.slice(0, 10)   : '?';
      _prependOhlcvMessage(`<p class="import-ok">Kraken 1h imported: ${escHtml(String(data.rows_inserted))} rows (${escHtml(from)} → ${escHtml(to)})</p>`);
      btnKrakenImport.textContent = 'Re-import Kraken 1h';
      btnKrakenImport.disabled = false;
      _refreshOhlcvSections(selectedInstrumentId);
    } catch (e) {
      _prependOhlcvMessage(`<p class="error">Kraken import failed: ${escHtml(e.message)}</p>`);
      btnKrakenImport.textContent = 'Import Kraken 1h';
      btnKrakenImport.disabled = false;
    }
  });

  // ── BTN_UPDATE_FUNDAMENTALS stub ──
  btnFundamentals.addEventListener('click', () => {
    console.log(`[stub] BTN_UPDATE_FUNDAMENTALS clicked for ${selectedInstrumentId}`);
  });

  // ── BTN_UPDATE_OHLCV — smart multi-step OHLCV update ──
  btnOhlcv.addEventListener('click', async () => {
    if (!selectedInstrumentId) return;
    btnOhlcv.disabled = true;
    btnOhlcv.textContent = 'Updating\u2026';
    try {
      const res = await fetch('/v1/admin/smart-update-ohlcv', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({instrument_id: selectedInstrumentId}),
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = (data.detail) ? escHtml(String(data.detail)) : `HTTP ${res.status}`;
        _prependOhlcvMessage(`<p class="error">OHLCV update failed: ${msg}</p>`);
        return;
      }
      // Build a human-readable summary from the steps list
      const steps = data.steps || [];
      const lines = [];
      steps.forEach(s => {
        if (s.step === '1h_freshness_check') {
          const ts = s.last_ts ? s.last_ts.slice(0,16).replace('T',' ') : 'none';
          lines.push(`1h data: ${s.status === 'stale' ? 'stale' : 'fresh'} (last: ${escHtml(ts)})`);
        } else if (s.step === '1h_ingest' && s.status !== 'skipped') {
          lines.push(`1h ingest: ${s.status === 'ok' ? escHtml(String(s.written)) + ' rows written' : escHtml(s.status)}`);
        } else if (s.step === '1m_gap_check' && s.status === 'gap') {
          lines.push(`1m gap: ${escHtml(String(s.gap_hours))}h`);
        } else if (s.step === '1m_fetch' && s.status === 'ok') {
          lines.push(`Fetched ${escHtml(String(s.fetched))} Binance 1m candles`);
        } else if (s.step === '1h_aggregation' && s.status === 'ok') {
          lines.push(`Aggregated \u2192 ${escHtml(String(s.written))} synthetic 1h candles`);
        } else if (s.step === 'binance_availability' && s.status === 'unavailable') {
          lines.push('Binance 1m not available for this instrument \u2014 gap fill skipped');
        } else if (s.step === '1m_fetch' && s.status === 'error') {
          lines.push(`Binance 1m fetch error: ${escHtml(s.error || '')}`);
        }
      });
      const summary = lines.length ? lines.join('. ') + '.' : `Done. ${data.total_written} rows written.`;
      _prependOhlcvMessage(`<p class="import-ok">${summary}</p>`);
      _refreshOhlcvSections(selectedInstrumentId);
    } catch (e) {
      _prependOhlcvMessage(`<p class="error">OHLCV update failed: ${escHtml(e.message)}</p>`);
    } finally {
      btnOhlcv.disabled = false;
      btnOhlcv.textContent = 'Update OHLCV Data';
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
