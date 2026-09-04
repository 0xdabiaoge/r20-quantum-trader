<div align="center">

# ⚡ R20 Quantum Trader

### 面向 OKX 永续合约的机构级 LLM 原生量化交易终端与多模型参谋系统

**全栈用户自由自定义 · 多模型决策委员会 · 动态标的资产池 · Python 物理拦截管线 · 启发式自进化防污染护栏 · 100% 交易所云端 OCO**

[![Release](https://img.shields.io/badge/release-v7.2.1-3875F6?style=flat-square)](https://github.com/555cute/r20-quantum-trader/releases)
[![LINUX DO](https://img.shields.io/badge/Community-LINUX%20DO-F97316?style=flat-square&logo=linux&logoColor=white)](https://linux.do/)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Exchange](https://img.shields.io/badge/Exchange-OKX%20V5%20Direct-111827?style=flat-square)](https://www.okx.com/)
[![Docker](https://img.shields.io/badge/Docker-Multi--Stage%20Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](#-极速部署指南)
[![Tests](https://img.shields.io/badge/tests-172%2F172%20passed-0ECB81?style=flat-square)](#-测试与质量保障)
[![Security](https://img.shields.io/badge/Security-Fail--Closed%20Audit-10B981?style=flat-square)](#-企业级安全与防护体系)
[![License](https://img.shields.io/badge/license-MIT-10B981?style=flat-square)](LICENSE)

[🌐 在线实盘大屏](https://www.r20.cn/) · [📖 官方图文开发指南](/docs) · [🚀 快速部署手册](#-极速部署指南) · [🐧 LINUX DO 社区](https://linux.do/)

<br/>

> 💬 **QQ 官方交流群**：**`655973677`** ｜ **作者 QQ**：`1090188816` ｜ 欢迎进群交流量化模型、提示词编写、微积分动力学因子与实盘动态！

</div>

---

![R20 机构级量化终端全景](https://raw.githubusercontent.com/555cute/r20-quantum-trader/main/docs/images/dashboard_trading.png)

> [!WARNING]
> R20 Quantum Trader 是面向加密货币市场的开源量化交易系统，致力于为个人交易员与量化团队提供高透明度、高度自由自定义、自进化与工业级的波段交易底座。**软件不构成任何投资建议，数字资产交易具有极高波动风险**。强烈建议先在 OKX **DEMO 模拟盘** 环境下完成全流程回测与沙箱验证，再评估实盘接入。

---

## 🌟 系统核心特性与设计哲学

传统量化软件往往是黑盒且逻辑写死的，而 R20 将「高胜率顺势算法」与「全链路用户自由自定义（User-Customizable First）」深度融为一体，将策略制定权、模型组合权、风控门禁权与记忆沉淀权 100% 完整交还给交易员：

### 1. 🧠 顺势高胜率提示词策略与 100% 自由编排工作室
- **抗噪宽止损体系**：止损强制外扩至结构外 **1.8x ~ 2.2x 1H ATR**（或 1.8%~3.0% 安全垫），宁可调降杠杆至 2x~3x，也给足波动呼吸空间，彻底隔绝 15M/5M 杂波插针扫损。
- **0.8R 浮盈保本移损（BE 锁死胜率）**：持仓浮盈一旦达 **0.8R ~ 1.0R**（或 ROI 达 +1.0%），无论多单还是空单，必须坚决触发 `UPDATE_SL` 移动至开仓成本保本位，最坏结果 0 亏损出场，杜绝盈利单回吐反转。
- **多空对称顺势主轴**：4H/1H 多头通道专注顺势回踩均线/支撑位低吸挂多，4H/1H 空头通道专注反弹承压阻力位逢高挂空，箱体震荡边界双向高抛低吸；执行层门禁科学设在 75%，形态达标自信标定 78%~88%，破除机械空仓。
- **全自由可视化编排（Prompt Studio）**：从底层解耦硬编码，前台可视化工作室自由编辑 **「交易 System」** 军规与 **「交易 User」** 行情拼装，内置变量插槽快速注入条（`{{macro_4h}}`、`{{calculus_1h}}`、`{{adx_1h}}` 等），支持 JSON 方案一键导入、导出与双模实时对照。

### 2. 🛡️ 独立的 AI 自进化认知中枢与白盒防污染护栏 (Evolution Shield)
- **宪法级防偏见审查（Constitution Linter）**：在复盘提炼阶段硬性阻断“极端做多/做空偏见”、“违规抗单放大止损”、“马丁格尔倍投”等危险认知，杜绝极端单边暴跌或插针行情反噬带偏大模型；
- **极端离群噪点过滤（Outlier Rejection）**：单笔插针与偶发亏损判定为市场随机噪点，禁止仅凭单笔事件制造新心法，必须具备连续样本支持；
- **白盒心法生命周期管理**：后台（`/admin/evolution`）落地结构化透明卡片，支持**心法单项热插拔启停开关（Toggle Switch）**，秒级休眠或激活任一实战心法；
- **敏锐半衰期机制（TTL 7~14 天）**：黄金基准 14 天半衰期，动态战术心法 7 天敏锐半衰期，配合动态健康评分体系快速淘汰过时经验；
- **一键黄金基准回滚（Emergency Rollback）**：遭遇突发极端行情时，支持一键将心法知识库瞬时恢复至官方黄金基准，实现安全“解毒”。

### 3. 🛡️ Python 原生物理拦截插件管线与沙箱热插拔
- **Fail-Closed 物理硬阻断防线**：任何大模型推演决策必须穿透物理拦截链，任一插件返回 REJECT 立即安全降级为 WAIT。内置 4H 顺势铁律（逆势一票否决）、单笔风险收益比 $R:R \ge 2.0$ 几何门禁、75% 置信度基准、ADX 震荡猴市过滤。
- **插件热插拔与现场沙箱**：基于标准 Python 插件协议（`check_risk(package, decision, context) -> tuple[bool, str]`），无需重启服务即可热加载生效；后台提供代码在线编辑、AST 静态语法校验，支持载入最近真实推演决策现场沙箱回放。

### 4. 🏛️ 多模型决策委员会（Council Pro · 席位自由指派）
- **多参谋并发辩论与博弈**：告别单一模型幻觉！支持 6 大参谋席位并发推演（动量进攻官、极端风控官、量化数理官、舆情侦察官、宏观策略官、盘口微结构官），由首席终审官权威裁决收敛。
- **席位人设与模型完全解耦**：管理员可自由增删、重命名席位，自由将任意供应商的大模型指派给特定席位（如风控席位指派 Claude 3.7，进攻席位指派 o3-mini，量化席位指派 DeepSeek-R1）；各席位自动继承专有的思考推演深度。

### 5. 🔌 精炼三基础渠道与开放模型连接矩阵
- **极简三渠道 + 任意自定义扩展**：移除冗余死板预设，仅保留 OpenAI、Claude、Gemini 三大核心通道，支持自由添加任意第三方或自建聚合 API（OneAPI、NewAPI、SiliconFlow 等）。
- **动态模型探测与协议自由解耦**：免二次密钥输入，自动继承已存凭据秒级拉取远程 400+ 模型；API 通信协议支持自由切换（OpenAI Chat / OpenAI Responses / Claude Messages）；针对前沿旗舰模型自适应开放 xhigh / max 极限推演。

### 6. 💾 企业级备份、下载与一键全量恢复
- **本地打包下载与外部包上传**：支持本地/云端全量数据灾备，后台归档列表支持一键流式打包下载 `.tar.gz` 至个人电脑，并支持上传本地外部备份压缩包。
- **一键全量恢复与安全回滚**：输入二次安全确认码即可一键全量解压恢复系统配置、历史数据与策略方案，内置严格的路径遍历（Path Traversal）安全审计防护。

### 7. 🎨 现代工程基底、容器化编排与美学体验
- **无技术债统一前端**：彻底清理历史双前端单文件，全站统一由现代化 Vue 3 + Vite + TypeScript SPA 接管，深色/浅色双模自适应高对比度；优雅点缀原生加密货币微徽（`₿` 图腾）；
- **生产级 Docker 编排**：内置多阶段轻量构建 `Dockerfile` 与 `docker-compose.yml`，支持一键容器化秒级部署与健康检查监控；
- **CI/CD 自动化流水线**：配套 GitHub Actions 矩阵测试流，精确定制依赖锁，防范供应链漂移。

---

## 📸 核心系统界面全景

### 1. ⌘ 提示词策略工作室（Prompt Studio · 100% 自由编排）
*聚焦交易主脑核心管线！专注于「交易 System 规则纪律」与「交易 User 实时行情快照拼装」；内置语义插槽工具条与变量字典手册，支持将策略一键导出为 JSON 分享或导入社区策略包；右侧提供「实发效果」与「模板源码」毫秒级双模对照。*

![提示词策略工作室](https://raw.githubusercontent.com/555cute/r20-quantum-trader/main/docs/images/admin_prompt_studio.png)

---

### 2. 🧬 独立的 AI 自进化认知中枢与白盒心法管理（Evolution Shield）
*涵盖复盘官 System 角色定位、战绩证据 User 模版；直观监控每 6 小时自动复盘计划；内置白盒心法生命周期卡片，支持单项热拔插启停、健康评分展示与突发极端行情一键回滚基准。*

![自进化配置与实战心法面板](https://raw.githubusercontent.com/555cute/r20-quantum-trader/main/docs/images/admin_evolution.png)

---

### 3. 🛡️ 物理拦截插件中心（Interceptors Safety Pipeline · 自由热插拔）
*代码级执行前硬阻断！所有进入 OKX 交易所的发单指令必须通过顺序链式拦截器，任一插件判定 REJECT 则立即终止交易执行。配置 75% 置信度基准门禁与 4H 宏观顺势铁律，支持现场沙箱测试，可直接载入最近推演决策回放执行并生成审计报告。*

![物理拦截插件中心](https://raw.githubusercontent.com/555cute/r20-quantum-trader/main/docs/images/admin_interceptors.png)

---

### 4. 🏛️ 多模型决策委员会（Council Pro · 席位自由指派）
*多参谋多线程并发辩论博弈：动量进攻、保守风控、量化数理、舆情侦察、宏观策略与盘口微结构各司其职，最终由首席终审仲裁官权衡收口。支持席位动态增删、全量动态模型自由绑定与思考深度自动继承。*

![多模型委员会决策系统](https://raw.githubusercontent.com/555cute/r20-quantum-trader/main/docs/images/admin_council.png)

---

### 5. 🔌 模型连接与供应商矩阵（LLM Connections · 自由扩展渠道）
*极简且强大的模型接入体系：仅保留 OpenAI、Claude、Gemini 三大基础渠道，支持任意自定义供应商扩展；采用真实 API 通信协议下拉矩阵；自动继承已存凭据秒级拉取远程 400+ 模型；针对前沿旗舰模型自适应开放 xhigh / max 极限推演。*

![模型连接与供应商矩阵](https://raw.githubusercontent.com/555cute/r20-quantum-trader/main/docs/images/admin_llm.png)

---

### 6. 机构级实盘监控大屏（Frontend Workstation）
*全新单行沉浸顶栏，四大财务 HUD 核心指标卡解耦直连；100% 全宽展开在途持仓明细（双行排版清晰舒展、云端止损盾牌与浮盈 ROI 实时透视）；在途 Maker 限价挂单监控与六币因果动力学微结构矩阵横向自适应平整铺满。*

![前台实盘矩阵终端](https://raw.githubusercontent.com/555cute/r20-quantum-trader/main/docs/images/dashboard_trading.png)

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
│ 【智能决策中枢】(100% 用户自由编排与多模型参谋)                        │
│  • 提示词策略：多空对称顺势 + 1.8~2.2x ATR 抗噪宽止损 + 0.8R 浮盈保本移损 │
│  • 模型委员会：N 参谋席位自由增删 + 跨厂商模型自由绑定 + 首席仲裁统一收口 │
│  • 自进化认知：Evolution Shield 防污染护栏 + 白盒心法单项启停 + 7~14d半衰期│
│  • 供应商网关：OpenAI / Gemini / Claude 核心渠道 + 任意自定义扩展通道   │
├────────────────────────────────────────────────────────────────────────┤
│ 【执行与风控防线】(Fail-Closed 物理硬阻断 + 插件自由热插拔)             │
│  • 物理拦截管线：4H顺势铁律 / 75%置信度门禁 / ADX震荡熔断 / 2.0R几何保护 │
│  • 交易执行层：Maker 限价挂单入场 + 动态撤重挂 + 100% 交易所云端 OCO   │
│  • 灾备与恢复：备份包本地打包下载 / 外部归档上传 / 一键安全全量恢复     │
├────────────────────────────────────────────────────────────────────────┤
│ 【控制面与监控展现】                                                    │
│  • 前端：Vue 3 + Vite + Tailwind CSS 纯静态轻量 SPA (宽屏横向6列铺满)   │
│  • 双模对比度：钛金深黑 / 极光亮色双模高对比度，原生点缀 ₿ 极客图腾     │
│  • 缓存机制：HTML 入口 no-cache 直连，数据轮询时间戳防脏读，CF 边缘加速 │
│  • 后台：FastAPI 异步控制面 + PBKDF2-SHA256 账号认证 + 全量操作审计     │
│  • 多渠道告警：企业微信 / Telegram (反代) / QQ 官方机器人 / 通用 Webhook │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🔒 企业级安全与防护体系

1. **账户鉴权与恒定时间比对**：
   - 管理后台基于安全会话机制，弃用不安全的通用静态明文 Header。
   - 所有登录认证与密码核验强制采用 `hmac.compare_digest` 恒定时间比对，彻底免疫针对登录接口的时序攻击（Timing Attack）。
2. **私有账本与资产数据防泄露**：
   - `/api/v1/cache/ledger` 包含历史交易收益与平仓台账，强制挂载 `require_admin_header` 鉴权门禁，严禁公开匿名调取。
   - 包含敏感信息的 API 端点全部下发 `Cache-Control: private, no-cache, no-store, must-revalidate`，杜绝 Cloudflare 或任何中间代理节点意外缓存私人交易隐私。
3. **Webhook 凭证与敏感环境变量自动掩码**：
   - 飞书、钉钉、企业微信、Telegram、Discord 及 QQ 机器人的 Webhook 地址在控制台与接口返回时，系统自动执行不可逆安全掩码（如 `https://qyapi.weixin.qq.com/...***MASKED***`），杜绝开发者截屏泄露。
4. **路径穿越防护（Path Traversal Hardening）**：
   - 拦截器文件名与备份恢复归档路径严格限制为文件名本身，校验任何带有绝对路径、`../`、`..\\` 的非法请求并直接抛出 400 阻断。
5. **Fail-Closed 交易所 OCO 终极兜底**：
   - 开仓即挂设交易所原生云端条件单（Take-Profit / Stop-Loss）。若云端 OCO 挂单缺失或网络故障无法修复，系统执行器坚决触发 **Fail-Closed 安全平仓**，绝不在没有止损保护的情况下暴露裸头寸。

---

## 🧪 测试与质量保障

系统配套有高覆盖度的全栈回归测试集，覆盖数学微积分因果律、多因子量化、多模型委员会、提示词编排、API 鉴权、物理拦截沙箱、Evolution Shield 防污染护栏、备份恢复与网关调度：

```bash
# 执行全量单元与系统回归测试
python3 -m unittest discover -s tests -p "test_*.py"
```

**测试通过状态：`172 / 172 Passed` (100% 通过率)**

---

## 🚀 极速部署指南

### 方式 A：Docker Compose 一键部署（推荐）
系统内置完整的多阶段构建轻量镜像与服务编排方案：

```bash
# 1. 克隆代码
git clone https://github.com/555cute/r20-quantum-trader.git
cd r20-quantum-trader

# 2. 配置环境变量
cp .env.example .env
vim .env

# 3. 一键构建并启动
docker compose up -d
```

---

### 方式 B：传统 Python 源码部署

#### 1. 环境依赖
- Linux 服务器 (Debian 11+ / Ubuntu 22.04+ 推荐)
- Python 3.10+
- Node.js 18+ (仅用于前端源码二次构建，直接运行生产已编译包无需 Node)

#### 2. 初始化虚拟环境并安装依赖
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 3. 配置核心环境变量
复制 `.env.example` 为 `.env`，填入您的 OKX API 与 大模型 API 密钥：
```bash
cp .env.example .env
vim .env
```
主要变量说明：
- `OKX_API_KEY` / `OKX_SECRET_KEY` / `OKX_PASSPHRASE`：OKX 官方 API 凭据
- `OKX_SIMULATED`：`1` 为 DEMO 模拟盘，`0` 为真实盘
- `LLM_BASE_URL` / `LLM_API_KEY`：默认大语言模型接口与密钥

#### 4. 启动控制台与交易调度
```bash
# 启动 FastAPI 控制面服务 (默认监听 8080 端口)
uvicorn r20_backend.app:app --host 0.0.0.0 --port 8080

# 启动多任务网关调度器 (负责 15M 巡检与每 6 小时自进化复盘)
python3 r20_gateway/worker.py
```

访问浏览器 `http://你的服务器IP:8080/` 即可进入实盘监控终端；访问 `/admin` 登录管理控制台。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源协议分发与使用。
