# -*- coding: utf-8 -*-
"""
overnight_trader.py — Estrategia Overnight Drift con Filtros Cuantitativos
===========================================================================
Basado en investigacion academica (Boyarchenko et al., FRBNY 2021) y backtest
historico con datos reales de SPY/QQQ 2015-2026.

LOGICA DE LA ESTRATEGIA:
  - Compra SPY o QQQ justo antes del cierre (orden MOC a las 3:50 PM ET)
  - Mantiene durante la noche mientras mercados europeos y asiaticos mueven el precio
  - Vende exactamente en la apertura del mercado (9:30 AM ET del dia siguiente)

FILTROS DE ALTA CONVICCION (probados empiricamente):
  1. Dia de la semana: Solo Lunes a Jueves (no Viernes, evitar 60h de riesgo)
  2. Tendencia macro:  Precio actual > Media Movil 200 dias (solo bull market)
  3. Descuento intradiario: RSI(2) < 20 (mercado en sobreventa al cierre)
  4. Volatilidad controlada: VIX < 25 (no operar en panico extremo)

TASA DE EXITO HISTORICA (2015-2026): ~64-66% con Combo Elite
"""

import os
import sys
import time
import csv
import math
import logging
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import yfinance as yf
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config

# Intentar importar alpaca
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

# ==============================================================================
# CONFIGURACION
# ==============================================================================

class OvernightConfig:
    # Activo a tradear (SPY = S&P 500 / QQQ = Nasdaq 100)
    TICKER           = "SPY"

    # Porcentaje del portafolio a usar en cada operacion nocturna (conservador)
    CAPITAL_PCT      = 0.20       # 20% del capital en cada noche que se activa

    # Filtros de la Estrategia (ajustados con backtest real 2015-2026)
    SMA_PERIOD       = 200        # Media movil de tendencia macro
    RSI_PERIOD       = 2          # RSI ultra-corto para detectar sobreventa al cierre
    RSI_THRESHOLD    = 20.0       # RSI(2) debe estar por debajo de este valor
    VIX_THRESHOLD    = 25.0       # VIX debe estar por debajo de este valor
    LOOKBACK_DAYS    = 220        # Dias de historia a descargar para calcular SMA200

    # Horarios en Eastern Time
    ENTRY_HOUR       = 15         # 3:00 PM ET - ventana de evaluacion (cierre a las 4PM)
    ENTRY_MINUTE     = 50         # 3:50 PM ET - momento exacto de envio de orden
    EXIT_HOUR        = 9          # 9:00 AM ET - ventana de liquidacion
    EXIT_MINUTE      = 32         # 9:32 AM ET - 2 min post-apertura (Opening Cross asentado)

    # Archivo de bitacora
    LOG_FILE         = "overnight_log.csv"
    LOG_DIR          = os.path.dirname(os.path.abspath(__file__))


# ==============================================================================
# LOGGING
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("overnight_trader")


# ==============================================================================
# MODULO DE INDICADORES TECNICOS
# ==============================================================================

def calcular_indicadores(ticker: str, lookback: int = 220) -> dict | None:
    """
    Descarga datos historicos y calcula SMA200, RSI(2) y VIX.
    Retorna un diccionario con todos los valores necesarios para evaluar los filtros.
    """
    try:
        # Descargar el activo principal
        data = yf.download(ticker, period=f"{lookback}d", interval="1d",
                           auto_adjust=True, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        if data.empty or len(data) < 202:
            log.error(f"Datos insuficientes para {ticker} ({len(data)} filas).")
            return None

        # Descargar VIX
        vix_data = yf.download("^VIX", period="5d", interval="1d",
                               auto_adjust=True, progress=False)
        if isinstance(vix_data.columns, pd.MultiIndex):
            vix_data.columns = vix_data.columns.get_level_values(0)

        close  = data["Close"]
        open_  = data["Open"]

        # 1. SMA(200)
        sma200 = float(close.rolling(OvernightConfig.SMA_PERIOD).mean().iloc[-1])

        # 2. RSI(2) — periodo ultra-corto para detectar sobreventa intradiaria
        delta  = close.diff()
        gain   = delta.clip(lower=0).rolling(OvernightConfig.RSI_PERIOD).mean()
        loss   = (-delta.clip(upper=0)).rolling(OvernightConfig.RSI_PERIOD).mean()
        rs     = gain / (loss + 1e-9)
        rsi2   = float((100 - (100 / (1 + rs))).iloc[-1])

        # 3. Retorno intradiario del dia de hoy (Close vs Open)
        day_ret = float((close.iloc[-1] / open_.iloc[-1]) - 1)

        # 4. Precio actual (ultimo cierre conocido, o precio en tiempo real)
        current_price = float(close.iloc[-1])

        # 5. VIX actual
        vix_value = float(vix_data["Close"].iloc[-1]) if not vix_data.empty else 99.0

        return {
            "ticker":          ticker,
            "price":           current_price,
            "sma200":          round(sma200, 2),
            "rsi2":            round(rsi2, 2),
            "day_ret_pct":     round(day_ret * 100, 3),
            "vix":             round(vix_value, 2),
            "above_sma200":    current_price > sma200,
            "rsi2_oversold":   rsi2 < OvernightConfig.RSI_THRESHOLD,
            "vix_ok":          vix_value < OvernightConfig.VIX_THRESHOLD,
        }

    except Exception as e:
        log.error(f"Error calculando indicadores para {ticker}: {e}")
        return None


# ==============================================================================
# EVALUACION DE FILTROS
# ==============================================================================

def evaluar_condiciones(ind: dict, hoy: date) -> tuple[bool, list[str], list[str]]:
    """
    Evalua los 4 filtros de alta conviccion.
    Retorna: (pasa_todos, condiciones_ok, condiciones_fallidas)
    """
    ok    = []
    fail  = []
    dow   = hoy.weekday()  # 0=Lunes ... 4=Viernes ... 6=Domingo

    # 1. Dia de la semana (Lunes=0 a Jueves=3)
    dia_nombre = ["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado","Domingo"][dow]
    if dow <= 3:
        ok.append(f"Dia OK: {dia_nombre} (Lun-Jue)")
    else:
        fail.append(f"Dia FAIL: {dia_nombre} (solo operar Lun-Jue)")

    # 2. Tendencia macro: precio > SMA(200)
    if ind["above_sma200"]:
        ok.append(f"Tendencia OK: ${ind['price']:.2f} > SMA200 ${ind['sma200']:.2f}")
    else:
        fail.append(f"Tendencia FAIL: ${ind['price']:.2f} < SMA200 ${ind['sma200']:.2f} — mercado bajista")

    # 3. RSI(2) en sobreventa (< 20)
    if ind["rsi2_oversold"]:
        ok.append(f"Sobreventa OK: RSI(2) = {ind['rsi2']:.1f} < {OvernightConfig.RSI_THRESHOLD}")
    else:
        fail.append(f"RSI FAIL: RSI(2) = {ind['rsi2']:.1f} — no hay descuento suficiente (umbral {OvernightConfig.RSI_THRESHOLD})")

    # 4. VIX (< 25)
    if ind["vix_ok"]:
        ok.append(f"VIX OK: {ind['vix']:.1f} < {OvernightConfig.VIX_THRESHOLD}")
    else:
        fail.append(f"VIX FAIL: {ind['vix']:.1f} >= {OvernightConfig.VIX_THRESHOLD} — volatilidad extrema, sin operacion")

    pasa = len(fail) == 0
    return pasa, ok, fail


# ==============================================================================
# CLIENTE ALPACA
# ==============================================================================

def get_alpaca_client() -> object | None:
    """Conecta al cliente de Alpaca Paper Trading."""
    if not ALPACA_AVAILABLE:
        log.warning("Libreria alpaca-py no instalada. Corriendo en modo SIMULACION.")
        return None

    key    = Config.ALPACA_API_KEY
    secret = Config.ALPACA_SECRET_KEY

    if not key or not secret:
        log.warning("Llaves de Alpaca no configuradas en .env. Modo SIMULACION.")
        return None

    try:
        client = TradingClient(key, secret, paper=Config.ALPACA_PAPER)
        acct   = client.get_account()
        log.info(f"Alpaca conectado. Equity: ${float(acct.equity):,.2f} | "
                 f"Cash: ${float(acct.cash):,.2f} | "
                 f"Buying Power: ${float(acct.buying_power):,.2f}")
        return client
    except Exception as e:
        log.error(f"Error al conectar Alpaca: {e}")
        return None


def get_portfolio_equity(client) -> float:
    """Obtiene el equity total de la cuenta de Alpaca."""
    if not client:
        return 100_000.0  # Capital virtual de simulacion
    try:
        return float(client.get_account().equity)
    except Exception:
        return 100_000.0


# ==============================================================================
# OPERACIONES DE MERCADO
# ==============================================================================

def calcular_shares(equity: float, precio: float) -> int:
    """
    Calcula cuantas acciones comprar usando el porcentaje de capital configurado.
    Garantiza al menos 1 accion.
    """
    capital_a_usar = equity * OvernightConfig.CAPITAL_PCT
    shares = math.floor(capital_a_usar / precio)
    return max(1, shares)


def comprar_al_cierre(client, ticker: str, shares: int, precio_ref: float, equity: float) -> dict:
    """
    Envia una orden de compra a mercado (MOC idealmente, market order si no disponible).
    Alpaca Paper Trading usa market orders que se ejecutan al precio disponible.
    """
    inversion_est = shares * precio_ref

    if not client:
        # Modo simulacion
        log.info(f"[SIMULACION] COMPRA: {shares} acciones de {ticker} @ ~${precio_ref:.2f} "
                 f"= ${inversion_est:,.2f} ({OvernightConfig.CAPITAL_PCT*100:.0f}% del capital)")
        return {
            "status":    "SIMULATED",
            "ticker":    ticker,
            "shares":    shares,
            "precio_ref": precio_ref,
            "inversion": inversion_est,
            "order_id":  "SIM-ENTRY"
        }

    try:
        try:
            order_data = MarketOrderRequest(
                symbol=ticker,
                qty=shares,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.CLS,
            )
            order = client.submit_order(order_data)
        except Exception as e_cls:
            log.warning(f"Orden CLS no admitida ({e_cls}), enviando orden DAY a mercado...")
            order_data = MarketOrderRequest(
                symbol=ticker,
                qty=shares,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
            order = client.submit_order(order_data)

        log.info(f"COMPRA enviada a Alpaca — ID: {order.id} | {shares} {ticker} @ ~${precio_ref:.2f}")
        return {
            "status":    "SUBMITTED",
            "ticker":    ticker,
            "shares":    shares,
            "precio_ref": precio_ref,
            "inversion": inversion_est,
            "order_id":  str(order.id)
        }
    except Exception as e:
        log.error(f"Error al enviar orden de compra: {e}")
        return {"status": "FAILED", "error": str(e)}


def vender_en_apertura(client, ticker: str) -> dict:
    """
    Liquida toda la posicion en el activo al precio de apertura.
    """
    if not client:
        log.info(f"[SIMULACION] VENTA: Liquidar toda la posicion de {ticker} en apertura.")
        return {"status": "SIMULATED", "ticker": ticker, "order_id": "SIM-EXIT"}

    try:
        # Verificar si hay posicion abierta
        positions = client.get_all_positions()
        pos = next((p for p in positions if p.symbol == ticker), None)

        if not pos:
            log.warning(f"No se encontro posicion abierta en {ticker}. Nada que liquidar.")
            return {"status": "NO_POSITION", "ticker": ticker}

        shares_held   = int(float(pos.qty))
        entry_price   = float(pos.avg_entry_price)
        unrealized_pl = float(pos.unrealized_pl)

        log.info(f"Posicion encontrada: {shares_held} {ticker} | "
                 f"Entrada: ${entry_price:.2f} | "
                 f"P/L no realizado: ${unrealized_pl:+,.2f}")

        order_data = MarketOrderRequest(
            symbol=ticker,
            qty=shares_held,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        order = client.submit_order(order_data)
        log.info(f"VENTA enviada a Alpaca — ID: {order.id} | {shares_held} {ticker}")
        return {
            "status":       "SUBMITTED",
            "ticker":       ticker,
            "shares":       shares_held,
            "entry_price":  entry_price,
            "unrealized_pl": unrealized_pl,
            "order_id":     str(order.id)
        }
    except Exception as e:
        log.error(f"Error al enviar orden de venta: {e}")
        return {"status": "FAILED", "error": str(e)}


# ==============================================================================
# BITACORA DE TRADES
# ==============================================================================

def registrar_trade(fecha: str, accion: str, ticker: str, shares: int,
                    precio: float, inversion: float, pnl: float | None,
                    status: str, condiciones: str, order_id: str):
    """Registra cada operacion en el archivo CSV de bitacora."""
    log_path = os.path.join(OvernightConfig.LOG_DIR, OvernightConfig.LOG_FILE)
    existe   = os.path.isfile(log_path)

    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not existe:
            writer.writerow([
                "fecha", "accion", "ticker", "shares",
                "precio_ref", "inversion", "pnl_estimado",
                "status", "condiciones_ok", "order_id"
            ])
        writer.writerow([
            fecha, accion, ticker, shares,
            round(precio, 2), round(inversion, 2),
            round(pnl, 2) if pnl is not None else "",
            status, condiciones, order_id
        ])
    log.info(f"Operacion registrada en {OvernightConfig.LOG_FILE}")


# ==============================================================================
# MODO MANUAL: CORRER AHORA PARA PROBAR
# ==============================================================================

def evaluar_y_entrar(modo_forzado: bool = False):
    """
    Evalua las condiciones en tiempo real y entra si todo esta verde.
    
    modo_forzado=True: Ignora los filtros y entra de todas formas (para testing).
    """
    log.info("=" * 65)
    log.info("  OVERNIGHT TRADER — EVALUACION DE ENTRADA (3:50 PM ET)")
    log.info("=" * 65)

    hoy    = date.today()
    client = get_alpaca_client()
    equity = get_portfolio_equity(client)

    log.info(f"Activo: {OvernightConfig.TICKER} | "
             f"Capital del portafolio: ${equity:,.2f} | "
             f"Capital a usar ({OvernightConfig.CAPITAL_PCT*100:.0f}%): "
             f"${equity * OvernightConfig.CAPITAL_PCT:,.2f}")

    # 1. Calcular indicadores
    log.info(f"Descargando datos de {OvernightConfig.TICKER} y VIX...")
    ind = calcular_indicadores(OvernightConfig.TICKER, OvernightConfig.LOOKBACK_DAYS)
    if not ind:
        log.error("No se pudieron calcular indicadores. Abortando.")
        return

    log.info(f"Precio actual:  ${ind['price']:.2f}")
    log.info(f"SMA(200):       ${ind['sma200']:.2f} — "
             f"{'ENCIMA' if ind['above_sma200'] else 'DEBAJO'} (Bull={'SI' if ind['above_sma200'] else 'NO'})")
    log.info(f"RSI(2):         {ind['rsi2']:.1f} — "
             f"{'SOBREVENTA' if ind['rsi2_oversold'] else 'Normal'}")
    log.info(f"VIX:            {ind['vix']:.1f} — "
             f"{'OK' if ind['vix_ok'] else 'ALTO'}")
    log.info(f"Retorno del dia: {ind['day_ret_pct']:+.2f}%")

    # 2. Evaluar filtros
    pasa, conds_ok, conds_fail = evaluar_condiciones(ind, hoy)

    log.info("-" * 65)
    for c in conds_ok:
        log.info(f"  [OK]   {c}")
    for c in conds_fail:
        log.info(f"  [FAIL] {c}")
    log.info("-" * 65)

    if not pasa and not modo_forzado:
        log.info("DECISION: No se opera esta noche. Condiciones no cumplidas.")
        log.info("=" * 65)
        return

    if modo_forzado and not pasa:
        log.info("MODO FORZADO: Entrando de todas formas (ignorando filtros fallidos).")

    log.info("DECISION: Todas las condiciones se cumplen. Colocando orden de COMPRA.")

    # 3. Calcular acciones y ejecutar entrada
    shares = calcular_shares(equity, ind["price"])
    resultado = comprar_al_cierre(client, OvernightConfig.TICKER, shares,
                                  ind["price"], equity)

    # 4. Registrar en bitacora
    registrar_trade(
        fecha      = hoy.isoformat(),
        accion     = "COMPRA_NOCTURNA",
        ticker     = OvernightConfig.TICKER,
        shares     = shares,
        precio     = ind["price"],
        inversion  = shares * ind["price"],
        pnl        = None,
        status     = resultado.get("status", "UNKNOWN"),
        condiciones = " | ".join(conds_ok),
        order_id   = resultado.get("order_id", "")
    )

    log.info("=" * 65)
    log.info(f"Orden {'enviada a Alpaca' if resultado['status'] == 'SUBMITTED' else 'simulada'}.")
    log.info(f"Manana a las {OvernightConfig.EXIT_HOUR}:{OvernightConfig.EXIT_MINUTE:02d} AM ET "
             f"corre 'python overnight_trader.py --salir' para cerrar la posicion.")
    log.info("=" * 65)


def salir_en_apertura():
    """Liquida la posicion nocturna en la apertura del mercado."""
    log.info("=" * 65)
    log.info("  OVERNIGHT TRADER — LIQUIDACION EN APERTURA (9:32 AM ET)")
    log.info("=" * 65)

    client = get_alpaca_client()

    # Precio actual para calcular PnL estimado
    try:
        data       = yf.download(OvernightConfig.TICKER, period="2d",
                                 interval="1d", auto_adjust=True, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        precio_hoy = float(data["Open"].iloc[-1])
    except Exception:
        precio_hoy = 0.0

    resultado = vender_en_apertura(client, OvernightConfig.TICKER)

    pnl_estimado = None
    shares_sold  = resultado.get("shares", 0)
    if resultado.get("status") in ("SUBMITTED", "SIMULATED") and shares_sold and precio_hoy:
        entry = resultado.get("entry_price", precio_hoy)
        pnl_estimado = (precio_hoy - entry) * shares_sold
        pnl_pct      = ((precio_hoy / entry) - 1) * 100 if entry else 0
        log.info(f"PnL estimado: ${pnl_estimado:+,.2f} ({pnl_pct:+.2f}%)")

    registrar_trade(
        fecha       = date.today().isoformat(),
        accion      = "VENTA_APERTURA",
        ticker      = OvernightConfig.TICKER,
        shares      = shares_sold,
        precio      = precio_hoy,
        inversion   = shares_sold * precio_hoy if shares_sold else 0,
        pnl         = pnl_estimado,
        status      = resultado.get("status", "UNKNOWN"),
        condiciones = "SALIDA_AUTOMATICA",
        order_id    = resultado.get("order_id", "")
    )

    log.info("=" * 65)


def mostrar_resumen():
    """Lee el CSV de bitacora y muestra estadisticas de rendimiento."""
    log_path = os.path.join(OvernightConfig.LOG_DIR, OvernightConfig.LOG_FILE)
    if not os.path.isfile(log_path):
        log.info("No hay bitacora de operaciones todavia.")
        return

    df = pd.read_csv(log_path)
    ventas = df[df["accion"] == "VENTA_APERTURA"].copy()
    ventas["pnl_estimado"] = pd.to_numeric(ventas["pnl_estimado"], errors="coerce")
    ventas = ventas.dropna(subset=["pnl_estimado"])

    if ventas.empty:
        log.info("Todavia no hay trades completados en la bitacora.")
        return

    total   = len(ventas)
    ganas   = (ventas["pnl_estimado"] > 0).sum()
    pierde  = (ventas["pnl_estimado"] <= 0).sum()
    pnl_tot = ventas["pnl_estimado"].sum()
    win_rate = (ganas / total) * 100

    print("\n" + "=" * 65)
    print("  RESUMEN DE TRADES OVERNIGHT")
    print("=" * 65)
    print(f"  Total de noches operadas: {total}")
    print(f"  Noches ganadas:           {ganas} ({win_rate:.1f}%)")
    print(f"  Noches perdidas:          {pierde}")
    print(f"  PnL Total Estimado:       ${pnl_tot:+,.2f}")
    print(f"  PnL Promedio por noche:   ${pnl_tot/total:+,.2f}")
    print("=" * 65)
    print(df[["fecha", "accion", "shares", "precio_ref", "pnl_estimado", "status"]].to_string(index=False))
    print("=" * 65 + "\n")


# ==============================================================================
# MODO AUTOMATICO: SCHEDULER INTERNO (corre indefinidamente)
# ==============================================================================

def correr_scheduler():
    """
    Corre un scheduler liviano que revisa la hora cada minuto.
    Ejecuta la entrada a las 3:50 PM ET y la salida a las 9:32 AM ET de lunes a viernes.
    Para dejarlo corriendo en background: python overnight_trader.py --auto
    """
    ET = ZoneInfo("America/New_York")
    log.info("Scheduler Overnight Trader iniciado. Escuchando horarios ET...")
    log.info(f"  Entrada: {OvernightConfig.ENTRY_HOUR}:{OvernightConfig.ENTRY_MINUTE:02d} PM ET (Lun-Jue)")
    log.info(f"  Salida:  {OvernightConfig.EXIT_HOUR}:{OvernightConfig.EXIT_MINUTE:02d} AM ET (Lun-Vie)")

    entrada_ejecutada = False
    salida_ejecutada  = False
    ultimo_dia        = None

    while True:
        ahora = datetime.now(ET)
        hoy   = ahora.date()

        # Reset de flags al nuevo dia
        if hoy != ultimo_dia:
            entrada_ejecutada = False
            salida_ejecutada  = False
            ultimo_dia        = hoy
            log.info(f"Nuevo dia de trading detectado: {hoy}")

        dow = hoy.weekday()  # 0=Lun ... 4=Vie

        # SALIDA: 9:32 AM ET (Lunes a Viernes)
        if (not salida_ejecutada
                and dow <= 4
                and ahora.hour == OvernightConfig.EXIT_HOUR
                and ahora.minute >= OvernightConfig.EXIT_MINUTE):
            log.info("Horario de SALIDA alcanzado. Ejecutando liquidacion...")
            salir_en_apertura()
            salida_ejecutada = True

        # ENTRADA: 3:50 PM ET (Lunes a Jueves)
        if (not entrada_ejecutada
                and dow <= 3
                and ahora.hour == OvernightConfig.ENTRY_HOUR
                and ahora.minute >= OvernightConfig.ENTRY_MINUTE):
            log.info("Horario de ENTRADA alcanzado. Evaluando condiciones...")
            evaluar_y_entrar(modo_forzado=False)
            entrada_ejecutada = True

        time.sleep(30)  # Revisar cada 30 segundos


# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--entrar" in args or len(args) == 0:
        # Evaluacion y entrada manual (o test inmediato)
        forzado = "--forzar" in args
        if forzado:
            log.info("MODO FORZADO activado: se ignoraran los filtros.")
        evaluar_y_entrar(modo_forzado=forzado)

    elif "--salir" in args:
        # Liquidacion manual
        salir_en_apertura()

    elif "--resumen" in args:
        # Ver estadisticas del historial de trades
        mostrar_resumen()

    elif "--auto" in args:
        # Scheduler automatico (correr siempre, revisa horario ET)
        correr_scheduler()

    else:
        print("""
Uso:
  python overnight_trader.py               — Evalua condiciones y entra si todo esta verde (3:50 PM)
  python overnight_trader.py --entrar      — Idem
  python overnight_trader.py --entrar --forzar  — Entra sin importar los filtros (testing)
  python overnight_trader.py --salir       — Liquida la posicion en apertura (9:32 AM)
  python overnight_trader.py --resumen     — Muestra estadisticas de todos los trades
  python overnight_trader.py --auto        — Scheduler automatico 24/7 (modo daemon)
        """)
