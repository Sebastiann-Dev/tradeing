import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Broker Config
    ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
    ALPACA_PAPER = os.getenv("ALPACA_PAPER", "True").lower() in ("true", "1")

    # Risk Management Config (Basado en el Framework)
    MAX_RISK_PER_TRADE = float(os.getenv("MAX_RISK_PER_TRADE", 0.01))     # 1%
    HIGH_CONVICTION_RISK = 0.015                                          # 1.5% cuando coinciden comités
    MAX_POSITION_PCT = float(os.getenv("MAX_POSITION_PCT", 0.15))         # 15% Cap
    MAX_SECTOR_PCT = float(os.getenv("MAX_SECTOR_PCT", 0.35))             # 35% Cap
    MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", 10))

    # Signal Filtering Config
    MAX_LAG_DAYS = int(os.getenv("MAX_LAG_DAYS", 30))                     # Max 30 días de retraso
    MIN_TRANSACTION_AMOUNT = float(os.getenv("MIN_TRANSACTION_AMOUNT", 15000)) # $15,000

    # Stop Loss & Take Profit
    ATR_PERIOD = 14
    ATR_MULTIPLIER_NORMAL = float(os.getenv("ATR_MULTIPLIER_NORMAL", 2.5))
    ATR_MULTIPLIER_HIGH_BETA = float(os.getenv("ATR_MULTIPLIER_HIGH_BETA", 3.0))
    TRAILING_STOP_TRIGGER_PCT = 0.15                                      # Mover a breakeven tras +15%
    TIME_STOP_DAYS = 45                                                   # Cerrar tras 45 días sin avance

    # Take Profit Escalonado
    TP1_PCT = 0.15                                                        # Cerrar 33% al +15%
    TP2_PCT = 0.30                                                        # Cerrar 33% al +30%
