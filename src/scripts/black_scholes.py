"""
Black-Scholes-Merton Model
==========================
Implementación del modelo Black-Scholes-Merton para pricing de opciones europeas
con dividendos continuos.

Para opciones americanas sobre SPY, esta aproximación es válida para:
- Opciones ATM o cerca de ATM
- Tenors cortos (< 90 días)
- Dividendos bajos (~1.5% anual para SPY)

Error estimado: < 2% vs precios de mercado
"""

import numpy as np
from scipy.stats import norm
import pandas as pd

# Intento de importar QuantLib
try:
    import QuantLib as ql
    HAS_QL = True
except ImportError:
    HAS_QL = False
    print("QuantLib no disponible. Se usará BSM como fallback.")


# ═══════════════════════════════════════════════════════════════════════
# PRICING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def black_scholes_merton(S, K, T, r, q, sigma, option_type='call'):
    """
    Calcula el precio de una opción Europea (Call o Put) usando el modelo Black-Scholes-Merton.
    
    Parameters:
    -----------
    S : float
        Precio spot del subyacente.
    K : float
        Precio de ejercicio (Strike).
    T : float
        Tiempo hasta vencimiento en años (ej: 30/365).
    r : float
        Tasa libre de riesgo anualizada (decimal).
    q : float
        Dividend yield anual continuo (decimal).
    sigma : float
        Volatilidad anualizada (decimal).
    option_type : str
        'call' para opciones de compra, 'put' para opciones de venta.
    
    Returns:
    --------
    float : Precio teórico de la opción.
    """
    
    # Manejo del vencimiento (Valor intrínseco)
    if T <= 0:
        if option_type.lower() == 'call':
            return max(S - K, 0)
        else:
            return max(K - S, 0)

    # Cálculos comunes de d1 y d2
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type.lower() == 'call':
        # Fórmula para Call: S*e^(-qT)*N(d1) - K*e^(-rT)*N(d2)
        price = S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    elif option_type.lower() == 'put':
        # Fórmula para Put: K*e^(-rT)*N(-d2) - S*e^(-qT)*N(-d1)
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)
    else:
        raise ValueError("El argumento 'option_type' debe ser 'call' o 'put'.")
        
    return price


# ═══════════════════════════════════════════════════════════════════════
# GREEKS - Ajustados por Dividendos
# ═══════════════════════════════════════════════════════════════════════

def calculate_delta(S, K, T, r, q, sigma, option_type='call'):
    """
    Calcula Delta ajustado por dividendos.
    
    Delta mide la sensibilidad del precio de la opción al cambio en el spot.
    
    Para straddles ATM:
    - Delta Call ≈ 0.5 * exp(-q*T)
    - Delta Put ≈ -0.5 * exp(-q*T)
    - Delta Straddle ≈ 0 (casi neutralidad direccional)
    
    Parameters:
    -----------
    option_type : str
        'call' o 'put'
    
    Returns:
    --------
    float
        Delta de la opción
    """
    if T <= 0:
        if option_type == 'call':
            return 1.0 if S > K else 0.0
        else:
            return -1.0 if S < K else 0.0
    
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    
    if option_type == 'call':
        return np.exp(-q * T) * norm.cdf(d1)
    else:  # put
        return -np.exp(-q * T) * norm.cdf(-d1)


def calculate_gamma(S, K, T, r, q, sigma):
    """
    Calcula Gamma ajustado por dividendos.
    
    Gamma mide la sensibilidad del Delta al cambio en el spot.
    Es la segunda derivada del precio respecto al spot.
    
    - Gamma es máximo cuando ATM
    - Gamma > 0 para long options (call y put)
    - Para straddles: Gamma_straddle = Gamma_call + Gamma_put = 2 * Gamma
    
    Returns:
    --------
    float
        Gamma de la opción (mismo para Call y Put)
    """
    if T <= 0:
        return 0.0
    
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    
    gamma = np.exp(-q * T) * norm.pdf(d1) / (S * sigma * np.sqrt(T))
    return gamma


def calculate_vega(S, K, T, r, q, sigma):
    """
    Calcula Vega ajustado por dividendos.
    
    Vega mide la sensibilidad del precio de la opción a cambios en volatilidad.
    
    - Vega > 0 para long options (tanto call como put)
    - Vega es máximo cuando ATM
    - Para straddles: Vega es alto (beneficia de aumentos en volatilidad)
    
    Returns:
    --------
    float
        Vega de la opción (mismo para Call y Put)
        Expresado como cambio en precio por 1% de cambio en volatilidad
    """
    if T <= 0:
        return 0.0
    
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    
    # Vega por 1% de cambio en volatilidad
    vega = S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T) / 100
    return vega


def calculate_theta(S, K, T, r, q, sigma, option_type='call'):
    """
    Calcula Theta ajustado por dividendos.
    
    Theta mide el decaimiento del valor temporal de la opción por día.
    
    - Theta < 0 para long options (pierden valor con el tiempo)
    - Theta es máximo (en valor absoluto) cuando ATM
    - Para straddles: Theta es negativo (sufren time decay)
    
    Parameters:
    -----------
    option_type : str
        'call' o 'put'
    
    Returns:
    --------
    float
        Theta diario (cambio en precio por día que pasa)
    """
    if T <= 0:
        return 0.0
    
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    # Término común
    term1 = -S * np.exp(-q * T) * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
    
    if option_type == 'call':
        term2 = q * S * np.exp(-q * T) * norm.cdf(d1)
        term3 = -r * K * np.exp(-r * T) * norm.cdf(d2)
        theta = (term1 + term2 + term3) / 365  # Convertir a diario
    else:  # put
        term2 = -q * S * np.exp(-q * T) * norm.cdf(-d1)
        term3 = r * K * np.exp(-r * T) * norm.cdf(-d2)
        theta = (term1 + term2 + term3) / 365  # Convertir a diario
    
    return theta


def calculate_rho(S, K, T, r, q, sigma, option_type='call'):
    """
    Calcula Rho ajustado por dividendos.
    
    Rho mide la sensibilidad del precio de la opción a cambios en la tasa de interés.
    
    - Para opciones de corto plazo (< 90 días), Rho es pequeño
    - Rho_call > 0 (aumenta con tasas)
    - Rho_put < 0 (disminuye con tasas)
    
    Returns:
    --------
    float
        Rho (cambio en precio por 1% de cambio en tasa)
    """
    if T <= 0:
        return 0.0
    
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
    else:  # put
        rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100
    
    return rho


def calculate_all_greeks(S, K, T, r, q, sigma, option_type='call'):
    """
    Calcula todos los Greeks de una opción.
    
    Returns:
    --------
    dict
        Diccionario con todos los Greeks
    """
    return {
        'delta': calculate_delta(S, K, T, r, q, sigma, option_type),
        'gamma': calculate_gamma(S, K, T, r, q, sigma),
        'vega': calculate_vega(S, K, T, r, q, sigma),
        'theta': calculate_theta(S, K, T, r, q, sigma, option_type),
        'rho': calculate_rho(S, K, T, r, q, sigma, option_type)
    }

# ═══════════════════════════════════════════════════════════════════════
# QUANTLIB - AMERICAN OPTIONS
# ═══════════════════════════════════════════════════════════════════════

def days_to_expiry_string(entry_date, tenor_days):
    """
    Convierte entry_date + tenor_days a formato YYYYMMDD para QuantLib.
    
    Parameters
    ----------
    entry_date : str or pd.Timestamp
        Fecha de entrada (formato 'YYYY-MM-DD' o Timestamp)
    tenor_days : int
        Días hasta vencimiento
    
    Returns
    -------
    str
        Fecha de expiración en formato 'YYYYMMDD'
    
    Examples
    --------
    >>> days_to_expiry_string('2024-01-15', 30)
    '20240214'
    """
    expiry = pd.to_datetime(entry_date) + pd.Timedelta(days=tenor_days)
    return expiry.strftime('%Y%m%d')


def ql_greeks_american(price, S, K, expiry_str, r, q, right):
    """
    Calcula IV y griegas para opciones americanas usando QuantLib.
    
    Usa aproximación de Barone-Adesi-Whaley para calcular IV implícita,
    luego calcula griegas con Bjerksund-Stensland.
    
    Parameters
    ----------
    price : float
        Precio de mercado de la opción
    S : float
        Precio spot del subyacente
    K : float
        Strike de la opción
    expiry_str : str
        Fecha de expiración en formato 'YYYYMMDD'
    r : float
        Tasa libre de riesgo (anualizada, en decimal)
    q : float
        Dividend yield (anualizado, en decimal)
    right : str
        'C' para Call, 'P' para Put
    
    Returns
    -------
    dict
        Diccionario con keys: 'iv', 'delta', 'gamma', 'vega', 'theta', 'rho'
        Si falla el cálculo, retorna NaN en todos los valores
    
    Notes
    -----
    - Requiere QuantLib instalado (pip install QuantLib)
    - Vega retornado por cambio de 1% en volatilidad (no por 1 punto)
    - Theta retornado por día (no por año)
    - Rho retornado por cambio de 1% en tasa (no por 1 punto base)
    
    Examples
    --------
    >>> greeks = ql_greeks_american(10.5, 450, 450, '20240215', 0.05, 0.015, 'C')
    >>> print(f"Delta: {greeks['delta']:.4f}")
    """
    res = {
        "iv": float("nan"), 
        "delta": float("nan"), 
        "gamma": float("nan"),
        "vega": float("nan"), 
        "theta": float("nan"), 
        "rho": float("nan")
    }

    if not HAS_QL or price <= 0: 
        return res

    try:
        today = ql.Date.todaysDate()
        ql.Settings.instance().evaluationDate = today
        exp_date = ql.DateParser.parseFormatted(expiry_str, "%Y%m%d")

        opt_type = ql.Option.Call if right == "C" else ql.Option.Put
        payoff = ql.PlainVanillaPayoff(opt_type, K)
        exercise = ql.AmericanExercise(today, exp_date)

        spot_handle = ql.QuoteHandle(ql.SimpleQuote(S))
        day_count = ql.Actual365Fixed()
        r_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(today, r, day_count)
        )
        q_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(today, q, day_count)
        )

        # --- FASE 1: IV con Barone-Adesi-Whaley ---
        option_calc = ql.VanillaOption(payoff, exercise)
        vol_dummy = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(
                today, 
                ql.UnitedStates(ql.UnitedStates.NYSE), 
                0.20, 
                day_count
            )
        )
        process_calc = ql.BlackScholesMertonProcess(
            spot_handle, q_ts, r_ts, vol_dummy
        )
        option_calc.setPricingEngine(
            ql.BaroneAdesiWhaleyApproximationEngine(process_calc)
        )

        try:
            iv = option_calc.impliedVolatility(
                price, process_calc, 1e-4, 100, 1e-4, 4.0
            )
        except RuntimeError:
            return res

        res["iv"] = iv

        # --- FASE 2: Griegas con Bjerksund-Stensland ---
        option_greeks = ql.VanillaOption(payoff, exercise)
        vol_final = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(
                today, 
                ql.UnitedStates(ql.UnitedStates.NYSE), 
                iv, 
                day_count
            )
        )
        process_final = ql.BlackScholesMertonProcess(
            spot_handle, q_ts, r_ts, vol_final
        )

        option_greeks.setPricingEngine(
            ql.BjerksundStenslandApproximationEngine(process_final)
        )

        res["delta"] = option_greeks.delta()
        res["gamma"] = option_greeks.gamma()
        res["vega"]  = option_greeks.vega() / 100.0  # Por 1% cambio en vol
        res["theta"] = option_greeks.theta() / 365.0  # Por día
        res["rho"]   = option_greeks.rho() / 100.0    # Por 1% cambio en r

    except Exception as e:
        print(f"Error interno QuantLib: {e}")
        pass

    return res


def calculate_option_greeks_american(S, K, T, r, q, sigma, option_type='call', 
                                     market_price=None):
    """
    Calcula griegas de una opción individual usando QuantLib (americanas).
    
    ÚTIL PARA PUNTO 5: Cuando necesites calcular griegas de opciones 
    individuales para hedging con otras opciones en lugar de con acciones.
    
    Parameters
    ----------
    S : float
        Precio spot del subyacente
    K : float
        Strike de la opción
    T : float
        Tiempo hasta vencimiento en años
    r : float
        Tasa libre de riesgo (anualizada, en decimal)
    q : float
        Dividend yield (anualizado, en decimal)
    sigma : float
        Volatilidad implícita (anualizada, en decimal)
    option_type : str, optional
        'call' o 'put'. Default: 'call'
    market_price : float, optional
        Precio de mercado. Si no se proporciona, se usa precio teórico BSM
    
    Returns
    -------
    dict
        Diccionario con griegas de la opción individual
    
    Examples
    --------
    >>> # Para el Punto 5: calcular griegas de una call OTM para hedging
    >>> greeks_hedge = calculate_option_greeks_american(
    ...     450, 455, 0.0822, 0.05, 0.015, 0.20, 'call'
    ... )
    >>> print(f"Delta de opción hedge: {greeks_hedge['delta']:.4f}")
    >>> print(f"Gamma de opción hedge: {greeks_hedge['gamma']:.6f}")
    """
    
    if not HAS_QL:
        # Fallback a BSM usando calculate_all_greeks
        greeks = calculate_all_greeks(S, K, T, r, q, sigma, option_type)
        greeks['method'] = 'bsm_fallback'
        return greeks
    
    # Convertir T a fecha de expiración
    tenor_days = int(T * 365)
    today_str = pd.Timestamp.today().strftime('%Y-%m-%d')
    expiry_str = days_to_expiry_string(today_str, tenor_days)
    
    # Si no hay precio de mercado, usar BSM como aproximación
    if market_price is None:
        market_price = black_scholes_merton(S, K, T, r, q, sigma, option_type)
    
    right = 'C' if option_type == 'call' else 'P'
    greeks = ql_greeks_american(market_price, S, K, expiry_str, r, q, right)
    greeks['method'] = 'american_ql'
    
    # Si falló, fallback a BSM
    if np.isnan(greeks['delta']):
        greeks = calculate_all_greeks(S, K, T, r, q, sigma, option_type)
        greeks['method'] = 'bsm_fallback'
    
    return greeks

# ═══════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════════

def implied_volatility_newton(option_price, S, K, T, r, q, option_type='call', 
                               initial_sigma=0.2, tolerance=1e-6, max_iterations=100):
    """
    Calcula volatilidad implícita usando método de Newton-Raphson.
    
    NOTA: Para backtesting usaremos VIX como proxy de IV, pero esta función
    es útil si quieres validar con precios de mercado reales.
    
    Parameters:
    -----------
    option_price : float
        Precio de mercado observado de la opción
    initial_sigma : float
        Volatilidad inicial para iterar (default: 20%)
    tolerance : float
        Tolerancia para convergencia
    max_iterations : int
        Máximo número de iteraciones
    
    Returns:
    --------
    float
        Volatilidad implícita (anualizada)
    """
    sigma = initial_sigma
    
    for i in range(max_iterations):
        if option_type == 'call':
            price = black_scholes_merton_call(S, K, T, r, q, sigma)
        else:
            price = black_scholes_merton_put(S, K, T, r, q, sigma)
        
        vega = calculate_vega(S, K, T, r, q, sigma) * 100  # Vega por 100% cambio
        
        diff = price - option_price
        
        if abs(diff) < tolerance:
            return sigma
        
        if vega == 0:
            return sigma
        
        sigma = sigma - diff / vega
        
        # Mantener sigma en rango razonable
        sigma = max(0.01, min(sigma, 3.0))
    
    # Si no converge, retornar última estimación
    return sigma


