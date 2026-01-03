"""
Backtest Module
===============
Motor de backtest para la estrategia de long straddle periodico.
Ejecuta la simulacion dia a dia, gestiona posiciones y calcula P&L.
Soporta delta hedging opcional a nivel de cartera.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from strategy import StraddlePosition, calculate_expiry_date
from straddle import price_straddle, calculate_straddle_greeks
from rates import get_risk_free_rate
from delta_hedge import (
    HedgeConfig, HedgeState, HedgeTrade,
    should_rebalance, calculate_target_shares,
    calculate_hedge_pnl, execute_rebalance
)


@dataclass
class BacktestResult:
    """
    Contenedor para los resultados del backtest.
    
    Si hedge_config es None, los campos de hedge estaran vacios.
    """
    # P&L del straddle (siempre presente)
    daily_pnl_straddle: pd.Series
    cumulative_pnl_straddle: pd.Series
    
    # P&L del hedge (solo si hedge_config != None)
    daily_pnl_hedge: pd.Series
    cumulative_pnl_hedge: pd.Series
    
    # P&L total (straddle + hedge - costes)
    daily_pnl_total: pd.Series
    cumulative_pnl_total: pd.Series
    
    # Trades y resumen
    trades: List[StraddlePosition]
    hedge_trades: List[HedgeTrade]
    summary: Dict


def run_backtest(
    market_data: pd.DataFrame,
    entry_dates: List[str],
    tenor_days: int = 30,
    hedge_config: Optional[HedgeConfig] = None
) -> BacktestResult:
    """
    Ejecuta el backtest de la estrategia de straddle periodico.
    
    Parameters
    ----------
    market_data : pd.DataFrame
        DataFrame con columnas: close_spy, close_vix, q_yield, 
        y tasas (30, 90, 180, 365). Index = fechas de trading.
    entry_dates : List[str]
        Fechas donde se abre un nuevo straddle.
    tenor_days : int
        Dias hasta vencimiento de cada straddle.
    hedge_config : HedgeConfig, optional
        Configuracion del delta hedge. Si es None, no se aplica hedge.
    
    Returns
    -------
    BacktestResult
        Objeto con P&L desglosado, trades y summary.
    """
    
    trading_days = market_data.index.tolist()
    
    # Listas para gestionar posiciones
    open_positions: List[StraddlePosition] = []
    closed_positions: List[StraddlePosition] = []
    
    # Series para P&L
    daily_pnl_straddle = pd.Series(index=trading_days, dtype=float)
    daily_pnl_straddle[:] = 0.0
    
    daily_pnl_hedge = pd.Series(index=trading_days, dtype=float)
    daily_pnl_hedge[:] = 0.0
    
    # Estado del hedge
    hedge_state = HedgeState() if hedge_config else None
    hedge_trades: List[HedgeTrade] = []
    
    # Variables para tracking
    spot_yesterday = None
    
    # Loop principal
    for date in trading_days:
        
        # --- Paso 1: Obtener datos del dia ---
        row = market_data.loc[date]
        S = row['close_spy']
        sigma = row['close_vix']
        q = row['q_yield']
        
        curve_row = {
            30: row[30],
            90: row[90],
            180: row[180],
            365: row[365]
        }
        
        # --- Paso 2: Calcular P&L del hedge (antes de actualizar posiciones) ---
        if hedge_config and spot_yesterday is not None and hedge_state.shares_held != 0:
            pnl_hedge_today = calculate_hedge_pnl(hedge_state.shares_held, spot_yesterday, S)
            hedge_state.cumulative_pnl += pnl_hedge_today
            daily_pnl_hedge[date] = pnl_hedge_today
        
        # --- Paso 3: Valorar posiciones abiertas y calcular delta de cartera ---
        delta_portfolio = 0.0
        
        for position in open_positions:
            T = position.time_to_expiry(date)
            
            if T > 0:
                days_remaining = position.days_to_expiry(date)
                r = get_risk_free_rate(days_remaining, curve_row)
                
                # Precio para MTM
                prices = price_straddle(S, position.strike, T, r, q, sigma)
                position.update_mtm(prices['straddle'])
                
                # Delta para hedge (si aplica)
                if hedge_config:
                    greeks = calculate_straddle_greeks(S, position.strike, T, r, q, sigma)
                    delta_portfolio += greeks['delta']
            else:
                # Al vencimiento
                position.update_mtm(position.intrinsic_value(S))
                # Delta al vencimiento: +1 si ITM call, -1 si ITM put
                if hedge_config:
                    if S > position.strike:
                        delta_portfolio += 1.0
                    elif S < position.strike:
                        delta_portfolio += -1.0
        
        # --- Paso 4: Cerrar posiciones que expiran ---
        positions_to_close = [p for p in open_positions if date >= p.expiry_date]
        
        for position in positions_to_close:
            intrinsic = position.intrinsic_value(S)
            position.close(date, intrinsic)
            open_positions.remove(position)
            closed_positions.append(position)
        
        # --- Paso 5: Abrir nueva posicion si es fecha de entrada ---
        if date in entry_dates:
            K = round(S)
            T = tenor_days / 365.0
            r = get_risk_free_rate(tenor_days, curve_row)
            
            prices = price_straddle(S, K, T, r, q, sigma)
            entry_price = prices['straddle']
            
            expiry_date = calculate_expiry_date(date, tenor_days, market_data.index)
            
            new_position = StraddlePosition(
                entry_date=date,
                expiry_date=expiry_date,
                strike=K,
                entry_price=entry_price,
                tenor_days=tenor_days,
                current_price=entry_price
            )
            open_positions.append(new_position)
            
            # Actualizar delta de cartera con la nueva posicion
            if hedge_config:
                greeks = calculate_straddle_greeks(S, K, T, r, q, sigma)
                delta_portfolio += greeks['delta']
        
        # --- Paso 6: Rebalancear hedge si corresponde ---
        if hedge_config and len(open_positions) > 0:
            if should_rebalance(date, hedge_config, delta_portfolio, hedge_state, trading_days):
                trade = execute_rebalance(date, delta_portfolio, S, hedge_state, hedge_config)
                hedge_trades.append(trade)
                
                # Restar costes del P&L del hedge
                if hedge_config.include_costs:
                    daily_pnl_hedge[date] -= trade.trade_cost
        
        # Si no hay posiciones abiertas, cerrar el hedge
        if hedge_config and len(open_positions) == 0 and hedge_state.shares_held != 0:
            # Liquidar posicion de acciones
            trade = execute_rebalance(date, 0.0, S, hedge_state, hedge_config)
            hedge_trades.append(trade)
            if hedge_config.include_costs:
                daily_pnl_hedge[date] -= trade.trade_cost
        
        # --- Paso 7: Calcular P&L del straddle ---
        mtm_total = sum(p.mtm_pnl for p in open_positions)
        realized_today = sum(p.realized_pnl for p in positions_to_close)
        daily_pnl_straddle[date] = mtm_total + realized_today
        
        # Guardar spot para calcular P&L del hedge manana
        spot_yesterday = S
    
    # Construir resultados
    all_trades = closed_positions + open_positions
    
    cumulative_pnl_straddle = daily_pnl_straddle.cumsum()
    cumulative_pnl_hedge = daily_pnl_hedge.cumsum()
    
    daily_pnl_total = daily_pnl_straddle + daily_pnl_hedge
    cumulative_pnl_total = daily_pnl_total.cumsum()
    
    summary = _calculate_summary(
        daily_pnl_straddle, cumulative_pnl_straddle,
        daily_pnl_hedge, cumulative_pnl_hedge,
        daily_pnl_total, cumulative_pnl_total,
        all_trades, hedge_trades, hedge_config
    )
    
    return BacktestResult(
        daily_pnl_straddle=daily_pnl_straddle,
        cumulative_pnl_straddle=cumulative_pnl_straddle,
        daily_pnl_hedge=daily_pnl_hedge,
        cumulative_pnl_hedge=cumulative_pnl_hedge,
        daily_pnl_total=daily_pnl_total,
        cumulative_pnl_total=cumulative_pnl_total,
        trades=all_trades,
        hedge_trades=hedge_trades,
        summary=summary
    )


def _calculate_summary(
    daily_pnl_straddle: pd.Series,
    cumulative_pnl_straddle: pd.Series,
    daily_pnl_hedge: pd.Series,
    cumulative_pnl_hedge: pd.Series,
    daily_pnl_total: pd.Series,
    cumulative_pnl_total: pd.Series,
    trades: List[StraddlePosition],
    hedge_trades: List[HedgeTrade],
    hedge_config: Optional[HedgeConfig]
) -> Dict:
    """Calcula metricas resumen del backtest."""
    
    closed_trades = [t for t in trades if t.status == 'closed']
    
    if len(closed_trades) == 0:
        return {'error': 'No hay trades cerrados para analizar'}
    
    # Metricas del straddle
    trade_pnls = [t.realized_pnl for t in closed_trades]
    total_pnl_straddle = sum(trade_pnls)
    num_trades = len(closed_trades)
    avg_pnl = total_pnl_straddle / num_trades
    
    winners = [pnl for pnl in trade_pnls if pnl > 0]
    losers = [pnl for pnl in trade_pnls if pnl <= 0]
    win_rate = len(winners) / num_trades if num_trades > 0 else 0
    
    avg_win = np.mean(winners) if winners else 0
    avg_loss = np.mean(losers) if losers else 0
    
    best_trade = max(trade_pnls)
    worst_trade = min(trade_pnls)
    
    # Max drawdown sobre P&L total
    rolling_max = cumulative_pnl_total.cummax()
    drawdown = cumulative_pnl_total - rolling_max
    max_drawdown = drawdown.min()
    
    # Profit factor
    gross_profit = sum(winners) if winners else 0
    gross_loss = abs(sum(losers)) if losers else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf
    
    summary = {
        # Metricas del straddle
        'total_pnl_straddle': total_pnl_straddle,
        'num_trades': num_trades,
        'avg_pnl_per_trade': avg_pnl,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'best_trade': best_trade,
        'worst_trade': worst_trade,
        'open_positions': len([t for t in trades if t.status == 'open'])
    }
    
    # Metricas del hedge (si aplica)
    if hedge_config:
        total_pnl_hedge = cumulative_pnl_hedge.iloc[-1] if len(cumulative_pnl_hedge) > 0 else 0
        total_costs = sum(t.trade_cost for t in hedge_trades)
        
        summary.update({
            'total_pnl_hedge': total_pnl_hedge,
            'hedge_num_rebalances': len(hedge_trades),
            'hedge_total_costs': total_costs,
            'hedge_config': hedge_config.rebalance_freq
        })
    
    # Metricas totales
    summary.update({
        'total_pnl': cumulative_pnl_total.iloc[-1] if len(cumulative_pnl_total) > 0 else 0,
        'max_drawdown': max_drawdown,
        'profit_factor': profit_factor
    })
    
    return summary


def prepare_market_data(
    spy_data: pd.DataFrame, 
    vix_data: pd.Series, 
    treasury_data: pd.DataFrame
) -> pd.DataFrame:
    """
    Consolida los datos de mercado en un unico DataFrame.
    """
    market_data = spy_data.copy()
    market_data['close_vix'] = vix_data
    
    for col in treasury_data.columns:
        market_data[col] = treasury_data[col]
    
    market_data = market_data.dropna()
    
    return market_data