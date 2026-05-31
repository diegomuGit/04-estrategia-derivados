"""
Tests de regresion para la contabilidad de P&L del backtest.
============================================================
Verifica que el P&L del straddle se acumula correctamente (cambio diario
via snapshot) y NO sufre doble conteo: la curva acumulada se construye con
daily_pnl_straddle.cumsum(), por lo que daily_pnl_straddle debe contener el
*cambio* diario, no el MTM acumulado.

Escenario determinista: un unico straddle, sin hedge ni filtros, mantenido
hasta vencimiento. El P&L acumulado final debe igualar exactamente el P&L
realizado de ese unico trade (intrinseco al vencimiento - prima de entrada),
no una cifra inflada que escale con los dias mantenidos.

Ejecutar (desde src/scripts):
    pytest tests/test_backtest_pnl.py -v
"""

import numpy as np
import pandas as pd
import pytest

from backtest import run_backtest


@pytest.fixture
def market_data():
    """Mercado sintetico: 40 dias habiles, vol/tasas/q constantes y un
    camino de precio determinista que genera un payoff no nulo al vencimiento."""
    dates = pd.date_range('2023-01-02', periods=40, freq='B')
    index = dates.strftime('%Y-%m-%d')

    # Camino de precio determinista (deriva suave al alza)
    spy = 400.0 + np.arange(40) * 0.5

    df = pd.DataFrame({
        'close_spy': spy,
        'close_vix': 0.20,
        'q_yield': 0.015,
        30: 0.05,
        90: 0.05,
        180: 0.05,
        365: 0.05,
    }, index=index)
    return df


@pytest.fixture
def result(market_data):
    entry_dates = [market_data.index[0]]   # una unica entrada
    return run_backtest(market_data, entry_dates, tenor_days=15)


class TestSingleStraddlePnL:

    def test_one_closed_trade(self, result):
        closed = [t for t in result.trades if t.status == 'closed']
        assert len(closed) == 1

    def test_realized_pnl_is_intrinsic_minus_premium(self, result, market_data):
        trade = next(t for t in result.trades if t.status == 'closed')
        intrinsic = abs(market_data.loc[trade.exit_date, 'close_spy'] - trade.strike)
        # exit_price del straddle al vencimiento == valor intrinseco
        assert trade.exit_price == pytest.approx(intrinsic, abs=1e-9)
        assert trade.realized_pnl == pytest.approx(trade.exit_price - trade.entry_price)

    def test_cumulative_equals_realized_no_double_count(self, result):
        """Clave de la regresion: la curva acumulada final == P&L realizado
        del unico trade. Con el bug antiguo (cumsum del MTM acumulado) esta
        cifra estaria muy inflada."""
        trade = next(t for t in result.trades if t.status == 'closed')
        final_cum = result.cumulative_pnl_straddle.iloc[-1]
        assert final_cum == pytest.approx(trade.realized_pnl, abs=1e-6)

    def test_summary_matches_cumulative(self, result):
        final_cum = result.cumulative_pnl_straddle.iloc[-1]
        assert result.summary['total_pnl_straddle'] == pytest.approx(final_cum, abs=1e-6)

    def test_daily_cumsum_consistency(self, result):
        """daily_pnl_straddle.cumsum() debe reproducir cumulative_pnl_straddle."""
        rebuilt = result.daily_pnl_straddle.cumsum()
        pd.testing.assert_series_equal(
            rebuilt, result.cumulative_pnl_straddle, check_names=False
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
