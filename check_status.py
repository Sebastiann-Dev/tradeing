from alpaca_executor import AlpacaExecutor

ex = AlpacaExecutor()
acc = ex.client.get_account()
print(f"Equity: ${float(acc.equity):,.2f}")
print(f"Cash: ${float(acc.cash):,.2f}")
print(f"Buying Power: ${float(acc.buying_power):,.2f}")

print("\n--- POSICIONES ACTIVAS ---")
for p in ex.client.get_all_positions():
    sym = p.symbol
    qty = p.qty
    entry = float(p.avg_entry_price)
    curr = float(p.current_price)
    val = float(p.market_value)
    pnl = float(p.unrealized_pl)
    pct = float(p.unrealized_plpc) * 100
    print(f"- {sym:5s}: {qty:>4} acc | Entrada: ${entry:>7.2f} | Actual: ${curr:>7.2f} | Valor: ${val:>10,.2f} | PnL: ${pnl:>+8.2f} ({pct:>+6.2f}%)")

print("\n--- ORDENES ABIERTAS (STOP LOSS Y TAKE PROFIT) ---")
for o in ex.client.get_orders():
    print(f"- {o.symbol:5s} | {o.side.value.upper():4s} {o.qty:>4} | Tipo: {o.order_type.value:6s} | Precio: {o.stop_price or o.limit_price or 'MKT'} | Status: {o.status.value}")
