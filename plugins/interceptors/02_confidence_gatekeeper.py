"""
R20 物理拦截插件规范
====================
id: 02_confidence_gatekeeper
name: 高置信度质量门禁
version: 1.0.0
author: R20 Official
description: 胜率第一，宁缺毋滥。置信度低于 80% 一律强制 WAIT；DOGE 等 Meme 杂波标的门禁提升至 85%。
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
    if name == "DOGE" and conf < 85.0:
        return False, f"DOGE高杂波标的置信度 {conf:.1f}% 未达 85% 防破位门禁，安全降级为 WAIT。"

    if conf < 80.0:
        return False, f"置信度 {conf:.1f}% 低于 80% 胜率质量硬门禁（宁缺毋滥），安全降级为 WAIT。"

    return True, ""
