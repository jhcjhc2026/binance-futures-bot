# 币安U本位合约量化交易机器人 🤖

> **马丁策略 + 做空网格策略**，基于 Python + ccxt，本地运行，全自动交易。

## ⚠️ 风险警告

**合约交易风险极高，可能导致本金全部亏损！**
本工具仅供学习研究，不构成任何投资建议。使用本软件造成的任何损失，由使用者自行承担。

---

## 策略简介

### 1. BTC 马丁策略（btc-martin/）

做多马丁格尔策略：开仓后如果亏损就加仓补仓，等价格反弹到盈利线自动止盈。

- 交易对：BTC/USDT U本位合约
- 杠杆：2x（保守）/ 可调
- 首仓：2U 保证金
- 补仓倍数：1.5x（最多5轮）
- 止盈：+0.8%
- 补仓触发：-1.5%
- 硬止损：总亏损30%

**5轮补仓保证金分布：**

| 轮次 | 保证金 | 累计 |
|------|--------|------|
| 1 | 2.0U | 2.0U |
| 2 | 3.0U | 5.0U |
| 3 | 4.5U | 9.5U |
| 4 | 6.75U | 16.25U |
| 5 | 10.13U | 26.38U |

### 2. ETH 做空网格策略（eth-grid/）

在震荡区间内高抛低吸：价格涨到网格线上方开空单，跌到下方平空止盈。

- 交易对：ETH/USDT U本位合约
- 杠杆：10x 逐仓
- 对冲模式（Hedge Mode）
- 网格区间：1680 - 1800 USDT
- 网格数量：8格（步长15U）
- 每格仓位：0.05 ETH
- 最大持仓：5格
- 止损：1850 USDT（价格突破网格上沿）

---

## 快速开始

### 1. 安装 Python

下载安装 [Python 3.9+](https://www.python.org/downloads/)，安装时勾选 "Add to PATH"。

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 API

进入对应策略目录，复制 `.env.example` 为 `.env`，填入你的币安 API Key 和 Secret：

```bash
cd btc-martin
copy .env.example .env
# 编辑 .env 填入 API Key
```

如需代理，填写代理地址（如 `http://127.0.0.1:7890`）。

### 4. 启动

**BTC 马丁：**
```bash
cd btc-martin
python main.py
```
或双击 `start.bat`

**ETH 网格：**
```bash
cd eth-grid
python grid_bot.py --yes
```
或双击 `start_grid.bat`

首次实盘启动需要输入 `YES` 确认。

### 5. 模拟模式（BTC 马丁）

编辑 `btc-martin/config.py`，将 `DRY_RUN = True`，即可模拟运行，不会下真单。

**强烈建议先模拟跑1-2天熟悉逻辑再上实盘！**

---

## 项目结构

```
binance-futures-bot/
├── btc-martin/              # BTC马丁策略
│   ├── main.py              # 主程序入口
│   ├── client.py            # 币安API客户端封装
│   ├── strategy.py          # 马丁策略引擎
│   ├── config.py            # 参数配置
│   ├── .env.example         # API密钥模板
│   └── start.bat            # Windows启动脚本
├── eth-grid/                # ETH做空网格策略
│   ├── grid_bot.py          # 网格机器人主程序
│   ├── config.py            # 参数配置
│   ├── close_long.py        # 平多单工具脚本
│   ├── .env.example         # API密钥模板
│   └── start_grid.bat       # Windows启动脚本（自动重启）
├── requirements.txt          # Python依赖
├── .gitignore
└── README.md
```

---

## 参数配置说明

### BTC 马丁参数（btc-martin/config.py）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| INITIAL_MARGIN | 2.0U | 首次开仓保证金 |
| MARTIN_MULTIPLIER | 1.5 | 补仓倍数 |
| MAX_MARTIN_ROUNDS | 5 | 最多补仓次数 |
| LOSS_TRIGGER_PCT | 1.5% | 亏损多少触发补仓 |
| TAKE_PROFIT_PCT | 0.8% | 盈利多少止盈 |
| MAX_LOSS_PCT | 30% | 总亏损硬止损 |
| DAILY_LOSS_LIMIT | 20% | 单日最大亏损 |
| LEVERAGE | 10x | 杠杆倍数 |
| DRY_RUN | False | 模拟模式开关 |

### ETH 网格参数（eth-grid/config.py）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| GRID_LOWER | 1680 | 网格下沿 |
| GRID_UPPER | 1800 | 网格上沿 |
| GRID_COUNT | 8 | 网格数量 |
| GRID_AMOUNT | 0.05 | 每格仓位(ETH) |
| MAX_HOLDING | 5 | 最大持仓格数 |
| STOP_LOSS_PRICE | 1850 | 止损价格 |
| MAX_DRAWDOWN_PCT | 15% | 最大回撤止损 |
| CHECK_INTERVAL | 10s | 价格检查间隔 |
| LEVERAGE | 10x | 杠杆倍数 |

---

## 风控机制

### BTC 马丁
1. **硬止损**：总亏损达30%强制平仓
2. **日亏损限制**：单日亏损达20%停止交易
3. **最大补仓次数**：达5轮仍亏损则止损
4. **保证金上限**：单方向保证金不超过80U
5. **止损冷却**：止损后冷却10分钟再开仓

### ETH 网格
1. **止损价格**：价格突破网格上沿(1850)全部平仓
2. **最大回撤**：总资产回撤15%全部平仓
3. **最大持仓**：最多持有5格空单
4. **自动重启**：进程退出后5秒自动重启

---

## 运行要求

- Windows 10/11
- Python 3.9+
- 稳定的网络（需访问币安API）
- 建议电脑24小时运行或使用云服务器
- 如在中国大陆，需配置代理

---

## 安全说明

- `.env` 文件包含 API 密钥，**不要分享给任何人**，已被 `.gitignore` 忽略
- 建议在币安创建专用 API Key，仅开启合约交易权限，不开提现权限
- 建议设置 IP 白名单限制

---

## 技术栈

- [ccxt](https://github.com/ccxt/ccxt) - 加密货币交易所API库
- [python-dotenv](https://github.com/theskumar/python-dotenv) - 环境变量管理
- [rich](https://github.com/Textualize/rich) - 终端美化输出

---

## License

MIT

---

## 免责声明

本软件仅供学习研究目的。加密货币合约交易具有极高风险，可能导致全部本金亏损。使用本软件进行实际交易所造成的任何损失，由使用者自行承担。作者不对任何直接或间接损失负责。
