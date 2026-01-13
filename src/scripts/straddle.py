"""
Straddle Pricing and Greeks
============================
Funciones para pricing y cálculo de griegas de straddles (call + put ATM).
Incluye versiones BSM (europeas) y QuantLib (americanas).
"""

import pandas as pd
import numpy as np

from black_scholes import (
    black_scholes_merton,
    calculate_delta,
    calculate_gamma,
    calculate_vega,
    calculate_theta,
    calculate_rho,
    ql_greeks_american,
    days_to_expiry_string,
    HAS_QL  # Importar la variable para no duplicarla
)


def price_straddle(S, K, T, r, q, sigma):
    """
    Calcula el precio de un Straddle (Call + Put ATM).
    
    Returns:
    --------
    dict
        Precios de call, put y straddle total
    """
    call_price = black_scholes_merton(S, K, T, r, q, sigma, 'call')
    put_price = black_scholes_merton(S, K, T, r, q, sigma, 'put')
    
    return {
        'call': call_price,
        'put': put_price,
        'straddle': call_price + put_price
    }


def calculate_straddle_greeks(S, K, T, r, q, sigma):
    """
    Calcula los Greeks de un Straddle (Call + Put) usando BSM.
    
    ESTA ES LA FUNCIÓN PRINCIPAL QUE USA EL BACKTEST.

    SIMPLIFICACIÓN DOCUMENTADA:
    ---------------------------
    Esta función usa la misma sigma para call y put, ignorando el volatility skew.
    
    Justificación académica:
    1. Para straddles ATM con tenores cortos (≤30d), la diferencia de IV entre
       call y put es relativamente pequeña (típicamente 0.5-2 vol points)
    2. El error introducido en el precio total es ~1-3%, aceptable para este análisis
    3. Es coherente con el uso de Black-Scholes (que asume vol constante)
    4. El VIX como proxy representa una volatilidad "promedio del mercado"
    
    Limitación conocida:
    - En la realidad, los puts ATM tienen IV ligeramente superior a las calls
    - Esto subestima marginalmente el vega y precio del straddle
    
    Para un straddle ATM:
    - Delta ≈ 0 (neutralidad direccional)
    - Gamma > 0 (alto, beneficia de movimientos grandes)
    - Vega > 0 (alto, beneficia de aumentos en volatilidad)
    - Theta < 0 (sufre time decay)
    
    Returns:
    --------
    dict
        Greeks del straddle completo
    """
    # Call Greeks
    delta_call = calculate_delta(S, K, T, r, q, sigma, 'call')
    theta_call = calculate_theta(S, K, T, r, q, sigma, 'call')
    rho_call = calculate_rho(S, K, T, r, q, sigma, 'call')
    
    # Put Greeks
    delta_put = calculate_delta(S, K, T, r, q, sigma, 'put')
    theta_put = calculate_theta(S, K, T, r, q, sigma, 'put')
    rho_put = calculate_rho(S, K, T, r, q, sigma, 'put')
    
    # Greeks que se suman igual para Call y Put
    gamma = calculate_gamma(S, K, T, r, q, sigma)
    vega = calculate_vega(S, K, T, r, q, sigma)
    
    return {
        'delta': delta_call + delta_put,
        'gamma': gamma * 2,  # Se suma
        'vega': vega * 2,    # Se suma
        'theta': theta_call + theta_put,
        'rho': rho_call + rho_put
    }


def calculate_straddle_greeks_precise(S, K, T, r, q, sigma_call, sigma_put):
    """
    Versión precisa usando IV diferenciadas para call y put.
    Útil para análisis puntual con datos de mercado reales.
    
    Para backtest histórico, usar la versión simplificada con sigma única (VIX).
    """
    # Call Greeks con su IV específica
    delta_call = calculate_delta(S, K, T, r, q, sigma_call, 'call')
    gamma_call = calculate_gamma(S, K, T, r, q, sigma_call)
    vega_call = calculate_vega(S, K, T, r, q, sigma_call)
    theta_call = calculate_theta(S, K, T, r, q, sigma_call, 'call')
    rho_call = calculate_rho(S, K, T, r, q, sigma_call, 'call')
    
    # Put Greeks con su IV específica
    delta_put = calculate_delta(S, K, T, r, q, sigma_put, 'put')
    gamma_put = calculate_gamma(S, K, T, r, q, sigma_put)
    vega_put = calculate_vega(S, K, T, r, q, sigma_put)
    theta_put = calculate_theta(S, K, T, r, q, sigma_put, 'put')
    rho_put = calculate_rho(S, K, T, r, q, sigma_put, 'put')
    
    return {
        'delta': delta_call + delta_put,
        'gamma': gamma_call + gamma_put,
        'vega': vega_call + vega_put,
        'theta': theta_call + theta_put,
        'rho': rho_call + rho_put
    }


def calculate_straddle_greeks_american(S, K, T, r, q, sigma,
                                        call_price=None, put_price=None):
    """
    Calcula griegas de un straddle usando pricing americano con QuantLib.

    FUNCIÓN PARA ANÁLISIS COMPARATIVO BSM vs AMERICAN.
    El backtest usa calculate_straddle_greeks() (BSM) por defecto.

    Si QuantLib no está disponible, hace fallback a BSM europeo.

    Parameters
    ----------
    S : float
        Precio spot del subyacente
    K : float
        Strike del straddle (mismo para call y put)
    T : float
        Tiempo hasta vencimiento en años
    r : float
        Tasa libre de riesgo (anualizada, en decimal)
    q : float
        Dividend yield (anualizado, en decimal)
    sigma : float
        Volatilidad implícita (anualizada, en decimal)
    call_price : float, optional
        Precio de mercado del call. Si no se proporciona, se calcula con BSM.
    put_price : float, optional
        Precio de mercado del put. Si no se proporciona, se calcula con BSM.

    Returns
    -------
    dict
        Diccionario con 'delta', 'gamma', 'vega', 'theta' del straddle
        También incluye 'method' ('american_ql' o 'bsm_fallback')

    Notes
    -----
    El straddle es la suma de call + put con mismo strike y vencimiento.
    Las griegas del straddle son la suma de las griegas individuales.

    Examples
    --------
    >>> # Comparar BSM vs American
    >>> greeks_bsm = calculate_straddle_greeks(450, 450, 0.0822, 0.05, 0.015, 0.20)
    >>> greeks_am = calculate_straddle_greeks_american(450, 450, 0.0822, 0.05, 0.015, 0.20)
    >>> print(f"Delta diff: {greeks_am['delta'] - greeks_bsm['delta']:.6f}")
    >>>
    >>> # Usar precios de mercado reales (recomendado)
    >>> greeks_am = calculate_straddle_greeks_american(
    ...     450, 450, 0.0822, 0.05, 0.015, 0.20,
    ...     call_price=10.5, put_price=9.8
    ... )
    """

    if not HAS_QL:
        # Fallback a BSM europeo
        greeks_bsm = calculate_straddle_greeks(S, K, T, r, q, sigma)
        greeks_bsm['method'] = 'bsm_fallback'
        return greeks_bsm

    # Convertir T (años) a días y luego a fecha
    tenor_days = int(T * 365)
    today_str = pd.Timestamp.today().strftime('%Y-%m-%d')
    expiry_str = days_to_expiry_string(today_str, tenor_days)

    # Usar precios de mercado si se proporcionan, sino calcular con BSM
    if call_price is None:
        call_price = black_scholes_merton(S, K, T, r, q, sigma, 'call')
    if put_price is None:
        put_price = black_scholes_merton(S, K, T, r, q, sigma, 'put')
    
    # Calcular griegas americanas
    greeks_call = ql_greeks_american(call_price, S, K, expiry_str, r, q, 'C')
    greeks_put = ql_greeks_american(put_price, S, K, expiry_str, r, q, 'P')
    
    # Verificar si algún cálculo falló
    if np.isnan(greeks_call['delta']) or np.isnan(greeks_put['delta']):
        # Fallback a BSM si QuantLib falla
        greeks_bsm = calculate_straddle_greeks(S, K, T, r, q, sigma)
        greeks_bsm['method'] = 'bsm_fallback'
        return greeks_bsm
    
    # Sumar griegas del straddle (call + put)
    straddle_greeks = {
        'delta': greeks_call['delta'] + greeks_put['delta'],
        'gamma': greeks_call['gamma'] + greeks_put['gamma'],
        'vega': greeks_call['vega'] + greeks_put['vega'],
        'theta': greeks_call['theta'] + greeks_put['theta'],
        'rho': greeks_call['rho'] + greeks_put['rho'],
        'method': 'american_ql'
    }
    
    return straddle_greeks