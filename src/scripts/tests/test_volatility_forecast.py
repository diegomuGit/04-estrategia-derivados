"""
Tests para el modulo volatility_forecast.py
============================================
Verifica el correcto funcionamiento de los modelos GARCH para
forecast de volatilidad realizada.

Ejecutar con: pytest test_volatility_forecast.py -v
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from volatility_forecast import (
    GARCHConfig,
    fit_garch_model,
    forecast_volatility,
    compute_garch_forecasts,
    compare_rv_methods
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_returns():
    """Genera returns simulados con estructura GARCH."""
    np.random.seed(42)
    n = 500
    returns = np.zeros(n)
    sigma = np.zeros(n)
    sigma[0] = 0.01

    omega, alpha, beta = 0.00001, 0.1, 0.85
    for t in range(1, n):
        sigma[t] = np.sqrt(omega + alpha * returns[t-1]**2 + beta * sigma[t-1]**2)
        returns[t] = sigma[t] * np.random.randn()

    dates = pd.date_range('2020-01-01', periods=n, freq='B')
    return pd.Series(returns, index=dates)


@pytest.fixture
def sample_prices():
    """Precios simulados a partir de returns GARCH."""
    np.random.seed(42)
    n = 600
    returns = np.zeros(n)
    sigma = np.zeros(n)
    sigma[0] = 0.01

    omega, alpha, beta = 0.00001, 0.1, 0.85
    for t in range(1, n):
        sigma[t] = np.sqrt(omega + alpha * returns[t-1]**2 + beta * sigma[t-1]**2)
        returns[t] = sigma[t] * np.random.randn()

    prices = 100 * np.exp(np.cumsum(returns))
    dates = pd.date_range('2020-01-01', periods=n, freq='B')
    return pd.Series(prices, index=dates)


@pytest.fixture
def short_returns():
    """Returns con pocas observaciones (para probar edge cases)."""
    np.random.seed(42)
    returns = pd.Series(np.random.randn(50) * 0.01)
    return returns


# =============================================================================
# TESTS DE GARCHCONFIG
# =============================================================================

class TestGARCHConfig:
    """Tests para la clase de configuracion."""

    def test_default_values(self):
        """Verifica valores por defecto."""
        config = GARCHConfig()
        assert config.p == 1
        assert config.q == 1
        assert config.horizon == 5
        assert config.refit_frequency == 21
        assert config.fit_window == 252
        assert config.min_fit_window == 126
        assert config.scale_returns == 100.0

    def test_custom_values(self):
        """Verifica valores personalizados."""
        config = GARCHConfig(p=2, q=2, horizon=10, refit_frequency=5)
        assert config.p == 2
        assert config.q == 2
        assert config.horizon == 10
        assert config.refit_frequency == 5


# =============================================================================
# TESTS DE FIT_GARCH_MODEL
# =============================================================================

class TestFitGARCH:
    """Tests para la funcion de estimacion."""

    def test_fit_success(self, sample_returns):
        """Verifica que el modelo se estima correctamente."""
        config = GARCHConfig()
        model, info = fit_garch_model(sample_returns, config)

        assert model is not None
        assert info['success'] == True
        assert info['nobs'] == len(sample_returns)
        assert 'omega' in info['params']

    def test_fit_insufficient_data(self, short_returns):
        """Verifica que retorna None si no hay suficientes datos."""
        config = GARCHConfig(min_fit_window=126)
        model, info = fit_garch_model(short_returns, config)

        assert model is None
        assert info['success'] == False

    def test_fit_params_reasonable(self, sample_returns):
        """Verifica que los parametros estimados son razonables."""
        config = GARCHConfig()
        model, info = fit_garch_model(sample_returns, config)

        # Alpha + Beta deberia ser < 1 para estacionariedad
        alpha = info['params'].get('alpha[1]', 0)
        beta = info['params'].get('beta[1]', 0)
        assert alpha + beta < 1, "Modelo no estacionario"

    def test_fit_different_distributions(self, sample_returns):
        """Prueba diferentes distribuciones de errores."""
        for dist in ['normal', 't']:
            config = GARCHConfig(dist=dist)
            model, info = fit_garch_model(sample_returns, config)
            assert info['success'] == True, f"Fallo con dist={dist}"


# =============================================================================
# TESTS DE FORECAST_VOLATILITY
# =============================================================================

class TestForecastVolatility:
    """Tests para la funcion de forecast."""

    def test_forecast_returns_float(self, sample_returns):
        """Verifica que el forecast es un float valido."""
        config = GARCHConfig(horizon=5)
        model, _ = fit_garch_model(sample_returns, config)

        forecast = forecast_volatility(model, 5, config)

        assert isinstance(forecast, float)
        assert not np.isnan(forecast)
        assert forecast > 0

    def test_forecast_reasonable_range(self, sample_returns):
        """Verifica que el forecast esta en rango razonable."""
        config = GARCHConfig(horizon=5)
        model, _ = fit_garch_model(sample_returns, config)

        forecast = forecast_volatility(model, 5, config)

        # Volatilidad anualizada tipica: 5% - 100%
        assert forecast > 0.01, "Volatilidad demasiado baja"
        assert forecast < 2.0, "Volatilidad demasiado alta"

    def test_forecast_none_model(self):
        """Verifica que retorna NaN si el modelo es None."""
        config = GARCHConfig()
        forecast = forecast_volatility(None, 5, config)
        assert np.isnan(forecast)

    def test_forecast_different_horizons(self, sample_returns):
        """Verifica forecasts con diferentes horizontes."""
        config = GARCHConfig()
        model, _ = fit_garch_model(sample_returns, config)

        forecast_5 = forecast_volatility(model, 5, config)
        forecast_20 = forecast_volatility(model, 20, config)

        # Ambos deben ser validos
        assert not np.isnan(forecast_5)
        assert not np.isnan(forecast_20)


# =============================================================================
# TESTS DE COMPUTE_GARCH_FORECASTS
# =============================================================================

class TestComputeGARCHForecasts:
    """Tests para la funcion principal de rolling forecast."""

    def test_output_shape(self, sample_prices):
        """Verifica forma del output."""
        config = GARCHConfig()
        result = compute_garch_forecasts(sample_prices, config)

        assert len(result) == len(sample_prices)
        assert 'rv_forecast' in result.columns
        assert 'model_fit_date' in result.columns
        assert 'model_converged' in result.columns

    def test_no_lookahead_bias(self, sample_prices):
        """Verifica que no hay look-ahead bias."""
        config = GARCHConfig()
        result = compute_garch_forecasts(sample_prices, config)

        # Las primeras min_fit_window filas deben ser NaN
        nan_count = result['rv_forecast'].iloc[:config.min_fit_window].isna().sum()
        assert nan_count == config.min_fit_window, \
            f"Esperaba {config.min_fit_window} NaN, encontre {nan_count}"

    def test_forecasts_after_warmup(self, sample_prices):
        """Verifica que hay forecasts validos despues del warmup."""
        config = GARCHConfig()
        result = compute_garch_forecasts(sample_prices, config)

        # Despues del warmup deberia haber forecasts validos
        valid_forecasts = result['rv_forecast'].iloc[config.min_fit_window:].dropna()
        assert len(valid_forecasts) > 0, "No hay forecasts validos despues del warmup"

    def test_refit_frequency(self, sample_prices):
        """Verifica que el modelo se re-estima con la frecuencia correcta."""
        config = GARCHConfig(refit_frequency=21)
        result = compute_garch_forecasts(sample_prices, config)

        # Contar fechas unicas de fit
        fit_dates = result['model_fit_date'].dropna().unique()
        expected_fits = (len(sample_prices) - config.min_fit_window) // config.refit_frequency + 1

        # Permitir margen
        assert len(fit_dates) >= expected_fits - 2, \
            f"Esperaba ~{expected_fits} fits, encontre {len(fit_dates)}"

    def test_default_config(self, sample_prices):
        """Verifica que funciona con config por defecto."""
        result = compute_garch_forecasts(sample_prices)  # Sin config
        assert 'rv_forecast' in result.columns

    def test_verbose_mode(self, sample_prices, capsys):
        """Verifica modo verbose."""
        config = GARCHConfig(refit_frequency=100)  # Menos fits para menos output
        compute_garch_forecasts(sample_prices, config, verbose=True)
        captured = capsys.readouterr()
        assert "GARCH fit" in captured.out


# =============================================================================
# TESTS DE COMPARE_RV_METHODS
# =============================================================================

class TestCompareRVMethods:
    """Tests para la funcion de comparacion."""

    def test_output_columns(self, sample_prices):
        """Verifica columnas del output."""
        result = compare_rv_methods(sample_prices)

        expected_cols = ['rv_historical', 'rv_forecast', 'diff', 'ratio']
        for col in expected_cols:
            assert col in result.columns, f"Falta columna {col}"

    def test_diff_calculation(self, sample_prices):
        """Verifica que diff = forecast - historical."""
        result = compare_rv_methods(sample_prices)

        # Donde ambos son validos
        valid_mask = result['rv_forecast'].notna() & result['rv_historical'].notna()
        if valid_mask.any():
            expected_diff = result.loc[valid_mask, 'rv_forecast'] - result.loc[valid_mask, 'rv_historical']
            np.testing.assert_array_almost_equal(
                result.loc[valid_mask, 'diff'].values,
                expected_diff.values,
                decimal=10
            )


# =============================================================================
# TESTS DE INTEGRACION CON SIGNALS.PY
# =============================================================================

class TestIntegrationSignals:
    """Tests de integracion con el modulo signals."""

    @pytest.fixture
    def sample_market_data(self, sample_prices):
        """Crea market_data simulado."""
        n = len(sample_prices)
        dates = sample_prices.index

        # Simular VIX
        np.random.seed(123)
        vix = 0.15 + 0.05 * np.random.randn(n).cumsum() * 0.01
        vix = np.clip(vix, 0.10, 0.80)

        market_data = pd.DataFrame({
            'close_spy': sample_prices.values,
            'close_vix': vix,
            'q_yield': 0.02,
            30: 0.05,
            90: 0.05,
            180: 0.05,
            365: 0.05
        }, index=dates)

        return market_data

    def test_compute_features_with_garch(self, sample_market_data):
        """Verifica que compute_features funciona con GARCH."""
        from signals import compute_features

        features = compute_features(
            sample_market_data,
            use_garch_forecast=True,
            forecast_horizon=5
        )

        assert 'rv_forecast' in features.columns
        assert 'rv_for_spread' in features.columns

        # Verificar que spread usa forecast
        valid_mask = features['rv_forecast'].notna()
        if valid_mask.any():
            pd.testing.assert_series_equal(
                features.loc[valid_mask, 'rv_for_spread'],
                features.loc[valid_mask, 'rv_forecast'],
                check_names=False
            )

    def test_backward_compatibility(self, sample_market_data):
        """Verifica compatibilidad hacia atras (sin GARCH)."""
        from signals import compute_features

        features = compute_features(
            sample_market_data,
            use_garch_forecast=False  # Comportamiento original
        )

        # spread_var debe usar rv_long
        expected_spread = features['iv']**2 - features['rv_long']**2
        pd.testing.assert_series_equal(
            features['spread_var'],
            expected_spread,
            check_names=False
        )

    def test_entry_config_garch_params(self):
        """Verifica nuevos parametros en EntryConfig."""
        from signals import EntryConfig

        # Config con GARCH
        config = EntryConfig(
            use_filters=True,
            use_garch_forecast=True,
            forecast_horizon=10,
            garch_refit_freq=5
        )

        assert config.use_garch_forecast == True
        assert config.forecast_horizon == 10
        assert config.garch_refit_freq == 5

        # Config sin GARCH (default)
        config_default = EntryConfig()
        assert config_default.use_garch_forecast == False


# =============================================================================
# TESTS DE EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Tests para casos extremos."""

    def test_constant_prices(self):
        """Verifica comportamiento con precios constantes."""
        prices = pd.Series(
            [100.0] * 300,
            index=pd.date_range('2020-01-01', periods=300, freq='B')
        )
        config = GARCHConfig()

        # No deberia fallar, pero forecasts pueden ser NaN
        result = compute_garch_forecasts(prices, config)
        assert len(result) == len(prices)

    def test_very_volatile_prices(self):
        """Verifica comportamiento con alta volatilidad."""
        np.random.seed(42)
        returns = np.random.randn(300) * 0.05  # 5% diario
        prices = 100 * np.exp(np.cumsum(returns))
        prices = pd.Series(prices, index=pd.date_range('2020-01-01', periods=300, freq='B'))

        config = GARCHConfig()
        result = compute_garch_forecasts(prices, config)

        valid = result['rv_forecast'].dropna()
        if len(valid) > 0:
            # La volatilidad anualizada deberia ser muy alta
            assert valid.mean() > 0.3, "Volatilidad esperada > 30%"

    def test_prices_with_gaps(self):
        """Verifica comportamiento con datos faltantes."""
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(300) * 0.5)
        dates = pd.date_range('2020-01-01', periods=300, freq='B')
        prices = pd.Series(prices, index=dates)

        # Introducir gaps (NaN)
        prices.iloc[100:105] = np.nan
        prices = prices.dropna()

        config = GARCHConfig()
        result = compute_garch_forecasts(prices, config)

        # Deberia manejar gaps sin crashear
        assert len(result) == len(prices)


# =============================================================================
# EJECUTAR TESTS
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
