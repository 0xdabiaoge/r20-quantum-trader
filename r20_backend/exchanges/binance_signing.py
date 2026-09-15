"""Binance USDⓈ-M 私有请求的**签名串构建**（从 `exchanges/binance.py::signed_request` 搬出）。

规则（原样保留，勿"优化"）：

- 由本函数补齐毫秒 `timestamp` 与 `recvWindow=5000`；
- **空值与 `None` 一律剔除**（判据是 `v not in (None, "")`）—— 注意 `0` 与 `False`
  **不在此列**（`0 not in (None, "")` 为真）⇒ 数量为 0 的参数不会被悄悄丢掉。
  这是最容易"顺手改成 `if v`"而改坏的一处；
- 签名 = `HMAC-SHA256(secret, query_string)` 的十六进制小写；
- 最终串形如 `a=1&timestamp=<ms>&recvWindow=5000&signature=<hex>`。

`time` / `urlencode` / `hmac` / `hashlib` 由本模块**自己 import**（分析器第 11 条：标准库名
不当参数注入）。已核实现无测试对 `binance.time` / `binance.hmac` 打桩，故不构成接缝迁移；
HTTP 传送（`Request`/`urlopen`）仍留在门面，`urlopen` 的既有 `patch.object` 接缝不受影响。
"""
import hashlib
import hmac
import time
from urllib.parse import urlencode
from typing import Any, Dict, Optional


def build_signed_query(*,
        params,
        secret):
    query_dict = dict(params or {})
    query_dict["timestamp"] = int(time.time() * 1000)
    query_dict["recvWindow"] = 5000
    clean_query = {k: v for k, v in query_dict.items() if v not in (None, "")}
    query_string = urlencode(clean_query)
    signature = hmac.new(secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()
    full_query = f"{query_string}&signature={signature}"
    return full_query
