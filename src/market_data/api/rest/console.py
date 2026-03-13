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

    /* ── SEG_ASSET_CLASS ── */
    #SEG_ASSET_CLASS { display: flex; gap: 4px; }
    #SEG_ASSET_CLASS button {
      padding: 6px 14px; border: 1px solid #444; border-radius: 4px;
      background: transparent; color: #ccc; cursor: pointer; font-size: 0.85rem;
    }
    #SEG_ASSET_CLASS button.active {
      background: #e94560; border-color: #e94560; color: #fff; font-weight: 600;
    }

    /* ── Main layout ── */
    #MAIN_LAYOUT { display: flex; flex: 1; overflow: hidden; }

    /* ── PANE_INSTRUMENT_LIST ── */
    #PANE_INSTRUMENT_LIST {
      width: 260px; min-width: 200px; background: #fff;
      border-right: 1px solid #e0e0e0; overflow-y: auto; display: flex; flex-direction: column;
    }
    #PANE_INSTRUMENT_LIST .list-header {
      padding: 10px 14px; font-size: 0.75rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.08em; color: #888;
      border-bottom: 1px solid #eee; position: sticky; top: 0; background: #fff;
    }
    #PANE_INSTRUMENT_LIST ul { list-style: none; flex: 1; }
    #PANE_INSTRUMENT_LIST li.ITEM_INSTRUMENT {
      padding: 10px 14px; cursor: pointer; border-bottom: 1px solid #f0f0f0;
    }
    #PANE_INSTRUMENT_LIST li.ITEM_INSTRUMENT:hover { background: #f8f8f8; }
    #PANE_INSTRUMENT_LIST li.ITEM_INSTRUMENT.selected { background: #e8f0fe; border-left: 3px solid #1a73e8; }
    #PANE_INSTRUMENT_LIST li.ITEM_INSTRUMENT .ticker { font-weight: 600; font-size: 0.9rem; }
    #PANE_INSTRUMENT_LIST li.ITEM_INSTRUMENT .name { font-size: 0.78rem; color: #666; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    #PANE_INSTRUMENT_LIST .list-empty { padding: 20px 14px; color: #999; font-size: 0.85rem; }

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

    /* ── PANE_FUNDAMENTALS ── */
    #PANE_FUNDAMENTALS { flex: 1; overflow-y: auto; padding: 24px; }
    #PANE_FUNDAMENTALS .placeholder { color: #aaa; font-size: 0.95rem; margin-top: 40px; text-align: center; }
    #PANE_FUNDAMENTALS .error { color: #c00; font-size: 0.9rem; }
    #PANE_FUNDAMENTALS h2 { font-size: 1.1rem; margin-bottom: 16px; }
    #PANE_FUNDAMENTALS table { border-collapse: collapse; width: 100%; max-width: 600px; }
    #PANE_FUNDAMENTALS td { padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 0.88rem; }
    #PANE_FUNDAMENTALS td:first-child { font-weight: 600; color: #555; width: 40%; }
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
</div>

<div id="MAIN_LAYOUT">

  <div id="PANE_INSTRUMENT_LIST">
    <div class="list-header">Instruments</div>
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
    </div>
    <div id="PANE_FUNDAMENTALS">
      <p class="placeholder">Select an instrument to view details</p>
    </div>
  </div>

</div>

<script>
  // ── State ──
  let selectedInstrumentId = null;

  // ── Element references ──
  const segButtons        = document.querySelectorAll('#SEG_ASSET_CLASS button');
  const listUl            = document.getElementById('INSTRUMENT_LIST_UL');
  const fundamentalsPane  = document.getElementById('PANE_FUNDAMENTALS');
  const btnFundamentals   = document.getElementById('BTN_UPDATE_FUNDAMENTALS');
  const btnOhlcv          = document.getElementById('BTN_UPDATE_OHLCV');
  const ddlPeriod         = document.getElementById('DDL_OHLCV_PERIOD');

  // ── Asset-class selector ──
  segButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      segButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedInstrumentId = null;
      setActionsEnabled(false);
      fundamentalsPane.innerHTML = '<p class="placeholder">Select an instrument to view details</p>';
      loadInstruments(btn.dataset.class);
    });
  });

  // ── Load instrument list ──
  async function loadInstruments(assetClass) {
    listUl.innerHTML = '';
    try {
      const res = await fetch(`/v1/instruments?asset_class=${assetClass}&is_active=true&page_size=200`);
      const data = await res.json();
      const items = data.items || [];
      if (items.length === 0) {
        listUl.innerHTML = '<li class="list-empty">No instruments found</li>';
        return;
      }
      items.forEach(inst => {
        const li = document.createElement('li');
        li.className = 'ITEM_INSTRUMENT';
        li.dataset.id = inst.instrument_id;
        li.innerHTML = `<div class="ticker">${escHtml(inst.ticker)}</div><div class="name">${escHtml(inst.full_name)}</div>`;
        li.addEventListener('click', () => selectInstrument(li, inst));
        listUl.appendChild(li);
      });
    } catch (e) {
      listUl.innerHTML = `<li class="list-empty">Error loading instruments</li>`;
    }
  }

  // ── Instrument selection ──
  function selectInstrument(li, inst) {
    document.querySelectorAll('#INSTRUMENT_LIST_UL .ITEM_INSTRUMENT').forEach(el => el.classList.remove('selected'));
    li.classList.add('selected');
    selectedInstrumentId = inst.instrument_id;
    setActionsEnabled(true);
    loadFundamentals(inst.instrument_id);
  }

  // ── Load fundamentals ──
  async function loadFundamentals(instrumentId) {
    fundamentalsPane.innerHTML = '<p class="placeholder">Loading…</p>';
    try {
      const res = await fetch(`/v1/instruments/${instrumentId}/fundamentals`);
      if (!res.ok) {
        fundamentalsPane.innerHTML = `<p class="error">Error loading fundamentals (HTTP ${res.status})</p>`;
        return;
      }
      const data = await res.json();
      const rows = Object.entries(data)
        .filter(([, v]) => v !== null && v !== undefined)
        .map(([k, v]) => `<tr><td>${escHtml(k)}</td><td>${escHtml(String(v))}</td></tr>`)
        .join('');
      fundamentalsPane.innerHTML = `<h2>${escHtml(instrumentId)}</h2><table>${rows}</table>`;
    } catch (e) {
      fundamentalsPane.innerHTML = `<p class="error">Error loading fundamentals: ${escHtml(e.message)}</p>`;
    }
  }

  // ── Enable/disable action bar ──
  function setActionsEnabled(enabled) {
    btnFundamentals.disabled = !enabled;
    btnOhlcv.disabled        = !enabled;
    ddlPeriod.disabled       = !enabled;
  }

  // ── BTN_UPDATE_FUNDAMENTALS stub ──
  btnFundamentals.addEventListener('click', () => {
    console.log(`[stub] BTN_UPDATE_FUNDAMENTALS clicked for ${selectedInstrumentId}`);
  });

  // ── BTN_UPDATE_OHLCV stub ──
  btnOhlcv.addEventListener('click', () => {
    console.log(`[stub] BTN_UPDATE_OHLCV clicked for ${selectedInstrumentId}, period=${ddlPeriod.value}`);
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
