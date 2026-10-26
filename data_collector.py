"""
data_collector.py
Módulo para consultar las operaciones de congresistas de EE.UU.
Extrae datos en tiempo real directamente de Capitol Trades.
"""

import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Any, Optional

CAPITOL_TRADES_BASE_URL = "https://www.capitoltrades.com/trades"

class DataCollector:
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

    def fetch_page_trades(self, page: int = 1) -> List[Dict[str, Any]]:
        """Extrae las operaciones de una página de Capitol Trades."""
        url = f"{CAPITOL_TRADES_BASE_URL}?page={page}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            
            table = soup.find("table")
            if not table:
                return []

            rows = table.find_all("tr")[1:] # omit header
            parsed_trades = []

            for row in rows:
                tds = row.find_all("td")
                if len(tds) < 8:
                    continue

                # 1. Politician info
                pol_elem = tds[0].find("h2", class_="politician-name")
                politician_name = pol_elem.get_text(strip=True) if pol_elem else ""

                party_elem = tds[0].find("span", class_=lambda c: c and "party" in c)
                party = party_elem.get_text(strip=True) if party_elem else ""

                chamber_elem = tds[0].find("span", class_=lambda c: c and "chamber" in c)
                chamber = chamber_elem.get_text(strip=True) if chamber_elem else ""

                state_elem = tds[0].find("span", class_=lambda c: c and "us-state-compact" in c)
                state = state_elem.get_text(strip=True) if state_elem else ""

                # 2. Issuer & Ticker
                issuer_elem = tds[1].find("h3", class_="issuer-name")
                issuer_name = issuer_elem.get_text(strip=True) if issuer_elem else ""

                ticker_elem = tds[1].find("span", class_="issuer-ticker")
                raw_ticker = ticker_elem.get_text(strip=True) if ticker_elem else ""
                clean_ticker = raw_ticker.split(":")[0].strip().upper() if ":" in raw_ticker else raw_ticker.strip().upper()

                # 3. Dates
                pub_date = tds[2].get_text(strip=True)
                trade_date = tds[3].get_text(strip=True)

                # 4. Lag (Filed After)
                gap_elem = tds[4].find("div", class_=lambda c: c and "cell--reporting-gap" in c)
                lag_text = gap_elem.find("div", class_="q-value").get_text(strip=True) if gap_elem else ""
                lag_days = None
                nums = re.findall(r"\d+", lag_text)
                if nums:
                    lag_days = int(nums[0])

                # 5. Type (buy/sell)
                type_elem = tds[6].find("span", class_=lambda c: c and "tx-type" in c)
                tx_type = type_elem.get_text(strip=True).lower() if type_elem else tds[6].get_text(strip=True).lower()

                # 6. Size
                size_elem = tds[7].find("span", class_=lambda c: c and "trade-size" in c)
                size_text = size_elem.get_text(strip=True) if size_elem else tds[7].get_text(strip=True)

                # 7. Price
                price_text = tds[8].get_text(strip=True) if len(tds) > 8 else "N/A"

                parsed_trades.append({
                    "politician": politician_name,
                    "party": party,
                    "chamber": chamber,
                    "state": state,
                    "ticker": clean_ticker,
                    "issuer_name": issuer_name,
                    "transaction_type": tx_type,
                    "transaction_date": trade_date,
                    "disclosure_date": pub_date,
                    "lag_days": lag_days,
                    "amount_range": size_text,
                    "price_reported": price_text
                })

            return parsed_trades
        except Exception as e:
            print(f"[ERROR] Error al consultar Capitol Trades pág {page}: {e}")
            return []

    def fetch_all_recent_trades(self, max_pages: int = 5) -> List[Dict[str, Any]]:
        """Recolecta operaciones recientes de las primeras N páginas."""
        all_trades = []
        print(f"[INFO] Descargando trades recientes de Capitol Trades ({max_pages} páginas)...")
        for p in range(1, max_pages + 1):
            trades = self.fetch_page_trades(p)
            if not trades:
                break
            all_trades.extend(trades)
        print(f"[INFO] Total recolectado: {len(all_trades)} transacciones.")
        return all_trades
