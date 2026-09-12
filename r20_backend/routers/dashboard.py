"""Public dashboard, real-time market data, and cache endpoints."""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse

from r20_backend.config import settings, refresh_settings
from r20_backend.time_utils import beijing_day
from r20_backend.dependencies import (
    ROOT, DATA_DIR, VUE_DIST, okx, read_json, require_admin_header,
)
import dashboard.app as dash_app

router = APIRouter(tags=["dashboard"])

_CANDLES_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}


@router.get("/api/all")
async def get_all_data():
    return await dash_app.get_all_data()


@router.get("/api/overview")
async def get_overview():
    return await dash_app.get_overview()


@router.get("/api/v1/cache/{resource}")
def cache(resource: str, x_r20_admin_token: str | None = Header(default=None), x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> JSONResponse:
    allowed = {
        "decisions": "ai_brain_decisions.json",
        "factors": "factor_library_snapshot.json",
        "ledger": "trading_ledger.json",
        "sentiment": "news_sentiment.json",
        "self-improvement": "self_improvement_report.json",
    }
    filename = allowed.get(resource)
    if not filename:
        raise HTTPException(status_code=404, detail="unknown cache resource")
    if resource == "ledger":
        require_admin_header(x_r20_admin_token, x_r20_session)
    return JSONResponse(read_json(filename, {} if resource != "ledger" else []))


@router.get("/api/v1/market/{inst_id}")
def market(inst_id: str) -> dict[str, Any]:
    if not inst_id.endswith("-SWAP"):
        raise HTTPException(status_code=400, detail="only SWAP instrument ids are accepted")
    try:
        ticker = okx.ticker(inst_id)
        return {"instId": inst_id, "ticker": ticker[0] if ticker else {}, "source": "OKX REST"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OKX market request failed: {exc}") from exc


@router.get("/api/v1/market/{inst_id}/candles")
def market_candles(inst_id: str, bar: str = "1H", limit: int = 150, response: Response = None) -> dict[str, Any]:
    if response:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    if not inst_id.endswith("-SWAP"):
        raise HTTPException(status_code=400, detail="only SWAP instrument ids are accepted")
    try:
        from scripts.market_data_service import normalize_bar as _nb
        bar = _nb(bar)
    except Exception:
        pass
    valid_bars = {"1m", "3m", "5m", "15m", "30m", "1H", "2H", "4H", "6H", "12H", "1D"}
    if bar not in valid_bars:
        bar = "1H"
    limit = max(10, min(limit, 300))
    cache_key = f"{inst_id}:{bar}:{limit}"
    now_ts = time.time()
    cached = _CANDLES_CACHE.get(cache_key)
    if cached and (now_ts - cached[0] < 1.0):
        return {"instId": inst_id, "bar": bar, "candles": cached[1], "source": "cache"}
    try:
        from scripts.market_data_service import fetch_candles as _fetch_candles
        raw = _fetch_candles(inst_id, bar=bar, limit=limit, timeout=5.0)
        candles = []
        for item in reversed(raw or []):
            try:
                candles.append({
                    "ts": int(item[0]),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "vol": float(item[5]),
                })
            except (ValueError, IndexError):
                continue
        if candles:
            _CANDLES_CACHE[cache_key] = (now_ts, candles)
            return {"instId": inst_id, "bar": bar, "candles": candles, "source": "OKX REST"}
        raise RuntimeError("upstream returned no candles (all fallback levels exhausted)")
    except Exception as exc:
        if cached:
            return {"instId": inst_id, "bar": bar, "candles": cached[1], "source": "stale_cache", "warn": str(exc)}
        factor_file = ROOT / "data" / "factor_library_snapshot.json"
        if factor_file.exists():
            try:
                snap = json.loads(factor_file.read_text(encoding="utf-8"))
                instruments = snap.get("instruments") or {}
                sym = inst_id.split("-")[0]
                inst_data = instruments.get(sym) or instruments.get(inst_id) or {}
                px = float(inst_data.get("price") or 100.0)
                if px > 0:
                    candles = []
                    step_sec = 3600 if "H" in bar else 900
                    for i in range(limit):
                        ts = int((now_ts - (limit - i) * step_sec) * 1000)
                        c_open = round(px * (1.0 + (i - limit/2) * 0.0003), 4)
                        c_close = round(px * (1.0 + (i - limit/2 + 0.3) * 0.0003), 4)
                        c_high = round(max(c_open, c_close) * 1.0015, 4)
                        c_low = round(min(c_open, c_close) * 0.9985, 4)
                        candles.append({
                            "ts": ts,
                            "open": c_open,
                            "high": c_high,
                            "low": c_low,
                            "close": c_close,
                            "vol": round(float(inst_data.get("vol_24h") or 1000.0) / 24.0, 2),
                        })
                    return {"instId": inst_id, "bar": bar, "candles": candles, "source": "factor_fallback"}
            except Exception:
                pass
        return {"instId": inst_id, "bar": bar, "candles": [], "source": "error", "detail": str(exc)}


@router.get("/health", include_in_schema=False)
@router.get("/api/v1/equity_history")
def equity_history(days: int = 14) -> dict[str, Any]:
    """权益迷你曲线（公开，与 /api/all 同级暴露）：
    初始资金 + 按北京时区自然日累计的已实现净盈亏（含手续费口径以台账 net_pnl 为准）。
    仅用于前端 sparkline 形状，精确数值以账户接口为准。"""
    import datetime as _dt
    try:
        days = max(5, min(60, int(days)))
    except Exception:
        days = 14
    tz8 = _dt.timezone(_dt.timedelta(hours=8))
    out: dict[str, Any] = {"days": [], "initial_capital": None, "source": "trading_ledger"}
    try:
        init_cap = None
        try:
            p_init = ROOT / "data" / "account_initial_state.json"
            if p_init.exists():
                init_cap = float(json.loads(p_init.read_text("utf-8")).get("initial_capital") or 0) or None
        except Exception:
            init_cap = None
        p_led = ROOT / "data" / "trading_ledger.json"
        daily: dict[str, float] = {}
        if p_led.exists():
            data = json.loads(p_led.read_text("utf-8"))
            rows = data if isinstance(data, list) else data.get("trades", []) or data.get("records", [])
            for r in rows:
                if not isinstance(r, dict):
                    continue
                if str(r.get("status", "")).lower() not in ("closed", "已平仓", "completed"):
                    ct = str(r.get("close_time") or "")
                    if not ct or "持仓" in ct:
                        continue
                ct = str(r.get("close_time") or "")
                if len(ct) < 10:
                    continue
                day = beijing_day(ct)
                if not day:
                    continue
                try:
                    daily[day] = daily.get(day, 0.0) + float(r.get("net_pnl") or r.get("pnl") or 0.0)
                except (TypeError, ValueError):
                    pass
        base = init_cap if init_cap is not None else 0.0
        out["initial_capital"] = init_cap
        today = _dt.datetime.now(tz8).date()
        start = today - _dt.timedelta(days=days - 1)
        if daily:
            earliest = min(daily.keys())
            try:
                ed = _dt.date.fromisoformat(earliest)
                if ed < start:
                    base = base + sum(v for k, v in daily.items() if k < start.isoformat())
            except ValueError:
                pass
        cum = base
        series = []
        d = start
        while d <= today:
            cum += daily.get(d.isoformat(), 0.0)
            series.append({"date": d.isoformat(), "equity": round(cum, 2)})
            d += _dt.timedelta(days=1)
        out["days"] = series
    except Exception as exc:
        out["error"] = str(exc)
    return out


@router.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    f = VUE_DIST / "robots.txt"
    if f.is_file():
        return FileResponse(str(f), media_type="text/plain", headers={"Cache-Control": "public, max-age=86400, s-maxage=604800"})
    pf = ROOT / "frontend" / "public" / "robots.txt"
    if pf.is_file():
        return FileResponse(str(pf), media_type="text/plain", headers={"Cache-Control": "public, max-age=86400, s-maxage=604800"})
    return PlainTextResponse("User-agent: *\nAllow: /\nAllow: /docs\nAllow: /images/\nDisallow: /admin/\nDisallow: /api/\nSitemap: https://www.r20.cn/sitemap.xml\n")


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    f = VUE_DIST / "sitemap.xml"
    if f.is_file():
        return FileResponse(str(f), media_type="application/xml", headers={"Cache-Control": "public, max-age=86400, s-maxage=604800"})
    pf = ROOT / "frontend" / "public" / "sitemap.xml"
    if pf.is_file():
        return FileResponse(str(pf), media_type="application/xml", headers={"Cache-Control": "public, max-age=86400, s-maxage=604800"})
    return Response(content="""<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://www.r20.cn/</loc><priority>1.0</priority></url><url><loc>https://www.r20.cn/docs</loc><priority>0.8</priority></url></urlset>""", media_type="application/xml")


@router.get("/docs/images/{img_name}", include_in_schema=False)
def docs_images(img_name: str):
    clean_name = Path(img_name).name
    img_path = ROOT / "docs" / "images" / clean_name
    if img_path.exists() and img_path.is_file():
        media_type = "image/png" if clean_name.endswith(".png") else "image/jpeg" if clean_name.endswith((".jpg", ".jpeg")) else "image/svg+xml" if clean_name.endswith(".svg") else "application/octet-stream"
        return FileResponse(str(img_path), media_type=media_type, headers={"Cache-Control": "public, max-age=604800, s-maxage=86400"})
    raise HTTPException(status_code=404, detail="图片不存在")


@router.api_route("/trading", methods=["GET", "HEAD"], include_in_schema=False)
@router.api_route("/factors", methods=["GET", "HEAD"], include_in_schema=False)
@router.api_route("/news", methods=["GET", "HEAD"], include_in_schema=False)
@router.api_route("/lab", methods=["GET", "HEAD"], include_in_schema=False)
@router.api_route("/history", methods=["GET", "HEAD"], include_in_schema=False)
@router.api_route("/docs", methods=["GET", "HEAD"], include_in_schema=False)
@router.api_route("/docs/{subpath:path}", methods=["GET", "HEAD"], include_in_schema=False)
def serve_vue_spa_subroutes(subpath: str = "") -> Response:
    vue_index = VUE_DIST / "index.html"
    if vue_index.is_file():
        return FileResponse(str(vue_index), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    fallback_index = ROOT / "frontend" / "index.html"
    return FileResponse(str(fallback_index), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@router.get("/admin", include_in_schema=False)
@router.get("/admin/{subpath:path}", include_in_schema=False)
def admin_page(subpath: str = "") -> FileResponse:
    vue_index = VUE_DIST / "index.html"
    if vue_index.is_file():
        return FileResponse(str(vue_index), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    fallback_index = ROOT / "frontend" / "index.html"
    return FileResponse(str(fallback_index), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
