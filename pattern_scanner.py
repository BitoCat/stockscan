#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
型態掃描器(每日收盤後執行,跑在 GitHub Actions)

用法:
  python pattern_scanner.py --market tw          掃描台股(不推播)
  python pattern_scanner.py --market us --push   掃描美股並推 Telegram 彙總

環境變數:
  SUPABASE_URL, SUPABASE_KEY        (必填,GitHub Secrets 已有)
  BOT_TOKEN                          (推播用,可選)
  TW_CHANNEL_ID, US_CHANNEL_ID       (推播用,可選)
  RAILWAY_API                        (可選,預設 splendid-prosperity)

流程:
  1. 彙整股票池: 概念股 JSON + scan_watchlist(美股) + 主力雷達持股(台股,自動偵測)
  2. 透過 Railway /screener-quote 批次抓一年日線+評級+基本面
  3. 六型態判斷
  4. 刪除當日舊資料 → 寫入 screener_results
  5. --push 時推 Telegram 收盤彙總(只列有結果的型態)
"""

import argparse
import datetime
import re
import sys
import time
import os

import requests

RAILWAY = os.environ.get(
    "RAILWAY_API", "https://splendid-prosperity-production-41ab.up.railway.app")
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TW_CHANNEL_ID = os.environ.get("TW_CHANNEL_ID", "")
US_CHANNEL_ID = os.environ.get("US_CHANNEL_ID", "")
SITE = "https://bitocat.github.io/stockscan"

SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
}

BATCH = 10          # /screener-quote 單次上限
SLEEP_SEC = 2       # 批次間隔,對 Railway/Yahoo 溫柔一點

PATTERN_NAMES = {
    "pullback_ma20": "強勢回調月線",
    "pullback_ma60": "強勢回調季線",
    "reversal_ma20": "低檔翻越月線",
    "reversal_ma60": "低檔翻越季線",
    "high_52w": "突破52週新高",
    "bull_alignment": "多頭排列成形",
}
PATTERN_EMOJI = {
    "pullback_ma20": "🔵", "pullback_ma60": "🔷",
    "reversal_ma20": "🟢", "reversal_ma60": "💚",
    "high_52w": "⭐", "bull_alignment": "🚀",
}

RATING_MAP = {
    "strong_buy": "強力買入", "buy": "買入", "hold": "中立",
    "underperform": "減碼", "sell": "賣出", "strong_sell": "強力賣出",
    "none": "無評級", None: "無評級", "": "無評級",
}

SECTOR_MAP = {
    "Technology": "科技", "Financial Services": "金融",
    "Healthcare": "醫療保健", "Consumer Cyclical": "非必需消費",
    "Consumer Defensive": "必需消費", "Industrials": "工業",
    "Energy": "能源", "Basic Materials": "原物料",
    "Communication Services": "通訊服務", "Utilities": "公用事業",
    "Real Estate": "房地產",
}


# ────────────────────────────────────────────────────
# 股票池
# ────────────────────────────────────────────────────

def load_concept_stocks(market):
    """從網站的概念股 JSON 取得代號與名稱"""
    fname = "concepts.json" if market == "tw" else "us_concepts.json"
    url = f"{SITE}/data/{fname}?t={int(time.time())}"
    stocks = {}
    try:
        data = requests.get(url, timeout=30).json()
        for concept in data.get("concepts", []):
            for s in concept.get("stocks", []):
                code = str(s.get("code", "")).strip()
                if code:
                    stocks[code] = s.get("name", "")
    except Exception as e:
        print(f"[warn] 概念股清單載入失敗: {e}")
    return stocks


def load_scan_watchlist():
    """美股: scan_watchlist 表(強力買入掃描共用清單)"""
    stocks = {}
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/scan_watchlist?select=symbol,name",
            headers={**SB, "Range": "0-1999"}, timeout=30)
        for row in r.json():
            sym = str(row.get("symbol", "")).strip().upper()
            if sym and not sym.isdigit():
                stocks[sym] = row.get("name", "")
    except Exception as e:
        print(f"[warn] scan_watchlist 載入失敗: {e}")
    return stocks


def load_radar_codes():
    """台股: 主力雷達投信持股(自動偵測欄位名,失敗就略過)"""
    codes = set()
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/tw_fund_positions?select=*&limit=1",
            headers=SB, timeout=15)
        rows = r.json()
        if not rows:
            return codes
        key = None
        for k, v in rows[0].items():
            if isinstance(v, str) and re.fullmatch(r"\d{4}", v.strip()):
                key = k
                break
        if not key:
            print("[warn] tw_fund_positions 找不到代號欄位,略過雷達池")
            return codes
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/tw_fund_positions?select={key}",
            headers={**SB, "Range": "0-9999"}, timeout=60)
        for row in r.json():
            c = str(row.get(key, "")).strip()
            if re.fullmatch(r"\d{4}", c) and not c.startswith("0"):  # 排除ETF
                codes.add(c)
        print(f"[info] 雷達池偵測欄位 {key},取得 {len(codes)} 檔")
    except Exception as e:
        print(f"[warn] 雷達池載入失敗: {e}")
    return codes


def load_tw_names():
    """台股中文名對照(tw_stocks 共2249筆)"""
    names = {}
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/tw_stocks?select=code,name",
            headers={**SB, "Range": "0-2999"}, timeout=60)
        for row in r.json():
            names[str(row.get("code", "")).strip()] = row.get("name", "")
    except Exception as e:
        print(f"[warn] tw_stocks 載入失敗: {e}")
    return names


def build_pool(market):
    """回傳 {code: name}"""
    pool = load_concept_stocks(market)
    if market == "us":
        for code, name in load_scan_watchlist().items():
            pool.setdefault(code, name)
    else:
        tw_names = load_tw_names()
        for code in load_radar_codes():
            pool.setdefault(code, tw_names.get(code, ""))
        # 概念股缺名的也補上
        for code in list(pool.keys()):
            if not pool[code]:
                pool[code] = tw_names.get(code, "")
    print(f"[info] {market} 股票池共 {len(pool)} 檔")
    return pool


# ────────────────────────────────────────────────────
# 技術計算與型態判斷
# ────────────────────────────────────────────────────

def sma_at(closes, k, offset=0):
    """closes 舊到新;offset=0 為最新,offset=1 為昨日,以此類推"""
    end = len(closes) - offset
    start = end - k
    if start < 0:
        return None
    seg = closes[start:end]
    if any(v is None for v in seg):
        return None
    return sum(seg) / k


def detect_patterns(q):
    """輸入 /screener-quote 單檔結果,回傳 (型態list, 共用指標dict) 或 (None,None)"""
    closes = q.get("closes") or []
    volumes = q.get("volumes") or []
    closes = [c for c in closes if c is not None]
    if len(closes) < 70 or len(volumes) < 25:
        return None, None

    price = closes[-1]
    prev = closes[-2]
    if not price or not prev:
        return None, None

    s10 = sma_at(closes, 10)
    s20 = sma_at(closes, 20)
    s60 = sma_at(closes, 60)
    s20_y = sma_at(closes, 20, offset=1)
    s20_3 = sma_at(closes, 20, offset=3)
    s60_5 = sma_at(closes, 60, offset=5)
    if not all([s10, s20, s60, s20_y, s20_3, s60_5]):
        return None, None

    hi52 = max(closes[:-1])
    lo52 = min(closes[:-1])
    dist_high = (1 - price / hi52) * 100 if hi52 else None
    dist_low = (price / lo52 - 1) * 100 if lo52 else None

    avg_vol = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else None
    rel_vol = (volumes[-1] / avg_vol) if avg_vol else None

    hits = []

    # 1 強勢回調月線: 多頭架構下回落至月線之上
    if (s20 > s60 and price < s10 and price >= s20
            and dist_high is not None and dist_high <= 20):
        hits.append("pullback_ma20")

    # 2 強勢回調季線: 季線上升,價格回測季線 ±3%
    if (s60 > s60_5 and price < s20
            and abs(price - s60) / s60 <= 0.03
            and dist_high is not None and dist_high <= 30):
        hits.append("pullback_ma60")

    # 3 低檔翻越月線: 昨日在月線下,今日站上,且爆量
    if (prev < s20_y and price > s20
            and dist_low is not None and dist_low <= 25
            and rel_vol is not None and rel_vol >= 1.5):
        hits.append("reversal_ma20")

    # 4 低檔翻越季線: 近5日內從季線下方翻上,月線開始上彎
    below_recent = any(
        c is not None and c < s60 for c in closes[-6:-1])
    if (price > s60 and below_recent and s20 > s20_3
            and dist_low is not None and dist_low <= 30):
        hits.append("reversal_ma60")

    # 5 突破52週新高(帶量)
    if price >= hi52 and rel_vol is not None and rel_vol >= 1.2:
        hits.append("high_52w")

    # 6 多頭排列成形: 10>20>60 且黃金交叉發生在10日內
    if s10 > s20 > s60:
        crossed_recently = False
        for off in range(1, 11):
            a = sma_at(closes, 10, offset=off)
            b = sma_at(closes, 20, offset=off)
            if a is not None and b is not None and a <= b:
                crossed_recently = True
                break
        if crossed_recently:
            hits.append("bull_alignment")

    if not hits:
        return None, None

    metrics = {
        "price": round(price, 2),
        "change_pct": round((price - prev) / prev * 100, 2),
        "rel_volume": round(rel_vol, 2) if rel_vol else None,
        "dist_high_pct": round(dist_high, 1) if dist_high is not None else None,
        "dist_low_pct": round(dist_low, 1) if dist_low is not None else None,
    }
    return hits, metrics


# ────────────────────────────────────────────────────
# 主流程
# ────────────────────────────────────────────────────

def fetch_quotes(codes):
    """分批呼叫 Railway /screener-quote"""
    out = []
    for i in range(0, len(codes), BATCH):
        batch = codes[i:i + BATCH]
        try:
            r = requests.get(
                f"{RAILWAY}/screener-quote",
                params={"codes": ",".join(batch)}, timeout=120)
            data = r.json()
            out.extend(data.get("results", []))
        except Exception as e:
            print(f"[warn] 批次 {batch[0]}~ 失敗: {e}")
        done = min(i + BATCH, len(codes))
        print(f"[info] 已抓取 {done}/{len(codes)}")
        time.sleep(SLEEP_SEC)
    return out


def save_results(market, scan_date, rows):
    # 先刪同日同市場舊資料
    requests.delete(
        f"{SUPABASE_URL}/rest/v1/screener_results"
        f"?market=eq.{market}&scan_date=eq.{scan_date}",
        headers=SB, timeout=60)
    # 分批寫入
    for i in range(0, len(rows), 200):
        chunk = rows[i:i + 200]
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/screener_results",
            headers={**SB, "Prefer": "return=minimal"},
            json=chunk, timeout=60)
        if r.status_code >= 300:
            print(f"[error] 寫入失敗 {r.status_code}: {r.text[:300]}")
            sys.exit(1)
    print(f"[info] 已寫入 {len(rows)} 筆結果")


def push_summary(market, scan_date, rows):
    if not BOT_TOKEN:
        print("[info] 無 BOT_TOKEN,略過推播")
        return
    chat_id = TW_CHANNEL_ID if market == "tw" else US_CHANNEL_ID
    if not chat_id:
        print("[info] 無頻道ID,略過推播")
        return

    by_pattern = {}
    for r in rows:
        by_pattern.setdefault(r["pattern"], []).append(r)

    label = "台股" if market == "tw" else "美股"
    lines = [f"📊 今日型態掃描｜{label} {scan_date[5:].replace('-', '/')}"]
    for pid in PATTERN_NAMES:
        items = by_pattern.get(pid)
        if not items:
            continue
        items.sort(key=lambda x: -(x.get("target_upside_pct") or -999))
        names = "、".join(
            (it.get("name") or it["code"]) for it in items[:3])
        more = "..." if len(items) > 3 else ""
        lines.append(
            f"{PATTERN_EMOJI[pid]} {PATTERN_NAMES[pid]}: "
            f"{len(items)}檔({names}{more})")
    if len(lines) == 1:
        lines.append("今日無符合型態的標的")
    lines.append(f"完整名單與評級 → {SITE}/screener.html")

    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": "\n".join(lines)},
            timeout=30)
        print("[info] 已推送 Telegram 彙總")
    except Exception as e:
        print(f"[warn] 推播失敗: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=["tw", "us"], required=True)
    ap.add_argument("--push", action="store_true", help="推 Telegram 彙總")
    args = ap.parse_args()

    scan_date = datetime.date.today().isoformat()
    pool = build_pool(args.market)
    if not pool:
        print("[error] 股票池為空")
        sys.exit(1)

    quotes = fetch_quotes(sorted(pool.keys()))

    rows = []
    for q in quotes:
        if q.get("error"):
            continue
        hits, metrics = detect_patterns(q)
        if not hits:
            continue
        price = metrics["price"]
        target = q.get("target")
        upside = round((target - price) / price * 100, 1) if target else None
        base = {
            "market": args.market,
            "scan_date": scan_date,
            "code": q["code"],
            "name": pool.get(q["code"]) or q.get("name_en") or q["code"],
            "sector": SECTOR_MAP.get(q.get("sector"), q.get("sector")),
            "industry": q.get("industry"),
            "rating": RATING_MAP.get(q.get("rating"), q.get("rating")),
            "rating_mean": q.get("rating_mean"),
            "analysts": q.get("analysts"),
            "target": target,
            "target_upside_pct": upside,
            "pe": q.get("pe"),
            "eps_growth": q.get("eps_growth"),
            "revenue_growth": q.get("revenue_growth"),
            "roe": q.get("roe"),
            "dividend_yield": q.get("dividend_yield"),
            "market_cap": q.get("market_cap"),
            **metrics,
        }
        for pid in hits:
            rows.append({**base, "pattern": pid})

    print(f"[info] 命中 {len(rows)} 筆(含一檔多型態)")
    save_results(args.market, scan_date, rows)
    if args.push:
        push_summary(args.market, scan_date, rows)
    print("[done] 掃描完成")


if __name__ == "__main__":
    main()
