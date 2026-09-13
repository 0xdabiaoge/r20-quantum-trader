"""委员会子系统。

结构优化阶段 2（B5）：把 r20_backend/council_manager.py 的花名册/辩论引擎拆开。
**关键约束**：council_manager 是测试注入接缝 —— 测试直接赋值
cm.COUNCIL_CONFIG_FILE / cm.DATA_DIR / cm._LEGACY_PRESET_PROMPT_HASHES，且
tests/test_beijing_time_producers.py 的 isolated() 按 AST 从该文件取
save_council_config / export_council_config / _backup_council_config。
因此配置侧留在门面，只有辩论引擎（不读那些常量）迁出。
"""
