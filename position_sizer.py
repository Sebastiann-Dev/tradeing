# -*- coding: utf-8 -*-
"""position_sizer.py — Auto-sizing + info rica de la accion"""

import yfinance as yf
from typing import Dict, Any, Optional
from config import Config
from scoring_politico import recomendar_risk_pct


class PositionSizer:
    def __init__(self, portfolio_equity: float):
        self.equity = portfolio_equity

    def obtener_metricas(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Descarga precio, ATR, Beta y datos fundamentales del ticker."""
        try:
            stock = yf.Ticker(ticker)
            hist  = stock.history(period="2mo")
            if hist.empty or len(hist) < 14:
                return None

            price = float(hist["Close"].iloc[-1])

            # ATR-14
            high, low, close = hist["High"], hist["Low"], hist["Close"]
            prev = close.shift(1)
            tr = (high - low).combine((high - prev).abs(), max).combine(
                (low - prev).abs(), max)
            atr = float(tr.rolling(14).mean().iloc[-1])

            # Info fundamental
            info = {}
            try:
                info = stock.info or {}
            except Exception:
                pass

            beta        = float(info.get("beta", 1.0) or 1.0)
            company     = info.get("longName") or info.get("shortName") or ticker
            sector      = info.get("sector", "N/A")
            industry    = info.get("industry", "N/A")
            market_cap  = info.get("marketCap")
            pe_ratio    = info.get("trailingPE")
            week52_high = info.get("fiftyTwoWeekHigh")
            week52_low  = info.get("fiftyTwoWeekLow")
            avg_vol     = info.get("averageDailyVolume10Day") or info.get("averageVolume")
            target_price = info.get("targetMeanPrice")
            description = info.get("longBusinessSummary", "")[:400] if info.get("longBusinessSummary") else ""
            dividend_yield = info.get("dividendYield")
            eps         = info.get("trailingEps")

            return {
                "current_price":  price,
                "atr":            atr,
                "beta":           beta,
                # fundamentales
                "company":        company,
                "sector":         sector,
                "industry":       industry,
                "market_cap":     market_cap,
                "pe_ratio":       pe_ratio,
                "week52_high":    week52_high,
                "week52_low":     week52_low,
                "avg_volume":     avg_vol,
                "target_price":   target_price,
                "description":    description,
                "dividend_yield": dividend_yield,
                "eps":            eps,
                # datos de precio historico para grafica
                "hist":           hist,
            }
        except Exception as e:
            print(f"[WARN] Metricas no disponibles para {ticker}: {e}")
            return None

    def calcular_posicion(
        self,
        ticker: str,
        signal_score: int,
        is_cluster: bool = False,
    ) -> Optional[Dict[str, Any]]:
        m = self.obtener_metricas(ticker)
        if not m:
            return None

        price = m["current_price"]
        atr   = m["atr"]
        beta  = m["beta"]

        # Auto risk% segun score + beta
        risk_pct = recomendar_risk_pct(signal_score, beta)
        if is_cluster:
            risk_pct = min(2.0, risk_pct + 0.5)
        dollar_risk = self.equity * (risk_pct / 100)

        # Stop Loss adaptado al ruido (ATR amplio)
        mult       = Config.ATR_MULTIPLIER_HIGH_BETA if beta > 1.5 else Config.ATR_MULTIPLIER_NORMAL
        stop_dist  = atr * mult
        stop_price = max(0.01, price - stop_dist)
        stop_pct   = round((stop_dist / price) * 100, 2)

        # Shares = riesgo / distancia al stop
        shares = max(1, int(dollar_risk / stop_dist))
        invest = shares * price

        # Cap 15% del portafolio
        cap = self.equity * Config.MAX_POSITION_PCT
        if invest > cap:
            shares = max(1, int(cap / price))
            invest = shares * price

        real_risk = shares * stop_dist
        tp1 = round(price * (1 + Config.TP1_PCT), 2)
        tp2 = round(price * (1 + Config.TP2_PCT), 2)

        # Costo minimo (1 accion)
        min_investment = round(price, 2)

        return {
            # Posicion
            "ticker":                   ticker,
            "entry_price":              round(price, 2),
            "stop_loss_price":          round(stop_price, 2),
            "stop_loss_distance":       round(stop_dist, 2),
            "stop_loss_pct":            stop_pct,
            "atr":                      round(atr, 2),
            "beta":                     round(beta, 2),
            "shares":                   shares,
            "total_investment":         round(invest, 2),
            "portfolio_allocation_pct": round((invest / self.equity) * 100, 2),
            "risk_dollar":              round(real_risk, 2),
            "risk_pct_portfolio":       round((real_risk / self.equity) * 100, 2),
            "risk_pct_used":            risk_pct,
            "is_cluster":               is_cluster,
            "tp1_price":                tp1,
            "tp2_price":                tp2,
            "min_investment":           min_investment,
            # Fundamentales
            "company":                  m.get("company", ticker),
            "sector":                   m.get("sector", "N/A"),
            "industry":                 m.get("industry", "N/A"),
            "market_cap":               m.get("market_cap"),
            "pe_ratio":                 m.get("pe_ratio"),
            "week52_high":              m.get("week52_high"),
            "week52_low":               m.get("week52_low"),
            "avg_volume":               m.get("avg_volume"),
            "target_price":             m.get("target_price"),
            "description":              m.get("description", ""),
            "dividend_yield":           m.get("dividend_yield"),
            "eps":                      m.get("eps"),
            "hist":                     m.get("hist"),
        }
