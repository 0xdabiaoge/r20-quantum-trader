#!/usr/bin/env python3
"""
Crypto News & Black-Swan Circuit Breaker Harvester (US-002: 多源公开快讯 RSS)
Features:
1. Harvest high-impact crypto news directly from public RSS feeds
   (CoinDesk + Cointelegraph) over urllib.request — no okxcli dependency.
   Every source fails soft: one dead feed never blanks the whole intelligence layer.
2. Aggregate real-time multi-coin social & news sentiment (Bullish vs Bearish Ratio)
3. Detect Black-Swan / Extreme Macro Events and trigger Automatic Circuit Breaker (30-min opening freeze)
4. Push critical alerts to QQ Channel
"""

import os

# 结构优化阶段 4·B3 第四十四刀：重要度分级与币种识别（纯判断逻辑）
# 已外提到 `scripts/news/importance.py`。门面**再导出** ——
# `tests/test_news_sentiment_harvester.py` 按门面名直接调用这两个函数。
from scripts.news.importance import (  # noqa: E402,F401
    _classify_importance,
    _extract_coins,
)
import sys
import tempfile
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import json
import time
import datetime
import hashlib
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: ⚠️ `R20_DATA_DIR` 是**测试沙箱专用环境变量**（由 tests/config_sandbox.isolate_config
#: 设置、由 `run_script` 拉起的子进程继承）：跑测试时把 data/ 写入重定向到沙箱，
#: **生产从不设置该变量 → 取值与原先逐位相同**。修复"测试经子进程写生产文件"
#: 的泄漏（§88/§91.6），不改任何业务行为。
DATA_DIR = os.environ.get("R20_DATA_DIR") or os.path.join(WORKSPACE_DIR, "data")
NEWS_CACHE_FILE = os.path.join(DATA_DIR, "news_sentiment.json")
CIRCUIT_BREAKER_FILE = os.path.join(DATA_DIR, "circuit_breaker.json")


def _atomic_write_json(path, payload):
    """审计③(2026-09-13)：与 trader/sync_full_ledger 同路数（mkstemp+fsync+replace）。
    熔断/状态类文件绝不直 open("w")——读者撞半截 JSON 会误停开仓且不自愈。"""
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + "-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


from instrument_pool import load_instruments
TARGET_COINS = [item["name"] for item in load_instruments()]

# Institutional-Grade Extreme Black-Swan Regular Expressions
# Only trigger circuit breaker for existential, catastrophic, systemic market shocks
BLACK_SWAN_PATTERNS = [
    (r"(USDT|USDC|DAI).*(严重脱锚|脱锚幅度|depeg|脱锚超过|跌破0\.9[0-8])", "头部稳定币恶性脱锚危机"),
    (r"(币安|OKX|Coinbase|Kraken).*(暂停全部提现|停止提币|申请破产重组|破产倒闭|发生严重挤兑)", "主流中心化交易所崩盘挤兑"),
    (r"(以太坊主网|比特币网络|Solana网络|BNB Chain).*(遭遇51%攻击|全网瘫痪停机|紧急硬分叉回滚)", "顶级底层公链系统性故障/51%攻击"),
    (r"(全面取缔所有加密|宣布比特币非法|宣布数字货币交易非法|爆发核危机|宣战)", "国家级极端不可抗力/战争")
]

# （US-014 前置）OKX CLI 的 news 抓取通道（run_json_cmd/_news_env/subprocess）已随
# CLI 移除整体删除；news latest/important/coin-sentiment 无公开 V5 等价接口，
# 数据源缺失语义见 fetch_and_analyze_news_sentiment() 内注释与 source_available。

def trigger_circuit_breaker(headline: str, keyword: str):
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    now_bj = datetime.datetime.now(tz_bj)
    now_ts = int(time.time())
    
    cb_data = {
        "active": True,
        "triggered_at": now_bj.strftime("%Y-%m-%d %H:%M:%S"),
        "expires_at_ts": now_ts + 1800,  # 30 minutes freeze
        "headline": headline,
        "keyword": keyword,
        "action": "暂停新开仓 30 分钟，启动存量持仓保本防御"
    }
    
    # 审计③(2026-09-13)：原子替换——本文件是全系统熔断写者，读者（trader/后端）
    # 撞半截 JSON 即每轮误停开仓。
    _atomic_write_json(CIRCUIT_BREAKER_FILE, cb_data)
        
    try:
        from qq_notifier import notify_circuit_breaker
        notify_circuit_breaker(headline, f"命中突发高危词汇【{keyword}】")
    except Exception:
        pass
    print(f"🚨 黑天鹅熔断已激活: {headline}")

def is_circuit_breaker_active():
    if os.path.exists(CIRCUIT_BREAKER_FILE):
        try:
            with open(CIRCUIT_BREAKER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("active") and time.time() < data.get("expires_at_ts", 0):
                    return True, data
        except Exception:
            pass
    return False, {}

def fetch_okx_announcements(limit=15) -> list:
    """OKX 官方公告流抓取（/api/v5/support/announcements）。
    第一时间捕获上币、下架、风控调整与系统维护公告，零第三方 RSS 依赖。"""
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    items = []
    try:
        url = "https://www.okx.com/api/v5/support/announcements"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for group in data.get("data", []):
            for it in (group.get("details", []) or []):
                title = str(it.get("title") or "").strip()
                if not title:
                    continue
                url = str(it.get("url") or "")
                ann_type = str(it.get("annType") or "公告")
                p_time = int(it.get("pTime") or it.get("businessPTime") or (time.time() * 1000))
                time_str = datetime.datetime.fromtimestamp(p_time / 1000.0, tz=tz_bj).strftime("%Y-%m-%d %H:%M:%S")
                summary = f"OKX官方通告【{ann_type}】: {title}"
                items.append({
                    # 审计 D7：去重 id 禁用 abs(hash())（PYTHONHASHSEED 每进程
                    # 随机化，重启后同一标题生成新 id → 去重失效重复入库）。
                    # id 全链按不透明字符串消费（单源核实），改确定性 sha256 前 8 位。
                    "id": f"okx-{p_time}-{hashlib.sha256(title.encode('utf-8')).hexdigest()[:8]}",
                    "title": title,
                    "summary": summary,
                    "time": time_str,
                    "cTime": str(p_time),
                    "url": url,
                    "platforms": ["OKX官方"],
                    "importance": _classify_importance(title, summary),
                })
    except Exception as e:
        print(f"[news_harvester] warn OKX 官方公告抓取异常: {e}")
    return items[:limit]


def fetch_jin10_macro_news(limit=20) -> list:
    """金十数据官方宏观与要闻流抓取（hits_rank.json）+ 实时 7x24 宏观快讯滚动补充。"""
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    items = []

    # 1. 金十数据官方热点要闻
    try:
        url = "https://cdn.jin10.com/json/index/hits_rank.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        news_list = (raw.get("all", {}).get("daily", {}).get("news", [])
                     + raw.get("all", {}).get("weekly", {}).get("news", []))
        updated_at = raw.get("all", {}).get("daily", {}).get("updated_at")
        ts_now = int(time.time() * 1000)
        for idx, it in enumerate(news_list):
            title = str(it.get("title") or "").strip()
            if not title:
                continue
            item_id = it.get("id") or (ts_now - idx * 60000)
            items.append({
                "id": f"jin10-{item_id}",
                "title": title,
                "summary": f"金十数据热点要闻: {title}",
                "time": updated_at or datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S"),
                "cTime": str(ts_now - idx * 60000),
                "url": "https://www.jin10.com",
                "platforms": ["金十数据"],
                "importance": _classify_importance(title, ""),
            })
    except Exception as e:
        print(f"[news_harvester] warn 金十数据抓取异常: {e}")

    # 2. 7x24 实时宏观快讯滚动补充（新浪财经 7x24 全球宏观快讯）
    try:
        url = "https://zhibo.sina.com.cn/api/zhibo/feed?page=1&page_size=20&zhibo_id=152"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        feed_list = data.get("result", {}).get("data", {}).get("feed", {}).get("list", [])
        for it in feed_list:
            text = (it.get("rich_text") or it.get("plain_text") or "").strip()
            if not text:
                continue
            create_time = it.get("create_time") or datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S")
            try:
                dt_obj = datetime.datetime.strptime(create_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz_bj)
                ts_ms = int(dt_obj.timestamp() * 1000)
            except Exception:
                ts_ms = int(time.time() * 1000)
            title_match = re.split(r"[。！!？?\n]", text)[0].strip()
            title = title_match[:70] if title_match else text[:70]
            items.append({
                "id": f"macro-{it.get('id') or ts_ms}",
                "title": title,
                "summary": text[:200],
                "time": create_time,
                "cTime": str(ts_ms),
                "url": "https://finance.sina.com.cn/7x24/",
                "platforms": ["全球宏观快讯"],
                "importance": _classify_importance(title, text),
            })
    except Exception as e:
        print(f"[news_harvester] warn 宏观快讯抓取异常: {e}")

    return items[:limit]


def fetch_okx_rubik_sentiment(ccy: str) -> dict:
    """从 OKX Rubik 官方数据端点拉取多空账户比与合约持仓情绪。"""
    c = ccy.upper()
    url = f"https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy={c}"
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            rows = data.get("data") or []
            if rows and len(rows[0]) >= 2:
                ratio = float(rows[0][1] or 1.0)
                bull_pct = round((ratio / (ratio + 1.0)) * 100, 1)
                bear_pct = round((1.0 / (ratio + 1.0)) * 100, 1)
                if ratio >= 1.25:
                    label = "bullish"
                elif ratio <= 0.82:
                    label = "bearish"
                else:
                    label = "neutral"
                score = round((ratio - 1.0) / max(1.0, ratio), 2)
                return {
                    "ccy": c,
                    "label": label,
                    "bullish_ratio": f"{bull_pct:.1f}%",
                    "bearish_ratio": f"{bear_pct:.1f}%",
                    "bullish_pct": f"{bull_pct:.1f}%",
                    "bearish_pct": f"{bear_pct:.1f}%",
                    "long_short_ratio": f"{ratio:.2f}",
                    "bull_cnt": int(bull_pct),
                    "bear_cnt": int(bear_pct),
                    "neutral_cnt": 0,
                    "mentions": 100,
                    "sentiment_factor_score": score,
                }
        except Exception:
            if attempt == 0:
                time.sleep(0.6)
    return None

def fetch_and_analyze_news_sentiment():
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    now_bj = datetime.datetime.now(tz_bj)
    now_str = now_bj.strftime("%Y-%m-%d %H:%M:%S")

    # 1. News sources：直连 OKX 官方公告流 + 金十数据宏观快讯，淘汰旧第三方 RSS。
    okx_news = fetch_okx_announcements(limit=20)
    jin10_news = fetch_jin10_macro_news(limit=25)
    raw_news = okx_news + jin10_news

    seen_ids = set()
    deduped_news = []
    for item in raw_news:
        nid = str(item.get("id", ""))
        if nid and nid not in seen_ids:
            seen_ids.add(nid)
            deduped_news.append(item)

    # 保障 OKX 官方公告与金十宏观要闻双向足额露出，避免单方时间差挤占
    top_okx = [n for n in deduped_news if "OKX官方" in n.get("platforms", [])][:15]
    top_other = [n for n in deduped_news if "OKX官方" not in n.get("platforms", [])][:20]
    raw_news = sorted(top_okx + top_other, key=lambda x: int(x.get("cTime", 0) or 0), reverse=True)

    parsed_news = []
    triggered_threat = None

    for item in raw_news:
        c_time = int(item.get("cTime", 0) or 0) / 1000.0
        dt_str = datetime.datetime.fromtimestamp(c_time, tz=tz_bj).strftime("%Y-%m-%d %H:%M:%S") if c_time > 0 else "--"
        title = item.get("title", "")
        summary = item.get("summary", "")
        full_text = f"{title} {summary}"

        # Only evaluate black-swan patterns for news within last 15 minutes
        if time.time() - c_time < 900:
            for pattern, threat_name in BLACK_SWAN_PATTERNS:
                if re.search(pattern, full_text, re.IGNORECASE):
                    triggered_threat = (title, threat_name)
                    break

        coins = item.get("ccyList") or item.get("coins") or _extract_coins(title, summary, TARGET_COINS)
        importance = item.get("importance") or _classify_importance(title, summary)

        parsed_news.append({
            "id": item.get("id"),
            "time": dt_str,
            "title": title,
            "summary": summary,
            "coins": coins,
            "platforms": item.get("platformList") or item.get("platforms", []),
            "importance": importance,
            "url": item.get("sourceUrl") or item.get("url", "")
        })

    if triggered_threat:
        trigger_circuit_breaker(triggered_threat[0], triggered_threat[1])
    else:
        # If no genuine black-swan is active, ensure circuit breaker is cleared if expired
        if os.path.exists(CIRCUIT_BREAKER_FILE):
            try:
                with open(CIRCUIT_BREAKER_FILE, "r", encoding="utf-8") as f:
                    cb_data = json.load(f)
                if cb_data.get("active") and time.time() >= cb_data.get("expires_at_ts", 0):
                    cb_data["active"] = False
                    _atomic_write_json(CIRCUIT_BREAKER_FILE, cb_data)
            except Exception as _ce:
                # 审计③(2026-09-13)：旧实现整段 except:pass——文件一旦撕裂，清除路径
                # 永远解析失败永远无法重写，读者每轮「熔断文件损坏，暂停开仓」直到人工
                # 删文件（无限期停摆+不自愈）。现损坏直接原子重写为 inactive 自愈：
                # 能走到这里说明本轮无真实黑天鹅（triggered_threat 为空），清除是安全方向。
                print(f"[熔断自愈] circuit_breaker.json 不可解析({_ce!r})，本轮无威胁 → 重写为 inactive")
                try:
                    _atomic_write_json(CIRCUIT_BREAKER_FILE, {
                        "active": False,
                        "self_healed_at": int(time.time()),
                        "note": "损坏自愈重写：见 r20 审计批3（news_sentiment_harvester）",
                    })
                except Exception as _we:
                    print(f"[熔断自愈] warn 重写失败: {_we}")

    # 2. Multi-Coin Sentiment：直连 OKX Rubik 官方多空账户比，真实反映全网多空力量
    active_instruments = load_instruments()
    target_coins = [item["name"] for item in active_instruments]
    coin_sentiments = {}

    # Load existing valid sentiments as fallback to prevent 0-mentions overwrite if API rate limits or drops temporarily
    existing_sentiments = {}
    if os.path.exists(NEWS_CACHE_FILE):
        try:
            with open(NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
                old_cache = json.load(f)
                existing_sentiments = old_cache.get("coins_sentiment", {})
        except Exception:
            pass

    for ccy in target_coins:
        rubik_data = fetch_okx_rubik_sentiment(ccy)
        if rubik_data:
            coin_sentiments[ccy] = rubik_data
        elif ccy in existing_sentiments:
            coin_sentiments[ccy] = existing_sentiments[ccy]
        else:
            coin_sentiments[ccy] = {
                "ccy": ccy,
                "label": "neutral",
                "bullish_ratio": "50.0%",
                "bearish_ratio": "50.0%",
                "bullish_pct": "50.0%",
                "bearish_pct": "50.0%",
                "long_short_ratio": "1.00",
                "bull_cnt": 50,
                "bear_cnt": 50,
                "neutral_cnt": 0,
                "mentions": 100,
                "sentiment_factor_score": 0.0,
            }
        time.sleep(0.3)

    # 3. Overall Macro Sentiment Synthesis
    cb_active, cb_info = is_circuit_breaker_active()
    if cb_active:
        macro_env = "🚨 避险熔断中"
    else:
        bull_count = sum(1 for c, s in coin_sentiments.items() if s["sentiment_factor_score"] > 0.15)
        bear_count = sum(1 for c, s in coin_sentiments.items() if s["sentiment_factor_score"] < -0.15)
        macro_env = "偏多震荡" if bull_count > bear_count else ("偏空承压" if bear_count > bull_count else "中性平衡")

    payload = {
        "timestamp": now_str,
        "updated_at": now_str,
        "source_available": bool(raw_news),
        "source_reason": ("OKX官方公告 + 金十数据宏观要闻 + OKX Rubik多空数据" if raw_news
                          else "OKX官方公告与金十数据拉取失败，显示缺失而非中性"),
        "macro_sentiment": macro_env,
        "circuit_breaker": cb_info if cb_active else {"active": False},
        "coins_sentiment": coin_sentiments,
        "latest_news": parsed_news[:35],
        # Freshness of the *content* (newest item time), not of this run.
        "news_fresh_at": (parsed_news[0]["time"] if parsed_news else None),
    }

    # Fail-closed: an upstream hiccup must not wipe a good cache into an empty page.
    if not payload["latest_news"] or not payload["coins_sentiment"]:
        try:
            if os.path.exists(NEWS_CACHE_FILE):
                with open(NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
                    previous = json.load(f)
                if previous.get("latest_news") or previous.get("coins_sentiment"):
                    if not payload["latest_news"] and previous.get("latest_news"):
                        payload["latest_news"] = previous["latest_news"]
                        payload["news_fresh_at"] = previous.get("news_fresh_at") or (
                            previous["latest_news"][0].get("time") if previous["latest_news"] else None
                        )
                    if not payload["coins_sentiment"] and previous.get("coins_sentiment"):
                        payload["coins_sentiment"] = {k: v for k, v in previous["coins_sentiment"].items() if k in target_coins}
                        bull_count = sum(1 for s in payload["coins_sentiment"].values() if float(s.get("sentiment_factor_score", 0)) > 0.25)
                        bear_count = sum(1 for s in payload["coins_sentiment"].values() if float(s.get("sentiment_factor_score", 0)) < -0.1)
                        if not cb_active:
                            payload["macro_sentiment"] = "偏多震荡" if bull_count > bear_count else ("偏空承压" if bear_count > bull_count else "中性平衡")
                    payload["stale_sections"] = True
        except Exception:
            pass

    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp_file = NEWS_CACHE_FILE + f".tmp.{os.getpid()}"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, NEWS_CACHE_FILE)
    except Exception as exc:
        print(f"Failed to write news cache: {exc}")

    return payload

if __name__ == "__main__":
    res = fetch_and_analyze_news_sentiment()
    flag = " ⚠️STALE(upstream empty, serving last cache)" if res.get("stale_sections") else ""
    print(f"✅ OKX News & Sentiment Engine complete. Macro: {res['macro_sentiment']}, News Count: {len(res['latest_news'])}{flag} 最新快讯: {res.get('news_fresh_at') or '--'}")
    # 数据源缺失（CLI 已移除、无公开 V5 等价）：按既有失败路径语义非零退出，
    # 调度/上层据 exit code 与 source_available 显式感知缺失（缓存回退仍生效）。
    if not res.get("source_available"):
        raise SystemExit(3)
