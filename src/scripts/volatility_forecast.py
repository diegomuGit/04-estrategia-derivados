"""
Volatility Forecasting Module
=============================
Implementacion de modelos GARCH para forecast de volatilidad realizada.
Usa la libreria arch para estimacion y prediccion.

Fundamento teorico:
- Un modelo GARCH captura la persistencia y clustering de volatilidad
- El forecast de RV futura mejora la estimacion del spread IV-RV
- Permite identificar mejor cuando IV esta "barata" vs RV esperada

Referencia:
- Bollerslev (1986): Generalized Autoregressive Conditional Heteroskedasticity
- arch package: https://arch.readthedocs.io/
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple, Dict
from dataclasses import dataclass
import warnings


# =============================================================================
# CONFIGURACION
# =============================================================================

@dataclass
class GARCHConfig:
    """
    Configuracion para el modelo GARCH.

    Attributes
    ----------
    p : int
        Orden del componente GARCH (rezagos de varianza). Default: 1
    q : int
        Orden del componente ARCH (rezagos de residuos^2). Default: 1
    mean_model : str
        Modelo para la media: 'Zero', 'Constant', 'AR'. Default: 'Zero'
    vol_model : str
        Modelo de volatilidad: 'GARCH', 'EGARCH', 'GJR-GARCH'. Default: 'GARCH'
    dist : str
        Distribucion de errores: 'normal', 't', 'skewt'. Default: 'normal'
    horizon : int
        Horizonte de forecast en dias. Default: 5
    fit_window : int
        Ventana de datos para estimar el modelo (dias). Default: 252
    min_fit_window : int
        Minimo de observaciones requeridas para fit. Default: 126
    refit_frequency : int
        Cada cuantos dias re-estimar el modelo. Default: 21 (mensual)
    scale_returns : float
        Factor de escala para returns (mejora estabilidad numerica). Default: 100
    """
    p: int = 1
    q: int = 1
    mean_model: str = 'Zero'
    vol_model: str = 'GARCH'
    dist: str = 'normal'
    horizon: int = 5
    fit_window: int = 252
    min_fit_window: int = 126
    refit_frequency: int = 21
    scale_returns: float = 100.0


# =============================================================================
# FUNCIONES DE ESTIMACION Y FORECAST
# =============================================================================

def fit_garch_model(
    returns: pd.Series,
    config: GARCHConfig
) -> Tuple[Optional[object], Dict]:
    """
    Estima un modelo GARCH sobre una serie de retornos.

    Parameters
    ----------
    returns : pd.Series
        Serie de log-retornos.
    config : GARCHConfig
        Configuracion del modelo.

    Returns
    -------
    Tuple[model_result, info_dict]
        Modelo estimado y diccionario con informacion del fit.

    Notes
    -----
    - Escala los retornos internamente para estabilidad numerica
    - Suprime warnings de convergencia (comunes en GARCH)
    """
    from arch import arch_model

    info = {
        'success': False,
        'nobs': len(returns),
        'converged': False,
        'aic': np.nan,
        'bic': np.nan,
        'params': {}
    }

    if len(returns) < config.min_fit_window:
        return None, info

    # Escalar retornos (mejora convergencia)
    scaled_returns = returns * config.scale_returns

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # Crear modelo
            model = arch_model(
                scaled_returns,
                mean=config.mean_model,
                vol=config.vol_model,
                p=config.p,
                q=config.q,
                dist=config.dist
            )

            # Estimar con opciones de robustez
            result = model.fit(
                disp='off',
                show_warning=False,
                options={'maxiter': 500}
            )

            info['success'] = True
            info['converged'] = result.convergence_flag == 0
            info['aic'] = result.aic
            info['bic'] = result.bic
            info['params'] = dict(result.params)

            return result, info

    except Exception as e:
        info['error'] = str(e)
        return None, info


def forecast_volatility(
    model_result: object,
    horizon: int,
    config: GARCHConfig
) -> float:
    """
    Genera forecast de volatilidad a partir de un modelo GARCH estimado.

    Parameters
    ----------
    model_result : arch model result
        Resultado de fit_garch_model().
    horizon : int
        Horizonte de forecast en dias.
    config : GARCHConfig
        Configuracion (para factor de escala).

    Returns
    -------
    float
        Volatilidad anualizada forecasted.

    Notes
    -----
    - El forecast es la raiz de la varianza promedio sobre el horizonte
    - Se anualiza multiplicando por sqrt(252)
    - Se des-escala por el factor usado en fit
    """
    if model_result is None:
        return np.nan

    try:
        # Forecast de varianza
        forecasts = model_result.forecast(horizon=horizon)

        # Varianza promedio sobre el horizonte
        variance_forecast = forecasts.variance.iloc[-1].mean()

        # Des-escalar y anualizar
        # variance esta en (returns * scale)^2, hay que dividir por scale^2
        daily_vol = np.sqrt(variance_forecast) / config.scale_returns
        annual_vol = daily_vol * np.sqrt(252)

        return annual_vol

    except Exception:
        return np.nan


# =============================================================================
# FUNCION PRINCIPAL: ROLLING FORECAST
# =============================================================================

def compute_garch_forecasts(
    prices: pd.Series,
    config: Optional[GARCHConfig] = None,
    verbose: bool = False
) -> pd.DataFrame:
    """
    Calcula forecasts de volatilidad GARCH de forma rolling.

    IMPORTANTE: Esta funcion es "look-ahead bias free":
    - Para cada fecha t, solo usa datos hasta t-1
    - El forecast es para los proximos 'horizon' dias
    - El modelo se re-estima cada 'refit_frequency' dias

    Parameters
    ----------
    prices : pd.Series
        Serie de precios de cierre (ej: close_spy).
    config : GARCHConfig, optional
        Configuracion del modelo. Si None, usa defaults.
    verbose : bool
        Si True, muestra progreso.

    Returns
    -------
    pd.DataFrame
        DataFrame con columnas:
        - rv_forecast: volatilidad anualizada forecasted
        - model_fit_date: fecha del ultimo fit del modelo
        - model_converged: si el modelo convergio

    Example
    -------
    >>> config = GARCHConfig(horizon=5, refit_frequency=21)
    >>> forecasts = compute_garch_forecasts(market_data['close_spy'], config)
    >>> # Usar en compute_features:
    >>> df['rv_forecast'] = forecasts['rv_forecast']
    """
    if config is None:
        config = GARCHConfig()

    # Calcular log-returns
    log_returns = np.log(prices / prices.shift(1)).dropna()

    # Inicializar resultados
    results = pd.DataFrame(
        index=prices.index,
        columns=['rv_forecast', 'model_fit_date', 'model_converged'],
        dtype=object
    )
    results['rv_forecast'] = np.nan
    results['model_converged'] = False

    # Variables para caching del modelo
    cached_model = None
    cached_fit_info = None
    last_fit_date = None
    last_fit_idx = -config.refit_frequency  # Forzar fit inicial

    dates = prices.index.tolist()

    for i, date in enumerate(dates):
        # Necesitamos al menos min_fit_window observaciones
        if i < config.min_fit_window:
            continue

        # Determinar si hay que re-estimar el modelo
        should_refit = (i - last_fit_idx) >= config.refit_frequency

        if should_refit or cached_model is None:
            # Obtener ventana de datos para fit
            start_idx = max(0, i - config.fit_window)
            returns_window = log_returns.iloc[start_idx:i]

            # Estimar modelo
            cached_model, cached_fit_info = fit_garch_model(returns_window, config)
            last_fit_date = date
            last_fit_idx = i

            if verbose and cached_fit_info['success']:
                print(f"[{date}] GARCH fit: converged={cached_fit_info['converged']}, "
                      f"nobs={cached_fit_info['nobs']}")

        # Generar forecast
        if cached_model is not None:
            rv_forecast = forecast_volatility(cached_model, config.horizon, config)
            results.loc[date, 'rv_forecast'] = rv_forecast
            results.loc[date, 'model_fit_date'] = last_fit_date
            results.loc[date, 'model_converged'] = cached_fit_info.get('converged', False)

    # Convertir columna a float
    results['rv_forecast'] = pd.to_numeric(results['rv_forecast'], errors='coerce')

    return results


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def get_garch_diagnostics(
    prices: pd.Series,
    config: GARCHConfig,
    fit_date: str
) -> Dict:
    """
    Obtiene diagnosticos detallados del modelo GARCH para una fecha especifica.

    Util para debugging y validacion del modelo.

    Parameters
    ----------
    prices : pd.Series
        Serie de precios.
    config : GARCHConfig
        Configuracion del modelo.
    fit_date : str
        Fecha hasta la cual usar datos para el fit.

    Returns
    -------
    dict
        Diccionario con parametros, tests de diagnostico, etc.
    """
    log_returns = np.log(prices / prices.shift(1)).dropna()

    # Obtener datos hasta fit_date
    returns_window = log_returns.loc[:fit_date].iloc[-config.fit_window:]

    model_result, fit_info = fit_garch_model(returns_window, config)

    if model_result is None:
        return {'error': 'Model fit failed', 'fit_info': fit_info}

    diagnostics = {
        'fit_info': fit_info,
        'params': dict(model_result.params),
        'std_errors': dict(model_result.std_err),
        'pvalues': dict(model_result.pvalues),
        'loglikelihood': model_result.loglikelihood,
        'conditional_volatility': model_result.conditional_volatility.iloc[-10:].tolist()
    }

    return diagnostics


def compare_rv_methods(
    prices: pd.Series,
    rv_window: int = 20,
    garch_config: Optional[GARCHConfig] = None
) -> pd.DataFrame:
    """
    Compara RV historica vs GARCH forecast para analisis.

    Util para evaluar si GARCH mejora las senales.

    Parameters
    ----------
    prices : pd.Series
        Serie de precios.
    rv_window : int
        Ventana para RV historica.
    garch_config : GARCHConfig, optional
        Configuracion del modelo GARCH.

    Returns
    -------
    pd.DataFrame
        Comparacion con columnas: rv_historical, rv_forecast, diff, ratio
    """
    if garch_config is None:
        garch_config = GARCHConfig()

    # RV historica
    log_returns = np.log(prices / prices.shift(1))
    rv_historical = log_returns.rolling(window=rv_window).std() * np.sqrt(252)

    # GARCH forecast
    garch_forecasts = compute_garch_forecasts(prices, garch_config)

    comparison = pd.DataFrame({
        'rv_historical': rv_historical,
        'rv_forecast': garch_forecasts['rv_forecast'],
        'diff': garch_forecasts['rv_forecast'] - rv_historical,
        'ratio': garch_forecasts['rv_forecast'] / rv_historical
    })

    return comparison
