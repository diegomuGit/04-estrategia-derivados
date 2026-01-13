# 04-estrategia-derivados

Repositorio de estrategias con derivados financieros - MIAX Master

## Descripción

Este proyecto implementa un sistema completo de backtesting y análisis para estrategias de opciones sobre SPY, con énfasis en long straddles periódicos con delta hedging. Incluye:

- Implementación del modelo Black-Scholes-Merton con dividendos continuos
- Soporte para pricing de opciones americanas usando QuantLib
- Motor de backtesting con gestión de posiciones y P&L
- Sistema de señales basado en volatilidad implícita (VIX) vs volatilidad realizada
- Delta hedging a nivel de cartera con múltiples frecuencias de rebalanceo
- Análisis de cobertura con opciones (8 estrategias diferentes)
- Forecasting de volatilidad con modelos GARCH
- Integración con Interactive Brokers API para datos en tiempo real

## Estructura del Proyecto

```
04-estrategia-derivados/
├── src/
│   ├── notebooks/           # Jupyter notebooks de desarrollo y análisis
│   └── scripts/             # Módulos Python del sistema
│       ├── black_scholes.py           # Pricing BSM y griegas (europeas y americanas)
│       ├── straddle.py                # Pricing y griegas de straddles
│       ├── strategy.py                # Estructura de posiciones de straddle
│       ├── backtest.py                # Motor principal de backtesting
│       ├── delta_hedge.py             # Lógica de delta hedging con acciones
│       ├── options_hedge.py           # Análisis de hedge con opciones
│       ├── signals.py                 # Señales de entrada/salida basadas en vol
│       ├── volatility_forecast.py     # Modelos GARCH para forecast de RV
│       ├── data_loader.py             # Carga de datos de mercado (yfinance, FRED)
│       ├── rates.py                   # Interpolación de curva de tasas
│       ├── dividends.py               # Cálculo de dividend yield implícito
│       ├── test_hedge_logic.py        # Tests de lógica de hedge
│       └── test_volatility_forecast.py # Tests de modelos GARCH
└── CAMBIOS_HEDGE.md         # Documentación de cambios en sistema de hedge
```

## Componentes Principales

### 1. Pricing de Opciones ([black_scholes.py](src/scripts/black_scholes.py))

Implementación del modelo Black-Scholes-Merton con soporte para:
- Opciones europeas (Call y Put) con dividendos continuos
- Cálculo de todas las griegas: Delta, Gamma, Vega, Theta, Rho
- Integración con QuantLib para opciones americanas
- Validación con error estimado < 2% vs precios de mercado para SPY

**Fórmulas BSM con dividendos:**
```
Call: C = S·e^(-q·T)·N(d₁) - K·e^(-r·T)·N(d₂)
Put:  P = K·e^(-r·T)·N(-d₂) - S·e^(-q·T)·N(-d₁)

donde:
d₁ = [ln(S/K) + (r - q + σ²/2)·T] / (σ·√T)
d₂ = d₁ - σ·√T
```

### 2. Estrategia de Straddle ([straddle.py](src/scripts/straddle.py), [strategy.py](src/scripts/strategy.py))

Implementación de long straddles ATM con:
- Pricing combinado de call + put
- Cálculo de griegas del straddle completo
- Gestión de posiciones individuales con tracking de P&L
- Valor intrínseco al vencimiento: |S - K|

### 3. Motor de Backtesting ([backtest.py](src/scripts/backtest.py))

Sistema robusto que simula día a día:
- Apertura de straddles en fechas programadas (monthly/weekly/biweekly)
- Valoración mark-to-market usando BSM
- Cierre al vencimiento o anticipado según señales
- Gestión de múltiples posiciones simultáneas
- Delta hedging opcional a nivel de cartera
- Tracking completo de P&L (straddle + hedge - costes)

### 4. Delta Hedging ([delta_hedge.py](src/scripts/delta_hedge.py))

Sistema de cobertura con acciones del subyacente:
- Rebalanceo configurable: diario, semanal, o por umbral de delta
- Cálculo automático de acciones objetivo para neutralizar delta
- Tracking de costes de transacción (comisiones + slippage)
- Gestión de P&L del hedge separado del straddle

### 5. Señales de Entrada/Salida ([signals.py](src/scripts/signals.py))

Sistema de filtros basado en análisis de volatilidad:

**Entrada:**
- IV Percentile bajo (IV "barata" en su historia)
- Spread IV² - RV² en percentiles bajos
- Señal de expansión: RV corto plazo > RV largo plazo

**Salida anticipada:**
- Take profit: Return >= umbral (ej: +50%)
- Stop loss: Return <= -umbral (ej: -50%)
- Time stop: % del tenor transcurrido sin ganancias
- Vol exit: IVP alto + posición en verde (capturar re-pricing)

### 6. Forecast de Volatilidad ([volatility_forecast.py](src/scripts/volatility_forecast.py))

Modelos GARCH para mejorar el spread IV-RV:
- Estimación GARCH(1,1) con librería `arch`
- Forecast de volatilidad realizada a N días
- Re-estimación periódica del modelo
- Comparación RV histórica vs RV forecasted

### 7. Hedge con Opciones ([options_hedge.py](src/scripts/options_hedge.py))

Análisis de 8 estrategias de cobertura usando opciones:
- 4 estrategias para delta positiva (Venta Calls + Compra Puts)
- 4 estrategias para delta negativa (Compra Calls + Venta Puts)
- Cálculo automático de contratos para neutralizar delta
- Análisis comparativo de retención de Gamma/Vega y cambio en Theta
- Integración con Interactive Brokers para precios en tiempo real

### 8. Datos de Mercado ([data_loader.py](src/scripts/data_loader.py), [rates.py](src/scripts/rates.py))

Carga y gestión de datos:
- Histórico de SPY con dividend yield dinámico (yfinance)
- VIX como proxy de volatilidad implícita
- Curva de tasas Treasury desde FRED (1M, 3M, 6M, 1Y)
- Interpolación lineal de tasas según tenor

## Requisitos

### Python
- Python 3.8+

### Librerías principales
- pandas, numpy, scipy
- matplotlib
- yfinance, fredapi
- ib_insync (para conexión con Interactive Brokers)
- QuantLib (opcional, para opciones americanas)
- arch (para modelos GARCH)
- pytest (para tests)

### Configuración
1. Crear archivo `.env` con:
   ```
   FRED_API_KEY=tu_api_key_de_fred
   ```
2. Para usar Interactive Brokers, tener TWS o IB Gateway ejecutándose

## Uso Básico

### Backtest simple de long straddle
```python
from backtest import run_backtest
from data_loader import get_spy_history, get_vix_history, load_treasury_curve
from strategy import generate_entry_dates

# Cargar datos
spy_data = get_spy_history('2020-01-01', '2023-12-31')
vix_data = get_vix_history('2020-01-01', '2023-12-31')
treasury = load_treasury_curve('2020-01-01', '2023-12-31')

# Consolidar
market_data = spy_data.copy()
market_data['close_vix'] = vix_data
for col in treasury.columns:
    market_data[col] = treasury[col]

# Generar fechas de entrada mensuales
entry_dates = generate_entry_dates('2020-01-01', '2023-12-31',
                                   market_data.index, frequency='monthly')

# Ejecutar backtest
result = run_backtest(market_data, entry_dates, tenor_days=30)

# Ver resultados
print(result.summary)
```

### Backtest con delta hedge
```python
from delta_hedge import HedgeConfig

hedge_config = HedgeConfig(
    rebalance_freq='daily',
    include_costs=True,
    cost_per_share=0.01
)

result = run_backtest(market_data, entry_dates, tenor_days=30,
                     hedge_config=hedge_config)
```

### Backtest con señales de entrada
```python
from signals import EntryConfig, ExitConfig

entry_config = EntryConfig(
    use_filters=True,
    ivp_threshold=30.0,
    spread_pctl_threshold=30.0,
    use_expansion_filter=True
)

exit_config = ExitConfig(
    use_exits=True,
    take_profit_pct=0.50,
    stop_loss_pct=0.50
)

result = run_backtest(market_data, entry_dates, tenor_days=30,
                     entry_config=entry_config, exit_config=exit_config)
```

## Fundamento Teórico

### 1. Long Straddle: Mecánica y Perfil de Riesgo

Un **long straddle** consiste en la compra simultánea de una opción call y una opción put con el mismo strike (típicamente ATM) y vencimiento.

**Payoff al vencimiento:**
```
Profit = |S_T - K| - Prima_Pagada
```

**Características clave:**
- **Delta ≈ 0**: Neutralidad direccional inicial (Delta_call + Delta_put ≈ 0 cuando ATM)
- **Gamma > 0**: Beneficia de movimientos grandes en cualquier dirección
- **Vega > 0**: Beneficia de aumentos en volatilidad implícita
- **Theta < 0**: Sufre time decay (valor temporal se erosiona con el paso del tiempo)

**Break-even points:**
```
S_lower = K - Prima_Pagada
S_upper = K + Prima_Pagada
```

La estrategia es rentable cuando el movimiento realizado del subyacente supera la prima pagada (ajustada por el costo del capital).

### 2. Volatilidad: Implícita vs Realizada

#### Volatilidad Realizada (RV)
Mide la volatilidad histórica observada del precio del activo:

```
RV_N = std(log(S_t/S_{t-1}), N días) × √252
```

Para un straddle de N días, la RV relevante es la que se materializará durante la vida del trade.

#### Volatilidad Implícita (IV)
Es la volatilidad que iguala el precio de mercado de la opción con el precio teórico del modelo BSM. Representa la expectativa del mercado sobre la volatilidad futura.

En este proyecto usamos **VIX como proxy de IV** para straddles ATM de ~30 días sobre SPY.

#### Variance Risk Premium (VRP)

Empíricamente, se observa que:
```
IV > RV  (en promedio)
```

Esto significa que **los compradores de opciones pagan una prima por el riesgo de volatilidad**. El VRP se define como:

```
VRP = IV² - E[RV²]
```

**Implicación para straddles:**
- Si IV² >> E[RV²] → Prima cara → Esperar return negativo
- Si IV² ≈ E[RV²] o IV² < E[RV²] → Prima justa/barata → Potencial de ganancia

### 3. Sistema de Señales: IV Percentile y Spread

#### IV Percentile (IVP)
Mide si la IV actual está alta o baja respecto a su propia historia:

```
IVP_t = % de valores en [t-252, t] donde IV_i <= IV_t
```

- IVP < 30: IV "barata" en términos históricos
- IVP > 70: IV "cara" en términos históricos

#### Spread en Varianza
El spread captura si estamos pagando "de más" por volatilidad:

```
Spread_t = IV_t² - RV_t²
```

donde RV puede ser:
1. **Histórica**: std(returns, 20 días) × √252
2. **Forecasted**: GARCH forecast a N días

**Lógica de entrada:**
- Entrar cuando IVP < 30 AND Spread_Percentile < 30
- Esto identifica momentos donde IV está barata tanto en términos absolutos como relativos a RV

#### Filtro de Expansión
Complementariamente, se puede requerir que:
```
RV_short (5d) > RV_long (20d)
```

Esto señala que la volatilidad está "despertando", lo cual aumenta la probabilidad de que el movimiento realizado supere la prima pagada.

### 4. Delta Hedging: Teoría y Práctica

#### Objetivo del Delta Hedging
Eliminar (o reducir) la exposición direccional del straddle, dejando solo exposición a gamma y vega.

**Delta de un straddle ATM:**
```
Δ_straddle = Δ_call + Δ_put ≈ 0  (inicialmente)
```

Sin embargo, cuando el spot se mueve:
- Si S > K: Δ_straddle > 0 (largo el subyacente)
- Si S < K: Δ_straddle < 0 (corto el subyacente)

#### Mecánica del Hedge
Para neutralizar delta:
```
Acciones_objetivo = -Δ_portfolio × Multiplicador
```

- Si Δ_portfolio > 0 → Vender acciones (short hedge)
- Si Δ_portfolio < 0 → Comprar acciones (long hedge)

#### Frecuencias de Rebalanceo

**Daily:**
- Mantiene delta cerca de 0 en todo momento
- Maximiza costes de transacción
- Mejor cuando volatilidad es alta (más gamma)

**Weekly:**
- Balance entre control de riesgo y costes
- Apropiado para straddles de 30+ días

**Threshold:**
- Rebalancea solo cuando |Δ| > umbral (ej: 0.10)
- Minimiza costes pero permite desviación de delta-neutral

#### Trade-off: Gamma vs Costes

El P&L de un straddle delta-hedged se aproxima por:

```
dP ≈ ½ Γ (dS)² - Θ dt - Costes_rebalanceo
```

- **Gamma profit**: Beneficio de los movimientos del subyacente (convexidad)
- **Theta decay**: Pérdida por paso del tiempo
- **Costes**: Proporcionales a frecuencia × spread bid-ask × slippage

**Resultado esperado:**
- Si Gamma profit > Theta + Costes → Ganancia
- Esto ocurre cuando RV realizada >> IV pagada

### 5. GARCH Forecasting: Mejorando el Spread

#### Limitación de RV Histórica
La volatilidad realizada histórica asume que la volatilidad futura será similar al pasado reciente. Sin embargo, la volatilidad exhibe:
- **Clustering**: Períodos de alta vol tienden a persistir
- **Mean-reversion**: Vol extrema tiende a volver a la media

#### Modelo GARCH(1,1)
Captura la dinámica de la varianza condicional:

```
σ²_t = ω + α ε²_{t-1} + β σ²_{t-1}
```

donde:
- ω: Varianza de largo plazo
- α: Impacto de shocks recientes
- β: Persistencia de la volatilidad

**Forecast a h-steps:**
```
σ²_{t+h} = E[σ²_{t+h} | I_t]
```

#### Ventaja para Señales de Entrada
Usar RV_forecast en lugar de RV_histórica mejora la estimación del spread:

```
Spread_mejorado = IV² - RV_forecast²
```

Esto permite identificar mejor cuándo IV está verdaderamente "barata" vs lo que el mercado realizará en el futuro.

### 6. Hedge con Opciones: Alternativa al Delta Hedge con Acciones

Además de usar acciones, se puede neutralizar delta usando otras opciones. Esto permite mantener exposición a gamma y vega mientras se controla la dirección.

**Estrategias según delta del straddle:**

Si **Δ_straddle > 0** (largo direccional):
1. Vender Call ATM/OTM (delta positiva → venta = negativa)
2. Comprar Put ATM/OTM (delta negativa → compra = más negativa)

Si **Δ_straddle < 0** (corto direccional):
1. Comprar Call ATM/OTM (delta positiva)
2. Vender Put ATM/OTM (delta negativa → venta = positiva)

**Número de contratos:**
```
N_contratos = -Δ_straddle / Δ_hedge
```

**Ventajas vs hedge con acciones:**
- Mantiene exposición a gamma (acciones tienen Γ = 0)
- Puede reducir theta (vendiendo opciones se cobra prima)
- Menos transacciones (opciones se mueven menos que acciones)

**Desventajas:**
- Añade complejidad (gestionar múltiples griegas)
- Menos liquidez que el subyacente
- Requiere gestión del vencimiento de las opciones de hedge

### 7. Métricas de Performance

El sistema calcula métricas estándar para evaluar la estrategia:

**Métricas de trades:**
- Win rate: % de trades ganadores
- Avg win / Avg loss: Relación beneficio/pérdida promedio
- Profit factor: Gross profit / Gross loss
- Best/Worst trade: Mejor y peor resultado

**Métricas de riesgo:**
- Max Drawdown: Máxima caída desde peak
- Avg holding period: Duración promedio de los trades

**Métricas de señales (si aplica):**
- Entry rate: % de entradas programadas ejecutadas
- Exit reasons: Distribución de motivos de cierre

**Métricas de hedge (si aplica):**
- Total hedge P&L: Ganancia/pérdida del hedge
- Hedge costs: Costes totales de rebalanceo
- Num rebalances: Número de transacciones

## Referencias Académicas

1. **Black, F. & Scholes, M. (1973)**. "The Pricing of Options and Corporate Liabilities". *Journal of Political Economy*.
   - Fundamento del modelo BSM usado para pricing

2. **Merton, R. (1973)**. "Theory of Rational Option Pricing". *Bell Journal of Economics and Management Science*.
   - Extensión con dividendos continuos

3. **Bollerslev, T. (1986)**. "Generalized Autoregressive Conditional Heteroskedasticity". *Journal of Econometrics*.
   - Modelo GARCH para forecasting de volatilidad

4. **Carr, P. & Wu, L. (2009)**. "Variance Risk Premiums". *Review of Financial Studies*.
   - Análisis del VRP y su relación con estrategias de volatilidad

5. **Schwab Options Trading Guide**. Concepto de IV Percentile y su uso en señales de entrada.

## Autor

Diego - MIAX Master
