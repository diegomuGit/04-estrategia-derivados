"""
Delta Hedge Module
==================
Lógica de delta hedging para la estrategia de straddle.
El hedge se aplica a nivel de cartera (delta agregado de todas las posiciones).
"""

import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class HedgeConfig:
    """
    Configuración del delta hedge.
    
    Parameters
    ----------
    rebalance_freq : str
        'daily': rebalancear cada día
        'weekly': rebalancear solo los lunes (o primer día hábil de la semana)
        'threshold': rebalancear cuando |delta| supera un umbral
    delta_threshold : float
        Solo para modo 'threshold'. Rebalancear cuando |delta_cartera| > umbral.
    include_costs : bool
        Si True, incluir costes de transacción en el P&L.
    cost_per_share : float
        Coste por acción (comisión + slippage estimado).
    multiplier : int
        Multiplicador del contrato de opciones (100 para SPY).
    """
    rebalance_freq: str = 'daily'
    delta_threshold: float = 0.10
    include_costs: bool = False
    cost_per_share: float = 0.01
    multiplier: int = 100


@dataclass
class HedgeState:
    """
    Estado actual del hedge.
    
    Trackea las acciones en cartera y el P&L acumulado del hedge.
    """
    shares_held: float = 0.0
    cumulative_pnl: float = 0.0
    cumulative_costs: float = 0.0
    last_rebalance_date: Optional[str] = None


@dataclass 
class HedgeTrade:
    """Registro de una operación de rebalanceo."""
    date: str
    delta_portfolio: float
    shares_before: float
    shares_after: float
    shares_traded: float
    spot_price: float
    trade_cost: float


def should_rebalance(
    date: str,
    config: HedgeConfig,
    delta_portfolio: float,
    state: HedgeState,
    trading_days: List[str]
) -> bool:
    """
    Determina si se debe rebalancear el hedge en esta fecha.
    
    Returns
    -------
    bool
        True si se debe rebalancear.
    """
    
    if config.rebalance_freq == 'daily':
        return True
    
    elif config.rebalance_freq == 'weekly':
        # Rebalancear si es lunes (o primer día hábil de la semana)
        current_date = pd.Timestamp(date)
        
        # Encontrar el lunes de esta semana
        monday = current_date - pd.Timedelta(days=current_date.dayofweek)
        week_end = monday + pd.Timedelta(days=6)
        
        # Buscar el primer día de trading de esta semana
        trading_days_dt = pd.to_datetime(trading_days)
        days_in_week = trading_days_dt[
            (trading_days_dt >= monday) & 
            (trading_days_dt <= week_end)
        ]
        
        if len(days_in_week) > 0:
            first_trading_day = days_in_week[0].strftime('%Y-%m-%d')
            return date == first_trading_day
        
        return False
    
    elif config.rebalance_freq == 'threshold':
        # Rebalancear si |delta| supera el umbral
        return abs(delta_portfolio) > config.delta_threshold
    
    else:
        raise ValueError(f"rebalance_freq '{config.rebalance_freq}' no soportado.")


def calculate_target_shares(delta_portfolio: float, multiplier: int) -> float:
    """
    Calcula las acciones objetivo para neutralizar el delta.
    
    Para neutralizar: compramos/vendemos acciones en dirección opuesta al delta.
    Si delta > 0, vendemos acciones (short).
    Si delta < 0, compramos acciones (long).
    
    Parameters
    ----------
    delta_portfolio : float
        Delta agregado de la cartera de opciones.
    multiplier : int
        Multiplicador del contrato (100 para SPY).
    
    Returns
    -------
    float
        Número de acciones objetivo (negativo = short, positivo = long).
    """
    return -delta_portfolio * multiplier


def calculate_hedge_pnl(
    shares_held: float,
    spot_yesterday: float,
    spot_today: float
) -> float:
    """
    Calcula el P&L del hedge por el movimiento del spot.
    
    P&L = acciones * (precio_hoy - precio_ayer)
    """
    return shares_held * (spot_today - spot_yesterday)


def calculate_rebalance_cost(
    shares_before: float,
    shares_after: float,
    cost_per_share: float
) -> float:
    """
    Calcula el coste de rebalancear.
    
    Coste = |acciones_nuevas - acciones_anteriores| * coste_por_accion
    """
    shares_traded = abs(shares_after - shares_before)
    return shares_traded * cost_per_share


def execute_rebalance(
    date: str,
    delta_portfolio: float,
    spot: float,
    state: HedgeState,
    config: HedgeConfig
) -> HedgeTrade:
    """
    Ejecuta el rebalanceo y actualiza el estado.
    
    Returns
    -------
    HedgeTrade
        Registro de la operación.
    """
    shares_before = state.shares_held
    shares_after = calculate_target_shares(delta_portfolio, config.multiplier)
    shares_traded = shares_after - shares_before
    
    # Calcular coste si aplica
    trade_cost = 0.0
    if config.include_costs:
        trade_cost = calculate_rebalance_cost(shares_before, shares_after, config.cost_per_share)
        state.cumulative_costs += trade_cost
    
    # Actualizar estado
    state.shares_held = shares_after
    state.last_rebalance_date = date
    
    return HedgeTrade(
        date=date,
        delta_portfolio=delta_portfolio,
        shares_before=shares_before,
        shares_after=shares_after,
        shares_traded=shares_traded,
        spot_price=spot,
        trade_cost=trade_cost
    )