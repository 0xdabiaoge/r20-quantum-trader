<div align="center">

# ⚡ R20 Quantum Trader
### LLM-Native Self-Evolving Quantitative Trading Terminal & Execution Engine
**全天候大模型全权决策 · 多维量化因子矩阵 · 启发式自进化记忆 · 暗黑磨砂极客监控终端**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Dashboard-FastAPI%20%2B%20Tailwind-009688.svg)](https://fastapi.tiangolo.com)
[![QwenPaw Framework](https://img.shields.io/badge/Agent%20Framework-QwenPaw-indigo.svg)](https://github.com/agentscope-ai/QwenPaw)

</div>

---

## 🌟 核心特性 (Key Features)

- 🧠 **LLM-Native 全权决策主权 (Pure Autonomous AI Brain)**:
  - 彻底废除死板的静态指标阈值规则，主权 100% 移交大语言模型（如 `gemini-3.7-flash-high` + `reasoning_effort: high` 深度思考模式）。
  - 单次推演并发输入 **15,500+ 字符高维全景 Prompt**（涵盖 6 标的多周期原生 K 线序列、Top100 聪明钱主力流向、即时盘口微观深度与全网重大快讯）。
- 👑 **OKX Top100 聪明钱资金流共振 (Smart Money Alignment)**:
  - 毫秒级接入 OKX 实盘胜率 > 80% 的顶级聪明钱主力资金加权多空比、建仓均价与 24H 资金净流入，严禁逆势扛单。
- 📊 **五大量化 Alpha 因子库 (5-Pillar Factor Library)**:
  - **动量趋势**: 1H ADX 趋势强度门禁（<20 垃圾震荡市坚决观望）、RSI(14)、VWAP 乖离率。
  - **波动通道**: ATR 动态波动率、布林带宽挤压。
  - **资金流向**: CMF 柴金资金流、5M Taker 主动吃单净差、未平仓合约量 (OI)。
  - **微观盘口**: 买一/卖一档价差、前 5 档买卖深度比。
  - **聪明钱衍生品**: 资金费率热力图、多空借贷比。
- 🔄 **QwenPaw 原生启发式自进化记忆 (Heuristic Self-Evolution)**:
  - 每日固定于 **20:00 (北京时间)** 自动穿透全天实战成交流水与手续费摩擦，提炼 3 条带时间戳的启发式实战心法沉淀至 `AI_TRADING_MEMORY.md`，并在后续每轮推演中作为软先验实时注入大模型。
- 🛡️ **机构级三级熔断与风控屏障 (3-Tier Risk & Circuit Breaker)**:
  - **致命黑天鹅哨兵**: 拦截稳定币恶性脱锚、头部交易所挤兑停服等系统性灾难；
  - **BTC 15M 暴跌秒级熔断**: 单根 15M 阴线暴跌 > 3.0% 立即冻结开仓；
  - **账户级日最大回撤熔断**: 单日亏损达 3% (120 USDT) 强制休眠；
  - **100% 云端 OCO 保护**: 开仓即挂交易所撮合级止盈止损单，防断网断电。
- 💻 **Bloomberg 级暗黑磨砂玻璃交易终端 (Dark Glassmorphism UI)**:
  - 极客暗黑主题（`#0B0E14`），7-8px 紧凑圆角，高信息密度排版；
  - 右下角常驻 **`⚡ 实时提示词` 悬浮胶囊**，随时一键展开 15,500+ 字符 Prompt 抽屉并支持一键复制与秒级时间戳审计；
  - 宽屏单行生命周期交易台账（Lifecycle Trades），彻底消除两行折行。

---

## 🏛️ 系统架构 (Architecture)

```text
                                  ┌──────────────────────────────┐
                                  │      全网重大快讯 & 舆情     │
                                  │ (news_sentiment_harvester)   │
                                  └──────────────┬───────────────┘
                                                 │
┌───────────────────────────┐                    ▼                    ┌──────────────────────────┐
│  OKX V5 行情/盘口/K线 API  │ ───►  scripts/ai_brain_trader.py  ◄─── │ OKX Top100 聪明钱主力资金 │
└───────────────────────────┘       (LLM Reasoning High 推演)         └──────────────────────────┘
                                                 ▲
                                                 │
                                  ┌──────────────┴───────────────┐
                                  │   QwenPaw 长期记忆与实战心法 │
                                  │   (data/AI_TRADING_MEMORY.md)│
                                  └──────────────────────────────┘
                                                 │
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │  scripts/ai_factor_trader.py │
                                  │  (Maker限价单 + 云端OCO保护)  │
                                  └──────────────┬───────────────┘
                                                 │
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │  Bloomberg 级暗黑监控终端 UI │
                                  │ (FastAPI + Tailwind WebApp)  │
                                  └──────────────────────────────┘
```

---

## 🚀 快速开始 (Quick Start)

### 1. 克隆项目与安装依赖
```bash
git clone https://github.com/555cute/r20-quantum-trader.git
cd r20-quantum-trader

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量
```bash
cp env.example .env
# 编辑 .env 文件填入你的 LLM API Key 以及 OKX 凭证
vim .env
```

### 3. 启动 Web 监控终端
```bash
python3 -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8080
```
在浏览器中打开：`http://localhost:8080` 即可体验暗黑交易终端。

### 4. 启动后台守护与交易推演
```bash
# 启动 60 秒量化因子库与快讯同步守护进程
python3 scripts/daemon_web_sync.py

# 手工触发一次 AI 大脑推演与执行
python3 scripts/ai_brain_trader.py
```

---

## ⚠️ 免责声明 (Disclaimer)

本项目仅供量化交易技术研究与学术交流使用，不构成任何投资建议或财务指导。加密货币衍生品交易具备极高风险，请在充分了解风险并确保符合当地法律法规的前提下使用模拟盘（Demo）进行验证。开发者不对任何实盘资金损益承担责任。
