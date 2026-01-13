"""
Options Hedge Module
====================
Módulo para análisis de estrategias de cobertura de straddles usando opciones.

Incluye:
- Dataclasses para representar opciones de hedge y resultados de análisis
- Clase OptionsHedgeAnalyzer para ejecutar análisis completo de 8 estrategias
- Funciones auxiliares para cálculo de volatilidad implícita y dividend yield
"""

import math
from dataclasses import dataclass
from typing import List, Literal
from black_scholes import black_scholes_merton, calculate_all_greeks
from ib_insync import Stock, Option


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class StraddleForHedge:
    """
    Representa un straddle con todos los datos necesarios para análisis de hedge.
    """
    spot: float
    strike: float
    expiry: str          # Formato YYYYMMDD
    T: float             # Tiempo a vencimiento en años
    r: float             # Tasa libre de riesgo
    q: float             # Dividend yield
    sigma: float         # Volatilidad implícita promedio
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


@dataclass
class HedgeOption:
    """
    Representa una opción de cobertura con sus griegas e impactos.
    """
    option_type: str     # 'call' o 'put'
    strike: float
    expiry: str
    T: float
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    contracts: float = 0.0         # Número de contratos (+ compra, - venta)
    delta_impact: float = 0.0
    gamma_impact: float = 0.0
    vega_impact: float = 0.0
    theta_impact: float = 0.0
    rho_impact: float = 0.0


@dataclass
class HedgeAnalysisResult:
    """
    Resultado del análisis de una estrategia de hedge.
    """
    strategy_name: str
    straddle: StraddleForHedge
    hedge: HedgeOption
    total_delta: float
    total_gamma: float
    total_vega: float
    total_theta: float
    total_rho: float
    delta_neutrality: float       # |total_delta| - cercano a 0 es mejor
    gamma_retention_pct: float    # % gamma retenido vs straddle original
    vega_retention_pct: float     # % vega retenido vs straddle original
    theta_change_pct: float       # % cambio en theta vs straddle original
    hedge_premium: float          # Prima pagada (+) o cobrada (-)


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════════════════════

def get_smart_price(ticker) -> float:
    """
    Obtiene el mejor precio disponible de un ticker de IBKR.

    Prioridad: last > close > modelPrice > midpoint

    Args:
        ticker: Ticker de ib_insync con datos de mercado

    Returns:
        float: Mejor precio disponible, o 0.0 si no hay precio válido
    """
    if ticker.last and math.isfinite(ticker.last) and ticker.last > 0:
        return ticker.last
    if ticker.close and math.isfinite(ticker.close) and ticker.close > 0:
        return ticker.close
    if ticker.modelGreeks and ticker.modelGreeks.optPrice:
        mp = ticker.modelGreeks.optPrice
        if math.isfinite(mp) and mp > 0:
            return mp
    if ticker.bid and ticker.ask and ticker.bid > 0 and ticker.ask > 0:
        return (ticker.bid + ticker.ask) / 2.0
    return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# CLASE PRINCIPAL: OptionsHedgeAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════

class OptionsHedgeAnalyzer:
    """
    Analizador de estrategias de cobertura para straddles.

    Evalúa 8 estrategias de hedge:
    - 4 ventas: Call ATM, Call OTM, Put ATM, Put OTM
    - 4 compras: Call ATM, Call OTM, Put ATM, Put OTM

    Ejemplo de uso:
    ```python
    analyzer = OptionsHedgeAnalyzer(ib)
    straddle = StraddleForHedge(spot=692, strike=692, ...)
    results = analyzer.run_full_analysis(straddle)
    ```
    """

    def __init__(self, ib, otm_offset_pct: float = 0.02, multiplier: int = 100, df_option_chain=None):
        """
        Inicializa el analizador.

        Args:
            ib: Conexión activa de ib_insync
            otm_offset_pct: Porcentaje de distancia para opciones OTM (default: 2%)
            multiplier: Multiplicador del contrato (default: 100)
            df_option_chain: (Opcional) DataFrame con cadena de opciones pre-descargada.
                           Debe contener las columnas: strike, call_conId, put_conId.
                           Si se provee, los strikes se buscarán en este DataFrame
                           en lugar de solicitarlos nuevamente a IBKR, evitando
                           inconsistencias en la selección de strikes.

        Raises:
            ValueError: Si df_option_chain no contiene las columnas requeridas
        """
        self.ib = ib
        self.OTM_OFFSET_PCT = otm_offset_pct
        self.MULTIPLIER = multiplier
        self.df_option_chain = df_option_chain

        # Validar DataFrame si se provee
        if df_option_chain is not None:
            import pandas as pd
            required_cols = ['strike', 'call_conId', 'put_conId']
            if not all(col in df_option_chain.columns for col in required_cols):
                raise ValueError(
                    f"df_option_chain debe contener las columnas: {required_cols}. "
                    f"Columnas recibidas: {list(df_option_chain.columns)}"
                )
            if df_option_chain.empty:
                raise ValueError("df_option_chain no puede estar vacío")

    def find_hedge_option(
        self,
        straddle: StraddleForHedge,
        option_type: Literal['call', 'put'],
        moneyness: Literal['atm', 'otm'],
        verbose: bool = True
    ) -> HedgeOption:
        """
        Encuentra la opción de cobertura apropiada.

        Si se proporcionó df_option_chain en el constructor, busca el strike
        en ese DataFrame. Caso contrario, solicita la cadena a IBKR (comportamiento
        original).

        En ambos casos, siempre solicita el precio actual a IBKR.

        Args:
            straddle: El straddle que queremos cubrir
            option_type: 'call' o 'put'
            moneyness: 'atm' o 'otm'
            verbose: Si True, imprime información

        Returns:
            HedgeOption con toda la información

        Raises:
            ValueError: Si el strike no existe en df_option_chain
            RuntimeError: Si no se puede obtener precio de IBKR
        """
        import pandas as pd

        S = straddle.spot

        # Determinar strike objetivo
        if moneyness == 'atm':
            K_target = round(S)
            if verbose:
                print(f"ATM Target Strike: {K_target}")
        else:  # otm
            if option_type == 'call':
                K_target = round(S * (1 + self.OTM_OFFSET_PCT))
                if verbose:
                    print(f"OTM Call Target Strike: {K_target}")
            else:  # put
                K_target = round(S * (1 - self.OTM_OFFSET_PCT))
                if verbose:
                    print(f"OTM Put Target Strike: {K_target}")

        # ========================================
        # NUEVO: Buscar strike en DataFrame si está disponible
        # ========================================
        if self.df_option_chain is not None:
            if verbose:
                print(f"   -> Buscando {option_type.upper()} {moneyness.upper()} (K~${K_target:.0f})...", end=" ")

            # Buscar strike más cercano EN EL DATAFRAME
            df = self.df_option_chain.copy()
            df['distance'] = abs(df['strike'] - K_target)
            K_actual = df.loc[df['distance'].idxmin(), 'strike']

            # Obtener conId según el tipo de opción
            row = df[df['strike'] == K_actual].iloc[0]
            con_id = row['call_conId'] if option_type == 'call' else row['put_conId']

            # Validar que el conId exista
            if pd.isna(con_id):
                raise ValueError(
                    f"No existe {option_type.upper()} para strike {K_actual} "
                    f"en el DataFrame provisto"
                )

            if verbose:
                print(f"K=${K_actual:.0f} (desde DataFrame)")

        else:
            # ========================================
            # FALLBACK: Comportamiento original (IBKR)
            # ========================================
            if verbose:
                print(f"   -> Buscando {option_type.upper()} {moneyness.upper()} (K~${K_target:.0f}) desde IBKR...", end=" ")

            # Obtener cadena de IBKR
            spy = Stock("SPY", "SMART", "USD")
            self.ib.qualifyContracts(spy)
            chains = self.ib.reqSecDefOptParams(spy.symbol, "", spy.secType, spy.conId)
            chain = next(c for c in chains if c.exchange == "SMART")

            # Strike más cercano
            strikes = [k for k in chain.strikes if k % 1 == 0]
            K_actual = min(strikes, key=lambda k: abs(k - K_target))

            if verbose:
                print(f"K seleccionado: {K_actual}")
        
        # Crear contrato
        opt = Option(
            "SPY",
            straddle.expiry,
            K_actual,
            "C" if option_type == 'call' else "P",
            "SMART",
            tradingClass="SPY",
            multiplier="100"
        )
        self.ib.qualifyContracts(opt)

        # Obtener precio
        ticker = self.ib.reqMktData(opt, "100,101,104,106", False, False)
        self.ib.sleep(1.5)
        price = get_smart_price(ticker)
        self.ib.cancelMktData(opt)

        if price <= 0:
            raise RuntimeError(f"No se pudo obtener precio para {option_type} K={K_actual}")

        if verbose:
            print(f"K=${K_actual:.0f}, Precio=${price:.2f}")

        # Calcular griegas usando funciones existentes
        greeks = calculate_all_greeks(
            S=S,
            K=K_actual,
            T=straddle.T,
            r=straddle.r,
            q=straddle.q,
            sigma=straddle.sigma,
            option_type=option_type
        )

        hedge = HedgeOption(
            option_type=option_type,
            strike=K_actual,
            expiry=straddle.expiry,
            T=straddle.T,
            price=price,
            delta=greeks['delta'],
            gamma=greeks['gamma'],
            vega=greeks['vega'],
            theta=greeks['theta'],
            rho=greeks['rho']
        )

        return hedge

    def calculate_hedge_contracts(
        self,
        straddle_delta: float,
        hedge_delta: float
    ) -> float:
        """
        Calcula el número de contratos necesarios para neutralizar delta.

        Fórmula:
            Delta_portfolio = Delta_straddle × 100
            Contratos = -Delta_portfolio / (Delta_hedge × 100)

        Args:
            straddle_delta: Delta del straddle (por contrato)
            hedge_delta: Delta de la opción de hedge (por contrato)

        Returns:
            Número de contratos (puede ser fraccionario)
            Negativo = vender, Positivo = comprar
        """
        if abs(hedge_delta) < 1e-6:
            return 0.0

        portfolio_delta = straddle_delta * self.MULTIPLIER
        contracts = -portfolio_delta / (hedge_delta * self.MULTIPLIER)

        return contracts

    def analyze_hedge_strategy(
        self,
        strategy_name: str,
        straddle: StraddleForHedge,
        hedge: HedgeOption,
        verbose: bool = True
    ) -> HedgeAnalysisResult:
        """
        Analiza una estrategia de hedge completa.

        El número de contratos (comprar/vender) se calcula automáticamente
        para neutralizar la delta del straddle. El signo del resultado indica:
        - Positivo: Comprar contratos
        - Negativo: Vender contratos

        Args:
            strategy_name: Nombre descriptivo de la estrategia
            straddle: El straddle original
            hedge: La opción de cobertura
            verbose: Si True, imprime resultados

        Returns:
            HedgeAnalysisResult con todos los detalles
        """
        if verbose:
            print(f"\n{'-'*70}")
            print(f"{strategy_name}")
            print(f"{'-'*70}")

        # 1. Calcular contratos necesarios (el signo indica buy/sell automáticamente)
        contracts = self.calculate_hedge_contracts(straddle.delta, hedge.delta)

        # Crear copia del hedge con contratos asignados
        hedge.contracts = contracts

        if verbose:
            action_str = "VENDER" if contracts < 0 else "COMPRAR"
            print(f"Accion: {action_str} {abs(contracts):.2f} contratos del {hedge.option_type.upper()} K=${hedge.strike:.0f}")
            print(f"   (Delta hedge: {hedge.delta:+.4f}, impacto esperado: {contracts * hedge.delta * self.MULTIPLIER:+.4f})")

        # 2. Calcular impacto en griegas
        hedge.delta_impact = contracts * hedge.delta * self.MULTIPLIER
        hedge.gamma_impact = contracts * hedge.gamma * self.MULTIPLIER
        hedge.vega_impact = contracts * hedge.vega * self.MULTIPLIER
        hedge.theta_impact = contracts * hedge.theta * self.MULTIPLIER
        hedge.rho_impact = contracts * hedge.rho * self.MULTIPLIER

        # 3. Griegas totales (Straddle + Hedge)
        straddle_delta_total = straddle.delta * self.MULTIPLIER
        straddle_gamma_total = straddle.gamma * self.MULTIPLIER
        straddle_vega_total = straddle.vega * self.MULTIPLIER
        straddle_theta_total = straddle.theta * self.MULTIPLIER
        straddle_rho_total = straddle.rho * self.MULTIPLIER

        total_delta = straddle_delta_total + hedge.delta_impact
        total_gamma = straddle_gamma_total + hedge.gamma_impact
        total_vega = straddle_vega_total + hedge.vega_impact
        total_theta = straddle_theta_total + hedge.theta_impact
        total_rho = straddle_rho_total + hedge.rho_impact

        # 4. Métricas de calidad
        delta_neutrality = abs(total_delta)

        gamma_retention_pct = (total_gamma / straddle_gamma_total * 100) if straddle_gamma_total != 0 else 0
        vega_retention_pct = (total_vega / straddle_vega_total * 100) if straddle_vega_total != 0 else 0

        theta_change_pct = ((total_theta - straddle_theta_total) / abs(straddle_theta_total) * 100) if straddle_theta_total != 0 else 0

        # 5. Prima del hedge (negativo = cobramos, positivo = pagamos)
        hedge_premium = contracts * hedge.price * self.MULTIPLIER

        # 6. Crear resultado
        result = HedgeAnalysisResult(
            strategy_name=strategy_name,
            straddle=straddle,
            hedge=hedge,
            total_delta=total_delta,
            total_gamma=total_gamma,
            total_vega=total_vega,
            total_theta=total_theta,
            total_rho=total_rho,
            delta_neutrality=delta_neutrality,
            gamma_retention_pct=gamma_retention_pct,
            vega_retention_pct=vega_retention_pct,
            theta_change_pct=theta_change_pct,
            hedge_premium=hedge_premium
        )

        # 7. Imprimir resumen
        if verbose:
            print(f"\nGriegas Finales (Cartera Completa):")
            print(f"   Delta:            {total_delta:>9.4f}  (neutralidad: {delta_neutrality:.4f})")
            print(f"   Gamma:            {total_gamma:>9.4f}  (retencion: {gamma_retention_pct:.1f}%)")
            print(f"   Vega:             {total_vega:>9.4f}  (retencion: {vega_retention_pct:.1f}%)")
            print(f"   Theta:            {total_theta:>9.4f}  (cambio: {theta_change_pct:+.1f}%)")
            print(f"   Rho:              {total_rho:>9.4f}")

            premium_str = "COBRADA" if hedge_premium < 0 else "PAGADA"
            print(f"\nPrima del Hedge: ${abs(hedge_premium):,.2f} ({premium_str})")

        return result

    def run_full_analysis(
        self,
        straddle: StraddleForHedge,
        verbose: bool = True
    ) -> List[HedgeAnalysisResult]:
        """
        Ejecuta análisis de las 4 estrategias de hedge apropiadas según la delta del straddle.

        Si delta > 0: Analiza ventas de Calls y compras de Puts (delta negativa)
        Si delta < 0: Analiza compras de Calls y ventas de Puts (delta positiva)

        Args:
            straddle: El straddle a cubrir
            verbose: Si True, imprime progreso y resultados

        Returns:
            Lista de HedgeAnalysisResult para cada estrategia (4 estrategias)
        """
        if verbose:
            print("=" * 70)
            print("ANALISIS DE ESTRATEGIAS DE COBERTURA")
            print("=" * 70)

            # Determinar dirección de la delta
            delta_direction = "POSITIVA" if straddle.delta > 0 else "NEGATIVA"

            print(f"\nStraddle a cubrir:")
            print(f"   Spot: ${straddle.spot:.2f}")
            print(f"   Strike: ${straddle.strike:.0f}")
            print(f"   Expiry: {straddle.expiry}")
            print(f"   Delta: {straddle.delta:+.4f} ({delta_direction})")
            print(f"   Gamma: {straddle.gamma:.4f}")
            print(f"   Vega: {straddle.vega:.4f}")
            print(f"   Theta: {straddle.theta:.4f}")
            print(f"\nBuscando opciones de hedge...")

        # 1. Buscar las 4 opciones de hedge
        options = {}

        option_types: List[Literal['call', 'put']] = ['call', 'put']
        moneyness_types: List[Literal['atm', 'otm']] = ['atm', 'otm']

        for opt_type in option_types:
            for moneyness in moneyness_types:
                key = f"{opt_type}_{moneyness}"
                options[key] = self.find_hedge_option(straddle, opt_type, moneyness, verbose)

        # 2. Determinar estrategias apropiadas según delta del straddle
        if straddle.delta > 0:
            # Delta positiva → necesitamos delta negativa para neutralizar
            # Venta de Calls (delta positiva → venta = negativa)
            # Compra de Puts (delta negativa → compra = más negativa)
            if verbose:
                print(f"\nDelta POSITIVA detectada → Estrategias: Venta Calls + Compra Puts")
                print(f"Analizando 4 estrategias de hedge apropiadas...")

            strategies: List[tuple] = [
                ("1. Venta Call ATM", 'call', 'atm'),
                ("2. Venta Call OTM", 'call', 'otm'),
                ("3. Compra Put ATM", 'put', 'atm'),
                ("4. Compra Put OTM", 'put', 'otm'),
            ]
        else:
            # Delta negativa → necesitamos delta positiva para neutralizar
            # Compra de Calls (delta positiva → compra = positiva)
            # Venta de Puts (delta negativa → venta = positiva)
            if verbose:
                print(f"\nDelta NEGATIVA detectada → Estrategias: Compra Calls + Venta Puts")
                print(f"Analizando 4 estrategias de hedge apropiadas...")

            strategies: List[tuple] = [
                ("1. Compra Call ATM", 'call', 'atm'),
                ("2. Compra Call OTM", 'call', 'otm'),
                ("3. Venta Put ATM", 'put', 'atm'),
                ("4. Venta Put OTM", 'put', 'otm'),
            ]

        # 3. Ejecutar análisis de cada estrategia
        results: List[HedgeAnalysisResult] = []
        for name, opt_type, moneyness in strategies:
            key = f"{opt_type}_{moneyness}"
            # Crear copia del hedge para no modificar el original
            hedge_copy = HedgeOption(
                option_type=options[key].option_type,
                strike=options[key].strike,
                expiry=options[key].expiry,
                T=options[key].T,
                price=options[key].price,
                delta=options[key].delta,
                gamma=options[key].gamma,
                vega=options[key].vega,
                theta=options[key].theta,
                rho=options[key].rho
            )
            result = self.analyze_hedge_strategy(name, straddle, hedge_copy, verbose)
            results.append(result)

        return results


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE VOLATILIDAD IMPLÍCITA (existentes)
# ═══════════════════════════════════════════════════════════════════════════════

def implied_vol_bisect(price_mkt: float, S: float, K: float, T: float, r: float, q: float, right: str,
                       lo: float = 1e-6, hi: float = 5.0, iters: int = 100) -> float:
    if not (math.isfinite(price_mkt) and price_mkt > 0):
        return float("nan")

    f_lo = black_scholes_merton(S, K, T, r, q, lo, right) - price_mkt
    f_hi = black_scholes_merton(S, K, T, r, q, hi, right) - price_mkt

    if not (math.isfinite(f_lo) and math.isfinite(f_hi)):
        return float("nan")

    if f_lo * f_hi > 0:
        return float("nan")

    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        f_mid = black_scholes_merton(S, K, T, r, q, mid, right) - price_mkt

        if not math.isfinite(f_mid):
            return float("nan")

        if abs(f_mid) < 1e-8:
            return mid

        if f_lo * f_mid <= 0:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid

    return 0.5 * (lo + hi)

def calculate_implied_q(S: float, K: float, T: float, r: float, priceC: float, priceP: float) -> float:
    """Calcula Dividend Yield (q) implícito por Paridad Put-Call."""
    if S <= 0 or T <= 0: return 0.0
    rhs = priceC - priceP + K * math.exp(-r * T)
    if rhs <= 0: return 0.0
    return -(1.0 / T) * math.log(rhs / S)