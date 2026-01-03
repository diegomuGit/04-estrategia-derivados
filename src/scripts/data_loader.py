import yfinance as yf
import pandas as pd
import numpy as np
import os
from fredapi import Fred
from dotenv import load_dotenv
load_dotenv()
fred_api_key = os.getenv('FRED_API_KEY')

def get_spy_history(start_date, end_date):

    """
    Obtiene el historial de precios del SPY y calcula el dividend yield dinámico.
    
    Args:
        start_date: Fecha de inicio del período
        end_date: Fecha de fin del período
        
    Returns:
        DataFrame con columnas 'Close' y 'q_yield' (dividend yield trimestral)
    """
    # Descargar datos históricos del SPY
    spy = yf.Ticker("SPY")
    spy_history = spy.history(start=start_date, end=end_date, auto_adjust=False)

    # Obtener historial de dividendos
    div_history = spy.dividends
    
    def div_yield_dinamico(row):
        # Calcular dividend yield usando dividendos de los últimos 12 meses
        fecha = row.name
        precio = row['Close']
        divs_12m = div_history[(div_history.index <= fecha) & (div_history.index > fecha - pd.DateOffset(months=12))].sum()
        q_yield = divs_12m / precio
        return q_yield
    
    # Aplicar cálculo de dividend yield a cada fila
    spy_history['q_yield'] = spy_history.apply(div_yield_dinamico, axis=1)
    
    # Eliminar información de zona horaria del índice
    spy_history.index = pd.to_datetime(spy_history.index).strftime('%Y-%m-%d')
    
    # Preparar DataFrame final con solo las columnas necesarias
    resultado = pd.DataFrame({
        'close_spy': spy_history['Close'],
        'q_yield': spy_history['q_yield']
    }, index=spy_history.index)
    
    return resultado

def get_vix_history(start_date,end_date):
    vix = yf.Ticker("^VIX")
    vix_history = vix.history(start=start_date, end=end_date, auto_adjust=True)
    vix_history = vix_history['Close'] / 100  # Normalizar a decimal
    vix_history.index = pd.to_datetime(vix_history.index).strftime('%Y-%m-%d')
    vix_history.name = 'close_vix'
    return vix_history

def load_treasury_curve(start_date, end_date):
    """
    Descarga puntos clave de la curva Treasury desde FRED y devuelve un DataFrame 
    normalizado en decimales con manejo de valores nulos (días festivos).
    """
    fred = Fred(api_key=fred_api_key)
    
    # Series de FRED para Treasury rates (Daily Treasury Bill/Yield Curve Rates)
    series = {
        30: 'DGS1MO',   # 1 month
        90: 'DGS3MO',   # 3 months  
        180: 'DGS6MO',  # 6 months
        365: 'DGS1',    # 1 year
    }
    
    curves = {}
    for days, serie_id in series.items():
        data = fred.get_series(serie_id, start_date, end_date)
        # Convertir a decimal (ej: 5.20 -> 0.052)
        curves[days] = pd.to_numeric(data, errors='coerce') / 100 
    
    df = pd.DataFrame(curves)
    df.index = pd.to_datetime(df.index).strftime('%Y-%m-%d')
    
    # Limpieza: Forward fill para cubrir fines de semana o festivos donde FRED no publica
    df = df.ffill().dropna()
    
    return df