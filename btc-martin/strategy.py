"""
马丁策略核心引擎
"""
import logging
import time
from datetime import datetime, date
from config import (
    INITIAL_MARGIN, MARTIN_MULTIPLIER, MAX_MARTIN_ROUNDS,
    LOSS_TRIGGER_PCT, TAKE_PROFIT_PCT, MAX_LOSS_PCT,
    MAX_POSITION_MARGIN, DAILY_LOSS_LIMIT, POSITION_SIDE
)

logger = logging.getLogger("martin")


class MartinEngine:
    def __init__(self, client, dry_run=False):
        self.client = client
        self.dry_run = dry_run

        # 状态
        self.rounds = 0              # 当前补仓次数
        self.entry_price = 0.0       # 首次开仓价格
        self.total_margin = 0.0      # 累计保证金
        self.side = "long"           # 当前方向
        self.running = True
        self.daily_start_balance = 0.0
        self.today = date.today()

    def initialize(self):
        """初始化 - 检查现有持仓"""
        balance = self.client.get_usdt_balance()
        self.daily_start_balance = balance["total"]
        logger.info(f"初始余额: {balance['total']}U")

        # 检查是否已有持仓
        positions = self.client.get_positions()
        if positions:
            p = positions[0]
            self.side = p["side"]
            self.entry_price = p["entry_price"]
            self.total_margin = p["margin"]
            self.rounds = 1  # 已有持仓算1轮
            logger.warning(f"发现已有持仓: {self.side} 入场价={self.entry_price} 保证金={self.total_margin}")
        else:
            logger.info("无持仓，等待开仓信号")

        return balance

    def should_open(self):
        """判断是否应该开仓"""
        if self.rounds > 0:
            return False  # 已有仓位不重复开
        return True

    def open_initial(self):
        """首次开仓"""
        margin = INITIAL_MARGIN
        logger.info(f"🎯 首次开仓: 方向={self.side} 保证金={margin}U")

        if self.dry_run:
            self.entry_price = self.client.get_price()
            self.total_margin = margin
            self.rounds = 1
            logger.info(f"[模拟] 开仓成功 价格={self.entry_price}")
            return

        if self.side == "long":
            self.client.open_long(margin)
        else:
            self.client.open_short(margin)

        time.sleep(1)
        positions = self.client.get_positions()
        if positions:
            p = positions[0]
            self.entry_price = p["entry_price"]
            self.total_margin = p["margin"]
            self.rounds = 1
            logger.info(f"✅ 开仓成功 价格={self.entry_price} 保证金={self.total_margin}U")

    def check_position(self):
        """检查当前持仓状态，返回动作: hold/add/close/stop"""
        if self.rounds == 0:
            return "open"

        positions = self.client.get_positions()
        if not positions:
            # 仓位已不存在（可能被强平）
            logger.warning("⚠️ 仓位消失! 可能已被强平!")
            self._reset()
            return "stop"

        p = positions[0]
        current_price = self.client.get_price()
        entry = p["entry_price"]
        pnl_pct = p["unrealized_pnl"] / (p["notional"] / 10)  # 近似盈亏比

        # 计算价格变动百分比
        if self.side == "long":
            price_change_pct = (current_price - entry) / entry
        else:
            price_change_pct = (entry - current_price) / entry

        # 1. 止盈检查
        if price_change_pct >= TAKE_PROFIT_PCT:
            logger.info(f"💰 触发止盈! 盈利={price_change_pct*100:.2f}%")
            return "close"

        # 2. 硬止损检查 - 亏损占总资金比例
        balance = self.client.get_usdt_balance()
        total_loss_pct = 1 - (balance["total"] / self.daily_start_balance) if self.daily_start_balance > 0 else 0
        if total_loss_pct >= MAX_LOSS_PCT:
            logger.warning(f"🛑 触发硬止损! 总亏损={total_loss_pct*100:.1f}%")
            return "stop"

        # 3. 单日亏损限制
        if total_loss_pct >= DAILY_LOSS_LIMIT:
            logger.warning(f"🛑 触发日亏损限制! 今日亏损={total_loss_pct*100:.1f}%")
            return "stop"

        # 4. 补仓检查
        if price_change_pct <= -LOSS_TRIGGER_PCT and self.rounds < MAX_MARTIN_ROUNDS:
            next_margin = INITIAL_MARGIN * (MARTIN_MULTIPLIER ** self.rounds)
            if self.total_margin + next_margin > MAX_POSITION_MARGIN:
                logger.warning(f"⚠️ 保证金超限! 总保证金将达{self.total_margin + next_margin:.1f}U，不补仓")
                return "hold"
            logger.info(f"📉 触发补仓! 亏损={price_change_pct*100:.2f}% 第{self.rounds+1}轮 保证金={next_margin:.1f}U")
            return "add"

        # 5. 已达最大补仓次数，仍然亏损 → 止损
        if price_change_pct <= -LOSS_TRIGGER_PCT and self.rounds >= MAX_MARTIN_ROUNDS:
            logger.warning(f"🛑 已达最大补仓次数({MAX_MARTIN_ROUNDS})且仍亏损，止损!")
            return "stop"

        return "hold"

    def add_position(self):
        """补仓"""
        next_margin = INITIAL_MARGIN * (MARTIN_MULTIPLIER ** self.rounds)
        self.rounds += 1

        logger.info(f"🔄 第{self.rounds}轮补仓: 保证金={next_margin:.1f}U")

        if self.dry_run:
            self.total_margin += next_margin
            logger.info(f"[模拟] 补仓成功 累计保证金={self.total_margin:.1f}U")
            return

        if self.side == "long":
            self.client.open_long(next_margin)
        else:
            self.client.open_short(next_margin)

        time.sleep(1)
        positions = self.client.get_positions()
        if positions:
            self.total_margin = positions[0]["margin"]

    def close_position(self):
        """止盈平仓"""
        logger.info(f"💰 止盈平仓! 轮次={self.rounds} 累计保证金={self.total_margin:.1f}U")

        if self.dry_run:
            self._reset()
            return

        self.client.close_all_positions()
        time.sleep(1)
        self._reset()

    def emergency_close(self):
        """紧急止损平仓"""
        logger.warning(f"🛑 紧急止损! 轮次={self.rounds} 累计保证金={self.total_margin:.1f}U")

        if self.dry_run:
            self._reset()
            return

        self.client.close_all_positions()
        time.sleep(1)
        self._reset()

    def _reset(self):
        """重置状态"""
        self.rounds = 0
        self.entry_price = 0.0
        self.total_margin = 0.0

    def check_day_reset(self):
        """每日重置检查"""
        today = date.today()
        if today != self.today:
            balance = self.client.get_usdt_balance()
            self.daily_start_balance = balance["total"]
            self.today = today
            logger.info(f"📅 新的一天! 起始余额: {self.daily_start_balance}U")

    def get_status(self):
        """获取当前状态摘要"""
        balance = self.client.get_usdt_balance()
        positions = self.client.get_positions()
        price = self.client.get_price()

        return {
            "price": price,
            "balance": balance,
            "positions": positions,
            "rounds": self.rounds,
            "total_margin": self.total_margin,
            "side": self.side,
            "dry_run": self.dry_run,
        }
