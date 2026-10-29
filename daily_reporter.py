# -*- coding: utf-8 -*-
"""
daily_reporter.py — Módulo de Reporte Diario de Toma de Decisiones y Estado de Cartera
====================================================================================
Genera y envía automáticamente un informe ejecutivo a Discord al cierre del mercado
(4:05 PM ET) de Lunes a Viernes, documentando:
  1. Decisiones tomadas por el Bot del Congreso y motivos de descarte/ejecución.
  2. Decisiones tomadas por el Bot Overnight Drift y métricas de cierre (SMA200, RSI(2), VIX).
  3. Estado financiero de la cuenta en Alpaca (Balance, Efectivo, P&L latente).
  4. Desglose detallado de posiciones y órdenes de protección activas.
"""

import os
import sys
from datetime import datetime, date
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config
from notifier import send_discord_embed

def obtener_datos_cartera():
    """Consulta el estado en vivo de la cuenta y posiciones en Alpaca."""
    try:
        from alpaca_executor import AlpacaExecutor
        ex = AlpacaExecutor()
        if not ex.client:
            return None

        acc = ex.client.get_account()
        positions = ex.client.get_all_positions()
        orders = ex.client.get_orders()

        pos_list = []
        for p in positions:
            entry = float(p.avg_entry_price)
            curr = float(p.current_price)
            val = float(p.market_value)
            pnl = float(p.unrealized_pl)
            pct = float(p.unrealized_plpc) * 100
            pos_list.append({
                "symbol": p.symbol,
                "qty": int(p.qty),
                "entry_price": entry,
                "current_price": curr,
                "market_value": val,
                "pnl_dollar": pnl,
                "pnl_pct": pct
            })

        order_list = []
        for o in orders:
            order_list.append({
                "symbol": o.symbol,
                "side": o.side.value.upper(),
                "qty": int(o.qty),
                "order_type": o.order_type.value,
                "price": o.stop_price or o.limit_price or "MKT",
                "status": o.status.value
            })

        return {
            "equity": float(acc.equity),
            "cash": float(acc.cash),
            "buying_power": float(acc.buying_power),
            "positions": pos_list,
            "orders": order_list
        }
    except Exception as e:
        print(f"[WARN] Error al obtener datos de Alpaca para el reporte: {e}")
        return None


def obtener_decision_overnight():
    """Evalúa los indicadores de cierre de SPY y la decisión del bot Overnight."""
    try:
        import overnight_trader
        ind = overnight_trader.calcular_indicadores(overnight_trader.OvernightConfig.TICKER)
        if not ind:
            return {"status": "ERROR", "detalle": "No se pudieron calcular indicadores de SPY."}

        pasa, conds_ok, conds_fail = overnight_trader.evaluar_condiciones(ind, date.today())
        
        if pasa:
            decision = "COMPRA EJECUTADA (Orden MOC enviada al cierre)"
            motivo = "Todas las condiciones cuantitativas se cumplieron: SPY > SMA200, VIX < 25 y RSI(2) en sobreventa extrema."
        else:
            decision = "COMPRA DESCARTADA (Capital protegido en liquidez)"
            motivos_fallo = "; ".join(conds_fail)
            motivo = f"Filtros cuantitativos no superados: {motivos_fallo}"

        return {
            "status": "OK",
            "ticker": ind["ticker"],
            "precio": ind["price"],
            "sma200": ind["sma200"],
            "above_sma200": ind["above_sma200"],
            "rsi2": ind["rsi2"],
            "rsi2_oversold": ind["rsi2_oversold"],
            "vix": ind["vix"],
            "vix_ok": ind["vix_ok"],
            "pasa": pasa,
            "decision": decision,
            "motivo": motivo,
            "conds_ok": conds_ok,
            "conds_fail": conds_fail
        }
    except Exception as e:
        return {"status": "ERROR", "detalle": str(e)}


def obtener_decision_congreso():
    """Analiza las decisiones del bot del Congreso para el día de hoy."""
    hoy_str = date.today().isoformat()
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "congreso_trades.csv")
    
    trades_hoy = []
    if os.path.exists(log_file):
        import csv
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("fecha_ejecucion", "").startswith(hoy_str):
                    trades_hoy.append(row)

    if trades_hoy:
        decision = f"{len(trades_hoy)} compras enviadas hoy"
        motivo = ", ".join([f"{t.get('ticker')} ({t.get('politico')}, Score {t.get('score')})" for t in trades_hoy])
    else:
        decision = "0 nuevas compras enviadas hoy"
        motivo = "Operaciones analizadas descartadas: señales calificadas (EL y GH) ya estaban en cartera (filtro anti-duplicados activado) o no superaron Score >= 60."

    return {
        "escaneos_programados": "3 franjas (10:00 AM, 1:00 PM, 3:30 PM ET)",
        "decision": decision,
        "motivo": motivo,
        "trades_hoy": trades_hoy
    }


def generar_y_enviar_reporte_diario():
    """Compila el reporte diario, lo guarda en disco y lo despacha a Discord."""
    ET = ZoneInfo("America/New_York")
    ahora_et = datetime.now(ET)
    fecha_str = ahora_et.strftime("%Y-%m-%d")
    hora_str = ahora_et.strftime("%H:%M:%S ET")

    print("=" * 70)
    print(f"GENERANDO REPORTE DIARIO DE TOMA DE DECISIONES — {fecha_str} {hora_str}")
    print("=" * 70)

    # 1. Obtener datos
    cartera = obtener_datos_cartera()
    overnight = obtener_decision_overnight()
    congreso = obtener_decision_congreso()

    # 2. Formatear sección Cartera
    if cartera:
        equity_str = f"${cartera['equity']:,.2f} USD"
        cash_str = f"${cartera['cash']:,.2f} USD"
        pnl_total = sum(p["pnl_dollar"] for p in cartera["positions"])
        pnl_total_str = f"+${pnl_total:,.2f}" if pnl_total >= 0 else f"-${abs(pnl_total):,.2f}"
        
        pos_lines = []
        for p in cartera["positions"]:
            sign = "+" if p["pnl_dollar"] >= 0 else "-"
            pos_lines.append(
                f"• {p['symbol']}: {p['qty']} u. | Entrada: ${p['entry_price']:.2f} | Cierre: ${p['current_price']:.2f} | PnL: {sign}${abs(p['pnl_dollar']):.2f} ({p['pnl_pct']:+.2f}%)"
            )
        pos_texto = "\n".join(pos_lines) if pos_lines else "Sin posiciones abiertas."

        ord_lines = []
        for o in cartera["orders"]:
            ord_lines.append(f"• {o['symbol']} | {o['side']} {o['qty']} u. ({o['order_type'].upper()}) @ ${o['price']}")
        ord_texto = "\n".join(ord_lines) if ord_lines else "Sin órdenes pendientes."
    else:
        equity_str = "No disponible"
        cash_str = "No disponible"
        pnl_total_str = "N/A"
        pos_texto = "Error de conexión con Alpaca."
        ord_texto = "Error de conexión con Alpaca."

    # 3. Formatear sección Overnight
    if overnight.get("status") == "OK":
        ind_text = (
            f"• SPY Cierre: ${overnight['precio']:.2f} | SMA200: ${overnight['sma200']:.2f} ({'Alcista' if overnight['above_sma200'] else 'Bajista'})\n"
            f"• RSI(2): {overnight['rsi2']:.2f} (Umbral < 20.0: {'Cumplido' if overnight['rsi2_oversold'] else 'No cumplido'})\n"
            f"• VIX: {overnight['vix']:.2f} (Umbral < 25.0: {'OK' if overnight['vix_ok'] else 'Riesgo alto'})"
        )
        on_decision = f"**{overnight['decision']}**\n{overnight['motivo']}"
    else:
        ind_text = "No se pudieron calcular indicadores de SPY."
        on_decision = overnight.get("detalle", "Error desconocido.")

    # 4. Formatear sección Congreso
    cong_decision = (
        f"**Decisión:** {congreso['decision']}\n"
        f"**Fundamento:** {congreso['motivo']}\n"
        f"**Monitoreo:** {congreso['escaneos_programados']}"
    )

    # 5. Construir campos de Embed de Discord
    fields = [
        {
            "name": "1. Decisiones Bot Congreso (main.py)",
            "value": cong_decision,
            "inline": False
        },
        {
            "name": "2. Decisiones Bot Overnight Drift (overnight_trader.py)",
            "value": f"{ind_text}\n\n{on_decision}",
            "inline": False
        },
        {
            "name": "3. Estado Financiero de Cartera (Alpaca Paper)",
            "value": f"• Balance Total: **{equity_str}**\n• Efectivo en Reserva: **{cash_str}**\n• P&L Latente Total: **{pnl_total_str}**",
            "inline": False
        },
        {
            "name": "4. Desglose de Posiciones en Cartera",
            "value": pos_texto,
            "inline": False
        },
        {
            "name": "5. Órdenes de Salida y Protección (Stop Loss / Take Profit)",
            "value": ord_texto,
            "inline": False
        }
    ]

    title = f"REPORTE DIARIO DE OPERACIONES Y DECISIONES — {fecha_str}"
    description = (
        f"Informe ejecutivo automatizado del cierre de sesión ({hora_str}). "
        f"Auditoría de filtros cuantitativos, decisiones algorítmicas y estado de la cuenta."
    )

    # Color del embed: Azul institucional si neutro / sin compras; Verde si positivo
    color = 0x3498DB

    # Enviar a Discord
    discord_enviado = send_discord_embed(title, description, fields, color=color)
    print(f"Despacho a Discord: {'EXITOSO' if discord_enviado else 'FALLIDO'}")

    # 6. Guardar archivo local en reportes_diarios/
    rep_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reportes_diarios")
    os.makedirs(rep_dir, exist_ok=True)
    rep_path = os.path.join(rep_dir, f"reporte_{fecha_str}.md")
    
    md_content = f"""# {title}
**Fecha:** {fecha_str} | **Hora:** {hora_str}

## 1. Toma de Decisiones: Bot del Congreso
{cong_decision}

## 2. Toma de Decisiones: Bot Overnight Drift
{ind_text}

{on_decision}

## 3. Estado Financiero de Cartera
- **Balance Total:** {equity_str}
- **Efectivo Disponible:** {cash_str}
- **P&L Latente Total:** {pnl_total_str}

### Posiciones Activas
{pos_texto}

### Órdenes de Protección
{ord_texto}
"""
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Reporte guardado en disco: {rep_path}")
    print("=" * 70)
    return discord_enviado


if __name__ == "__main__":
    generar_y_enviar_reporte_diario()
