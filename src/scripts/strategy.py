"""
Strategy Module
===============
Define la estructura de una posición de straddle y la lógica de scheduling
para la estrategia periódica.
"""

import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class StraddlePosition:
    """
    Representa una posición individual de straddle (long call + long put).
    
    Se inicializa al abrir la posición con los datos de entrada.
    Se actualiza diariamente con el valor mark-to-market.
    Se cierra al vencimiento con el valor intrínseco.
    """
    
    # Atributos de entrada (inmutables)
    entry_date: str
    expiry_date: str
    strike: float
    entry_price: float
    tenor_days: int
    
    # Atributos actualizables
    current_price: float = field(default=0.0)
    status: str = field(default='open')
    
    # Atributos de cierre
    exit_date: Optional[str] = field(default=None)
    exit_price: Optional[float] = field(default=None)
    
    @property
    def mtm_pnl(self) -> float:
        """P&L no realizado (mark-to-market)."""
        return self.current_price - self.entry_price
    
    @property
    def realized_pnl(self) -> Optional[float]:
        """P&L realizado (solo disponible tras el cierre)."""
        if self.status == 'closed' and self.exit_price is not None:
            return self.exit_price - self.entry_price
        return None
    
    def days_to_expiry(self, current_date: str) -> int:
        """Calcula los días restantes hasta vencimiento."""
        current = pd.Timestamp(current_date)
        expiry = pd.Timestamp(self.expiry_date)
        return max((expiry - current).days, 0)
    
    def time_to_expiry(self, current_date: str) -> float:
        """Calcula el tiempo hasta vencimiento en años (para BSM)."""
        return self.days_to_expiry(current_date) / 365.0
    
    def update_mtm(self, new_price: float) -> None:
        """Actualiza el precio mark-to-market."""
        self.current_price = new_price
    
    def close(self, exit_date: str, exit_price: float) -> None:
        """Cierra la posición."""
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.current_price = exit_price
        self.status = 'closed'
    
    def intrinsic_value(self, spot: float) -> float:
        """
        Calcula el valor intrínseco del straddle al vencimiento.
        
        Straddle intrinsic = |S - K|
        (el lado ITM vale S-K o K-S, el otro vale 0)
        """
        return abs(spot - self.strike)


def generate_entry_dates(
    start_date: str,
    end_date: str,
    trading_days: pd.Index,
    frequency: str = 'monthly'
) -> List[str]:
    """
    Genera las fechas de entrada para la estrategia periódica.
    
    Parameters
    ----------
    start_date : str
        Fecha de inicio del backtest (YYYY-MM-DD)
    end_date : str
        Fecha de fin del backtest (YYYY-MM-DD)
    trading_days : pd.Index
        Índice con los días de trading reales (del market_data)
    frequency : str
        'monthly': primer día hábil de cada mes
        'weekly': cada lunes (o primer día hábil de la semana)
        'biweekly': cada dos semanas
    
    Returns
    -------
    List[str]
        Lista de fechas de entrada en formato YYYY-MM-DD
    """
    
    # Convertir trading_days a DatetimeIndex para operaciones de fecha
    trading_days_dt = pd.to_datetime(trading_days)
    
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    
    entry_dates = []
    
    if frequency == 'monthly':
        # Generar primer día de cada mes en el rango
        current = start.replace(day=1)
        while current <= end:
            # Buscar el primer día de trading del mes
            month_start = current
            month_end = (current + pd.offsets.MonthEnd(1))
            
            # Filtrar días de trading en este mes
            days_in_month = trading_days_dt[
                (trading_days_dt >= month_start) & 
                (trading_days_dt <= month_end)
            ]
            
            if len(days_in_month) > 0:
                first_trading_day = days_in_month[0]
                # Solo añadir si está dentro del rango del backtest
                if first_trading_day >= start and first_trading_day <= end:
                    entry_dates.append(first_trading_day.strftime('%Y-%m-%d'))
            
            # Siguiente mes
            current = current + pd.offsets.MonthBegin(1)
    
    elif frequency == 'weekly':
        # Cada lunes (o primer día hábil de la semana)
        current = start
        while current <= end:
            # Encontrar el lunes de esta semana
            monday = current - pd.Timedelta(days=current.dayofweek)
            
            # Buscar el primer día de trading de esta semana
            week_end = monday + pd.Timedelta(days=6)
            days_in_week = trading_days_dt[
                (trading_days_dt >= monday) & 
                (trading_days_dt <= week_end)
            ]
            
            if len(days_in_week) > 0:
                first_trading_day = days_in_week[0]
                if first_trading_day >= start and first_trading_day <= end:
                    date_str = first_trading_day.strftime('%Y-%m-%d')
                    if date_str not in entry_dates:
                        entry_dates.append(date_str)
            
            # Siguiente semana
            current = monday + pd.Timedelta(days=7)
    
    elif frequency == 'biweekly':
        # Cada dos semanas desde el inicio
        current = start
        week_count = 0
        
        while current <= end:
            monday = current - pd.Timedelta(days=current.dayofweek)
            
            if week_count % 2 == 0:
                week_end = monday + pd.Timedelta(days=6)
                days_in_week = trading_days_dt[
                    (trading_days_dt >= monday) & 
                    (trading_days_dt <= week_end)
                ]
                
                if len(days_in_week) > 0:
                    first_trading_day = days_in_week[0]
                    if first_trading_day >= start and first_trading_day <= end:
                        date_str = first_trading_day.strftime('%Y-%m-%d')
                        if date_str not in entry_dates:
                            entry_dates.append(date_str)
            
            current = monday + pd.Timedelta(days=7)
            week_count += 1
    
    else:
        raise ValueError(f"Frequency '{frequency}' no soportada. Usar 'monthly', 'weekly' o 'biweekly'.")
    
    return sorted(entry_dates)


def calculate_expiry_date(entry_date: str, tenor_days: int, trading_days: pd.Index) -> str:
    """
    Calcula la fecha de vencimiento dado un tenor en días.
    
    Busca el día de trading más cercano a entry_date + tenor_days.
    Si ese día no es hábil, usa el siguiente día de trading.
    
    Parameters
    ----------
    entry_date : str
        Fecha de entrada (YYYY-MM-DD)
    tenor_days : int
        Días hasta vencimiento
    trading_days : pd.Index
        Días de trading disponibles
    
    Returns
    -------
    str
        Fecha de vencimiento (YYYY-MM-DD)
    """
    trading_days_dt = pd.to_datetime(trading_days)
    target_date = pd.Timestamp(entry_date) + pd.Timedelta(days=tenor_days)
    
    # Buscar el día de trading más cercano (igual o posterior)
    valid_days = trading_days_dt[trading_days_dt >= target_date]
    
    if len(valid_days) > 0:
        return valid_days[0].strftime('%Y-%m-%d')
    else:
        # Si no hay días posteriores, usar el último disponible
        return trading_days_dt[-1].strftime('%Y-%m-%d')