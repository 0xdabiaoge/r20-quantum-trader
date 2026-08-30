<div align="center">

# ⚡ R20 Quantum Trader
### LLM-Native Self-Evolving Quantitative Trading Terminal & Execution Engine
**全天候大模型全权决策 · 多维量化因子矩阵 · 顺势浮盈金字塔加仓 · 启发式自进化记忆 · 暗黑极客监控终端**

<br/>

[![Version](https://img.shields.io/badge/Version-v5.3.1-6366F1.svg)](https://github.com/555cute/r20-quantum-trader/releases)
[![License](https://img.shields.io/badge/License-MIT-10B981.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![QwenPaw](https://img.shields.io/badge/Agent_Framework-QwenPaw-4F46E5.svg)](https://github.com/agentscope-ai/QwenPaw)

<br/>

[🔥 线上实盘监控终端](https://www.r20.cn) • [💬 社区与交流群](#-作者与量化交流社区) • [✨ 核心交易特性](#-核心交易系统特性) • [🚀 快速开始](#-快速开始) • [📖 部署手册](RECOVERY_GUIDE.md)

</div>

---

## 💬 作者与量化交流社区

欢迎量化交易策略研究员、大模型 Agent 开发者与开源技术爱好者加入交流，共同探讨实盘心得与自进化量化架构！

<div align="center">

| 交流渠道 | 详细联系方式 / 直达链接 | 备注说明 |
| :--- | :--- | :--- |
| 👥 **官方量化实战交流群** | **QQ 群号: `655973677`** | 实时探讨实盘策略、因子优化与大模型调优 |
| 🐧 **作者个人 QQ** | **QQ: `1090188816`** | 技术交流、系统定制与开源协作 |
| 🌐 **24H 在线实盘终端** | **[https://www.r20.cn](https://www.r20.cn)** | 纯净域名直连，毫秒级同步 OKX 实盘数据 |
| 🐙 **GitHub 开源主仓** | **[555cute/r20-quantum-trader](https://github.com/555cute/r20-quantum-trader)** | 欢迎 Star ⭐️ 与提交 PR 协同演进 |

</div>

---

## 🌐 线上实盘终端概览

> 💡 **生产环境监控直链**: **[https://www.r20.cn](https://www.r20.cn)**  
> 24H 全天候不间断运行，纯只读开放 6 核心加密资产（**BTC / ETH / SOL / DOGE / SUI / LINK**）的**大模型长思考链推演 (CoT Prompt)、顶级聪明钱资金流向、多周期量化因子矩阵、在途限价挂单实时状态及生命周期交易台账**。

---

## 📷 系统实机截图

### 1. 🖥️ 暗黑极客量化监控大屏
*涵盖官方总权益、今日已结净盈亏、在途持仓实时监控、在途限价挂单排队监控以及动态资产净值与回撤曲线。*
![Terminal Overview](docs/images/terminal_overview.png)

---

### 2. 🧠 AI 大脑全权决策矩阵
*单卡综合 15M/1H 多周期共振、1H ADX 趋势强度门禁、Top100 聪明钱主力加权多空比、24H 资金净流向与买一卖一盘口微观深度比。*
![AI Brain Matrix](docs/images/ai_brain_matrix.png)

---

### 3. ⚡ 15,500+ 字符真实 Prompt 审计抽屉
*全屏深色代码终端抽屉，100% 透明展示 System Prompt 交易铁律与 User Prompt 全周期行情、聪明钱主力及挂单持仓输入，支持一键复制与秒级时间戳审计。*
![Realtime Prompt Modal](docs/images/realtime_prompt_modal.png)

---

### 4. 📜 宽屏生命周期交易台账
*1680px 宽屏视野，标的/杠杆、策略形态、开平仓均价与时间、净盈亏（ROI）及离场归因全部单行对齐，毫秒级出场回填。*
![Lifecycle Trades](docs/images/lifecycle_trades.png)

---

### 5. 🔄 启发式自进化长期记忆库
*每日 20:00 自动穿透全天实战流水，提炼带时间戳的启发式心法与失误归因，动态注入大模型下一轮决策先验。*
![Self Evolution Memory](docs/images/self_evolution_memory.png)

---

## 🌟 核心交易系统特性

### 🧠 1. LLM-Native 首席 AI 交易官与长思考链
- **废除死板硬编码规则**: 彻底摒弃传统量化僵化的单指标阈值加减分，开仓、平仓、加仓与挂单生命周期管理主权 100% 交由大语言模型（默认搭载 `gemini-3.7-flash-high`，显式启用 `reasoning_effort: high` 深度思考模式，推理 Token 占比超 65%）。
- **15,500+ 字符高维推演上下文**: 单次推演全量并发注入 6 大资产的 **15M / 1H / 4H 连续 26 根 K 线序列、OKX Top100 聪明钱加权成本、微观盘口买一/卖一即时深度、全网重大快讯舆情、在途持仓与盘口在途挂单**。
- **严密盈亏比数学自洽 (R:R ≥ 2.0)**: 大模型输出入场价 (Entry)、止盈价 (TP) 与止损价 (SL) 必须严格满足 $\text{Risk/Reward} \ge 2.0$ 的空间几何自洽，空间不足坚决观望。

### 🚀 2. 顺势浮盈金字塔加仓体系
- **0 风险底仓加仓铁律**: 仅当已有持仓产生显著浮盈（$\text{ROI} \ge +0.8\%$）或系统已将止损线上移至开仓价上方（推保本锁盈）时，才允许 AI 触发顺势加仓（Pyramiding），乘胜追击放大利润。
- **坚决杜绝逆势补仓**: 浮亏或未脱离成本区的持仓物理禁止追加订单，从源头彻底扑灭“越跌越买/扛单穿仓”的马丁格尔陷阱。
- **单标的仓位硬上限**: 单一标的最大顺势加仓次数限制为 1 次，累计占用保证金严格锁死在 $\le 600\text{ USDT}$ 以内，确保资产敞口均衡。

### ⚡ 3. 智能 Maker 限价挂单与自主撤单
- **费率大幅降低 60%**: 开仓执行全面升级为基于盘口买一/卖一档的 `ordType: limit` 智能限价挂单，手续费直接从 Taker 万5 降至 Maker 万2，年化交易磨损大幅骤降。
- **挂单生命周期自主撤单**: 在途挂单全景实时输入大模型；当行情剧烈偏离、逻辑反转或挂单过时，AI 大脑自主输出 `CANCEL` 指令动态撤单，杜绝挂单在不利位置成交。

### 👑 4. OKX Top100 顶级聪明钱主力共振
- **毫秒级主力透视**: 直连 OKX 官方顶级聪明钱（实盘胜率 $>80\%$ 的 Top100 机构与高盈利率交易员）的资金加权多空比、多空持仓成本均价及 24H 资金净流入流出。
- **顺庄交易铁律**: 严禁逆全网顶级聪明钱主力大势盲目重仓开单，必须在聪明钱建仓成本价附近寻找高确定性共振点位。

### 📊 5. 五大量化 Alpha 因子矩阵
1. **动量趋势**: 1H ADX 趋势强度硬门禁（$\text{ADX} < 20$ 垃圾震荡市坚决封锁观望，彻底杜绝无量震荡反复扫止损；$\text{ADX} \ge 22$ 伴随放量方可捕获趋势）、RSI(14)、VWAP 价格加权均价偏离度。
2. **波动通道**: ATR 动态真实波幅自适应计算，$1.2 \sim 1.5 \times \text{ATR}$ 缓冲止损空间。
3. **资金流向**: CMF 柴金资金流指标、5M Taker 主动吃单净买卖量差、合约未平仓量 (OI) 增减动能。
4. **微观盘口**: 买一/卖一档即时价差比、盘口前 5 档买卖挂单总量深度比。
5. **衍生品筹码**: 8 小时资金费率热力图、多空借贷比与持仓多空偏置。

### 🔄 6. 启发式自进化记忆体系
- **每日 20:00 深度复盘**: 每天固定于北京时间 20:00（美盘开盘前 1 小时）自动穿透全天实战成交流水；
- **Markdown 长效心法沉淀**: 穿透真实损益与手续费磨损，提炼带 `[YYYY-MM-DD HH:MM:SS]` 精确时间戳的实战心法沉淀至 `data/AI_TRADING_MEMORY.md`；
- **智能时效淘汰与先验注入**: 动态淘汰被证伪的旧认知，下一轮推演自动将最新心法作为直觉约束拼入 Prompt，实现模型认知的持续自进化。

### 🛡️ 7. 机构级三级熔断与 100% 云端 OCO 保护
- **致命黑天鹅哨兵**: 双路快讯采集，正则实时监测稳定币脱锚、交易所爆雷等系统性灾难，触发全局避险；
- **BTC 15M 暴跌熔断**: BTC 单根 15M 阴线跌幅 $> 3.0\%$ 立即封锁所有加密币开仓通道；
- **单日最大回撤熔断**: 单日亏损达预设阈值强制休眠；
- **100% 交易所撮合级云端 OCO 保护**: 开仓同时向 OKX 服务器提交云端止盈止损单，彻底防范网络波动或单边断崖风险。

### 💻 8. 暗黑极客量化监控终端
- **深邃暗黑极客质感**: 采用 `#0B0E14` 深板岩底色搭配钛金属微边框（`#1E293B`）与玻璃磨砂质感；
- **实时提示词悬浮抽屉**: 右下角常驻悬浮胶囊，单击秒级呼出 15,500+ 字符真实 Prompt，支持一键复制；
- **宽屏生命周期台账**: 支持全部/在途/已平仓一键筛选与多维搜索，实时回填持仓耗时与离场原因。

---

## 🏛️ 系统全景架构图

```text
                                  ┌──────────────────────────────┐
                                  │      全网重大快讯 & 舆情     │
                                  │ (news_sentiment_harvester)   │
                                  └──────────────┬───────────────┘
                                                 │
┌───────────────────────────┐                    ▼                    ┌──────────────────────────┐
│  OKX V5 行情/盘口/K线 API  │ ───►  scripts/ai_brain_trader.py  ◄─── │ OKX Top100 聪明钱主力资金 │
└───────────────────────────┘       (Gemini 3.7 Flash High 推演)       └──────────────────────────┘
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
                                  │ (Maker 限价单 + 浮盈加仓门禁) │
                                  └──────────────┬───────────────┘
                                                 │
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │  Modern Dark 极客监控终端 UI │
                                  │ (FastAPI + Tailwind WebApp)  │
                                  └──────────────────────────────┘
```

---

## 🚀 快速开始

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
# 编辑 .env 文件填入你的 LLM API Key 以及 OKX API 凭证
vim .env
```

### 3. 一键启动 Web 监控终端
```bash
python3 -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8080
```
在浏览器中访问：`http://localhost:8080` 即可进入暗黑量化监控终端。

### 4. 启动后台守护与定时推演
```bash
# 启动 60 秒量化因子库与快讯同步守护进程 (后台常驻)
nohup python3 scripts/daemon_web_sync.py > /tmp/daemon_sync.log 2>&1 &

# 手工触发一次 AI 大脑推演与限价单执行
python3 scripts/ai_brain_trader.py

# 手工触发每日自进化复盘
python3 scripts/self_improvement_engine.py
```

---

## 📁 核心项目结构规范

```text
r20-quantum-trader/
├── data/                             # 核心持久化数据 (带 .gitignore 隔离保护)
│   ├── AI_TRADING_MEMORY.md          # QwenPaw 原生带时间戳实战心法长期记忆
│   ├── ai_brain_last_prompt.txt      # 15,500+ 字符真实 System + User Prompt 快照
│   ├── factor_library_snapshot.json  # 5 大量化因子库快照
│   ├── news_sentiment.json           # 全网实时重大快讯与宏观情报
│   └── .gitkeep
├── scripts/                          # 核心量化算法与交易执行引擎
│   ├── ai_brain_trader.py            # LLM-Native 首席 AI 交易官大脑 (Reasoning High 深度推演)
│   ├── ai_factor_trader.py           # 交易执行层 (智能 Maker 限价挂单 + 顺势浮盈金字塔加仓门禁)
│   ├── factor_library.py             # 5 大量化 Alpha 因子计算引擎 (ADX/ATR/RSI/CMF/盘口微观)
│   ├── self_improvement_engine.py   # 启发式自进化复盘引擎 (每日 20:00 提炼 Markdown 心法)
│   ├── news_sentiment_harvester.py   # 实时快讯情报采集与三级黑天鹅避险哨兵
│   ├── daemon_web_sync.py            # 60 秒因子并发计算与 Web 数据同步守护进程
│   ├── qq_notifier.py                # QQ 即时交易挂单、加仓与平仓推送通知
│   └── nightly_backup_and_clean.py   # 凌晨 02:00 百度网盘异地云灾备归档与 SHA-256 校验
├── dashboard/                        # Web 极客监控控制台
│   ├── app.py                        # FastAPI 毫秒级内存缓存后端
│   └── templates/index.html          # Modern Dark Glassmorphism 5 大 Tab 监控页面
├── docs/images/                      # 终端高清实机截图资源
├── requirements.txt                  # Python 依赖清单
├── env.example                       # 环境变量模板
├── RECOVERY_GUIDE.md                 # 完整部署与灾备恢复手册
├── LICENSE                           # MIT 开源协议
└── README.md                         # 本说明文档
```

---

## 🛡️ 安全与隐私声明

本项目在开源架构设计上严格执行**金融级隐私与数据解耦标准**：
- 真实 OKX 交易密钥（`.okx/`）与大模型 API Key 严格采用环境变量与密文存储解耦，**源码中 100% 零硬编码密钥**；
- 实盘私有账本与资金流水已被 `.gitignore` 彻底物理隔离，绝不上云；
- 开源代码库已经过自动化敏感特征全量静态穿透审计。

---

## ⚠️ 免责声明

本项目仅供量化交易算法研究、大模型自主 Agent 技术探索与学术交流使用，不构成任何投资建议、财务指导或实盘收益承诺。加密货币衍生品交易具备极高风险，请在充分了解风险并确保符合当地法律法规的前提下使用模拟盘（Demo）进行验证。开发者不对任何实盘资金损益承担责任。

---

<div align="center">
Made with ❤️ by R20 Quantum Trader Team • Powered by <a href="https://github.com/agentscope-ai/QwenPaw">QwenPaw Framework</a>
</div>
