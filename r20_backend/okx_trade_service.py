"""Environment-bound OKX account snapshot and confirmed fast-close workflow."""
from __future__ import annotations
import json
import subprocess
import time
from typing import Any
from scripts.okx_runtime import OKXEnvironment, selected_environment


def _run(args: list[str], env: OKXEnvironment | None = None, timeout: int = 25) -> list[dict[str, Any]]:
    selected = env or selected_environment()
    command = ["okx", f"--{selected.mode}", *args, "--json"]
    result = subprocess.run(command, text=True, capture_output=True, timeout=timeout, env=selected.cli_env())
    if result.returncode != 0: raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "OKX CLI failed")
    try: payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc: raise RuntimeError("OKX 返回了无效 JSON") from exc
    if isinstance(payload, dict) and str(payload.get("code", "0")) != "0": raise RuntimeError(str(payload.get("msg") or payload))
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(data, list): data = [data] if isinstance(data, dict) else []
    failures = [row for row in data if isinstance(row, dict) and row.get("sCode") not in (None, 0, "0")]
    if failures: raise RuntimeError(str(failures[0].get("sMsg") or failures[0]))
    return [row for row in data if isinstance(row, dict)]


def account_snapshot() -> dict[str, Any]:
    env = selected_environment()
    positions = _run(["account", "positions"], env)
    positions = [p for p in positions if abs(float(p.get("pos", 0) or 0)) > 1e-12]
    orders = _run(["swap", "orders"], env)
    return {
        "environment": env.mode, "environment_id": env.identity, "credential_source": env.source,
        "positions": positions, "orders": orders, "captured_at_ms": int(time.time() * 1000),
    }


def _position_match(positions: list[dict[str, Any]], inst_id: str, pos_side: str, pos_id: str) -> dict[str, Any] | None:
    candidates = [p for p in positions if p.get("instId") == inst_id and str(p.get("posSide", "")).lower() == pos_side]
    if pos_id: candidates = [p for p in candidates if str(p.get("posId", "")) == pos_id]
    return candidates[0] if candidates else None


def fast_close_confirmed(
    inst_id: str, pos_side: str, pos_id: str, expected_size: float, expected_environment_id: str,
) -> dict[str, Any]:
    env = selected_environment()
    if env.identity != expected_environment_id: raise ValueError("OKX 环境或凭证已变化，请刷新当前持仓后重新确认")
    before_positions = _run(["account", "positions"], env)
    target = _position_match(before_positions, inst_id, pos_side, pos_id)
    if not target: raise ValueError("目标仓位已不存在，请刷新")
    actual_size = abs(float(target.get("pos", 0) or 0))
    tolerance = max(1e-12, actual_size * 1e-6)
    if abs(actual_size - abs(expected_size)) > tolerance: raise ValueError(f"仓位数量已从 {expected_size} 变化为 {actual_size}，请刷新后重新确认")
    mgn_mode = str(target.get("mgnMode") or "cross")
    # Cancel only orders that can increase this exact position. Exit/reduce orders must not be removed early.
    live_orders = _run(["swap", "orders"], env)
    canceled: list[str] = []
    target_side = pos_side if pos_side in {"long", "short"} else ("long" if float(target.get("pos", 0) or 0) > 0 else "short")
    risk_increasing_order_side = "buy" if target_side == "long" else "sell"
    for order in live_orders:
        if order.get("instId") != inst_id: continue
        order_pos_side = str(order.get("posSide") or "net").lower()
        if order_pos_side not in {target_side, "net"}: continue
        if str(order.get("reduceOnly", "false")).lower() == "true": continue
        if str(order.get("side") or "").lower() != risk_increasing_order_side: continue
        order_id = str(order.get("ordId") or "")
        if order_id:
            _run(["swap", "cancel", inst_id, "--ordId", order_id], env); canceled.append(order_id)
    close_result = _run(["swap", "close", "--instId", inst_id, "--mgnMode", mgn_mode, "--posSide", pos_side, "--autoCxl"], env)
    remaining = actual_size; query_failures = 0
    for _ in range(8):
        time.sleep(0.75)
        try:
            current = _position_match(_run(["account", "positions"], env), inst_id, pos_side, pos_id)
            remaining = abs(float(current.get("pos", 0) or 0)) if current else 0.0
            if remaining <= tolerance: break
        except Exception:
            query_failures += 1
    if remaining > tolerance:
        status = "unknown_verification_timeout" if query_failures >= 8 else "still_open"
        raise RuntimeError(f"平仓请求已发送但未确认归零，状态={status}，剩余仓位={remaining}；禁止重复点击，请刷新")
    return {
        "status": "confirmed_closed", "environment": env.mode, "environment_id": env.identity,
        "instId": inst_id, "posSide": pos_side, "posId": pos_id, "closed_size": actual_size,
        "canceled_entry_orders": canceled, "close_result": close_result,
    }
