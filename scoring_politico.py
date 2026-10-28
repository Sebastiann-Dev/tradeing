"""
scoring_politico.py — Módulo 2 del Framework
Score 0-100 para TODAS las señales incluyendo:
  • Treasury Notes / Bonos (relevancia macro)
  • Compras pequeñas (informativas)
  • Cluster detection (>1 político mismo ticker)
  • Auto-cálculo de risk% recomendado por trade
"""

from typing import Dict, Any, Tuple

TICKER_SECTORS = {
    # Defensa
    "CACI": "DEFENSE", "LMT": "DEFENSE", "RTX": "DEFENSE",
    "GD": "DEFENSE", "NOC": "DEFENSE", "LHX": "DEFENSE",
    "KTOS": "DEFENSE", "PLTR": "DEFENSE",
    # Tecnología
    "NVDA": "TECHNOLOGY", "TSM": "TECHNOLOGY", "DDOG": "TECHNOLOGY",
    "MSFT": "TECHNOLOGY", "GOOGL": "TECHNOLOGY", "AAPL": "TECHNOLOGY",
    "META": "TECHNOLOGY", "AMZN": "TECHNOLOGY", "AMD": "TECHNOLOGY",
    "INTC": "TECHNOLOGY", "AVGO": "TECHNOLOGY", "SMCI": "TECHNOLOGY",
    # Energía
    "RIG": "ENERGY", "XOM": "ENERGY", "CVX": "ENERGY",
    "WMB": "ENERGY", "OXY": "ENERGY", "SLB": "ENERGY",
    "HAL": "ENERGY", "PSX": "ENERGY",
    # Salud
    "GH": "HEALTHCARE", "EL": "HEALTHCARE", "JNJ": "HEALTHCARE",
    "UNH": "HEALTHCARE", "PFE": "HEALTHCARE", "ABBV": "HEALTHCARE",
    "MRK": "HEALTHCARE", "ISRG": "HEALTHCARE",
    # Materiales
    "OLN": "MATERIALS", "FCX": "MATERIALS", "NEM": "MATERIALS",
    # Telecomunicaciones
    "NOK": "TELECOM", "T": "TELECOM", "VZ": "TELECOM",
    # Finanzas
    "JPM": "FINANCE", "GS": "FINANCE", "BAC": "FINANCE",
}

POLITICIAN_PROFILES = {
    "NANCY PELOSI": {
        "tier": "S", "win_rate": 0.72,
        "committees": ["LEADERSHIP"],
        "key_sectors": ["TECHNOLOGY"],
        "bonus_history": 25,
    },
    "DAN CRENSHAW": {
        "tier": "A", "win_rate": 0.68,
        "committees": ["ENERGY & COMMERCE"],
        "key_sectors": ["ENERGY", "HEALTHCARE"],
        "bonus_history": 22,
    },
    "LISA MCCLAIN": {
        "tier": "A", "win_rate": 0.66,
        "committees": ["ARMED SERVICES", "OVERSIGHT"],
        "key_sectors": ["DEFENSE"],
        "bonus_history": 22,
    },
    "MICHAEL MCCAUL": {
        "tier": "A", "win_rate": 0.65,
        "committees": ["FOREIGN AFFAIRS", "HOMELAND SECURITY"],
        "key_sectors": ["DEFENSE", "TECHNOLOGY"],
        "bonus_history": 20,
    },
    "TOMMY TUBERVILLE": {
        "tier": "A", "win_rate": 0.64,
        "committees": ["ARMED SERVICES", "AGRICULTURE"],
        "key_sectors": ["DEFENSE", "AGRICULTURE", "ENERGY"],
        "bonus_history": 20,
    },
    "LAUREL LEE": {
        "tier": "B", "win_rate": 0.60,
        "committees": ["JUDICIARY", "HOMELAND SECURITY"],
        "key_sectors": ["TECHNOLOGY", "DEFENSE"],
        "bonus_history": 15,
    },
    "JONATHAN JACKSON": {
        "tier": "B", "win_rate": 0.58,
        "committees": ["AGRICULTURE", "FOREIGN AFFAIRS"],
        "key_sectors": ["AGRICULTURE", "CONSUMER", "HEALTHCARE"],
        "bonus_history": 12,
    },
    "JOHN BOOZMAN": {
        "tier": "A", "win_rate": 0.63,
        "committees": ["AGRICULTURE", "APPROPRIATIONS", "FINANCE"],
        "key_sectors": ["FINANCE", "AGRICULTURE"],
        "bonus_history": 18,
    },
    "DARRELL ISSA": {
        "tier": "A", "win_rate": 0.61,
        "committees": ["JUDICIARY", "FOREIGN AFFAIRS", "FINANCE"],
        "key_sectors": ["TECHNOLOGY", "DEFENSE", "FINANCE"],
        "bonus_history": 18,
    },
    "JIM HIMES": {
        "tier": "A", "win_rate": 0.62,
        "committees": ["FINANCIAL SERVICES", "INTELLIGENCE"],
        "key_sectors": ["FINANCE", "TECHNOLOGY"],
        "bonus_history": 18,
    },
}

RISK_TABLE = {
    # (score_min, score_max): risk_pct
    (75, 100): 2.0,
    (60,  74): 1.5,
    (0,   59): 1.0,  # Mínimo garantizado del 1.0%
}


def recomendar_risk_pct(score: int, beta: float = 1.0) -> float:
    """
    Determina el % de riesgo por trade automáticamente:
    - Base / Mínimo: 1.0%
    - Score 60 a 74: 1.5%
    - Score >= 75: 2.0%
    Si beta > 1.5, reduce 0.5pp pero siempre respetando el piso mínimo de 1.0%.
    """
    if score >= 75:
        risk = 2.0
    elif score >= 60:
        risk = 1.5
    else:
        risk = 1.0

    if beta > 1.5:
        risk = max(1.0, risk - 0.5)

    return round(risk, 2)


class ScoringPolitico:
    def calcular_score(self, trade: Dict[str, Any]) -> Tuple[int, str, Dict[str, int]]:
        """
        Calcula score 0-100. Funciona para TODOS los tipos de señal.
        """
        pol_name  = trade.get("politician", "").upper()
        ticker    = trade.get("ticker", "").upper()
        amount    = trade.get("min_amount", 0.0)
        lag       = trade.get("lag_days") or 99
        sig_type  = trade.get("signal_type", "EQUITY_STRONG")

        desglose = {
            "historial_politico": 0,
            "conviccion_monto":   0,
            "frescura_lag":       0,
            "comite_relevante":   0,
        }

        # 1. Perfil del político
        profile = None
        for name, data in POLITICIAN_PROFILES.items():
            if name in pol_name:
                profile = data
                break
        desglose["historial_politico"] = profile["bonus_history"] if profile else 10

        # 2. Convicción por monto (aplica a todo tipo de señal)
        if amount >= 1_000_000:
            desglose["conviccion_monto"] = 20   # Mega trade (bonos millonarios)
        elif amount >= 200_000:
            desglose["conviccion_monto"] = 20
        elif amount >= 50_000:
            desglose["conviccion_monto"] = 14
        elif amount >= 15_000:
            desglose["conviccion_monto"] = 8
        elif amount >= 5_000:
            desglose["conviccion_monto"] = 4
        else:
            desglose["conviccion_monto"] = 1

        # 3. Frescura (lag)
        if lag <= 7:
            desglose["frescura_lag"] = 25
        elif lag <= 14:
            desglose["frescura_lag"] = 18
        elif lag <= 21:
            desglose["frescura_lag"] = 12
        elif lag <= 30:
            desglose["frescura_lag"] = 6
        else:
            desglose["frescura_lag"] = 0   # Señal caducada

        # 4. Comité vs Sector / Tipo de activo
        if sig_type == "MACRO_BOND":
            # Bonos del Tesoro: valor especial si hay comité de finanzas/fed
            key_finance_committees = ["FINANCIAL SERVICES", "FINANCE", "APPROPRIATIONS", "BANKING"]
            has_finance_committee = profile and any(
                c in " ".join(profile.get("committees", [])) for c in key_finance_committees
            )
            desglose["comite_relevante"] = 28 if has_finance_committee else 15
        else:
            ticker_sector = TICKER_SECTORS.get(ticker, "GENERAL")
            if profile and ticker_sector in profile.get("key_sectors", []):
                desglose["comite_relevante"] = 30  # Coincidencia directa comité–sector
            elif profile:
                desglose["comite_relevante"] = 15
            else:
                desglose["comite_relevante"] = 10

        total = min(100, max(0, sum(desglose.values())))

        # Clasificación
        if total >= 60:
            clasif = "FUERTE"
        elif total >= 45:
            clasif = "MODERADA"
        elif total >= 30:
            clasif = "BAJA"
        else:
            clasif = "DÉBIL"

        return total, clasif, desglose


def detectar_clusters(trades: list) -> Dict[str, list]:
    """
    Detecta tickers comprados por más de un político.
    Retorna dict: ticker -> [lista de políticos]
    """
    from collections import defaultdict
    ticker_pols = defaultdict(set)
    for t in trades:
        ticker = t.get("ticker", "")
        pol = t.get("politician", "")
        if ticker and pol:
            ticker_pols[ticker].add(pol)
    return {tk: list(pols) for tk, pols in ticker_pols.items() if len(pols) > 1}
