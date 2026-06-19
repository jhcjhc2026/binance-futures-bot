"""
主程序 - 币安U本位合约马丁策略机器人
"""
import sys
import time
import logging
import winsound
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live

from config import (
    CHECK_INTERVAL, DRY_RUN, ENABLE_CONSOLE_LOG, ENABLE_SOUND_ALERT,
    POSITION_SIDE, INITIAL_MARGIN, MARTIN_MULTIPLIER, MAX_MARTIN_ROUNDS,
    LOSS_TRIGGER_PCT, TAKE_PROFIT_PCT, MAX_LOSS_PCT, SYMBOL, LEVERAGE
)
from client import BinanceClient
from strategy import MartinEngine

console = Console()

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler("martin_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("martin")


def alert_sound():
    """止损/异常告警音"""
    if ENABLE_SOUND_ALERT:
        try:
            winsound.Beep(800, 300)
            winsound.Beep(1000, 300)
            winsound.Beep(1200, 500)
        except Exception:
            pass


def print_status(engine):
    """打印当前状态面板"""
    status = engine.get_status()
    balance = status["balance"]
    positions = status["positions"]

    # 状态面板
    table = Table(title="🤖 马丁策略机器人", show_header=False, border_style="blue")
    table.add_column("项目", style="cyan", width=16)
    table.add_column("值", style="white", width=30)

    table.add_row("交易对", SYMBOL)
    table.add_row("当前价格", f"{status['price']:.2f} USDT")
    table.add_row("杠杆", f"{LEVERAGE}x")
    table.add_row("可用余额", f"{balance['free']:.2f} U")
    table.add_row("总资产", f"{balance['total']:.2f} U")
    table.add_row("补仓轮次", f"{status['rounds']} / {MAX_MARTIN_ROUNDS}")
    table.add_row("累计保证金", f"{status['total_margin']:.2f} U")
    table.add_row("模式", "🧪 模拟" if DRY_RUN else "🔴 实盘")

    if positions:
        p = positions[0]
        pnl_color = "green" if p["unrealized_pnl"] >= 0 else "red"
        table.add_row("持仓方向", "做多 📈" if p["side"] == "long" else "做空 📉")
        table.add_row("入场价", f"{p['entry_price']:.2f}")
        table.add_row("未实现盈亏", f"[{pnl_color}]{p['unrealized_pnl']:.4f} U[/{pnl_color}]")
        table.add_row("强平价", f"[red]{p['liquidation_price']:.2f}[/red]")
    else:
        table.add_row("持仓", "无仓位，等待开仓")

    console.clear()
    console.print(table)
    console.print(f"[dim]下次检查: {CHECK_INTERVAL}秒后 | Ctrl+C 停止[/dim]")


def main():
    console.print(Panel.fit(
        "[bold yellow]🤖 币安合约马丁策略机器人[/bold yellow]\n"
        f"交易对: {SYMBOL} | 杠杆: {LEVERAGE}x | 模式: {'模拟' if DRY_RUN else '实盘'}\n"
        f"首仓: {INITIAL_MARGIN}U | 补仓倍数: {MARTIN_MULTIPLIER}x | 最多补仓: {MAX_MARTIN_ROUNDS}轮\n"
        f"补仓触发: -{LOSS_TRIGGER_PCT*100}% | 止盈: +{TAKE_PROFIT_PCT*100}% | 硬止损: -{MAX_LOSS_PCT*100}%",
        border_style="yellow",
    ))

    # 安全确认
    if not DRY_RUN:
        console.print("\n[bold red]⚠️ 实盘模式! 请确认:[/bold red]")
        console.print("1. API Key已正确配置(.env文件)")
        console.print("2. 已理解马丁策略风险")
        console.print("3. 止损参数已设置合理")
        confirm = input("\n输入 YES 确认启动实盘: ")
        if confirm != "YES":
            console.print("[yellow]已取消[/yellow]")
            return

    # 初始化
    try:
        client = BinanceClient()
    except Exception as e:
        console.print(f"[red]❌ 连接币安失败: {e}[/red]")
        console.print("[yellow]请检查: 1)API Key是否正确 2)是否需要配置代理 3)网络是否正常[/yellow]")
        return

    engine = MartinEngine(client, dry_run=DRY_RUN)
    engine.side = POSITION_SIDE.lower()
    engine.initialize()

    console.print("\n[green]✅ 机器人启动成功! 开始运行...[/green]\n")

    # 主循环
    try:
        while engine.running:
            engine.check_day_reset()

            action = engine.check_position()

            if action == "open":
                engine.open_initial()
            elif action == "add":
                engine.add_position()
            elif action == "close":
                engine.close_position()
                console.print("[green]💰 止盈成功! 等待下一次开仓机会...[/green]")
            elif action == "stop":
                alert_sound()
                engine.emergency_close()
                console.print("[red]🛑 已止损! 冷却10分钟后继续...[/red]")
                time.sleep(600)  # 止损后冷却10分钟

            print_status(engine)
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        console.print("\n[yellow]⏹ 收到停止信号[/yellow]")
        positions = client.get_positions()
        if positions:
            console.print("[yellow]当前仍有持仓! 请手动处理或选择:[/yellow]")
            choice = input("输入 CLOSE 平仓，其他键保留仓位退出: ")
            if choice.upper() == "CLOSE":
                client.close_all_positions()
                console.print("[green]✅ 已平仓[/green]")
        console.print("[green]机器人已停止[/green]")

    except Exception as e:
        logger.error(f"❌ 运行异常: {e}", exc_info=True)
        alert_sound()
        console.print(f"[red]❌ 运行异常: {e}[/red]")
        console.print("[yellow]仓位可能仍在，请手动检查币安APP！[/yellow]")


if __name__ == "__main__":
    main()
