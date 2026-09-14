"""平仓单聚合 → 当日/累计胜负统计（结构优化阶段 4·B3 第二十四刀）。

原样搬自 `dashboard/app.py::update_cache_cycle` 的「平仓聚合」循环（29 行）。

## 这段在算什么

输入是按「分钟 + 币种」聚合好的平仓单（`aggregate_bills` 的产物），
本段再往上滚一层，得到仪表盘 KPI 需要的量：

| 输出 | 含义 |
|---|---|
| `today_win_trades` / `today_loss_trades` | **当日**盈利/亏损笔数 |
| `all_win_trades` / `all_loss_trades` | 周期内累计笔数 |
| `all_win_amt` / `all_loss_amt` | 累计盈/亏金额（亏损取绝对值） |
| `today_realized_gross` | 当日已实现毛盈亏（Σ `gross_pnl`） |
| `by_inst` | 分币种统计（trades / wins / losses / pnl） |

## 三处容易出错的地方（均原样保留）

1. **尘埃过滤**：`abs(net) < 0.01 and abs(gross_pnl) < 0.01` 才跳过 ——
   两个条件都要满足。只判一个会把"净额小而毛额大"的真实交易误删
   （例如手续费吃掉全部利润但方向确实盈利的单子）。
   **注意：过滤发生在 `by_inst` 记账之后**，所以分币种的 `trades` 计数
   **包含**尘埃单，而全局 win/loss 计数**不含** —— 两者口径不同是**故意的**，
   不是 bug。若"顺手统一"，分币种表的笔数会与前端预期不符。
2. **`today_bj_str in t_time` 是子串判断**（同日判定），不是相等 ——
   与 `bills.py` 同款口径，两处必须一致。
3. **`today_realized_gross` 只在当日行累加**，且用的是 `gross_pnl`
   （不含手续费），而 `net` 用的是 `pnl`（含手续费）。两个字段口径不同，
   不能互相替代。

## 与门面的分工

`by_inst` 与七个计数器都在函数内新建，随返回值给出；调用方把它们接回局部变量。
本函数不读任何外部状态，是**纯计算**。
"""
from __future__ import annotations

__all__ = ["aggregate_trade_stats"]


def aggregate_trade_stats(orders_by_key, *, today_bj_str):
    """把「分钟+币种」平仓聚合滚动成当日/累计胜负统计。

    返回 dict：

    ```python
    {
        "by_inst": {...},              # 分币种统计
        "today_realized_gross": 0.0,
        "today_win_trades": 0, "today_loss_trades": 0,
        "all_win_trades": 0, "all_loss_trades": 0,
        "all_win_amt": 0.0, "all_loss_amt": 0.0,
    }
    ```

    `orders_by_key` 为空/非 dict 时返回全零（原实现对空 dict 自然如此）。
    """
    by_inst: dict = {}
    today_realized_gross = 0.0
    today_win_trades = 0
    today_loss_trades = 0
    all_win_trades = 0
    all_loss_trades = 0
    all_win_amt = 0.0
    all_loss_amt = 0.0

    for agg_k, o in orders_by_key.items():
        net = o["pnl"]
        inst = o["inst"]
        t_time = o["time"]

        if inst not in by_inst:
            by_inst[inst] = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0}
        by_inst[inst]["trades"] += 1
        by_inst[inst]["pnl"] += net

        # Exclude friction dust / zero-margin test orders (< 0.01 USDT absolute PnL) from win/loss trade count
        if abs(net) < 0.01 and abs(o.get("gross_pnl", 0.0)) < 0.01:
            continue

        if net > 0:
            all_win_trades += 1
            all_win_amt += net
            by_inst[inst]["wins"] += 1
            if today_bj_str in t_time:
                today_win_trades += 1
        elif net < 0:
            all_loss_trades += 1
            all_loss_amt += abs(net)
            by_inst[inst]["losses"] += 1
            if today_bj_str in t_time:
                today_loss_trades += 1

        if today_bj_str in t_time:
            today_realized_gross += o["gross_pnl"]

    return {
        "by_inst": by_inst,
        "today_realized_gross": today_realized_gross,
        "today_win_trades": today_win_trades,
        "today_loss_trades": today_loss_trades,
        "all_win_trades": all_win_trades,
        "all_loss_trades": all_loss_trades,
        "all_win_amt": all_win_amt,
        "all_loss_amt": all_loss_amt,
    }
