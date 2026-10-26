"""
main.py
Orquestador Principal del Sistema de Réplica de Trades del Congreso.
Ejecuta el flujo completo:
1. Ingesta de datos (Capitol Trades en tiempo real)
2. Filtro de Calidad (Lag <= 30d, Monto >= $15k, Compras directas)
3. Scoring del Político (Comités, Historial, Convicción, Lag)
4. Dimensionamiento de Posición (Riesgo máx 1%, Stop ATR 2.5x-3.0x, Cap 15%)
5. Ejecución (Simulación o Alpaca Paper Trading con órdenes Bracket)
"""

from datetime import datetime
from data_collector import DataCollector
from filtro_calidad import FiltroCalidad
from scoring_politico import ScoringPolitico
from position_sizer import PositionSizer
from alpaca_executor import AlpacaExecutor
from config import Config

def run_pipeline(max_pages: int = 15):
    print("=" * 75)
    print("  SISTEMA DE RÉPLICA DE TRADES DEL CONGRESO - PIPELINE COMPLETO")
    print(f"  Fecha de ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 75)

    # 1. Ingesta de Datos en Vivo
    collector = DataCollector()
    raw_trades = collector.fetch_all_recent_trades(max_pages=max_pages)
    if not raw_trades:
        print("[ERROR] No se pudieron descargar trades del Congreso. Finalizando.")
        return

    # 2. Inicializar Módulos de Decisión
    filtro = FiltroCalidad()
    scorer = ScoringPolitico()
    executor = AlpacaExecutor()
    equity = executor.get_portfolio_equity()
    sizer = PositionSizer(portfolio_equity=equity)

    print(f"\n[INFO] Capital del Portafolio: ${equity:,.2f}")
    print(f"[INFO] Límite de riesgo base por trade: {Config.MAX_RISK_PER_TRADE*100}% (${equity * Config.MAX_RISK_PER_TRADE:,.2f})")
    print(f"[INFO] Evaluando {len(raw_trades)} transacciones del Congreso...\n")

    candidatos_validos = []
    descartados_count = 0

    # 3. Filtrado y Scoring
    for trade in raw_trades:
        pasa, motivo, trade_enriquecido = filtro.evaluar_trade(trade)
        if not pasa:
            descartados_count += 1
            continue

        score, clasificacion, desglose = scorer.calcular_score(trade_enriquecido)
        trade_enriquecido["score"] = score
        trade_enriquecido["clasificacion"] = clasificacion
        trade_enriquecido["desglose_score"] = desglose

        # Filtramos para ejecución señales Moderadas o Fuertes (Score >= 45)
        if score >= 45:
            candidatos_validos.append(trade_enriquecido)

    print(f"[RESUMEN DE FILTRADO]")
    print(f"  Total analizados:   {len(raw_trades)}")
    print(f"  Descartados:        {descartados_count} (por lag > 30d, montos bajos o ventas)")
    print(f"  Señales viables:    {len(candidatos_validos)} con Score >= 45\n")

    if not candidatos_validos:
        print("[INFO] No hay señales recientes que cumplan los estrictos filtros de calidad hoy.")
        return

    # Ordenar por Score descendente y menor lag
    candidatos_validos.sort(key=lambda x: (x["score"], -x.get("lag_days", 999)), reverse=True)

    # Evitar duplicar tickers en la misma corrida
    tickers_procesados = set()
    senales_unicas = []
    for c in candidatos_validos:
        t = c["ticker"]
        if t not in tickers_procesados:
            tickers_procesados.add(t)
            senales_unicas.append(c)

    top_signals = senales_unicas[:5]

    print("=" * 75)
    print("  MEJORES SEÑALES DETECTADAS (TOP CANDIDATOS A EJECUTAR)")
    print("=" * 75)

    for i, sig in enumerate(top_signals, 1):
        ticker = sig["ticker"]
        pol = sig["politician"]
        score = sig["score"]
        clasif = sig["clasificacion"]
        lag = sig["lag_days"]
        amt = sig.get("amount_range", "")
        desglose = sig.get("desglose_score", {})

        print(f"\n[{i}] TICKER: {ticker} | Político: {pol} ({sig.get('chamber', '')})")
        print(f"    Score: {score}/100 [{clasif}] | Lag: {lag} días | Monto: {amt}")
        print(f"    Desglose: Historial: {desglose.get('historial_politico')}pts, Convicción: {desglose.get('conviccion_monto')}pts, Frescura: {desglose.get('frescura_lag')}pts, Comité: {desglose.get('comite_relevante')}pts")
        print(f"    Consultando métricas en tiempo real con Yahoo Finance (Precio, ATR, Beta)...")

        plan = sizer.calcular_posicion(ticker, score)
        if not plan:
            print(f"    [SKIP] No se pudieron obtener cotizaciones para {ticker}.")
            continue

        print(f"    -> Precio Actual:    ${plan['entry_price']}")
        print(f"    -> Volatilidad:      ATR(14)=${plan['atr']} | Beta={plan['beta']}")
        print(f"    -> Stop Loss ATR:    ${plan['stop_loss_price']} (-{plan['stop_loss_pct']}%) [Protegido contra ruido]")
        print(f"    -> Acciones sugeridas: {plan['shares']} acciones")
        print(f"    -> Inversión Total:  ${plan['total_investment']:,.2f} ({plan['portfolio_allocation_pct']}% del capital)")
        print(f"    -> Riesgo Máximo:    ${plan['risk_dollar']:,.2f} ({plan['risk_pct_portfolio']}% del capital total)")
        print(f"    -> Take Profit 1:    ${plan['tp1_price']} (+{Config.TP1_PCT*100}%) | TP2: ${plan['tp2_price']} (+{Config.TP2_PCT*100}%)")

        # Ejecución de orden (simulación o Alpaca Paper)
        executor.execute_bracket_order(plan)

    print("\n" + "=" * 75)
    print("  EJECUCIÓN DEL PIPELINE COMPLETADA EXITOSAMENTE")
    print("=" * 75)

if __name__ == "__main__":
    run_pipeline(max_pages=15)
