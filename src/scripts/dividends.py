import yfinance as yf
import pandas as pd
import numpy as np



def implied_dividend_yield(C, P, S, K, r, T):
    """
    Calcula el rendimiento por dividendo implícito utilizando los precios de las opciones de compra y venta.
    
    Parámetros:
    C : float : Precio de la opción de compra
    P : float : Precio de la opción de venta
    S : float : Precio actual del activo subyacente
    K : float : Precio de ejercicio de las opciones
    r : float : Tasa libre de riesgo anualizada (en decimal)
    T : float : Tiempo hasta el vencimiento en años
    
    Retorna:
    q : float : Rendimiento por dividendo implícito (en decimal)
    """
    q = - (1 / T) * np.log((C - P + K * np.exp(-r * T)) / S)
    return q