# 04-estrategia-derivados

Repositorio de estrategias con derivados - MIAX

## Descripción

Este proyecto contiene herramientas y análisis para estrategias de trading con derivados financieros, incluyendo:

- Implementación del modelo Black-Scholes para valoración de opciones
- Sistema de backtesting para estrategias de opciones
- Análisis de griegas (Delta, Gamma, Theta, Vega, Rho)
- Estrategias de opciones (Straddle, Delta Hedge)
- Integración con Interactive Brokers API

## Estructura del Proyecto

```
04-estrategia-derivados/
├── src/
│   ├── notebooks/       # Jupyter notebooks de desarrollo y análisis
│   └── scripts/         # Scripts Python para estrategias y cálculos
├── otros/              # Archivos de prueba y ejercicios
└── salidas/            # Visualizaciones HTML generadas
```

## Componentes Principales

### Scripts

- `black_scholes.py` - Modelo de valoración de opciones
- `backtest.py` - Sistema de backtesting
- `strategy.py` - Implementación de estrategias
- `straddle.py` - Estrategia straddle
- `delta_hedge.py` - Cobertura delta
- `data_loader.py` - Carga de datos de mercado
- `rates.py` - Tasas de interés
- `dividends.py` - Gestión de dividendos

### Notebooks

- `notebook_desarrrollo_v1.ipynb` - Desarrollo principal
- `prueba_ibrk_api.ipynb` - Pruebas con Interactive Brokers API
- `test_backtest.ipynb` - Testing del sistema de backtesting

## Requisitos

- Python 3.x
- Jupyter Notebook
- Librerías necesarias (ver requirements.txt)

## Uso

1. Configurar las variables de entorno en `.env`
2. Ejecutar los notebooks en `src/notebooks/`
3. Los resultados se guardarán en la carpeta `salidas/`

## Autor

Diego - MIAX Master
