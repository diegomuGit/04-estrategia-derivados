import numpy as np

def get_risk_free_rate(T_days, curve_row):
    """
    Obtiene la tasa libre de riesgo mediante interpolación lineal o 
    asignación directa según la lógica de tenores.
    
    Lógica:
    - Si T < 30 días: Usa r(1M) directamente (sin extrapolación).
    - Si 30 <= T <= 365: Interpola linealmente entre los puntos de la curva.
    - Si T > 365 días: Usa r(1Y) (cap en el punto máximo).
    
    Returns:
        float: Tasa libre de riesgo interpolada
    """
    # Definimos los puntos observados
    tenors = np.array([30, 90, 180, 365])
    rates = np.array([
        curve_row[30], 
        curve_row[90], 
        curve_row[180], 
        curve_row[365]
    ])
    
    # Caso 1: T inferior al punto más corto (1 mes)
    if T_days <= 30:
        return curve_row[30]
    
    # Caso 2: T superior al punto más largo (1 año)
    if T_days >= 365:
        return curve_row[365]
    
    # Caso 3: Interpolación lineal inteligente entre 30 y 365 días
    return np.interp(T_days, tenors, rates)