<div align="center">

# ⚡ R20 Quantum Trader

### 面向 OKX 永续合约的机构级 LLM 原生量化交易终端与多模型参谋系统

**多模型决策委员会 · 动态标的资产池 · Python 物理拦截管线 · 启发式自进化记忆 · 原生 Vue 3 双模终端 · 100% 交易所云端 OCO**

[![Release](https://img.shields.io/badge/release-v6.6.1%20(Mobile%20Navigation%20Boost)-3875F6?style=flat-square)](https://github.com/555cute/r20-quantum-trader/releases/tag/v6.6.1)
[![LINUX DO](https://img.shields.io/badge/Community-LINUX%20DO-F97316?style=flat-square&logo=linux&logoColor=white)](https://linux.do/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Exchange](https://img.shields.io/badge/Exchange-OKX%20V5%20Direct-111827?style=flat-square)](https://www.okx.com/)
[![Tests](https://img.shields.io/badge/tests-166%2F166%20passed-0ECB81?style=flat-square)](#-测试与质量保障)
[![Security](https://img.shields.io/badge/Security-Fail--Closed%20Audit-10B981?style=flat-square)](#-企业级安全与防护体系)
[![License](https://img.shields.io/badge/license-MIT-10B981?style=flat-square)](LICENSE)

[🌐 在线实盘大屏](https://www.r20.cn/) · [📖 官方图文开发指南](/docs) · [🚀 快速部署手册](#-极速部署指南) · [🐧 LINUX DO 社区](https://linux.do/)

<br/>

> 💬 **QQ 官方交流群**：**`655973677`** ｜ **作者 QQ**：`1090188816` ｜ 欢迎进群交流量化模型、提示词编写、微积分动力学因子与实盘动态！

</div>

---

![R20 机构级量化终端全景](docs/images/dashboard_trading.png)

> [!WARNING]
> R20 Quantum Trader 是面向加密货币市场的开源量化交易系统，致力于为个人交易员与量化团队提供高透明度、自进化与工业级的波段交易底座。**软件不构成任何投资建议，数字资产交易具有极高波动风险**。强烈建议先在 OKX **DEMO 模拟盘** 环境下完成全流程回测与沙箱验证，再评估实盘接入。

---

## 🌟 系统核心亮点

- 🧠 **LLM-Native AI 全权决策主脑**：彻底废除机械死板数值阈值，采用原生高思维链推演（支持 OpenAI o1/o3/o4、Gemini Flash High、Claude 3.7 Sonnet、DeepSeek-R1 等）。每 15 分钟聚合多周期 K 线、微积分因果微结构、OBV/VWAP 动能与全网突发资讯，生成高确定性波段决策。
- 🏛️ **多模型参谋决策委员会（Council Pro）**：告别单一模型决策幻觉！支持 N 席位多模型并发辩论博弈（动量进攻官、极端风控官、量化数理官、舆情侦察官、宏观策略官、盘口微结构官），提供**加权共识、一票否决、动能突破优先**三大决策模式，由首席仲裁官收敛输出。
- 🛡️ **Python 原生物理拦截插件管线（Fail-Closed Hard Risk Interceptors）**：执行层绝对物理防线！4H 顺势铁律（逆势强制否决）、单笔风险几何 $R:R \ge 2.0$ 强校验、80% 置信度门禁、震荡市 ADX 过滤；支持自定义 Python 插件热插拔、AST 语法静态校验与现场沙箱回归回放。
- 🪙 **动态资产标的池全链原子同步（Dynamic Trading Universe）**：支持用户在后台自由增删交易标的（如接入 ASTER、下架 LINK）。底层状态毫秒级就地原子刷新，多因子矩阵、因果雷达与快讯舆情引擎自适应伸缩渲染。
- ⚡ **100% 交易所云端 OCO 止盈止损**：开仓即挂设交易所原生云端条件单（Take-Profit / Stop-Loss），杜绝本地服务器故障、断网或进程奔溃带来的敞口风险；支持大模型实时动态上移保本止损（UPDATE_SL）。
- 🧬 **启发式自进化长期记忆（Self-Evolution Engine）**：每日深夜自动穿透成交损益流水深度反思，进行归因复盘与证伪推演，提炼生成 `data/AI_TRADING_MEMORY.md` 实战心法；时效覆盖机制驱动下一轮推演自动加载最新认知，形成正向增强闭环。
- 🌓 **现代暗黑/亮色双模量化终端（Vue 3 + Vite + Tailwind CSS）**：对冲基金级 Glassmorphism 磨砂质感终端，支持深浅双模无缝切换；独立 Bento 资产面板、机构级极细横向防爆滑动条、单行无折行成交台账与移动端目录抽屉。
- 🔒 **企业级端到端安全基座（Enterprise Security Hardening）**：PBKDF2-SHA256 账号认证与恒定时间防枚举对比；敏感账本与持仓鉴权隔离；环境变量与 Webhook Token 自动掩码；路径越界物理防御；Cloudflare 边缘分级微缓存（Micro-Caching）与源站防爬虫锁。

---

## 📸 核心功能界面一览

### 1. 机构级实盘监控大屏（Frontend Matrix Dashboard）
*全新单行沉浸顶栏，四大财务 HUD 核心指标卡解耦直连；100% 全宽展开在途持仓明细（双行排版清晰舒展、云端止损盾牌与浮盈 ROI 实时透视）；在途 Maker 限价挂单监控与多币种因果动力学微结构矩阵一览无余。*

![前台实盘矩阵终端](docs/images/dashboard_trading.png)

---

### 2. 🏛️ 多模型决策委员会（Multi-Agent Council）
*支持多参谋多线程并发辩论博弈：**动量进攻官**（寻找 Alpha 突破）、**保守风控官**（量价背离与一票否决权）、**量化数理官**（ADX/微积分纯数学门禁）、**舆情侦察官**、**宏观策略官**与**盘口微结构官**各司其职，最终由**首席终审仲裁官**权衡收口，严格输出标准化交易发单契约。支持席位全动态 CRUD、独立模型绑定与现场沙箱辩论测试。*

![多模型委员会决策系统](docs/images/admin_council.png)

---

### 3. 🛡️ 物理拦截插件中心（Interceptors Safety Pipeline）
*代码级执行前硬阻断！所有进入 OKX 交易所的发单指令必须通过顺序链式拦截器，任一插件判定 REJECT 则立即终止交易执行。内置现场沙箱测试，可直接载入最近推演决策回放执行并生成审计报告。*

![物理拦截插件中心](docs/images/admin_interceptors.png)

---

### 4. ⌘ 提示词策略工作室与变量插槽系统（Prompt Studio）
*拒绝死板黑盒！四大消息管线模块化拖拽编排、P0 核心风控物理联动；内置变量快速插入条与变量字典手册，支持将策略一键导出为 JSON 分享，或一键导入社区策略包；右侧提供「实发效果」与「模板源码」毫秒级双模对照。*

![提示词策略工作室与变量插槽](docs/images/admin_prompt_studio.png)

---

### 5. 🧬 自进化实验室与长期记忆库（Self-Evolution Engine）
*每日深夜读取全量真实平仓流水深度反思，进行痛点归因与逻辑推演，自动提炼生成 `data/AI_TRADING_MEMORY.md` 启发式实战心法；具备智能时效覆盖与动态淘汰机制，下一轮交易周期自动在提示词插槽中加载最新认知，形成“实战 → 复盘 → 提炼 → 进化”的飞轮。*

![自进化实验室与长期记忆库](docs/images/self_evolution_memory.png)

---

## 🏗️ 系统全景架构设计

```
┌────────────────────────────────────────────────────────────────────────┐
│                        R20 QUANTUM TRADER 体系全景                      │
├────────────────────────────────────────────────────────────────────────┤
│ 【数据层】                                                              │
│  • OKX V5 官方 REST/WebSocket 原生行情与私有仓位                        │
│  • 全网突发资讯与要闻情绪倾向采集器 (news_sentiment_harvester)           │
│  • 因果动力学速度/加速度/加加速度 (v, a, j) + 定积分能量储备 (E, A)       │
│  • 经典量化五大因子库：OBV 资金流向 / VWAP 乖离率 / ATR(14) / RSI / ADX  │
├────────────────────────────────────────────────────────────────────────┤
│ 【智能决策中枢】                                                        │
│  • 提示词引擎：语义变量插槽动态渲染 ({{news_intelligence}}, {{memory}}) │
│  • 模型委员会：N 参谋席位并发辩论 + 长思考链交叉审视 + 首席仲裁统一收口     │
│  • 策略基线：收敛于「全维度波段强化版」，杜绝预设发散与过度拟合          │
│  • 供应商网关：统一协议兼容 OpenAI / Gemini / Claude / DeepSeek / 本地   │
├────────────────────────────────────────────────────────────────────────┤
│ 【执行与风控防线】(Fail-Closed 物理硬阻断)                              │
│  • 物理拦截管线：4H顺势铁律 / 80%置信度门禁 / ADX震荡熔断 / 2.0R几何保护 │
│  • 交易执行层：Maker 限价挂单入场 + 动态撤重挂 + 100% 交易所云端 OCO   │
│  • 三级熔断哨兵：极端黑天鹅舆情正则 / 账户回撤 3% 刹车 / 连败强制冷却   │
│  • 自进化引擎：每日北京时间 20:00 深度复盘，原子覆盖更新实战记忆心法    │
├────────────────────────────────────────────────────────────────────────┤
│ 【控制面与监控展现】                                                    │
│  • 前端：Vue 3 + Vite + Tailwind CSS 纯静态轻量 SPA (0 Node.js 运行时负担) │
│  • 后台：FastAPI 异步控制面 + PBKDF2-SHA256 账号认证 + 全量操作审计     │
│  • 边缘微缓存：静态资源 1 年不可变，实时数据 3 秒微缓存，管理路由零缓存   │
│  • 多渠道告警：企业微信 / Telegram (反代) / QQ 官方机器人 / 通用 Webhook │
│  • 异地灾备：预对账 + SHA-256 校验 + 百度网盘/S3/WebDAV 指数退避同步    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🔒 企业级安全与防护体系

安全与资产保全是量化交易的第一铁律。R20 Quantum Trader 践行全栈 **Fail-Closed** 安全哲学：

1. **凭证隔离与脱敏机制**：
   - 真实的 OKX API Key/Secret/Passphrase 以及模型凭证严格隔离在本地 `.env` 与加密存储中，受到 `.gitignore` 物理隔离，严防代码外泄；
   - 控制台查询接口（`/api/v1/admin/notifications`、`/api/v1/admin/config`）对 Webhook Key、Token 与密码实施全自动脱敏掩码（如 `mask_url()`），防前端窥探。
2. **鉴权与防暴力破解加固**：
   - 管理后台基于标准 PBKDF2-SHA256 密钥推导算法（100,000 次哈希加盐）+ 服务端安全会话（`X-R20-Session`）；
   - **恒定时间防时序攻击**：针对不存在的用户引入虚拟 Dummy 哈希运算，彻底消除通过请求响应耗时探测枚举管理员账号的侧信道漏洞；
   - 连续 5 次密码错误自动触发 15 分钟账号物理锁定。
3. **私密财务账本鉴权拦截**：
   - `/api/v1/cache/ledger` 包含历史交易收益与平仓台账，强制挂载 `require_admin_header` 鉴权门禁，严禁公开匿名调取。
4. **路径穿越与越界硬防御**：
   - 针对插件管理（`/interceptors/*`）与前端 SPA 深链加载，引入基于 Python 标准库 `Path.resolve().is_relative_to()` 的严格物理边界校验，杜绝任何 `../` 目录穿越攻击。
5. **反爬虫锁与分级 CDN 缓存**：
   - `/robots.txt` 规范爬虫行为，严格禁止抓取 `/admin/` 与 `/api/`；
   - 静态资源 1 年不可变缓存，前台实时数据端点 3 秒边缘微缓存，管理路由严格配置 `private, no-store`。

---

## 🚀 极速部署指南

### 1. 克隆代码仓库

```bash
git clone https://github.com/555cute/r20-quantum-trader.git
cd r20-quantum-trader
```

### 2. 环境配置与依赖安装

推荐使用 Python 3.10 或更高版本：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp env.example .env
chmod 600 .env
```

编辑 `.env` 文件填入核心参数：

```dotenv
# 大模型推演连接 (支持 OpenAI / Claude / Gemini / DeepSeek 等主流供应商)
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your_llm_api_key
LLM_MODEL=gemini-3.8-flash-high
LLM_REASONING_EFFORT=high

# 交易所环境选择 (demo 模拟盘 / live 实盘)
R20_OKX_ENV=demo
OKX_DEMO_API_KEY=your_demo_api_key
OKX_DEMO_SECRET_KEY=your_demo_secret_key
OKX_DEMO_PASSPHRASE=your_demo_passphrase

# 超级管理员初始化 Token (首次登录后台控制台生成账号时使用)
R20_SETUP_TOKEN=your_secure_random_token
```

### 4. 启动系统

```bash
# 启动统一管理控制面与监控大屏
./scripts/start_standalone.sh
# 或直接通过 uvicorn 启动:
python3 -m uvicorn r20_backend.app:app --host 0.0.0.0 --port 8080
```

- 🌐 **前台实盘大屏**：`http://localhost:8080/`
- 📖 **官方图文文档**：`http://localhost:8080/docs`
- 🎛️ **管理控制台**：`http://localhost:8080/admin`

---

## ⚙️ 核心任务调度（Cron 定时建议）

系统自带内置轻量级 Scheduler，若需配合 Linux 系统原生 `crontab` 调度，可参考如下最佳实践：

```bash
# 每 15 分钟触发一次 AI 决策推演与风控巡检
*/15 * * * * cd /path/to/r20-quantum-trader && /path/to/.venv/bin/python3 scripts/ai_factor_trader.py >> logs/ai_factor_trader.log 2>&1

# 每日北京时间 20:00 执行自进化反思复盘（提炼心法迎战夜盘高波动）
0 12 * * * cd /path/to/r20-quantum-trader && /path/to/.venv/bin/python3 scripts/self_improvement_engine.py >> logs/self_improvement.log 2>&1

# 每日凌晨 02:00 异地容灾与账本预对账打包上传
0 18 * * * cd /path/to/r20-quantum-trader && /path/to/.venv/bin/python3 scripts/nightly_backup_and_clean.py >> logs/backup.log 2>&1
```

---

## 🧪 测试与质量保障

系统内置覆盖核心全链路的自动化测试套件，全面检验数理微积分计算、OKX 签名、消息网关、提示词插槽渲染、物理拦截插件沙箱与后台权限安全：

```bash
# 执行全量 166 项自动化回归测试
/path/to/.venv/bin/python3 -m unittest discover -s tests -p "test_*.py"
```

```text
......................................................................................................................................................................
----------------------------------------------------------------------
Ran 166 tests in 29.002s

OK
```

---

## 🤝 社区交流与支持

- **🐧 LINUX DO 社区**：[linux.do](https://linux.do/)（感谢社区量化极客与技术佬友的大力支持与交流！）
- **💬 QQ 官方交流群**：**`655973677`**
- **👨‍💻 作者 QQ**：`1090188816`
- **🐛 Issue & 提案**：欢迎提交 [GitHub Issues](https://github.com/555cute/r20-quantum-trader/issues)

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 协议开源。
