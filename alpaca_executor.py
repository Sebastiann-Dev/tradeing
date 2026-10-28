"""
alpaca_executor.py
Módulo 4 y 5 del Framework: Ejecución y Gestión de Órdenes en Alpaca
Soporta Paper Trading y Live Trading con órdenes bracket automáticas (Take Profit y Stop Loss).
"""

from typing import Dict, Any, Optional
from config import Config

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, StopLossRequest, TakeProfitRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
except ImportError:
    TradingClient = None

class AlpacaExecutor:
    def __init__(self, api_key: str = None, secret_key: str = None, paper: bool = True):
        self.api_key = api_key or Config.ALPACA_API_KEY
        self.secret_key = secret_key or Config.ALPACA_SECRET_KEY
        self.paper = paper
        self.client = None

        if self.api_key and self.secret_key and TradingClient:
            try:
                self.client = TradingClient(self.api_key, self.secret_key, paper=self.paper)
                print(f"[INFO] Conectado a Alpaca ({'Paper' if self.paper else 'Live'}).")
            except Exception as e:
                print(f"[WARN] Error al conectar con Alpaca: {e}")
        else:
            print("[INFO] Modo SIMULACIÓN LOCAL activo (configura tus llaves en .env para Alpaca Paper).")

    def get_portfolio_equity(self, default_virtual: float = 10000.0) -> float:
        """Devuelve el equity fijado para dimensionamiento (o el de Alpaca si no está configurado)."""
        if getattr(Config, "PORTFOLIO_EQUITY", 0) > 0:
            return float(Config.PORTFOLIO_EQUITY)
        if self.client:
            try:
                account = self.client.get_account()
                return float(account.equity)
            except Exception as e:
                print(f"[WARN] No se pudo leer equity de Alpaca: {e}")
        return default_virtual

    def get_open_positions_count(self) -> int:
        """Obtiene la cantidad de posiciones abiertas actualmente."""
        if self.client:
            try:
                positions = self.client.get_all_positions()
                return len(positions)
            except Exception as e:
                print(f"[WARN] Error al consultar posiciones: {e}")
        return 0

    def get_open_tickers(self) -> set:
        """Devuelve el conjunto de símbolos que ya tienen posición o orden abierta en Alpaca."""
        open_set = set()
        if self.client:
            try:
                positions = self.client.get_all_positions()
                for p in positions:
                    open_set.add(p.symbol)
            except Exception as e:
                print(f"[WARN] Error al consultar posiciones abiertas: {e}")
            try:
                from alpaca.trading.requests import GetOrdersRequest
                from alpaca.trading.enums import QueryOrderStatus
                req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
                orders = self.client.get_orders(filter=req)
                for o in orders:
                    open_set.add(o.symbol)
            except Exception as e:
                print(f"[WARN] Error al consultar órdenes abiertas: {e}")
        return open_set

    def execute_bracket_order(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta la compra con Stop Loss y Take Profit integrados (Bracket Order).
        """
        ticker = plan["ticker"]
        shares = plan["shares"]
        stop_loss_price = plan["stop_loss_price"]
        tp_price = plan["tp1_price"]

        if not self.client:
            # Simulación local registrada
            print(f"\n[SIMULACIÓN DE ORDEN BRACKET]")
            print(f"  Ticker:        {ticker}")
            print(f"  Acciones:      {shares} u.")
            print(f"  Precio Aprox:  ${plan['entry_price']}")
            print(f"  Inversión:     ${plan['total_investment']:,.2f} ({plan['portfolio_allocation_pct']}% del portafolio)")
            print(f"  Stop Loss:     ${stop_loss_price} (-{plan['stop_loss_pct']}%)")
            print(f"  Take Profit 1: ${tp_price} (+{Config.TP1_PCT*100}%)")
            print(f"  Riesgo Total:  ${plan['risk_dollar']:,.2f} ({plan['risk_pct_portfolio']}% del capital)")
            return {
                "status": "SIMULATED_SUCCESS",
                "ticker": ticker,
                "shares": shares,
                "plan": plan
            }

        try:
            # Creación de orden Bracket real en Alpaca
            order_data = MarketOrderRequest(
                symbol=ticker,
                qty=shares,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=tp_price),
                stop_loss=StopLossRequest(stop_price=stop_loss_price)
            )
            order = self.client.submit_order(order_data=order_data)
            print(f"[SUCCESS] Orden Bracket enviada a Alpaca ID: {order.id}")
            return {
                "status": "SUBMITTED",
                "order_id": str(order.id),
                "ticker": ticker,
                "shares": shares
            }
        except Exception as e:
            print(f"[ERROR] Error al enviar orden a Alpaca para {ticker}: {e}")
            return {
                "status": "FAILED",
                "error": str(e)
            }
