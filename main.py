"""
main.py
Orquestador Principal del Sistema de Réplica de Trades del Congreso.
Ejecuta el flujo completo:
1. Ingesta de datos (Capitol Trades en tiempo real)
2. Filtro de Calidad (Lag <= 30d, Monto >= $15k, Compras directas)
3. Scoring del Político (Comités, Historial, Convicción, Lag)
4. Dimensionamiento de Posición (Riesgo mín 1%, Stop ATR 2.5x-3.0x, Cap 15%)
5. Ejecución (Simulación o Alpaca Paper Trading con órdenes Bracket)
6. Protección anti-duplicados y registro de auditoría en congreso_trades.csv
"""

import sys
import os
import csv
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from data_collector import DataCollector
from filtro_calidad import FiltroCalidad
from scoring_politico import ScoringPolitico
from position_sizer import PositionSizer
from alpaca_executor import AlpacaExecutor
from config import Config

CSV_LOG_FILE = "congreso_trades.csv"

def registrar_auditoria(ticker: str, pol: str, score: int, amt: str, plan: dict, res: dict):
    """Guarda cada trade ejecutado en un archivo permanente de auditoria."""
    existe = os.path.isfile(CSV_LOG_FILE)
    with open(CSV_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not existe:
            writer.writerow([
                "fecha_ejecucion", "ticker", "politico", "score",
                "monto_declarado", "precio_entrada", "stop_loss",
                "tp1", "tp2", "shares", "inversion", "riesgo_dollar",
                "order_id", "status"
            ])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ticker, pol, score, amt,
            plan["entry_price"], plan["stop_loss_price"],
            plan["tp1_price"], plan["tp2_price"],
            plan["shares"], plan["total_investment"], plan["risk_dollar"],
            res.get("order_id", "SIM-ORDER"), res.get("status", "UNKNOWN")
        ])

def run_pipeline(max_pages: int = 15, min_score_auto: int = 60):
    print("=" * 75)
    print("  SISTEMA DE RÉPLICA DE TRADES DEL CONGRESO — ESCANEO Y AUTO-EJECUCIÓN")
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

    # 3. Protección Anti-Duplicados y Límites
    open_tickers = executor.get_open_tickers()
    print(f"\n[INFO] Capital del Portafolio: ${equity:,.2f}")
    print(f"[INFO] Posiciones u órdenes ya abiertas en Alpaca: {list(open_tickers) if open_tickers else 'Ninguna'}")
    print(f"[INFO] Límite de posiciones simultáneas: {Config.MAX_OPEN_POSITIONS}")
    print(f"[INFO] Evaluando {len(raw_trades)} transacciones del Congreso...\n")

    candidatos_validos = []
    descartados_count = 0

    # 4. Filtrado y Scoring
    for trade in raw_trades:
        sig_type, motivo, trade_enriquecido = filtro.clasificar(trade)
        if sig_type != "EQUITY_STRONG":
            descartados_count += 1
            continue

        score, clasificacion, desglose = scorer.calcular_score(trade_enriquecido)
        trade_enriquecido["score"] = score
        trade_enriquecido["clasificacion"] = clasificacion
        trade_enriquecido["desglose_score"] = desglose
        trade_enriquecido["signal_type"] = sig_type

        # Filtro estricto para auto-ejecución: solo señales fuertes (Score >= min_score_auto)
        if score >= min_score_auto:
            candidatos_validos.append(trade_enriquecido)

    print(f"[RESUMEN DE FILTRADO]")
    print(f"  Total analizados:     {len(raw_trades)}")
    print(f"  Descartados:          {descartados_count} (por lag > 30d, montos bajos, bonos o ventas)")
    print(f"  Señales Fuertes (>= {min_score_auto}p): {len(candidatos_validos)}\n")

    if not candidatos_validos:
        print(f"[INFO] No hay señales recientes que superen el Score mínimo de {min_score_auto} hoy.")
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
    print("  MEJORES SEÑALES DETECTADAS (EVALUANDO APERTURA EN ALPACA)")
    print("=" * 75)

    ejecutadas = 0
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
        print(f"    Desglose: Historial: {desglose.get('historial_politico')}p, Convicción: {desglose.get('conviccion_monto')}p, Frescura: {desglose.get('frescura_lag')}p, Comité: {desglose.get('comite_relevante')}p")

        # REGLA 1: Anti-duplicados
        if ticker in open_tickers:
            print(f"    [SKIP] {ticker} ya está abierto o con orden pendiente en Alpaca. No se duplica.")
            continue

        # REGLA 2: Límite de posiciones abiertas
        if len(open_tickers) >= Config.MAX_OPEN_POSITIONS:
            print(f"    [SKIP] Límite de {Config.MAX_OPEN_POSITIONS} posiciones simultáneas alcanzado en Alpaca.")
            break

        print(f"    Consultando métricas en tiempo real con Yahoo Finance (Precio, ATR, Beta)...")
        plan = sizer.calcular_posicion(ticker, score)
        if not plan:
            print(f"    [SKIP] No se pudieron obtener cotizaciones para {ticker}.")
            continue

        print(f"    -> Precio Actual:    ${plan['entry_price']}")
        print(f"    -> Volatilidad:      ATR(14)=${plan['atr']} | Beta={plan['beta']}")
        print(f"    -> Stop Loss ATR:    ${plan['stop_loss_price']} (-{plan['stop_loss_pct']}%) [Protegido]")
        print(f"    -> Acciones:         {plan['shares']} acciones")
        print(f"    -> Inversión Total:  ${plan['total_investment']:,.2f} ({plan['portfolio_allocation_pct']}% del capital)")
        print(f"    -> Riesgo Máximo:    ${plan['risk_dollar']:,.2f} ({plan['risk_pct_portfolio']}% del portafolio)")
        print(f"    -> Take Profit 1:    ${plan['tp1_price']} (+{Config.TP1_PCT*100}%) | TP2: ${plan['tp2_price']} (+{Config.TP2_PCT*100}%)")

        # REGLA 3: Ejecución de orden Bracket
        res = executor.execute_bracket_order(plan)
        registrar_auditoria(ticker, pol, score, amt, plan, res)
        open_tickers.add(ticker)
        ejecutadas += 1

    print("\n" + "=" * 75)
    print(f"  EJECUCIÓN COMPLETADA — {ejecutadas} NUEVAS ÓRDENES ENVIADAS")
    print("=" * 75)


def correr_scheduler_congreso():
    """
    Scheduler autónomo para el bot del Congreso.
    Monitorea el reloj de Nueva York (ET) y corre de Lunes a Viernes a las 10:00 AM ET.
    """
    ET = ZoneInfo("America/New_York")
    print("Scheduler del Bot del Congreso iniciado. Monitoreando horario ET...")
    print("Horario programado: Lunes a Viernes a las 10:00 AM ET (mercado abierto y spreads estables).")

    ejecutado_hoy = False
    ultimo_dia = None

    while True:
        ahora = datetime.now(ET)
        hoy = ahora.date()

        if hoy != ultimo_dia:
            ejecutado_hoy = False
            ultimo_dia = hoy

        dow = hoy.weekday()  # 0=Lunes ... 4=Viernes

        # Disparo: 10:00 AM ET en días hábiles
        if (not ejecutado_hoy
                and dow <= 4
                and ahora.hour == 10
                and ahora.minute >= 0):
            print(f"\n[HORARIO ALCANZADO] 10:00 AM ET — Iniciando escaneo del Congreso...")
            try:
                run_pipeline(max_pages=15, min_score_auto=60)
            except Exception as e:
                print(f"[ERROR] Error inesperado en el escaneo del Congreso: {e}")
            ejecutado_hoy = True

        time.sleep(30)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--auto" in args:
        correr_scheduler_congreso()
    else:
        # Corrida manual bajo demanda
        run_pipeline(max_pages=15, min_score_auto=60)
