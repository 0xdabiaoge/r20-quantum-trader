"""台账（lifecycle ledger）构建的可复用部件。

`scripts/sync_full_ledger.py` 是公开门面（`scripts.sync_full_ledger` 与
`sync_full_ledger` 两种导入路径都被测试使用），本子包承载它的**实现细节**。

## 为什么不直接改门面结构

门面里的 `build_lifecycle_ledger()` 长 330 行，但它是**唯一入口**：读初始状态、
读旧台账、拉三所历史、合并、去重、原子落盘。它不适合整体搬走（会牵动
`__main__` 与全部测试接缝），适合的是把其中**自成一体的计算段**逐个抽出来。

## 抽取约定（与 scripts/trader、scripts/brain 一致）

- 需要时间/工具函数时**由调用方传入**，不在 import 期绑定 ——
  门面里的模块级名字会被测试 `patch.object`，import 期绑定会绕过接缝。
- 只搬"纯计算"，不搬副作用：文件读写、`print`、全局状态更新留在门面。
"""
