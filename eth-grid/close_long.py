# -*- coding: utf-8 -*-
"""Close ETH long position - utility script for position management"""
import os
import sys
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import ccxt
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
PROXY_URL = os.getenv("PROXY_URL", "")
SYMBOL = "ETH/USDT:USDT"

exchange = ccxt.binance({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "enableRateLimit": True,
    "options": {"defaultType": "future", "adjustForTimeDifference": True},
})
if PROXY_URL:
    exchange.proxies = {"http": PROXY_URL, "https": PROXY_URL}

exchange.load_time_difference()

# Check existing long position
positions = exchange.fetch_positions([SYMBOL])
long_pos = [p for p in positions if float(p.get("contracts", 0)) > 0 and p["side"] == "long"]

if long_pos:
    p = long_pos[0]
    size = float(p["contracts"])
    entry = float(p["entryPrice"])
    pnl = float(p["unrealizedPnl"])
    print(f"Found LONG: {size} ETH @ {entry}, PnL: {pnl:+.4f}U")

    # Close long: sell with positionSide=LONG
    order = exchange.create_order(
        SYMBOL, "market", "sell", size,
        params={"positionSide": "LONG"}
    )
    print(f"Long position closed! Order ID: {order['id']}")
else:
    print("No long position found.")

# Verify
positions2 = exchange.fetch_positions([SYMBOL])
long2 = [p for p in positions2 if float(p.get("contracts", 0)) > 0 and p["side"] == "long"]
if not long2:
    print("Confirmed: No long position remaining.")
else:
    print(f"WARNING: Long position still exists: {long2[0]}")
