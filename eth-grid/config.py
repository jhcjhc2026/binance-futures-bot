# -*- coding: utf-8 -*-
"""
ETH Short Grid Strategy Config
"""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ============ API ============
API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
PROXY_URL = os.getenv("PROXY_URL", "")

# ============ Trading ============
SYMBOL = "ETH/USDT:USDT"
LEVERAGE = 10

# ============ Grid ============
GRID_LOWER = 1680
GRID_UPPER = 1800
GRID_COUNT = 8
GRID_AMOUNT = 0.05
MAX_HOLDING = 5

# ============ Risk ============
MAX_DRAWDOWN_PCT = 0.15
STOP_LOSS_PRICE = 1850      # Short stop loss: price above grid range

# ============ Runtime ============
CHECK_INTERVAL = 10

# ============ Auto ============
GRID_STEP = (GRID_UPPER - GRID_LOWER) / GRID_COUNT  # 15U per grid
