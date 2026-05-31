# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Backtesting and trading system for **volatility strategies on SPY**, centered on periodic ATM **long straddles**. Built for the MIAX Master. Documentation, comments and identifiers are in Spanish — keep new code/comments in Spanish for consistency.

There are two largely independent sub-systems sharing the pricing layer:
- **Offline research**: the day-by-day backtest engine (no external connections beyond data download).
- **Live trading/analysis**: options-hedge analysis and order routing against Interactive Brokers (requires TWS/IB Gateway running).

## Environment & commands

```bash
pip install -r requirements.txt          # core deps
# QuantLib is OPTIONAL and commented out in requirements.txt.
# Without it, American-option pricing silently falls back to European BSM.
```

Create a `.env` at repo root with `FRED_API_KEY=...` (required by `data_loader.load_treasury_curve`; loaded via python-dotenv).

### Running tests

Tests live in `src/scripts/tests/` but import modules with **flat imports** (e.g. `from volatility_forecast import ...`), so they must resolve `src/scripts` on the path:

```bash
cd src/scripts
pytest tests/test_volatility_forecast.py -v        # full GARCH suite
pytest tests/test_volatility_forecast.py::TestFitGARCH::test_fit_success -v   # single test
pytest tests/test_hedge_logic.py tests/test_backtest_pnl.py -v   # hedge sign + backtest P&L
```

Existing suites in `src/scripts/tests/`:
- `test_volatility_forecast.py` — GARCH fit/forecast/rolling, plus integration with `signals`.
- `test_hedge_logic.py` — sign/magnitude of `OptionsHedgeAnalyzer.calculate_hedge_contracts` (pure, no IBKR; uses `OptionsHedgeAnalyzer(ib=None)`).
- `test_backtest_pnl.py` — regression guarding the straddle P&L accounting (no double-counting).

Pricing, signals, and delta hedge still have no dedicated test coverage.

## Critical architectural fact: flat imports, no package

`src/scripts/` is **not** a Python package (no `__init__.py`, no relative imports). Every module imports its siblings by bare name (`from strategy import ...`, `from black_scholes import ...`). Consequence:
- Code only runs with `src/scripts` on `sys.path`. Notebooks do `sys.path.insert(...)` at the top; tests rely on being run from `src/scripts`.
- When adding modules, follow the same flat-import convention rather than introducing package-relative imports.

## Layered architecture

```
data_loader.py / rates.py / dividends.py     →  market data (yfinance, FRED, IBKR)
black_scholes.py → straddle.py               →  pricing + greeks (BSM core, optional QuantLib)
strategy.py / signals.py / volatility_forecast.py  →  positions, entry/exit logic, GARCH
backtest.py + delta_hedge.py                 →  day-by-day simulation engine
options_hedge.py + IBKR notebooks            →  live hedging/execution (parallel sub-system)
```

### Pricing layer (`black_scholes.py`, `straddle.py`)
BSM-with-dividends pricing and the 5 greeks. `calculate_straddle_greeks` (call+put with a **single sigma**, VIX as IV proxy, skew intentionally ignored — documented in the docstring) is the function the backtest depends on. QuantLib paths (`ql_greeks_american`, `*_american`) auto-fall back to BSM when QuantLib is absent, and use **today's date** as evaluation date, so they are only valid for "as-of-now" analysis, not historical valuation.

### Backtest engine (`backtest.py`)
`run_backtest(market_data, entry_dates, tenor_days, hedge_config?, entry_config?, exit_config?)` drives an 8-step daily loop: MTM valuation → portfolio delta → early exits → expiries → filtered entries → hedge rebalance → liquidation when flat → P&L aggregation. Returns a `BacktestResult` with straddle/hedge/total P&L split out and a `summary` dict. `market_data` must be a single DataFrame indexed by trading day with columns `close_spy`, `close_vix`, `q_yield`, and rate tenors keyed by the **integers** `30, 90, 180, 365` (use `prepare_market_data` to assemble it). Hedge, entry filters, and early exits are all opt-in via their config objects (`None` = simple buy-and-hold-to-expiry straddle).

### Signals & GARCH (`signals.py`, `volatility_forecast.py`)
`compute_features` builds RV (short/long), IV percentile, variance spread (IV²−RV²), and an expansion flag; it can optionally swap historical RV for a GARCH forecast. `compute_garch_forecasts` is explicitly **look-ahead-bias-free** (rolling re-fit, only past data per date). Entry = low IVP + low spread percentile + (optional) expansion; exits = take-profit / stop-loss / time-stop / vol-exit.

### Live options hedge (`options_hedge.py`)
`OptionsHedgeAnalyzer` picks the 4 delta-neutralizing strategies based on the **sign of the straddle delta** and computes contract counts automatically (sign of result = buy/sell). This selection logic was a recent fix (see `CAMBIOS_HEDGE.md`) — do not reintroduce a forced buy/sell `action` parameter. Requires a live `ib_insync` connection for prices; not runnable offline.

## P&L accounting note
`backtest.py` step 8 computes `daily_pnl_straddle` as the **daily change** of total portfolio value
(`cumulative_realized + unrealized` snapshot minus yesterday's), so `cumulative_pnl_straddle = daily_pnl_straddle.cumsum()`
reconstructs the equity curve without double-counting. This mirrors the hedge P&L, which is also a daily change.
When touching that loop, keep `daily_pnl_*` series as daily deltas (not cumulative snapshots) so the `.cumsum()`
aggregation stays correct.
