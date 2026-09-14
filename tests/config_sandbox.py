"""Per-test configuration sandbox: patch source constants AND imported path aliases."""
import importlib
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


def isolate_config(test):
    temp = tempfile.TemporaryDirectory(prefix='r20-test-config-')
    test.addCleanup(temp.cleanup)
    root = Path(temp.name)
    project = Path(__file__).resolve().parents[1]
    for name in ('r20_backend.llm_manager', 'r20_backend.council_manager',
                 'r20_backend.policy_snapshot', 'r20_backend.interceptor_manager',
                 'scripts.prompt_library', 'scripts.evolution_shield',
                 'r20_gateway.secrets',
                 # `dashboard.app` 的一批大写路径常量（DASHBOARD_CACHE_FILE、
                 # LOG_FILE、STATE_JSON_FILE、LEDGER_JSON_FILE…）此前**不在任何
                 # 白名单里**，于是直调 `update_cache_cycle()` 的测试会写生产
                 # `data/dashboard_last_good.json`（实测有告警但无人处理）。
                 # 它内部会调 `load_persisted_dashboard_cache()`，但那只是读一个
                 # JSON，且所有跑过仪表盘的测试本来就会 import 它。
                 'dashboard.app',
                 # ---- 第七十三刀补：下面 15 个模块用内联 `ROOT / "data" / …`
                 # 拼生产路径。**沙箱只 patch 已 import 模块的大写常量**，
                 # 所以"模块不在这个白名单里"就等于"它的路径常量不受管辖"
                 # —— 无论写法多规范都一样漏（实测 `scripts/instrument_pool.py`
                 # 的 `TRADING_STATE_FILE` 提成模块级常量后，
                 # 不 import 它依然不被重定向）。
                 #
                 # 逐个确认过：15 个都能在**零副作用**下 import
                 # （无网络、无起进程、无端口绑定），与既有白名单同性质。
                 # 对应回归测试：`tests/test_production_data_isolation.py`。
                 'r20_backend.account_baseline',
                 'r20_backend.admin_auth',
                 'r20_backend.backup_secrets',
                 'r20_backend.backup_store',
                 'r20_backend.exchanges.env_profiles',
                 'r20_backend.exchanges.routing_policy',
                 'r20_backend.qq_gateway_daemon',
                 'r20_backend.routers.dashboard',
                 'r20_backend.routers.strategy',
                 'r20_backend.schedule_store',
                 'scripts.archive_ledger',
                 'r20_gateway.agents',
                 'r20_gateway.publisher',
                 'r20_gateway.supervisor',
                 'r20_gateway.worker'):
        importlib.import_module(name)
    # Patch every already-bound alias, not just the defining module (law 2).
    # 白名单必须覆盖**顶层名**形式的兄弟模块：`scripts/` 在 sys.path 上，脚本以
    # `import ai_brain_trader` 引入的是与 `scripts.ai_brain_trader` 不同的模块实例，
    # 不在白名单里就完全不被重定向 → 测试会写生产 data/（如 ai_brain_last_prompt.txt、
    # system_prompt_override.txt）。批2 P1-3 回归测试就是被这条断言抓出来的。
    for name, module in list(sys.modules.items()):
        if not module or name.startswith('tests'):
            continue
        if not (name.startswith(('r20_backend.', 'r20_gateway.', 'scripts.',
                                 'dashboard.')) or
                name in ('prompt_library', 'evolution_shield', 'ai_brain_trader', 'ai_factor_trader')):
            continue
        for key, value in list(vars(module).items()):
            if not key.isupper() or not isinstance(value, (str, Path)):
                continue
            try:
                relative = Path(value).relative_to(project / 'data')
            except ValueError:
                continue
            target = root / 'data' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            replacement = str(target) if isinstance(value, str) else target
            p = patch.object(module, key, replacement)
            p.start(); test.addCleanup(p.stop)
    app = sys.modules.get("r20_backend.app")
    if app is not None:
        git_probe = patch.object(app, "git", side_effect=lambda args: (
            "0 0" if args[0] == "rev-list" else "test" if args[0] == "branch" else
            "" if args[0] in ("fetch", "status") else "abc1234"))
        git_probe.start(); test.addCleanup(git_probe.stop)
    return root
