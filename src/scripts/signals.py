"""
Signals Module
==============
Lógica de señales para entrada y salida basada en volatilidad implícita (IV),
volatilidad realizada (RV), y sus percentiles históricos.

Fundamento teórico:
- Un long straddle es rentable cuando el movimiento realizado supera la prima pagada
- La prima está determinada por la IV (proxy: VIX)
- El "edge" viene de comprar cuando IV está barata vs lo que el activo tiende a realizar

Referencias:
- Variance Risk Premium: Carr & Wu (2009)
- IV Percentile: Schwab, BME documentation
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional


# =============================================================================
# CONFIGURACIÓN DE SEÑALES
# =============================================================================

@dataclass
class EntryConfig:
    """
    Configuración para señales de entrada.
    
    Attributes
    ----------
    use_filters : bool
        Si False, entra en todas las fechas programadas (modo simple original).
        Si True, aplica los filtros de IV/RV.
    
    ivp_threshold : float
        Umbral máximo de IV Percentile para entrar. 
        Ejemplo: 30 significa entrar solo si IV está en el percentil 30 o inferior.
    
    spread_pctl_threshold : float
        Umbral máximo del percentil del spread (IV² - RV²).
        Valores bajos indican que IV está "barata" vs RV reciente.
    
    use_expansion_filter : bool
        Si True, requiere que RV de corto plazo > RV de largo plazo
        (señal de que la volatilidad está "despertando").
    
    lookback_pctl : int
        Días de lookback para calcular percentiles (típico: 252 = 1 año).
    
    rv_short_window : int
        Ventana corta para RV en filtro de expansión (típico: 5 días).

    rv_long_window : int
        Ventana larga para RV base (típico: 20-30 días).

    use_garch_forecast : bool
        Si True, usa GARCH forecast en lugar de RV histórica para el spread.
        Default: False (mantiene compatibilidad con comportamiento original).

    forecast_horizon : int
        Horizonte de forecast GARCH en días (solo si use_garch_forecast=True).
        Típico: 5-10 días para straddles de 30 días.
        Default: 5

    garch_refit_freq : int
        Frecuencia de re-estimación del modelo GARCH en días.
        Default: 21 (mensual)
    """
    use_filters: bool = True
    ivp_threshold: float = 30.0
    spread_pctl_threshold: float = 30.0
    use_expansion_filter: bool = True
    lookback_pctl: int = 252
    rv_short_window: int = 5
    rv_long_window: int = 20
    use_garch_forecast: bool = False
    forecast_horizon: int = 5
    garch_refit_freq: int = 21


@dataclass
class ExitConfig:
    """
    Configuración para señales de salida anticipada.
    
    Attributes
    ----------
    use_exits : bool
        Si False, mantiene hasta vencimiento (modo simple original).
        Si True, aplica reglas de salida anticipada.
    
    take_profit_pct : float
        Cerrar si MTM return >= este valor. Ejemplo: 0.50 = +50%.
    
    stop_loss_pct : float
        Cerrar si MTM return <= -este valor. Ejemplo: 0.50 = -50%.
    
    time_stop_fraction : float
        Cerrar si ha pasado esta fracción del tenor sin alcanzar TP.
        Ejemplo: 0.5 = cerrar al 50% del tiempo si no hay ganancias.
    
    time_stop_min_return : float
        Return mínimo requerido para NO activar time stop.
        Ejemplo: 0.10 = si return < 10% al time stop, cerrar.
    
    ivp_exit_threshold : float
        Si IVP sube por encima de este valor y estamos en verde, cerrar.
        Captura el "re-pricing" de volatilidad.
    """
    use_exits: bool = True
    take_profit_pct: float = 0.50
    stop_loss_pct: float = 0.50
    time_stop_fraction: float = 0.50
    time_stop_min_return: float = 0.10
    ivp_exit_threshold: float = 60.0


# =============================================================================
# CÁLCULO DE FEATURES
# =============================================================================

def compute_realized_volatility(prices: pd.Series, window: int) -> pd.Series:
    """
    Calcula la volatilidad realizada (anualizada) usando retornos log.
    
    RV_N = std(log returns, N días) * sqrt(252)
    
    Parameters
    ----------
    prices : pd.Series
        Serie de precios de cierre.
    window : int
        Ventana de días para el cálculo.
    
    Returns
    -------
    pd.Series
        Volatilidad realizada anualizada.
    """
    log_returns = np.log(prices / prices.shift(1))
    rv = log_returns.rolling(window=window).std() * np.sqrt(252)
    return rv


def compute_percentile_rank(series: pd.Series, lookback: int) -> pd.Series:
    """
    Calcula el percentil rolling de cada valor respecto a su historia.
    
    Percentile(x_t) = % de valores en [t-lookback, t] que son <= x_t
    
    Parameters
    ----------
    series : pd.Series
        Serie de valores.
    lookback : int
        Días de lookback para el cálculo.
    
    Returns
    -------
    pd.Series
        Percentil (0-100) de cada valor.
    """
    def pctl_rank(window):
        if len(window) < 2:
            return np.nan
        # Percentil del último valor respecto a la ventana completa
        current = window.iloc[-1]
        return (window <= current).sum() / len(window) * 100
    
    return series.rolling(window=lookback, min_periods=lookback//2).apply(pctl_rank, raw=False)


def compute_features(
    market_data: pd.DataFrame,
    rv_short_window: int = 5,
    rv_long_window: int = 20,
    lookback_pctl: int = 252,
    use_garch_forecast: bool = False,
    forecast_horizon: int = 5,
    garch_refit_freq: int = 21
) -> pd.DataFrame:
    """
    Añade columnas de features para señales de entrada/salida.

    Features calculados:
    - ret_log_1d: retorno logarítmico diario
    - rv_short: volatilidad realizada de corto plazo
    - rv_long: volatilidad realizada de largo plazo (histórica)
    - rv_forecast: volatilidad forecasted con GARCH (si use_garch_forecast=True)
    - rv_for_spread: RV usada en spread (forecast si GARCH, sino histórica)
    - iv: volatilidad implícita (alias de close_vix)
    - spread_var: IV² - RV_for_spread² (spread en varianza)
    - iv_pctl: percentil de IV
    - rv_long_pctl: percentil de RV
    - spread_var_pctl: percentil del spread
    - expansion_signal: True si RV_short > RV_long

    Parameters
    ----------
    market_data : pd.DataFrame
        DataFrame con close_spy, close_vix como mínimo.
    rv_short_window : int
        Ventana para RV de corto plazo.
    rv_long_window : int
        Ventana para RV de largo plazo.
    lookback_pctl : int
        Lookback para percentiles.
    use_garch_forecast : bool
        Si True, calcula forecasts GARCH y los usa en el spread.
    forecast_horizon : int
        Horizonte de forecast GARCH (días).
    garch_refit_freq : int
        Frecuencia de re-fit del modelo GARCH.

    Returns
    -------
    pd.DataFrame
        DataFrame original con columnas adicionales de features.
    """
    df = market_data.copy()

    # Retornos logarítmicos
    df['ret_log_1d'] = np.log(df['close_spy'] / df['close_spy'].shift(1))

    # Volatilidad realizada histórica (siempre calculada)
    df['rv_short'] = compute_realized_volatility(df['close_spy'], rv_short_window)
    df['rv_long'] = compute_realized_volatility(df['close_spy'], rv_long_window)

    # GARCH forecast (si habilitado)
    if use_garch_forecast:
        from volatility_forecast import compute_garch_forecasts, GARCHConfig

        garch_config = GARCHConfig(
            horizon=forecast_horizon,
            refit_frequency=garch_refit_freq
        )
        garch_results = compute_garch_forecasts(df['close_spy'], garch_config)
        df['rv_forecast'] = garch_results['rv_forecast']

        # Usar forecast para el spread
        df['rv_for_spread'] = df['rv_forecast']
    else:
        df['rv_forecast'] = np.nan
        # Usar RV histórica para el spread (comportamiento original)
        df['rv_for_spread'] = df['rv_long']

    # IV (alias para claridad)
    df['iv'] = df['close_vix']

    # Spread en varianza: IV² - RV²
    # Valores positivos indican IV > RV (pagando "de más")
    # Valores negativos indican IV < RV (volatilidad "barata")
    df['spread_var'] = df['iv']**2 - df['rv_for_spread']**2

    # Percentiles
    df['iv_pctl'] = compute_percentile_rank(df['iv'], lookback_pctl)
    df['rv_long_pctl'] = compute_percentile_rank(df['rv_long'], lookback_pctl)
    df['spread_var_pctl'] = compute_percentile_rank(df['spread_var'], lookback_pctl)

    # Señal de expansión: volatilidad de corto plazo superando la de largo plazo
    df['expansion_signal'] = df['rv_short'] > df['rv_long']

    return df


# =============================================================================
# FUNCIONES DE DECISIÓN
# =============================================================================

def should_enter(
    date: str,
    features: pd.DataFrame,
    config: EntryConfig
) -> bool:
    """
    Determina si se debe abrir una posición en esta fecha.
    
    Lógica de entrada (cuando use_filters=True):
    1. IV Percentile bajo (IV "barata" en su historia)
    2. Spread Percentile bajo (IV "barata" vs RV reciente)
    3. (Opcional) Señal de expansión (vol despertando)
    
    Parameters
    ----------
    date : str
        Fecha a evaluar (formato YYYY-MM-DD).
    features : pd.DataFrame
        DataFrame con features calculados (output de compute_features).
    config : EntryConfig
        Configuración de umbrales.
    
    Returns
    -------
    bool
        True si se debe entrar.
    """
    if not config.use_filters:
        return True
    
    # Obtener datos del día
    if date not in features.index:
        return False
    
    row = features.loc[date]
    
    # Verificar que tenemos datos suficientes
    if pd.isna(row['iv_pctl']) or pd.isna(row['spread_var_pctl']):
        return False
    
    # Condición 1: IV Percentile bajo
    iv_ok = row['iv_pctl'] < config.ivp_threshold
    
    # Condición 2: Spread Percentile bajo
    spread_ok = row['spread_var_pctl'] < config.spread_pctl_threshold
    
    # Condición 3: Expansión (opcional)
    if config.use_expansion_filter:
        if pd.isna(row['expansion_signal']):
            expansion_ok = False
        else:
            expansion_ok = row['expansion_signal']
    else:
        expansion_ok = True
    
    return iv_ok and spread_ok and expansion_ok


def should_exit(
    position,  # StraddlePosition
    date: str,
    features: pd.DataFrame,
    config: ExitConfig
) -> bool:
    """
    Determina si se debe cerrar anticipadamente una posición.
    
    Reglas de salida (en orden de prioridad):
    1. Take profit: MTM return >= umbral
    2. Stop loss: MTM return <= -umbral
    3. Time stop: pasó X% del tenor sin ganancias significativas
    4. Vol exit: IVP subió mucho y estamos en verde (capturar re-pricing)
    
    Parameters
    ----------
    position : StraddlePosition
        Posición a evaluar.
    date : str
        Fecha actual.
    features : pd.DataFrame
        DataFrame con features calculados.
    config : ExitConfig
        Configuración de umbrales.
    
    Returns
    -------
    bool
        True si se debe cerrar la posición.
    """
    if not config.use_exits:
        return False
    
    # Calcular métricas de la posición
    if position.entry_price <= 0:
        return False
    
    mtm_return = (position.current_price - position.entry_price) / position.entry_price
    
    # Calcular fracción del tiempo transcurrido
    days_in_trade = position.days_to_expiry(position.entry_date) - position.days_to_expiry(date)
    time_fraction = days_in_trade / position.tenor_days if position.tenor_days > 0 else 0
    
    # Regla 1: Take profit
    if mtm_return >= config.take_profit_pct:
        return True
    
    # Regla 2: Stop loss
    if mtm_return <= -config.stop_loss_pct:
        return True
    
    # Regla 3: Time stop
    if time_fraction >= config.time_stop_fraction:
        if mtm_return < config.time_stop_min_return:
            return True
    
    # Regla 4: Vol exit (IVP alto + en verde)
    if date in features.index:
        row = features.loc[date]
        if not pd.isna(row['iv_pctl']):
            if row['iv_pctl'] >= config.ivp_exit_threshold and mtm_return > 0:
                return True
    
    return False


def get_exit_reason(
    position,
    date: str,
    features: pd.DataFrame,
    config: ExitConfig
) -> Optional[str]:
    """
    Retorna el motivo de salida para logging/análisis.
    
    Returns
    -------
    str or None
        'take_profit', 'stop_loss', 'time_stop', 'vol_exit', o None si no sale.
    """
    if not config.use_exits:
        return None
    
    if position.entry_price <= 0:
        return None
    
    mtm_return = (position.current_price - position.entry_price) / position.entry_price
    
    days_in_trade = position.days_to_expiry(position.entry_date) - position.days_to_expiry(date)
    time_fraction = days_in_trade / position.tenor_days if position.tenor_days > 0 else 0
    
    if mtm_return >= config.take_profit_pct:
        return 'take_profit'
    
    if mtm_return <= -config.stop_loss_pct:
        return 'stop_loss'
    
    if time_fraction >= config.time_stop_fraction:
        if mtm_return < config.time_stop_min_return:
            return 'time_stop'
    
    if date in features.index:
        row = features.loc[date]
        if not pd.isna(row['iv_pctl']):
            if row['iv_pctl'] >= config.ivp_exit_threshold and mtm_return > 0:
                return 'vol_exit'
    
    return None


# =============================================================================
# FUNCIONES DE ANÁLISIS
# =============================================================================

def analyze_entry_conditions(
    features: pd.DataFrame,
    entry_dates: list,
    config: EntryConfig
) -> pd.DataFrame:
    """
    Analiza las condiciones de entrada para cada fecha programada.
    
    Útil para entender por qué se filtraron ciertas entradas.
    
    Returns
    -------
    pd.DataFrame
        Resumen de condiciones para cada entry_date.
    """
    results = []
    
    for date in entry_dates:
        if date not in features.index:
            results.append({
                'date': date,
                'iv_pctl': np.nan,
                'spread_var_pctl': np.nan,
                'expansion': np.nan,
                'would_enter': False,
                'reason': 'no_data'
            })
            continue
        
        row = features.loc[date]
        
        iv_ok = row['iv_pctl'] < config.ivp_threshold if not pd.isna(row['iv_pctl']) else False
        spread_ok = row['spread_var_pctl'] < config.spread_pctl_threshold if not pd.isna(row['spread_var_pctl']) else False
        expansion_ok = row['expansion_signal'] if not pd.isna(row['expansion_signal']) else False
        
        if not config.use_expansion_filter:
            expansion_ok = True
        
        would_enter = iv_ok and spread_ok and expansion_ok
        
        # Determinar razón de rechazo
        if would_enter:
            reason = 'enter'
        elif not iv_ok:
            reason = 'iv_too_high'
        elif not spread_ok:
            reason = 'spread_too_high'
        else:
            reason = 'no_expansion'
        
        results.append({
            'date': date,
            'iv': row['iv'],
            'iv_pctl': row['iv_pctl'],
            'rv_long': row['rv_long'],
            'spread_var': row['spread_var'],
            'spread_var_pctl': row['spread_var_pctl'],
            'expansion': row['expansion_signal'],
            'would_enter': would_enter,
            'reason': reason
        })
    
    return pd.DataFrame(results)


def summarize_features(features: pd.DataFrame) -> dict:
    """
    Genera estadísticas descriptivas de los features calculados.
    
    Útil para calibrar umbrales y entender la distribución de señales.
    """
    summary = {
        'iv': {
            'mean': features['iv'].mean(),
            'std': features['iv'].std(),
            'min': features['iv'].min(),
            'max': features['iv'].max(),
            'median': features['iv'].median()
        },
        'rv_long': {
            'mean': features['rv_long'].mean(),
            'std': features['rv_long'].std(),
            'min': features['rv_long'].min(),
            'max': features['rv_long'].max(),
            'median': features['rv_long'].median()
        },
        'spread_var': {
            'mean': features['spread_var'].mean(),
            'std': features['spread_var'].std(),
            'pct_positive': (features['spread_var'] > 0).mean() * 100,
            'pct_negative': (features['spread_var'] < 0).mean() * 100
        },
        'expansion_signal': {
            'pct_true': features['expansion_signal'].mean() * 100
        }
    }
    
    return summary