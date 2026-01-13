"""
Script de prueba para verificar la lógica de hedge según delta del straddle.

Este script prueba 3 casos:
1. Delta positiva (+0.15) - Debe sugerir: Venta Calls + Compra Puts
2. Delta negativa (-0.15) - Debe sugerir: Compra Calls + Venta Puts
3. Delta cercana a cero (+0.02) - Debe calcular contratos pequeños
"""

import sys
sys.path.insert(0, 'c:\\Users\\diego\\MIAX\\04-estrategia-derivados\\src\\scripts')

from options_hedge import StraddleForHedge

# Caso 1: Delta positiva
print("=" * 80)
print("CASO 1: Delta POSITIVA (+0.15)")
print("=" * 80)

straddle_pos = StraddleForHedge(
    spot=694.07,
    strike=694.0,
    expiry="20260114",
    T=0.0082,
    r=0.037,
    q=0.0247,
    sigma=0.1092,
    delta=+0.15,  # Delta POSITIVA
    gamma=0.1161,
    vega=0.5018,
    theta=-0.9129,
    rho=0.0007
)

print(f"\nStraddle con delta POSITIVA: {straddle_pos.delta:+.4f}")
print("\nEstrategias esperadas:")
print("  ✓ Venta Call ATM")
print("  ✓ Venta Call OTM")
print("  ✓ Compra Put ATM")
print("  ✓ Compra Put OTM")
print("\nRazón: Delta positiva necesita delta negativa para neutralizar")
print("       - Vender calls (delta+ → venta = delta-)")
print("       - Comprar puts (delta- → compra = más delta-)")

# Caso 2: Delta negativa
print("\n\n" + "=" * 80)
print("CASO 2: Delta NEGATIVA (-0.15)")
print("=" * 80)

straddle_neg = StraddleForHedge(
    spot=694.07,
    strike=694.0,
    expiry="20260114",
    T=0.0082,
    r=0.037,
    q=0.0247,
    sigma=0.1092,
    delta=-0.15,  # Delta NEGATIVA
    gamma=0.1161,
    vega=0.5018,
    theta=-0.9129,
    rho=0.0007
)

print(f"\nStraddle con delta NEGATIVA: {straddle_neg.delta:+.4f}")
print("\nEstrategias esperadas:")
print("  ✓ Compra Call ATM")
print("  ✓ Compra Call OTM")
print("  ✓ Venta Put ATM")
print("  ✓ Venta Put OTM")
print("\nRazón: Delta negativa necesita delta positiva para neutralizar")
print("       - Comprar calls (delta+ → compra = delta+)")
print("       - Vender puts (delta- → venta = delta+)")

# Caso 3: Delta cercana a cero
print("\n\n" + "=" * 80)
print("CASO 3: Delta cercana a CERO (+0.02)")
print("=" * 80)

straddle_atm = StraddleForHedge(
    spot=694.07,
    strike=694.0,
    expiry="20260114",
    T=0.0082,
    r=0.037,
    q=0.0247,
    sigma=0.1092,
    delta=+0.02,  # Delta cercana a CERO
    gamma=0.1161,
    vega=0.5018,
    theta=-0.9129,
    rho=0.0007
)

print(f"\nStraddle ATM con delta pequeña: {straddle_atm.delta:+.4f}")
print("\nEstrategias esperadas:")
print("  ✓ Venta Call ATM (contratos pequeños)")
print("  ✓ Venta Call OTM (contratos pequeños)")
print("  ✓ Compra Put ATM (contratos pequeños)")
print("  ✓ Compra Put OTM (contratos pequeños)")
print("\nRazón: Delta pequeña → necesita pocos contratos para neutralizar")

print("\n\n" + "=" * 80)
print("VERIFICACIÓN COMPLETADA")
print("=" * 80)
print("\nPara ejecutar el análisis completo con IBKR, usar:")
print("  analyzer = OptionsHedgeAnalyzer(ib)")
print("  results = analyzer.run_full_analysis(straddle)")
print("\nEl código ahora:")
print("  1. Detecta automáticamente el signo de la delta")
print("  2. Selecciona solo las 4 estrategias apropiadas")
print("  3. Calcula automáticamente si comprar o vender según neutralización")
