#!/usr/bin/env python3
"""用 BigGo 取得酷澎(Coupang)台灣商品的價格與歷史價，輸出 data/products.json。

流程：
  1. 對 keywords.txt 每個關鍵字呼叫 BigGo 搜尋 API，只保留賣場為 Coupang/酷澎 的商品。
  2. 以 BigGo 價格歷史 API 取得「近 N 日最高價」(預設 30 日)作為參考價。
  3. 現價低於參考價達 MIN_DISCOUNT_PCT 以上者，視為降價商品。

注意：參考價是「近 N 日最高價」，不是 Coupang 頁面上的原價/劃線價。
結束碼：0 成功；2 被阻擋或沒有結果（保留舊資料，讓 Actions 失敗並寄通知）。

用法：
  python scraper/update_deals.py                 # 正式更新
  python scraper/update_deals.py --probe 衛生紙   # 只檢查 BigGo 有沒有收錄酷澎
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
KEYWORDS = ROOT / "scraper" / "keywords.txt"
OUT = ROOT / "data" / "products.json"

SEARCH_URL = "https://api.biggo.com/api/v1/spa/search/{q}/product"
HISTORY_URL = "https://extension.biggo.com/api/product_price_history.php"
SITE = os.getenv("BIGGO_SITE", "biggo.com.tw")
REGION = os.getenv("BIGGO_REGION", "tw")
STORE_KEYS = [k.strip().lower() for k in os.getenv("STORE_FILTER", "coupang,酷澎").split(",") if k.strip()]
REF_DAYS = int(os.getenv("REF_DAYS", "30"))          # 7 / 30 / 90 / 180
MIN_DISCOUNT = float(os.getenv("MIN_DISCOUNT_PCT", "5"))
MAX_PRODUCTS = int(os.getenv("MAX_PRODUCTS", "200"))
DELAY = (1.0, 2.0)
BLOCK_CODES = {401, 403, 429, 503}
UA = "coupang-tw-deal-finder/3.0 (+https://github.com/a0914150215/coupang-tw-deal-finder)"


class Blocked(Exception):
    pass


def _check(r: requests.Response) -> None:
    if r.status_code in BLOCK_CODES:
        raise Blocked(f"{r.status_code} {r.url}")
    r.raise_for_status()


def search(session: requests.Session, keyword: str) -> list[dict]:
    r = session.get(
        SEARCH_URL.format(q=quote(keyword, safe="")),
        headers={"Content-Type": "application/json", "site": SITE, "region": REGION, "User-Agent": UA},
        timeout=25,
    )
    _check(r)
    time.sleep(random.uniform(*DELAY))
    data = r.json()
    items = data.get("list") if isinstance(data, dict) else None
    return [i for i in (items or []) if isinstance(i, dict)]


def _g(d, *path):
    for p in path:
        d = d.get(p) if isinstance(d, dict) else None
    return d


def is_target_store(item: dict) -> bool:
    text = " ".join(str(x) for x in (
        item.get("nindex"), _g(item, "store", "name"), _g(item, "shop", "name"),
        _g(item, "shop", "username"), item.get("affurl"), item.get("url"),
    ) if x).lower()
    return any(k in text for k in STORE_KEYS)


def history_id(item: dict) -> str | None:
    if item.get("history_id"):
        return str(item["history_id"])
    if item.get("nindex") and item.get("oid"):
        return f"{item['nindex']}-{item['oid']}"
    return None


def fetch_history(session: requests.Session, ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 20):
        batch = ids[i:i + 20]
        r = session.post(HISTORY_URL, json={"item": batch, "days": 90},
                         headers={"User-Agent": UA}, timeout=30)
        _check(r)
        time.sleep(random.uniform(*DELAY))
        data = r.json()
        if not isinstance(data, dict) or data.get("result") is False:
            continue
        for k, v in data.items():
            if isinstance(v, dict) and isinstance(v.get("statistics"), dict):
                out[k] = v
    return out


def _price(v):
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def build_product(item: dict, hist: dict) -> dict | None:
    price = _price(item.get("price"))
    stats = hist.get("statistics", {})
    ref = _price(_g(stats, f"days{REF_DAYS}", "max_price"))
    if not price or not ref or ref <= price:
        return None
    pct = round((ref - price) / ref * 100, 1)
    if pct < MIN_DISCOUNT or pct > 90:
        return None
    low90 = _price(_g(stats, "days90", "min_price"))
    aff = item.get("affurl")
    link = f"https://{SITE}{aff}" if isinstance(aff, str) and aff.startswith("/") else item.get("url")
    if not (isinstance(link, str) and link.startswith("https://")):
        return None
    img = item.get("image")
    if not (isinstance(img, str) and img.startswith("https://")):
        img = None
    return {
        "id": history_id(item),
        "name": str(item.get("title", "")).strip()[:200],
        "url": link,
        "image": img,
        "price": int(price),
        "original_price": int(ref),
        "basis": f"{REF_DAYS}日最高價",
        "discount_pct": pct,
        "discount_amount": int(ref - price),
        "is_90d_low": bool(low90 and price <= low90),
        "currency": item.get("currency") or "TWD",
    }


def read_keywords() -> list[str]:
    if not KEYWORDS.exists():
        return []
    return [l.strip() for l in KEYWORDS.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")]


def probe(keywords: list[str]) -> int:
    s = requests.Session()
    try:
        for kw in keywords:
            items = search(s, kw)
            stores = Counter((_g(i, "store", "name") or i.get("nindex") or "?") for i in items)
            hit = [i for i in items if is_target_store(i)]
            print(f"[{kw}] 共 {len(items)} 筆，符合 {STORE_KEYS} 的 {len(hit)} 筆")
            print("  賣場分佈：", dict(stores.most_common(10)))
            for i in hit[:3]:
                print("  樣本：", i.get("title"), i.get("price"), i.get("nindex"), history_id(i))
            if items and not hit:
                print("  第一筆原始欄位：", json.dumps(items[0], ensure_ascii=False)[:600])
    except (Blocked, requests.RequestException) as e:
        print(f"失敗：{e}", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", nargs="+", metavar="KEYWORD")
    args = ap.parse_args()
    if args.probe:
        return probe(args.probe)

    keywords = read_keywords()
    if not keywords:
        print("scraper/keywords.txt 沒有關鍵字。", file=sys.stderr)
        return 2

    s = requests.Session()
    found: dict[str, dict] = {}
    ok = 0
    try:
        for kw in keywords:
            try:
                items = search(s, kw)
            except requests.RequestException as e:
                print(f"略過 {kw}: {e}", file=sys.stderr)
                continue
            ok += 1
            for it in items:
                hid = history_id(it)
                if hid and is_target_store(it) and hid not in found:
                    found[hid] = it
        if not ok:
            print("所有關鍵字搜尋都失敗。", file=sys.stderr)
            return 2
        print(f"符合酷澎的商品：{len(found)} 件")
        ids = list(found)[:MAX_PRODUCTS]
        hist = fetch_history(s, ids)
    except Blocked as e:
        print(f"被阻擋，停止（不嘗試繞過）：{e}", file=sys.stderr)
        return 2
    except requests.RequestException as e:
        print(f"請求失敗：{e}", file=sys.stderr)
        return 2

    products = [p for hid in ids if hid in hist and (p := build_product(found[hid], hist[hid]))]
    if not found:
        print("BigGo 搜尋結果中沒有酷澎商品；請先用 --probe 或 Probe workflow 檢查是否收錄。", file=sys.stderr)
        return 2
    if not products:
        print("今天沒有符合降價門檻的商品；保留舊資料。")
        return 0

    products.sort(key=lambda p: p["discount_pct"], reverse=True)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(products),
        "source": "BigGo",
        "products": products,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成：{len(products)} 件降價商品")
    return 0


if __name__ == "__main__":
    sys.exit(main())
