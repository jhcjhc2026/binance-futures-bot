# -*- coding: utf-8 -*-
"""
ETH Short Grid Bot - Live | Hedge Mode | Isolated
"""
import sys
import os
import time
import logging
import argparse

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import ccxt
from datetime import datetime, date
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from config import (
    API_KEY, API_SECRET, PROXY_URL, SYMBOL, LEVERAGE,
    GRID_LOWER, GRID_UPPER, GRID_COUNT, GRID_AMOUNT, MAX_HOLDING,
    MAX_DRAWDOWN_PCT, STOP_LOSS_PRICE, CHECK_INTERVAL, GRID_STEP
)

console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler("grid_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("grid")


class GridBot:
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
        if PROXY_URL:
            self.exchange.proxies = {"http": PROXY_URL, "https": PROXY_URL}

        try:
            self.exchange.load_time_difference()
            logger.info("Time sync done")
        except Exception as e:
            logger.warning(f"Time sync failed (non-critical): {e}")

        try:
            self.exchange.set_leverage(LEVERAGE, SYMBOL)
            logger.info(f"Leverage set: {LEVERAGE}x")
        except Exception as e:
            logger.warning(f"Set leverage failed (may already be set): {e}")

        try:
            self.exchange.set_margin_mode("isolated", SYMBOL)
            logger.info("Margin mode: isolated")
        except Exception as e:
            logger.warning(f"Margin mode may already be isolated: {e}")

        self.grid_levels = []
        for i in range(GRID_COUNT + 1):
            level = GRID_LOWER + i * GRID_STEP
            self.grid_levels.append(round(level, 2))
        logger.info(f"Grid levels: {self.grid_levels}")

        self.filled_grids = {}
        self.daily_start_balance = 0.0
        self.today = date.today()
        self.total_profit = 0.0
        self.trade_count = 0
        self.last_price = 0.0
        self.first_check = True
        self._sync_existing_position()
        self.last_price = self.get_price()

    def _sync_existing_position(self):
        try:
            positions = self.exchange.fetch_positions([SYMBOL])
            active = [p for p in positions if float(p.get("contracts", 0)) > 0 and p["side"] == "short"]
            if active:
                p = active[0]
                contracts = float(p["contracts"])
                entry_price = float(p["entryPrice"])
                logger.warning(f"Found existing ETH short: {contracts} ETH @ {entry_price}")
                logger.warning("Existing position merged with grid")
                grids_needed = round(contracts / GRID_AMOUNT)
                for i in range(min(grids_needed, MAX_HOLDING)):
                    closest = min(self.grid_levels, key=lambda x: abs(x - entry_price))
                    if closest not in self.filled_grids:
                        self.filled_grids[closest] = {
                            "amount": GRID_AMOUNT,
                            "entry_price": entry_price,
                            "time": datetime.now().strftime("%H:%M:%S"),
                        }
                    self.grid_levels = [g for g in self.grid_levels if g != closest]
                    self.grid_levels.append(closest)
                logger.info(f"Synced {len(self.filled_grids)} grid shorts")
            else:
                logger.info("No existing short position, starting fresh")
        except Exception as e:
            logger.error(f"Position sync failed: {e}")

    def get_price(self):
        ticker = self.exchange.fetch_ticker(SYMBOL)
        return ticker["last"]

    def get_balance(self):
        balance = self.exchange.fetch_balance({"type": "future"})
        usdt = balance.get("USDT", {})
        return {
            "total": float(usdt.get("total", 0)),
            "free": float(usdt.get("free", 0)),
            "used": float(usdt.get("used", 0)),
        }

    def get_position_info(self):
        positions = self.exchange.fetch_positions([SYMBOL])
        for p in positions:
            if float(p.get("contracts", 0)) > 0 and p["side"] == "short":
                return {
                    "size": float(p["contracts"]),
                    "entry": float(p["entryPrice"]),
                    "pnl": float(p["unrealizedPnl"]),
                    "margin": float(p["initialMargin"]),
                    "liquidation": float(p.get("liquidationPrice", 0)),
                }
        return None

    def open_short(self, grid_level):
        try:
            order = self.exchange.create_order(
                SYMBOL, "market", "sell", GRID_AMOUNT,
                params={"positionSide": "SHORT"}
            )
            self.filled_grids[grid_level] = {
                "amount": GRID_AMOUNT,
                "entry_price": grid_level,
                "time": datetime.now().strftime("%H:%M:%S"),
            }
            logger.info(f"Short opened @ grid {grid_level}: {GRID_AMOUNT} ETH")
            return True
        except Exception as e:
            logger.error(f"Open short failed @ {grid_level}: {e}")
            return False

    def close_short(self, grid_level):
        try:
            order = self.exchange.create_order(
                SYMBOL, "market", "buy", GRID_AMOUNT,
                params={"positionSide": "SHORT", "reduceOnly": True}
            )
            if grid_level in self.filled_grids:
                entry = self.filled_grids[grid_level]["entry_price"]
                exit_price = self.get_price()
                profit = (entry - exit_price) * GRID_AMOUNT
                self.total_profit += profit
                self.trade_count += 1
                logger.info(f"Short closed @ grid {grid_level}: entry={entry}, exit={exit_price:.2f}, profit={profit:+.4f}U")
                del self.filled_grids[grid_level]
            return True
        except Exception as e:
            logger.error(f"Close short failed @ {grid_level}: {e}")
            return False

    def close_all(self):
        logger.warning("Closing ALL short positions!")
        for grid_level in list(self.filled_grids.keys()):
            self.close_short(grid_level)

    def check_grid(self):
        price = self.get_price()

        if price <= 0:
            return "run"

        # Stop loss: price goes too high (above STOP_LOSS_PRICE)
        if price >= STOP_LOSS_PRICE:
            logger.warning(f"Price {price} hit stop loss {STOP_LOSS_PRICE}! Closing all shorts!")
            self.close_all()
            return "stop"

        # Max drawdown check
        balance = self.get_balance()
        if self.daily_start_balance > 0:
            drawdown = 1 - (balance["total"] / self.daily_start_balance)
            if drawdown >= MAX_DRAWDOWN_PCT:
                logger.warning(f"Drawdown {drawdown*100:.1f}% exceeded! Closing all!")
                self.close_all()
                return "stop"

        # Take profit: price drops below grid_level - step (close short for profit)
        for grid_level in list(self.filled_grids.keys()):
            take_profit_price = grid_level - GRID_STEP
            if price <= take_profit_price and self.last_price > take_profit_price:
                logger.info(f"Take profit triggered: {grid_level} -> {take_profit_price} (current {price:.2f})")
                self.close_short(grid_level)

        # Open short: price rises through grid level from below
        # Special: first check with no position, open immediately at nearest grid
        if self.first_check and len(self.filled_grids) == 0:
            nearest = max([g for g in self.grid_levels if g <= price], default=self.grid_levels[0])
            logger.info(f"Initial short: price {price:.2f}, opening @ grid {nearest}")
            self.open_short(nearest)
            self.first_check = False
        elif len(self.filled_grids) < MAX_HOLDING:
            for grid_level in self.grid_levels:
                if grid_level not in self.filled_grids:
                    if price >= grid_level and self.last_price < grid_level:
                        logger.info(f"Short grid triggered: price {price:.2f} crossed up grid {grid_level}")
                        self.open_short(grid_level)
                        break

        self.last_price = price
        return "run"

    def check_day_reset(self):
        today = date.today()
        if today != self.today:
            balance = self.get_balance()
            self.daily_start_balance = balance["total"]
            self.today = today
            logger.info(f"New day! Start balance: {self.daily_start_balance:.2f}U")

    def print_status(self):
        price = self.get_price()
        balance = self.get_balance()
        pos = self.get_position_info()

        table = Table(title="ETH Short Grid Bot", show_header=False, border_style="red")
        table.add_column("Item", style="cyan", width=16)
        table.add_column("Value", style="white", width=34)

        table.add_row("Symbol", SYMBOL)
        table.add_row("Price", f"{price:.2f} USDT")
        table.add_row("Leverage", f"{LEVERAGE}x | Isolated")
        table.add_row("Grid Range", f"{GRID_LOWER} - {GRID_UPPER} (step={GRID_STEP:.0f})")
        table.add_row("Free", f"{balance['free']:.2f} U")
        table.add_row("Total", f"{balance['total']:.2f} U")

        filled_count = len(self.filled_grids)
        table.add_row("Grids", f"{filled_count} / {MAX_HOLDING} filled")

        if pos:
            pnl_color = "green" if pos["pnl"] >= 0 else "red"
            table.add_row("Position", f"SHORT {pos['size']:.4f} ETH @ {pos['entry']:.2f}")
            table.add_row("PnL", f"[{pnl_color}]{pos['pnl']:+.4f} U[/{pnl_color}]")
            table.add_row("Liq. Price", f"{pos['liquidation']:.2f}")
        else:
            table.add_row("Position", "None (waiting)")

        table.add_row("Total Profit", f"{self.total_profit:+.4f} U ({self.trade_count} trades)")

        console.clear()
        console.print(table)
        console.print(f"[dim]Next check: {CHECK_INTERVAL}s | Ctrl+C to stop[/dim]")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="skip confirm")
    args = parser.parse_args()

    console.print(Panel.fit(
        f"[bold red]ETH Short Grid Bot[/bold red]\n"
        f"Symbol: {SYMBOL} | Leverage: {LEVERAGE}x | Isolated\n"
        f"Grid: {GRID_LOWER}-{GRID_UPPER} | {GRID_COUNT} grids | Step={GRID_STEP:.0f}U\n"
        f"Per grid: {GRID_AMOUNT} ETH | Max holding: {MAX_HOLDING}\n"
        f"Stop loss: {STOP_LOSS_PRICE}U (above grid = trend reversal)",
        border_style="red",
    ))

    if not args.yes:
        console.print("\n[bold red]LIVE MODE! Type YES to start:[/bold red]")
        confirm = input()
        if confirm != "YES":
            console.print("[yellow]Cancelled[/yellow]")
            return

    try:
        bot = GridBot()
    except Exception as e:
        console.print(f"[red]Connection failed: {e}[/red]")
        return

    balance = bot.get_balance()
    bot.daily_start_balance = balance["total"]
    console.print(f"\n[green]Bot started! Balance: {balance['total']:.2f}U[/green]\n")

    try:
        error_count = 0
        while True:
            try:
                bot.check_day_reset()
                result = bot.check_grid()
                bot.print_status()
                error_count = 0

                if result == "stop":
                    console.print("[red]Emergency stop! Cooling 10min...[/red]")
                    time.sleep(600)

            except Exception as e:
                error_count += 1
                logger.error(f"Loop error #{error_count}: {e}")
                if error_count <= 3:
                    logger.warning(f"Retry in 30s... (attempt {error_count}/3)")
                    time.sleep(30)
                else:
                    logger.warning("Too many errors, waiting 5min...")
                    time.sleep(300)

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by user[/yellow]")
        pos = bot.get_position_info()
        if pos:
            console.print(f"[yellow]Position still open: SHORT {pos['size']} ETH @ {pos['entry']:.2f}[/yellow]")
            console.print("[yellow]Check Binance app to manage.[/yellow]")
        console.print(f"[green]Total profit: {bot.total_profit:+.4f}U ({bot.trade_count} trades)[/green]")

    except Exception as e:
        logger.error(f"Runtime error: {e}", exc_info=True)
        console.print(f"[red]Error: {e}[/red]")
        console.print("[yellow]Check Binance app for positions![/yellow]")


if __name__ == "__main__":
    main()
