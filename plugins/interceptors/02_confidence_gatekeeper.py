"""
R20 物理拦截插件规范
====================
id: 02_confidence_gatekeeper
name: 高置信度质量门禁
version: 1.1.0
author: R20 Official
description: 兼顾开单欲望与胜率质量。置信度低于 75% 强制 WAIT；DOGE 维持 80% 门禁。
tags: 置信度, 胜率优化, 官方预设
"""

def check_risk(package: dict, decision: dict, context: dict) -> tuple[bool, str]:
    action = str(decision.get("action", "WAIT")).upper()
    if action == "WAIT":
        return True, ""

    try:
        conf = float(decision.get("confidence", 0) or 0)
    except (ValueError, TypeError):
        conf = 0.0

    name = str(package.get("name", "")).upper()
    if name == "DOGE" and conf < 80.0:
        return False, f"DOGE高杂波标的置信度 {conf:.1f}% 未达 80% 防破位门禁，安全降级为 WAIT。"

    if conf < 75.0:
        return False, f"置信度 {conf:.1f}% 低于 75% 胜率质量基准门禁，安全降级为 WAIT。"

    return True, ""
