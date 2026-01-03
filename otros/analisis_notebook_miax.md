# Análisis Exhaustivo: EJERCICIO_MIAX_2025.ipynb

## 1. Resumen de Alto Nivel

### Propósito Principal
Este notebook es un **ejercicio práctico de Máster** diseñado para enseñar el **ciclo completo de trading algorítmico de opciones** sobre el ETF SPY utilizando la API de Interactive Brokers (IBKR). El objetivo pedagógico es que el estudiante comprenda desde la conexión con el broker hasta la ejecución de estrategias de cobertura delta-neutral, pasando por el cálculo de griegas y superficies de volatilidad.

### Contexto Académico
- **Programa**: Máster en Inteligencia Artificial aplicada a los Mercados Financieros (MIAX)
- **Autor del código**: jrg (José Ramón González, presumiblemente)
- **Fecha de creación**: Diciembre 2025
- **Subyacente de trabajo**: SPY (SPDR S&P 500 ETF Trust)

### Alcance Funcional
El notebook abarca **8 ejercicios principales** que cubren:
1. Conexión a broker (IBKR Paper Trading)
2. Obtención de cadenas de opciones (Option Chains)
3. Estimación de volatilidad implícita (IV)
4. Cálculo de griegas (Δ, Γ, Θ, Vega, Rho)
5. Visualización de smiles y superficies de volatilidad
6. Evolución temporal histórica de opciones
7. Diseño de funciones de cobertura (Delta-Hedging)
8. Simulación de envío de órdenes y cobertura algorítmica

---

## 2. Flujo de Trabajo (Workflow)

### 2.1 FASE 1: Infraestructura y Conectividad (Celdas 1-4)
**Objetivo**: Establecer conexión con la pasarela de IBKR

| Componente | Descripción |
|------------|-------------|
| Arquitectura | Python → Socket TCP/IP → TWS/IB Gateway → Servidores IBKR |
| Protocolo | Conexión local (127.0.0.1) al puerto 7497 (Paper) o 7496 (Live) |
| Autenticación | ClientID único por sesión |

**Código clave**:
```python
from ib_insync import IB, util
ib = IB()
ib.connect("127.0.0.1", 7497, clientId=28)
```

---

### 2.2 FASE 2: Definición de Contratos y Option Chains (Celdas 5-9)
**Objetivo**: Obtener la estructura completa de opciones disponibles sobre SPY

**Proceso**:
1. Calificar el contrato subyacente (SPY como Stock)
2. Solicitar parámetros de cadena (`reqSecDefOptParams`)
3. Filtrar cadena estándar (tradingClass=SPY, no FLEX)
4. Obtener vencimientos y strikes disponibles

**Consideraciones técnicas**:
- Distinción entre opciones estándar (SPY) y FLEX (2SPY)
- Identificación de vencimientos 0DTE vs. mensuales
- Selección de vencimiento estrictamente > fecha actual

---

### 2.3 FASE 3: Estimación de Volatilidad Implícita (Celdas 10-16)
**Objetivo**: Calcular IV ATM usando múltiples metodologías

**Métodos implementados**:

| Método | Descripción | Precisión |
|--------|-------------|-----------|
| **BS Manual + Bisección** | Implementación propia del modelo Black-Scholes con búsqueda binaria | Base |
| **QuantLib** | Motor profesional con soporte para opciones americanas | Alta |
| **IBKR Model** | IV calculada por el broker (ModelGreeks) | Referencia |

**Fórmulas fundamentales**:
```
d₁ = [ln(S/K) + (r - q + σ²/2)T] / (σ√T)
d₂ = d₁ - σ√T
```

**Calibración dinámica**: El script calcula el dividend yield (q) implícito usando paridad Put-Call.

---

### 2.4 FASE 4: Cálculo de Griegas (Celdas 17-22)
**Objetivo**: Computar sensibilidades de primer y segundo orden

**Matriz de Griegas calculadas**:

| Griega | Fórmula | Interpretación |
|--------|---------|----------------|
| **Delta (Δ)** | ∂V/∂S | Sensibilidad al precio |
| **Gamma (Γ)** | ∂²V/∂S² | Convexidad |
| **Vega (ν)** | ∂V/∂σ | Sensibilidad a volatilidad |
| **Theta (Θ)** | ∂V/∂t | Time decay (por día) |
| **Rho (ρ)** | ∂V/∂r | Sensibilidad a tasas |

**Nota técnica importante**: La API de IBKR **no envía Rho** en `OptionComputation`. El código implementa fallback manual.

---

### 2.5 FASE 5: Visualización de Superficies de Volatilidad (Celdas 23-24)
**Objetivo**: Representar gráficamente la estructura term structure de IV

**Dimensiones de la superficie**:
- **Eje X**: Strike (Moneyness)
- **Eje Y**: Tiempo a vencimiento
- **Eje Z**: Volatilidad Implícita (%)

**Características de implementación**:
- Detección de strikes reales usando `reqContractDetails`
- Priorización de IV oficial de IBKR
- Fallback a cálculo manual si IBKR no provee datos
- Visualización 3D interactiva con Plotly

---

### 2.6 FASE 6: Evolución Temporal Histórica (Celdas 25-26)
**Objetivo**: Analizar series temporales de precio, griegas y payoff

**Componentes de visualización**:
1. **Subplot 1**: Precio del subyacente vs. tiempo
2. **Subplot 2**: Evolución de Delta
3. **Subplot 3**: Evolución de Gamma
4. **Subplot 4**: Theta decay

**Técnicas de reconstrucción de datos**: El código reconstruye históricos a partir de datos disponibles cuando la API no provee series completas.

---

### 2.7 FASE 7: Motor de Cobertura Delta-Hedging (Celdas 27-33)
**Objetivo**: Simular estrategias de cobertura dinámica

**Estrategias soportadas**:
- Long Call + Delta Hedge
- Long Put + Delta Hedge  
- Short Call + Delta Hedge
- Short Put + Delta Hedge

**Ecuación de PnL para cartera Delta-Hedged**:
```
dΠ ≈ 0 (Delta Neutral) + (∂V/∂σ)dσ (Vega) + ½(∂²V/∂S²)(dS)² (Gamma) + (∂V/∂t)dt (Theta)
```

**Motor de simulación**:
- Tracking de posición en acciones (shares_held)
- Cash accounting para rebalanceos
- Comparación PnL cubierto vs. descubierto

---

### 2.8 FASE 8: Sistema Algorítmico de Ejecución (Celdas 34-37)
**Objetivo**: Implementar algoritmo de ejecución + cobertura automática

**Modos de operación**:
| Modo | Descripción | Uso |
|------|-------------|-----|
| `MODO_SIMULACION = True` | Ejecución virtual | Backtest/Forward Test |
| `MODO_SIMULACION = False` | Órdenes reales a TWS | **¡CUIDADO: Opera con capital real!** |

**Algoritmo "Limit Chase"**:
1. Envío de orden límite
2. Monitorización de fill
3. Ajuste de precio si no hay ejecución
4. Cobertura delta inmediata post-fill

**Taxonomía de riesgos documentada**:
- Riesgos de ejecución (Legging Risk, Latency, Slippage)
- Riesgos de modelo (Discrete Hedging, Dividend, Vol Surface)
- Riesgos financieros (Margin, Assignment, PDT Rule)
- Riesgos de mercado (Gap, Vega Crush, Explosive Gamma)

---

## 3. Identificación de Variables Clave

### 3.1 Parámetros de Conexión
```python
HOST = "127.0.0.1"
PORT = 7497          # Paper Trading
CLIENT_ID = 28       # Único por sesión
```

### 3.2 Funciones Matemáticas Críticas

| Función | Propósito |
|---------|-----------|
| `norm_cdf(x)` | Distribución normal acumulada |
| `norm_pdf(x)` | Densidad de probabilidad normal |
| `bs_price(S, K, T, r, q, sigma, right)` | Precio Black-Scholes europeo |
| `implied_vol_bisect(...)` | IV por búsqueda binaria |
| `bs_greeks_manual(...)` | Cálculo de todas las griegas |
| `calculate_delta(...)` | Delta para cobertura |
| `calculate_implied_q(...)` | Dividend yield implícito |

### 3.3 Variables de Mercado

| Variable | Descripción | Fuente |
|----------|-------------|--------|
| `S` | Precio spot del subyacente | IBKR API |
| `K` | Strike de la opción | Cadena de opciones |
| `T` | Tiempo a vencimiento (años) | Calculado |
| `r` | Tasa libre de riesgo | Yahoo Finance (^IRX) |
| `q` | Dividend yield | Paridad Put-Call |
| `sigma` | Volatilidad implícita | Calculada/IBKR |

### 3.4 Objetos de Contrato IBKR

```python
spy = Stock("SPY", "SMART", "USD")           # Subyacente
opt = Option("SPY", expiry, strike, "C", "SMART")  # Opción
```

---

## 4. Dependencias

### 4.1 Librerías Críticas

| Librería | Versión | Propósito | Criticidad |
|----------|---------|-----------|------------|
| `ib_insync` | - | API asíncrona para IBKR | **ESENCIAL** |
| `pandas` | - | Manipulación de datos | **ESENCIAL** |
| `plotly` | - | Visualización interactiva 3D | **ESENCIAL** |
| `math` | stdlib | Funciones matemáticas | **ESENCIAL** |
| `datetime` | stdlib | Manejo de fechas | **ESENCIAL** |

### 4.2 Librerías Opcionales

| Librería | Propósito | Fallback |
|----------|-----------|----------|
| `QuantLib` | Pricing profesional de opciones | BS manual |
| `yfinance` | Obtención de tasa libre de riesgo | Default: 4.5% |
| `nest_asyncio` | Fix para event loops en notebooks | `util.startLoop()` |

### 4.3 Requisitos de Infraestructura

| Componente | Requisito |
|------------|-----------|
| **TWS o IB Gateway** | Debe estar ejecutándose localmente |
| **Cuenta IBKR** | Paper o Live (Paper recomendado para pruebas) |
| **Suscripción de datos** | Opcional (sin suscripción = datos retrasados 15-20 min) |
| **Configuración API** | Enable ActiveX and Socket Clients ✅ |

### 4.4 Datos Externos

| Fuente | Datos | Uso |
|--------|-------|-----|
| IBKR API | Precios spot, cadenas de opciones, griegas del broker | Principal |
| Yahoo Finance | Tasa T-Bill 13 semanas (^IRX) | Tasa libre de riesgo |

---

## 5. Observaciones Técnicas Adicionales

### 5.1 Patrones de Código Recurrentes

**Fix para notebooks (event loop)**:
```python
def ensure_ipython_loop():
    try:
        from IPython import get_ipython
        ip = get_ipython()
        if ip and getattr(ip, "kernel", None):
            util.startLoop()
    except: pass
```

**Manejo de datos retrasados**:
```python
ib.reqMarketDataType(3)  # Acepta datos delayed
```

### 5.2 Limitaciones Documentadas

1. **Datos no sincronizados**: Spot y opciones pueden tener desfase temporal con datos delayed
2. **API de IBKR no envía Rho**: Requiere cálculo manual
3. **Premium americano negligible**: Para SPY, Black-Scholes funciona bien aunque las opciones son americanas
4. **Rate limiting**: `reqContractDetails` está sujeto a throttling

### 5.3 Advertencias de Seguridad

⚠️ **CRÍTICO**: La celda 36 contiene un flag `MODO_SIMULACION` que cuando está en `False` **envía órdenes reales** al mercado. Verificar siempre antes de ejecutar.

---

## 6. Mapa Visual del Notebook

```
┌─────────────────────────────────────────────────────────────────┐
│                    EJERCICIO MIAX 2025                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ 1. CONEXIÓN │───▶│ 2. OPTION   │───▶│ 3. CÁLCULO  │         │
│  │   BROKER    │    │   CHAINS    │    │     IV      │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                  │                  │                 │
│         ▼                  ▼                  ▼                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ 4. GRIEGAS  │───▶│ 5. SMILE &  │───▶│ 6. HISTÓRICO│         │
│  │  Δ Γ Θ ν ρ  │    │  SUPERFICIE │    │  TEMPORAL   │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                  │                  │                 │
│         └──────────────────┴──────────────────┘                 │
│                            │                                    │
│                            ▼                                    │
│         ┌─────────────────────────────────┐                    │
│         │      7. DELTA-HEDGING           │                    │
│         │   Simulación de Cobertura       │                    │
│         └─────────────────────────────────┘                    │
│                            │                                    │
│                            ▼                                    │
│         ┌─────────────────────────────────┐                    │
│         │   8. EJECUCIÓN ALGORÍTMICA      │                    │
│         │   + Taxonomía de Riesgos        │                    │
│         └─────────────────────────────────┘                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Conclusión

Este notebook representa un **material didáctico completo** para el aprendizaje de trading cuantitativo de opciones. Su fortaleza radica en:

1. **Progresión pedagógica**: Desde conceptos básicos hasta ejecución algorítmica
2. **Múltiples enfoques**: Comparación entre cálculos manuales, QuantLib e IBKR
3. **Código funcional**: Listo para ejecutar con cuenta Paper de IBKR
4. **Documentación de riesgos**: Taxonomía exhaustiva de riesgos operacionales

El notebook es especialmente relevante para tu trabajo actual con Interactive Brokers API y estrategias de delta-hedging sobre SPY.
