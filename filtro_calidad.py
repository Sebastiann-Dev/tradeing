"""
filtro_calidad.py — Módulo 1 del Framework
Ya NO descarta Treasury Notes ni montos pequeños de forma dura.
En su lugar clasifica cada trade con un TIPO de señal:
  EQUITY_STRONG → acción >= $15k, lag <= 30 días, compra → OPERABLE
  EQUITY_SMALL  → acción < $15k, compra             → INFORMATIVA (visible)
  MACRO_BOND    → bonos / Tesoro / ETF renta fija   → MACRO SIGNAL (visible)
  STALE         → lag > 30 días                     → CADUCADA (filtro opcional)
  SELL          → venta                             → SALIDA (visible)
"""

import re
from typing import Dict, Any, Tuple
from config import Config

BOND_KEYWORDS = {
    "TREASURY", "T-NOTE", "T-BOND", "T-BILL", "GOVT", "BOND",
    "MUNICIPAL", "MBS", "IEF", "TLH", "BND", "AGG", "SGOV",
    "CMBS", "JMBS", "MBB", "XTWO", "GIGB", "XFIV", "SPYM"
}
GENERIC_INDEX_ETFS = {"SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "VEA", "EFA"}


def parse_size_to_amount(size_str: str) -> float:
    """Convierte '1K-15K', '50K-100K', '1M-5M' al extremo inferior en dólares."""
    if not size_str:
        return 0.0
    cleaned = size_str.upper().replace("$", "").replace(",", "").strip()
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*([KM])?", cleaned)
    if not matches:
        return 0.0
    num_str, mult = matches[0]
    val = float(num_str)
    if mult == "K":
        return val * 1_000
    elif mult == "M":
        return val * 1_000_000
    return val if val >= 1000 else val * 1_000


def is_bond_instrument(ticker: str, description: str) -> bool:
    ticker_up = ticker.upper()
    desc_up = (description or "").upper()
    if ticker_up in BOND_KEYWORDS:
        return True
    for kw in BOND_KEYWORDS:
        if kw in desc_up:
            return True
    return False


class FiltroCalidad:
    def __init__(self):
        self.max_lag = Config.MAX_LAG_DAYS
        self.min_amount = Config.MIN_TRANSACTION_AMOUNT

    def clasificar(self, trade: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
        """
        Clasifica el trade en un TIPO y retorna (tipo, motivo, trade_enriquecido).
        Tipos: EQUITY_STRONG | EQUITY_SMALL | MACRO_BOND | STALE | SELL | INDEX_ETF | INVALID
        """
        ticker = trade.get("ticker", "").strip().upper()
        desc = trade.get("asset_description", "") or trade.get("issuer_name", "")
        t_type = trade.get("transaction_type", "").lower()
        lag = trade.get("lag_days")
        amount = parse_size_to_amount(trade.get("amount_range", ""))
        trade["min_amount"] = amount

        # Ticker inválido / vacío
        if not ticker or ticker in {"--", "N/A", ""}:
            # Para bonos sin ticker, usar descripción
            if is_bond_instrument("", desc):
                trade["signal_type"] = "MACRO_BOND"
                return "MACRO_BOND", "Instrumento de deuda / Tesoro (sin ticker)", trade
            return "INVALID", "Ticker vacío o desconocido", trade

        # Venta
        if "sell" in t_type or "sale" in t_type:
            trade["signal_type"] = "SELL"
            return "SELL", f"Venta de {ticker}", trade

        # ETF de índice genérico
        if ticker in GENERIC_INDEX_ETFS:
            trade["signal_type"] = "INDEX_ETF"
            return "INDEX_ETF", f"ETF de índice genérico ({ticker}), sin ventaja informacional", trade

        # Instrumento de deuda / Tesoro
        if is_bond_instrument(ticker, desc):
            trade["signal_type"] = "MACRO_BOND"
            return "MACRO_BOND", f"Instrumento de renta fija/Tesoro ({ticker})", trade

        # Compra de acción individual
        # ¿Caducada?
        if lag is not None and lag > self.max_lag:
            trade["signal_type"] = "STALE"
            return "STALE", f"Lag de {lag} días > {self.max_lag} días límite", trade

        # ¿Pequeña pero válida?
        if amount < self.min_amount:
            trade["signal_type"] = "EQUITY_SMALL"
            return "EQUITY_SMALL", f"Compra pequeña (${amount:,.0f} < ${self.min_amount:,.0f}) — informativa", trade

        # ¡Señal fuerte operable!
        trade["signal_type"] = "EQUITY_STRONG"
        return "EQUITY_STRONG", "Señal operable: compra directa, monto y lag válidos", trade
