from black_scholes import (
    black_scholes_merton,
    calculate_delta,
    calculate_gamma,
    calculate_vega,
    calculate_theta,
    calculate_rho
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
    Calcula los Greeks de un Straddle (Call + Put).
    
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