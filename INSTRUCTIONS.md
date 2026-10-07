# Global Development Instructions

Read this file at the start of every feature implementation.

---

## Tech Stack

- **Language**: Python (≥ 3.14 as pinned in `.python-version`)
- **Package / runtime manager**: `uv` — always use `uv run <script>` and `uv add <package>`.  
  **Never invoke `python3` or `pip` directly.**
- **Web framework**: FastAPI + HTMX + Bootstrap 5 (no JS build step)
- **Data sources**: Yahoo Finance (primary OHLCV), CoinGecko (fallback), CoinMarketCap (metadata only)

---

## Feature-Driven Development Workflow

### Starting a new feature `fNN`

```bash
# From the repo root (main branch)
git worktree add .worktrees/fNN -b fNN
cd .worktrees/fNN        # work here
```

### Implementing

- Follow the plan documented in `features/fNN-<name>.md`
- Use `uv run serve` to test the web app (auto-reloads on file save)
- Use `uv run draw-chart <SYMBOL>` to test chart generation

### After the user accepts the implementation

```bash
# From the worktree directory
git add .
git commit -m "feat(fNN): <concise description>"

# Back on main — merge and clean up
cd ../..                              # back to repo root
git merge fNN
git worktree remove .worktrees/fNN
git branch -d fNN
```

Commit messages follow **Conventional Commits**:
- `feat(fNN):` — new feature
- `fix(bNN):` — bug fix
- `chore:` — tooling / housekeeping
- `refactor:` — code restructure without behaviour change

---

## Repository Conventions

| Path | Purpose |
|---|---|
| `features/fNN-*.md` | Feature specs & plans |
| `features/iNN-*.md` | Improvement specs |
| `features/bNN-*.md` | Bug reports |
| `INSTRUCTIONS.md` | **This file** — global rules |
| `draw_chart.py` | CLI chart generator; `uv run draw-chart <SYM>` |
| `draw_all_charts.py` | Batch chart generator; `uv run draw-all-charts` |
| `web.py` | FastAPI server; `uv run serve` → http://localhost:8000 |
| `cmc_info.py` | CoinMarketCap metadata fetcher |
| `cache/ohlcv/` | Daily OHLCV disk cache (`{key}_{date}.json`) |
| `cache/cmc_info/` | Daily CMC info disk cache (`{symbol}_{date}.json`) |
| `png/` | Generated chart PNGs (gitignored) |
| `.worktrees/` | Git worktrees for in-progress features (gitignored) |

---

## Key Implementation Notes

- `CG_COIN_ID_MAP` in `draw_chart.py` maps HL symbols to CoinGecko slug IDs.  
  Keys are plain HL symbols (e.g. `"SUI"`), values are exact CoinGecko slugs (e.g. `"sui"`).  
  Verify new entries at: `https://api.coingecko.com/api/v3/coins/{id}/ohlc?vs_currency=usd&days=7`
- `K_SCALE_SET` contains HL symbols that represent 1000 × the underlying coin.
- OHLCV cache key for CoinGecko entries is `cg:{slug}` (e.g. `cg:sui`).
- CoinMarketCap key comes from the `CMC_API_KEY` environment variable (optional; empty disables CMC data). `coinMarketCapKey.py` remains gitignored as a precaution — never commit API keys to it.
