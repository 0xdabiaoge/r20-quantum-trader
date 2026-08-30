<div align="center">

# ⚡ R20 Quantum Trader
### LLM-Native Self-Evolving Quantitative Trading Terminal & Execution Engine
**全天候大模型全权决策 · 多维量化因子矩阵 · 启发式自进化记忆 · Bloomberg 级暗黑磨砂极客监控终端**

<br/>

[![Live Demo](https://img.shields.io/badge/🌐_Live_Demo-www.r20.cn-6366F1?style=for-the-badge&logo=googlechrome&logoColor=white)](https://www.r20.cn)
[![Version: v5.2.0](https://img.shields.io/badge/Version-v5.2.0-8B5CF6?style=for-the-badge&logo=github&logoColor=white)](https://github.com/555cute/r20-quantum-trader/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-10B981?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Dashboard-FastAPI%20%2B%20Tailwind-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![QwenPaw Framework](https://img.shields.io/badge/Agent_Framework-QwenPaw-4F46E5?style=for-the-badge&logo=probot&logoColor=white)](https://github.com/agentscope-ai/QwenPaw)

<br/>

[🔥 线上实盘监控终端 (Live Terminal)](https://www.r20.cn) • [📖 系统部署与灾备手册](RECOVERY_GUIDE.md) • [✨ 核心亮点](#-核心特性-key-features) • [🚀 快速开始](#-快速开始-quick-start)

</div>

---

## 🌐 线上实盘终端预览 (Live Terminal Preview)

> 💡 **在线监控地址**: **[https://www.r20.cn](https://www.r20.cn)**  
> 生产环境 24H 全天候运行，支持实时查看 6 核心加密资产（BTC / ETH / SOL / DOGE / SUI / LINK）的**大模型实时思考链 (CoT Prompt)、顶级聪明钱资金流、多周期量化因子与生命周期交易台账**。

---

## 📷 系统全景截图 (Screenshots Gallery)

### 1. 🖥️ 极客暗黑终端主屏 (Trading Overview & Equity Curve)
*涵盖官方总权益、今日已结净盈亏、在途持仓实时监控、以及平滑动态回撤曲线。*
![Terminal Overview](docs/images/terminal_overview.png)

---

### 2. 🧠 AI 大脑决策矩阵与多维量化因子库 (AI Brain Decision Matrix)
*单卡综合 15M/1H 趋势、1H ADX 趋势强度门禁、Top100 聪明钱加权多空比与 24H 净流入、买一卖一盘口微观深度比。*
![AI Brain Matrix](docs/images/ai_brain_matrix.png)

---

### 3. ⚡ 15,500+ 字符真实 Prompt 透明审计抽屉 (Realtime Prompt Transparency)
*全屏深色代码终端抽屉，100% 透明展示 System Prompt 交易铁律与 User Prompt 全周期 K 线及聪明钱输入，支持一键复制与推演秒级时间戳。*
![Realtime Prompt Modal](docs/images/realtime_prompt_modal.png)

---

### 4. 📜 宽屏生命周期交易台账 (Lifecycle Trades & Execution Ledger)
*1680px 宽屏视野，标的/方向、策略形态、开平仓时价与净盈亏全部单行对齐，毫秒级出场归因。*
![Lifecycle Trades](docs/images/lifecycle_trades.png)

---

### 5. 🔄 QwenPaw 原生启发式长期记忆库 (Heuristic Self-Evolution Memory)
*每日 20:00 自动穿透全天实战流水，提炼带时间戳的启发式心法与失误归因，动态注入大模型先验。*
![Self Evolution Memory](docs/images/self_evolution_memory.png)

---

## 🌟 核心特性 (Key Features)

### 🧠 1. LLM-Native 全权决策主权 (Pure Autonomous AI Brain)
- **拒绝机械硬编码指标**: 彻底废除死板的指标加减分阈值规则，开仓与持仓管理主权 100% 交由大语言模型（如 `gemini-3.7-flash-high` + `reasoning_effort: high` 深度思考模式）。
- **全景高维输入**: 单次推演并发输入 **15,500+ 字符 Prompt**，全景覆盖 6 币种原生 15M/1H/4H 的 26 根完整 K 线序列、Top100 聪明钱建仓成本、即时盘口微观深度与全网重大资讯。
- **动态持仓管理**: 在途持仓支持大模型实时发出 `UPDATE_SL`（抬高止损锁定利润）与 `CLOSE_MARKET` 指令。

### 👑 2. OKX Top100 聪明钱资金流共振 (Smart Money Alignment)
- 毫秒级接入 OKX 实盘胜率 > 80% 的顶级聪明钱主力资金加权多空比、多空建仓均价与 24H 资金净流入；
- 严禁逆全网顶级聪明钱主力大势盲目重仓开单，在主力成本区寻找高确定性共振点位。

### 📊 3. 五大核心量化 Alpha 因子库 (5-Pillar Factor Engine)
1. **动量趋势 (Trend & Momentum)**: 1H ADX 趋势强度门禁（<20 垃圾震荡市坚决观望，彻底杜绝假突破）、RSI(14)、VWAP 价格偏离度。
2. **波动通道 (Volatility & Channel)**: ATR 动态真实波幅、布林带宽挤压。
3. **资金流向 (Money Flow)**: CMF 柴金资金流、5M Taker 主动吃单净差、未平仓合约量 (OI)。
4. **微观盘口 (Microstructure)**: 买一/卖一档价差、前 5 档买卖挂单深度比。
5. **衍生品筹码 (Derivatives)**: 资金费率热力图、多空借贷比。

### 🔄 4. QwenPaw 原生启发式自进化记忆体系 (Self-Evolution Memory)
- **每日 20:00 深度复盘**: 每天固定于北京时间 20:00（美盘开盘前 1 小时）自动穿透全天实战成交流水；
- **Markdown 长效心法沉淀**: 提炼 3 条带 `[YYYY-MM-DD HH:MM:SS]` 时间戳的实战心法（如 *顺势做多警惕末端接盘*、*阻力位严禁左侧硬摸*、*手续费摩擦前置过滤*）沉淀至 `data/AI_TRADING_MEMORY.md`；
- **动态先验注入**: 下一轮推演时自动读取最新有效记忆作为直觉约束注入 Prompt，实现真正的自我迭代。

### 🛡️ 5. 机构级三级熔断与风控屏障 (3-Tier Risk & Safety Guard)
- **致命黑天鹅哨兵**: 精准正则拦截稳定币恶性脱锚、头部交易所挤兑破产等系统性灾难；
- **BTC 15M 暴跌秒级熔断**: 单根 15M 阴线暴跌 > 3.0% 立即冻结所有开仓通道；
- **单日最大回撤熔断**: 单日亏损达 3% (120 USDT) 强制休眠；
- **100% 云端 OCO 保护**: 开仓即挂交易所撮合级止盈止损单，防断网断电。

### 💻 6. Bloomberg 级暗黑磨砂极客监控终端 (Dark Glassmorphism UI)
- 采用深邃暗黑基调（`#0B0E14`）搭配微光磨砂玻璃卡片（`backdrop-filter: blur(16px)`）；
- 右下角常驻 **`⚡ 实时提示词` 悬浮胶囊**，随时一键调阅并一键复制 15,500+ 字符 Prompt；
- 宽屏单行生命周期交易台账（Lifecycle Trades），支持实时收益与出场归因穿透。

---

## 🏛️ 系统架构图 (Architecture)

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

### 3. 一键启动 Web 监控终端
```bash
python3 -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8080
```
在浏览器中访问：`http://localhost:8080` 即可进入暗黑交易终端。

### 4. 启动后台守护与推演任务
```bash
# 启动 60 秒量化因子库与快讯同步守护进程 (后台常驻)
nohup python3 scripts/daemon_web_sync.py > /tmp/daemon_sync.log 2>&1 &

# 手工触发一次 AI 大脑推演与限价单执行
python3 scripts/ai_brain_trader.py

# 手工触发每日自进化复盘
python3 scripts/self_improvement_engine.py
```

---

## 📁 核心目录结构规范

```text
r20-quantum-trader/
├── data/                             # 核心持久化数据 (带 .gitignore 隔离保护)
│   ├── AI_TRADING_MEMORY.md          # QwenPaw 原生带时间戳实战心法长期记忆
│   ├── ai_brain_last_prompt.txt      # 15,500+ 字符真实 System + User Prompt 快照
│   ├── factor_library_snapshot.json  # 五大量化因子库快照
│   ├── news_sentiment.json           # 全网实时重大快讯与宏观情报
│   └── .gitkeep
├── scripts/                          # 核心算法与交易执行引擎
│   ├── ai_brain_trader.py            # LLM-Native 首席 AI 交易官决策大脑 (Reasoning High)
│   ├── ai_factor_trader.py           # 交易执行层 (智能 Maker 限价单 + OKX 云端 OCO 保护)
│   ├── factor_library.py             # 5 大量化 Alpha 因子计算引擎 (ADX/ATR/RSI/CMF/盘口微观)
│   ├── self_improvement_engine.py   # 启发式自进化复盘引擎 (每日 20:00 提炼 Markdown 心法)
│   ├── news_sentiment_harvester.py   # 快讯情报采集与致命黑天鹅哨兵
│   ├── daemon_web_sync.py            # 60 秒因子并发计算与 Web 数据同步守护进程
│   └── nightly_backup_and_clean.py   # 凌晨 02:00 异地云灾备归档与 SHA-256 校验
├── dashboard/                        # Web 监控控制台
│   ├── app.py                        # FastAPI 毫秒级内存缓存后端
│   └── templates/index.html          # Bloomberg 级 Dark Glassmorphism 5 大 Tab 监控页面
├── docs/images/                      # 终端高清实机截图资源
├── requirements.txt                  # Python 依赖清单
├── env.example                       # 环境变量模板
├── RECOVERY_GUIDE.md                 # 完整部署与灾备恢复手册
├── LICENSE                           # MIT 开源协议
└── README.md                         # 本说明文档
```

---

## 🛡️ 安全与隐私声明 (Security & Privacy)

本项目在开源架构设计上严格执行**金融级隐私与数据解耦标准**：
- 真实 OKX 交易密钥（`.okx/`）与大模型 API Key 严格采用环境变量与密文存储解耦，**源码中 100% 零硬编码密钥**；
- 实盘私有账本与资金流水已被 `.gitignore` 彻底物理隔离，绝不上云；
- 开源代码库已经过自动化敏感特征全量静态穿透审计。

---

## ⚠️ 免责声明 (Disclaimer)

本项目仅供量化交易算法研究、大模型自主 Agent 技术探索与学术交流使用，不构成任何投资建议、财务指导或实盘收益承诺。加密货币衍生品交易具备极高风险，请在充分了解风险并确保符合当地法律法规的前提下使用模拟盘（Demo）进行验证。开发者不对任何实盘资金损益承担责任。

---

<div align="center">
Made with ❤️ by R20 Quantum Trader Team • Powered by <a href="https://github.com/agentscope-ai/QwenPaw">QwenPaw Framework</a>
</div>
