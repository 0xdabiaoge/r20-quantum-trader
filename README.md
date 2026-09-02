<div align="center">

# R20 Quantum Trader

### 面向 OKX 永续合约的 LLM 原生量化交易系统

**独立 Gateway · 多因子推演 · 极速内存直出 · 管理控制面 · QQ 官方 Bot 扫码绑定 · 模块化提示词 · 加密灾备**

[![Release](https://img.shields.io/badge/release-v6.2.0-3875F6?style=flat-square)](https://github.com/555cute/r20-quantum-trader/releases/tag/v6.2.0)
[![QQ Group](https://img.shields.io/badge/QQ%E4%BA%A4%E6%B5%81%E7%BE%A4-655973677-12B7F5?style=flat-square&logo=tencent-qq&logoColor=white)](#-社区与致谢)
[![LINUX DO](https://img.shields.io/badge/Community-LINUX%20DO-F97316?style=flat-square&logo=linux&logoColor=white)](https://linux.do/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Exchange](https://img.shields.io/badge/Exchange-OKX%20V5%20Direct-111827?style=flat-square)](https://www.okx.com/)
[![Tests](https://img.shields.io/badge/tests-135%2F135%20passed-0ECB81?style=flat-square)](#-验证与测试)
[![License](https://img.shields.io/badge/license-MIT-10B981?style=flat-square)](LICENSE)

[🌐 在线实盘大屏](https://www.r20.cn/) · [🚀 独立部署指南](STANDALONE.md) · [📦 灾备恢复](RECOVERY_GUIDE.md) · [🐧 LINUX DO 社区](https://linux.do/)

<br/>

> 💬 **QQ 官方交流群**：**`655973677`** ｜ **作者 QQ**：`1090188816` ｜ 欢迎进群交流策略调优与实盘动态！

</div>

---

![R20 v6.2.0 机构级量化终端](docs/images/dashboard_trading.png)

> [!WARNING]
> R20 是研究型自动化量化交易开源项目，不构成任何投资建议，亦不承诺任何收益。强烈建议在 OKX **DEMO 模拟盘** 环境下完成策略验证、风控测试、QQ 扫码通知与灾备演练后，再评估是否接入实盘。

---

## 📸 产品界面展示

### 1. 实盘矩阵大屏（前台监控终端）
*官方账户总权益、净收益、今日战绩、持仓浮盈、在途限价挂单监控与云端 OCO 100% 保护状态一览无余，内置实时遥测时钟与状态呼吸灯。*

![前台实盘矩阵](docs/images/dashboard_trading.png)

### 2. AI 全维因子推演矩阵
*覆盖因果微积分动力学（速度 $v$、加速度 $a$、冲量 $I$、加加速度 $j$）、定积分能量学（做功 $E$、偏离面积 $A$）、概率论延续度与 OKX Top100 聪明钱主力持仓均价及多空胜率。*

![AI 全维因子矩阵](docs/images/dashboard_factors.png)

### 3. 模块化提示词策略工作室（核心亮点）
*拒绝死板黑盒！后台支持稳健/激进/自定义多方案热切换；交易与自进化的 4 条消息管线（System/User）模块化自由编排、正文编辑、安全校验与右侧实发 Prompt 毫秒级拼装对照。*

![模块化提示词策略工作室](docs/images/admin_prompt_studio.png)

---

## 🛠️ 核心能力概览

| 模块维度 | 当前特性与规格 |
|---|---|
| **交易标的** | 默认覆盖 BTC、ETH、SOL、DOGE、SUI、LINK 六大主流高流动性合约，支持后台动态增删 |
| **数理基石** | 微积分动力学、定积分能量学、概率论风险评估（VaR / CVaR）、微观买卖盘口深度比 |
| **聪明钱透视** | OKX Top100 实盘主力加权多空占比、主力资金净流向、多头均价、空头均价与多空胜率 |
| **大模型大脑** | OpenAI 兼容接口（Gemini 3.7 Flash High / GPT-4o / Claude 3.5），输出严格合规 JSON 决策 |
| **交易执行层** | OKX V5 原生直签、Maker 限价低费率挂单、动态撤单重挂、100% 交易所云端 OCO 双向止盈止损 |
| **多通道通知** | **QQ 官方 Bot（支持手机扫码一键绑定）**、企业微信机器人、Telegram Bot、通用 Webhook |
| **多后端灾备** | Kopia 极简设计、scrypt + AES-256-GCM 强加密、定时自动快照、清单校验与只读演练 |
| **架构与性能** | FastAPI 异步控制面 + 内存预热直出（17ms 响应）+ 原生 Gateway Scheduler |

---

## 🚀 极速部署指南

### 1. 克隆代码仓库

```bash
git clone https://github.com/555cute/r20-quantum-trader.git
cd r20-quantum-trader
```

### 2. 运行自动化部署脚本

```bash
# 推荐一键部署：自动配置 Python 虚拟环境与依赖
./deploy/install.sh
```

或手动执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 环境变量配置

```bash
cp env.example .env
chmod 600 .env
```

配置核心参数：

```dotenv
# 大模型推演连接 (OpenAI 兼容接口)
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your_llm_api_key
LLM_MODEL=gemini-3.7-flash-high
LLM_REASONING_EFFORT=high

# 交易所环境选择 (demo 模拟盘 / live 实盘)
R20_OKX_ENV=demo
OKX_DEMO_API_KEY=
OKX_DEMO_SECRET_KEY=
OKX_DEMO_PASSPHRASE=

# 超级管理员初始化 Token
R20_SETUP_TOKEN=your_secure_random_token
```

### 4. 启动系统

```bash
# 启动统一管理后端与监控大屏
python3 -m uvicorn r20_backend.app:app --host 0.0.0.0 --port 8080
```

- 🌐 前台大屏：`http://localhost:8080/`
- 🎛️ 后台管理：`http://localhost:8080/admin`

---

## 🧪 验证与测试

系统内置完善的单元测试与回归测试套件，全面覆盖数理微积分、OKX 签名与交易服务、QQ 扫码加密解密、提示词管线与后台 API 鉴权：

```bash
# 运行全量 135 项自动化测试
python3 -m unittest discover -s tests
```

```text
----------------------------------------------------------------------
Ran 135 tests in 27.28s

OK
```

---

## 🤝 社区与致谢

- **🐧 LINUX DO 社区**：[linux.do](https://linux.do/)（感谢社区各位佬友的大力支持与开源认可！）
- **💬 QQ 官方交流群**：`655973677`
- **👨‍💻 作者 QQ**：`1090188816`
- **🐛 问题反馈**：[GitHub Issues](https://github.com/555cute/r20-quantum-trader/issues)

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 协议开源。
