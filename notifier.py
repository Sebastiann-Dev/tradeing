# -*- coding: utf-8 -*-
"""
notifier.py — Sistema de Notificaciones a Discord
Envía alertas enriquecidas (Embeds) con diseño institucional y sin emojis.
"""

import os
import requests
from datetime import datetime
from config import Config

def send_discord_embed(title: str, description: str, fields: list[dict], color: int = 0x2ECC71) -> bool:
    """
    Envía una tarjeta Embed a Discord mediante Webhook.
    Colores comunes:
      0x2ECC71 (Verde - Compra / Ganancia)
      0xE74C3C (Rojo - Venta / Pérdida / Alerta)
      0x3498DB (Azul - Informativo / Sistema)
      0xF1C40F (Dorado - Overnight / Take Profit)
    """
    webhook_url = Config.DISCORD_WEBHOOK_URL.strip()
    if not webhook_url:
        return False

    payload = {
        "username": "Trading Desk Terminal",
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "fields": fields,
                "footer": {
                    "text": "Congressional & Overnight Quant System | " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
        ]
    }

    try:
        r = requests.post(webhook_url, json=payload, timeout=8)
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"[WARN] Error al enviar notificación a Discord: {e}")
        return False


def notify_congress_trade(sig: dict, plan: dict, res: dict):
    """Notifica la ejecución de una réplica de trade del Congreso."""
    ticker = sig.get("ticker", "")
    pol = sig.get("politician", "")
    chamber = sig.get("chamber", "")
    score = sig.get("score", 0)
    clasif = sig.get("clasificacion", "")
    lag = sig.get("lag_days", "?")
    amt = sig.get("amount_range", "")

    fields = [
        {"name": "Político", "value": f"{pol} ({chamber})", "inline": True},
        {"name": "Activo", "value": f"**{ticker}**", "inline": True},
        {"name": "Score Cuantitativo", "value": f"{score}/100 [{clasif}]", "inline": True},
        {"name": "Acciones Compradas", "value": f"{plan.get('shares')} u.", "inline": True},
        {"name": "Precio de Entrada", "value": f"${plan.get('entry_price', 0):,.2f}", "inline": True},
        {"name": "Inversión Total", "value": f"${plan.get('total_investment', 0):,.2f} ({plan.get('portfolio_allocation_pct')}% cap)", "inline": True},
        {"name": "Stop Loss Técnico (ATR)", "value": f"${plan.get('stop_loss_price', 0):,.2f} (-{plan.get('stop_loss_pct')}%)", "inline": True},
        {"name": "Take Profit 1 (+15%)", "value": f"${plan.get('tp1_price', 0):,.2f}", "inline": True},
        {"name": "Take Profit 2 (+30%)", "value": f"${plan.get('tp2_price', 0):,.2f}", "inline": True},
        {"name": "Riesgo Asignado", "value": f"${plan.get('risk_dollar', 0):,.2f} ({plan.get('risk_pct_used')}% riesgo)", "inline": True},
        {"name": "Monto Reportado", "value": f"{amt} (Lag: {lag}d)", "inline": True},
        {"name": "ID de Orden Alpaca", "value": f"`{res.get('order_id', 'N/A')}`", "inline": True},
    ]

    title = f"ALERTA CONGRESO: Orden Bracket Ejecutada — {ticker}"
    desc = f"Se detectó compra institucional de alta convicción reportada por {pol} y se envió orden de réplica a Alpaca."
    send_discord_embed(title, desc, fields, color=0x2ECC71)


def notify_overnight_entry(ticker: str, shares: int, price: float, inversion: float, conds_ok: list, order_id: str):
    """Notifica la entrada nocturna a las 3:50 PM ET."""
    fields = [
        {"name": "Activo", "value": f"**{ticker}**", "inline": True},
        {"name": "Acciones", "value": f"{shares} u.", "inline": True},
        {"name": "Precio Cierre Ref.", "value": f"${price:,.2f}", "inline": True},
        {"name": "Capital Asignado", "value": f"${inversion:,.2f}", "inline": True},
        {"name": "Condiciones Validadas", "value": "\n".join([f"• {c}" for c in conds_ok]), "inline": False},
        {"name": "ID de Orden Alpaca", "value": f"`{order_id}`", "inline": False},
    ]
    title = f"OVERNIGHT TRADER: Compra al Cierre Ejecutada — {ticker}"
    desc = "Condiciones de mercado óptimas validadas (SMA200 + RSI2 sobreventa + VIX bajo). Posición mantenida durante la noche."
    send_discord_embed(title, desc, fields, color=0xF1C40F)


def notify_overnight_exit(ticker: str, shares: int, exit_price: float, pnl_dollar: float, pnl_pct: float, order_id: str):
    """Notifica la liquidación en apertura a las 9:32 AM ET."""
    es_ganancia = pnl_dollar >= 0
    color = 0x2ECC71 if es_ganancia else 0xE74C3C
    resultado_str = f"+${pnl_dollar:,.2f} (+{pnl_pct:.2f}%)" if es_ganancia else f"-${abs(pnl_dollar):,.2f} ({pnl_pct:.2f}%)"

    fields = [
        {"name": "Activo Liquidado", "value": f"**{ticker}**", "inline": True},
        {"name": "Acciones", "value": f"{shares} u.", "inline": True},
        {"name": "Precio Apertura", "value": f"${exit_price:,.2f}", "inline": True},
        {"name": "Resultado P&L", "value": f"**{resultado_str}**", "inline": True},
        {"name": "ID de Orden Alpaca", "value": f"`{order_id}`", "inline": True},
    ]
    title = f"OVERNIGHT TRADER: Posición Liquidada — {resultado_str}"
    desc = f"Se cerró la posición nocturna al precio de apertura oficial. Capital 100% en liquidez."
    send_discord_embed(title, desc, fields, color=color)


def notify_test_connection():
    """Envía un mensaje de prueba inicial."""
    fields = [
        {"name": "Estado del Sistema", "value": "En línea y vinculado", "inline": True},
        {"name": "Canal", "value": "Alertas Cuantitativas", "inline": True},
        {"name": "Alpaca Paper Trading", "value": "Conectado ($100k USD)", "inline": True},
        {"name": "Módulos Activos", "value": "1. Bot Réplica Congreso (10:00 AM, 1:00 PM, 3:30 PM ET)\n2. Bot Overnight Drift (3:50 PM / 9:32 AM ET)", "inline": False},
    ]
    title = "SISTEMA CUANTITATIVO: Vinculación con Discord Exitosa"
    desc = "El terminal de notificaciones en tiempo real quedó conectado correctamente. Recibirás aquí cada compra, venta y resultado de ejecución."
    return send_discord_embed(title, desc, fields, color=0x3498DB)
