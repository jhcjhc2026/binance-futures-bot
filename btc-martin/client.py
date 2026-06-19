"""
币安合约客户端封装
"""
import ccxt
import time
import logging
from config import API_KEY, API_SECRET, PROXY_URL, SYMBOL, LEVERAGE

logger = logging.getLogger("martin")


class BinanceClient:
    def __init__(self):
        self.exchange = ccxt.binance({
            "apiKey": API_KEY,
            "secret": API_SECRET,
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
                "adjustForTimeDifference": True,
            },
        })

        # 设置代理
        if PROXY_URL:
            self.exchange.proxies = {"http": PROXY_URL, "https": PROXY_URL}

        # 设置杠杆
        try:
            self.exchange.set_leverage(LEVERAGE, SYMBOL)
            logger.info(f"杠杆设置: {LEVERAGE}x")
        except Exception as e:
            logger.warning(f"设置杠杆失败(可能已设置): {e}")

        # 验证连接
        try:
            balance = self.exchange.fetch_balance({"type": "future"})
            usdt = balance.get("USDT", {})
            free = usdt.get("free", 0)
            logger.info(f"连接成功! USDT可用余额: {free}")
        except Exception as e:
            logger.error(f"连接币安失败: {e}")
            raise

    def get_price(self):
        """获取当前价格"""
        ticker = self.exchange.fetch_ticker(SYMBOL)
        return ticker["last"]

    def get_usdt_balance(self):
        """获取USDT余额"""
        balance = self.exchange.fetch_balance({"type": "future"})
        usdt = balance.get("USDT", {})
        return {
            "total": float(usdt.get("total", 0)),
            "free": float(usdt.get("free", 0)),
            "used": float(usdt.get("used", 0)),
        }

    def get_positions(self):
        """获取当前持仓"""
        positions = self.exchange.fetch_positions([SYMBOL])
        active = []
        for p in positions:
            contracts = float(p.get("contracts", 0))
            if contracts > 0:
                active.append({
                    "side": p["side"],           # long / short
                    "contracts": contracts,
                    "entry_price": float(p["entryPrice"]),
                    "notional": float(p["notional"]),
                    "unrealized_pnl": float(p["unrealizedPnl"]),
                    "liquidation_price": float(p.get("liquidationPrice", 0)),
                    "margin": float(p["initialMargin"]),
                })
        return active

    def open_long(self, margin):
        """开多单"""
        price = self.get_price()
        amount = (margin * LEVERAGE) / price
        amount = self._round_amount(amount)
        logger.info(f"开多: 保证金={margin}U, 数量={amount}, 价格≈{price}")
        order = self.exchange.create_market_buy_order(SYMBOL, amount, {"reduceOnly": False})
        return order

    def open_short(self, margin):
        """开空单"""
        price = self.get_price()
        amount = (margin * LEVERAGE) / price
        amount = self._round_amount(amount)
        logger.info(f"开空: 保证金={margin}U, 数量={amount}, 价格≈{price}")
        order = self.exchange.create_market_sell_order(SYMBOL, amount, {"reduceOnly": False})
        return order

    def close_position(self, side="long"):
        """平仓"""
        positions = self.get_positions()
        for p in positions:
            if p["side"] == side:
                amount = p["contracts"]
                logger.info(f"平仓: {side} 数量={amount}")
                if side == "long":
                    self.exchange.create_market_sell_order(SYMBOL, amount, {"reduceOnly": True})
                else:
                    self.exchange.create_market_buy_order(SYMBOL, amount, {"reduceOnly": True})
                return True
        return False

    def close_all_positions(self):
        """平掉所有仓位"""
        positions = self.get_positions()
        for p in positions:
            amount = p["contracts"]
            side = p["side"]
            logger.info(f"平仓: {side} 数量={amount}")
            if side == "long":
                self.exchange.create_market_sell_order(SYMBOL, amount, {"reduceOnly": True})
            else:
                self.exchange.create_market_buy_order(SYMBOL, amount, {"reduceOnly": True})
        return len(positions) > 0

    def _round_amount(self, amount):
        """按交易对精度取整 - BTC最小0.001"""
        step = 0.001
        return max(step, round(amount / step) * step)
