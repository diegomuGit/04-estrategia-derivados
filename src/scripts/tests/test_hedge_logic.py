"""
Tests para la logica de seleccion de hedge segun el signo de la delta.
=====================================================================
Verifica que OptionsHedgeAnalyzer.calculate_hedge_contracts neutraliza
correctamente la delta del straddle (el signo del resultado indica
automaticamente si comprar (+) o vender (-)).

Estos tests no requieren conexion a IBKR: el constructor de
OptionsHedgeAnalyzer no usa `ib` mientras df_option_chain sea None,
y calculate_hedge_contracts es una funcion pura.

Ejecutar (desde src/scripts):
    pytest tests/test_hedge_logic.py -v
"""

import pytest

from options_hedge import OptionsHedgeAnalyzer


@pytest.fixture
def analyzer():
    """Analizador sin conexion IBKR (suficiente para la logica pura)."""
    return OptionsHedgeAnalyzer(ib=None)


# Deltas tipicas de opciones individuales (por contrato)
CALL_DELTA = 0.50    # call ATM ~ +0.5
PUT_DELTA = -0.50    # put ATM ~ -0.5


class TestHedgeContractSign:
    """El signo de los contratos debe neutralizar la delta del straddle."""

    def test_positive_delta_sell_call(self, analyzer):
        """Delta straddle +: vender calls (delta+) => contratos negativos."""
        contracts = analyzer.calculate_hedge_contracts(0.15, CALL_DELTA)
        assert contracts < 0

    def test_positive_delta_buy_put(self, analyzer):
        """Delta straddle +: comprar puts (delta-) => contratos positivos."""
        contracts = analyzer.calculate_hedge_contracts(0.15, PUT_DELTA)
        assert contracts > 0

    def test_negative_delta_buy_call(self, analyzer):
        """Delta straddle -: comprar calls (delta+) => contratos positivos."""
        contracts = analyzer.calculate_hedge_contracts(-0.15, CALL_DELTA)
        assert contracts > 0

    def test_negative_delta_sell_put(self, analyzer):
        """Delta straddle -: vender puts (delta-) => contratos negativos."""
        contracts = analyzer.calculate_hedge_contracts(-0.15, PUT_DELTA)
        assert contracts < 0


class TestHedgeContractMagnitude:
    """El numero de contratos debe neutralizar la delta exactamente."""

    def test_neutralizes_delta(self, analyzer):
        """straddle_delta + contracts*hedge_delta == 0 (impacto neto nulo)."""
        straddle_delta = 0.15
        contracts = analyzer.calculate_hedge_contracts(straddle_delta, CALL_DELTA)
        # Impacto del hedge en la delta de la cartera (sin multiplicador neto)
        net_delta = straddle_delta + contracts * CALL_DELTA
        assert net_delta == pytest.approx(0.0, abs=1e-9)

    def test_small_delta_small_contracts(self, analyzer):
        """Delta cercana a cero => pocos contratos."""
        contracts = analyzer.calculate_hedge_contracts(0.02, CALL_DELTA)
        assert abs(contracts) < 0.1

    def test_zero_hedge_delta_returns_zero(self, analyzer):
        """Si la opcion de hedge no tiene delta, no se puede neutralizar."""
        contracts = analyzer.calculate_hedge_contracts(0.15, 0.0)
        assert contracts == 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
