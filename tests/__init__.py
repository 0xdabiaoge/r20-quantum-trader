"""测试环境统一隔离。

生产 .env 可能带有用户经后台「风控管理页」应用的套件/自定义覆盖值（R20_* 风控键），
而全部引擎测试的断言基线是代码默认值。本模块在 discover 导入任何测试模块之前：
1) 先正常 import r20_backend.config，完成真实 .env 加载（OKX/LLM/QQ 等配置是测试需要的）；
2) 禁用后续 load_dotenv 回灌（refresh_settings/update_env 每次都会调用它）；
3) 用静态键表从进程环境剥离全部风控覆盖键——必须在 import risk_constants 之前完成，
   因为其常量在 import 时一次性绑定；
4) 再首次导入 risk_constants（此时得到代码默认基线），并断言静态键表与单一事实源一致。
"""
import os
import tempfile

# 审计卫生（2026-09-13 清积压）：audit.py / self_improvement_engine.log_msg 的
# 路径此前是模块级硬编码、不可重定向，走 TestClient 的后台测试把伪造记录直写
# 生产 logs/r20_admin_audit.jsonl（实测 2000+ 条 testclient）与
# self_improvement.log（fake "corrupt" 行）。二者已改为调用时读环境变量；这里
# 在 discover 导入任何测试模块之前把变量指到会话级临时目录，一次性隔离所有
# 此类落盘副作用（律①：测试不触生产文件）。
_TEST_SANDBOX = tempfile.mkdtemp(prefix="r20-tests-")
os.environ.setdefault("R20_AUDIT_FILE", os.path.join(_TEST_SANDBOX, "r20_admin_audit.jsonl"))
os.environ.setdefault("R20_SELF_IMPROVEMENT_LOG", os.path.join(_TEST_SANDBOX, "self_improvement.log"))
# 批E(2026-09-13)：仪表盘载荷构建在台账 >60s 未更新时会 spawn 真实台账同步子进程
# （打三所接口 + 重写 data/trading_ledger.json）。仪表盘相关测试走真实 DATA_DIR，
# 于是测试会打真网络并改写生产台账——同款隔离：默认禁用该触发点。生产不设此变量。
os.environ.setdefault("R20_LEDGER_SYNC_DISABLED", "1")

import r20_backend.config as _config

_config.load_dotenv = lambda path: None

_RISK_KEYS_STATIC = (
    "R20_PORTFOLIO_RISK_BUDGET_USDT",
    "R20_MAX_CONCURRENT_POSITIONS", "R20_MAX_SAME_DIRECTION_POSITIONS",
    "R20_MAX_MARGIN_EQUITY_RATIO", "R20_SINGLE_ASSET_EQUITY_RATIO",
    "R20_MAX_SINGLE_ASSET_MARGIN_USDT", "R20_MAX_LEVERAGE", "R20_MIN_LEVERAGE",
    "R20_RISK_PER_TRADE_RATIO", "R20_MIN_RISK_REWARD", "R20_MIN_ENTRY_CONFIDENCE",
    "R20_MAX_DAILY_LOSS_USDT", "R20_DAILY_LOSS_EQUITY_RATIO",
    "R20_TIME_STOP_HOURS", "R20_TIME_STOP_ATR_BAND", "R20_STOP_COOLDOWN_MINUTES",
    "R20_MAX_SCALE_IN_COUNT", "R20_MIN_SCALE_IN_PROFIT_RATIO", "R20_MIN_SCALE_IN_CONFIDENCE",
)
for _key in _RISK_KEYS_STATIC:
    os.environ.pop(_key, None)

from scripts.risk_constants import RISK_ENV_KEYS as _RISK_KEYS  # noqa: E402

assert set(_RISK_KEYS) == set(_RISK_KEYS_STATIC), (
    "tests/__init__.py 的静态风控键表与 scripts/risk_constants.RISK_ENV_KEYS 漂移，请同步")

# 律①续（批1 P0-2 配套，2026-09-13）：settings_store.ENV_FILE 默认指向仓库根 .env，
# 而 config_sandbox.isolate_config 只重定向 data/ 下的路径——于是**任何**走
# update_env/remove_env 的测试都会真实改写生产 .env（实测：test_policy_snapshot_isolated
# 的 rollback 流程在 23:19 重写了根 .env，只是值恰好与线上相同才没出事故；
# settings_store 加 flock 后还会在仓库根留下 ..env.lock）。
# 这里上硬闸：测试进程内 ENV_FILE 仍指向仓库根 .env 时，写操作直接失败，
# 逼调用方显式沙箱化（`patch.object(settings_store, "ENV_FILE", tmp)`）。
import r20_backend.settings_store as _settings_store  # noqa: E402

_REAL_ENV_FILE = _settings_store.ENV_FILE


def _sandbox_required(original, name):
    def guarded(*args, **kwargs):
        if _settings_store.ENV_FILE == _REAL_ENV_FILE:
            raise AssertionError(
                f"测试禁止写生产配置 {_REAL_ENV_FILE}（{name}）——"
                "请先把 settings_store.ENV_FILE 指向临时文件")
        return original(*args, **kwargs)
    return guarded


_settings_store.update_env = _sandbox_required(_settings_store.update_env, "update_env")
_settings_store.remove_env = _sandbox_required(_settings_store.remove_env, "remove_env")
