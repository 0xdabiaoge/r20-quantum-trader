"""Small native OKX REST client; public endpoints work without credentials."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .config import settings


class OKXClient:
    def __init__(self) -> None:
        self.base_url = settings.okx_base_url.rstrip("/")

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        params = params or {}
        query = urlencode(params)
        url = f"{self.base_url}{path}" + (f"?{query}" if query else "")
        headers = {"User-Agent": "R20-Standalone/5.4.2"}
        if settings.okx_api_key and settings.okx_secret_key and settings.okx_passphrase:
            timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            prehash = timestamp + method.upper() + path + (f"?{query}" if query else "")
            digest = hmac.new(settings.okx_secret_key.encode(), prehash.encode(), hashlib.sha256).digest()
            headers.update({
                "OK-ACCESS-KEY": settings.okx_api_key,
                "OK-ACCESS-SIGN": base64.b64encode(digest).decode(),
                "OK-ACCESS-TIMESTAMP": timestamp,
                "OK-ACCESS-PASSPHRASE": settings.okx_passphrase,
            })
            if settings.okx_simulated:
                headers["x-simulated-trading"] = "1"
        req = Request(url, headers=headers, method=method.upper())
        with urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("code") not in (None, "0", 0):
            raise RuntimeError(payload.get("msg", "OKX request failed"))
        return payload.get("data", payload)

    def ticker(self, inst_id: str) -> Any:
        return self._request("GET", "/api/v5/market/ticker", {"instId": inst_id})

    def candles(self, inst_id: str, bar: str = "1H", limit: int = 100) -> Any:
        return self._request("GET", "/api/v5/market/candles", {"instId": inst_id, "bar": bar, "limit": limit})

    def instruments(self, inst_type: str = "SWAP", inst_id: str | None = None) -> Any:
        params = {"instType": inst_type}
        if inst_id:
            params["instId"] = inst_id
        return self._request("GET", "/api/v5/public/instruments", params)

    def balance(self) -> Any:
        return self._request("GET", "/api/v5/account/balance")

    def positions(self) -> Any:
        return self._request("GET", "/api/v5/account/positions", {"instType": "SWAP"})
