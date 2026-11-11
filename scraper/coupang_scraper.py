#!/usr/bin/env python3
"""Coupang 台灣折扣商品擷取器（每日由 GitHub Actions 執行）。

流程：seeds.txt 的列表頁 -> 收集商品連結 -> 逐一讀取商品頁 JSON-LD -> 輸出 data/products.json
原則：只讀公開頁面；遇到 403/429/503 立即停止，不嘗試繞過。
結束碼：0 成功；2 被網站阻擋或沒有任何結果（舊資料保留，讓 Actions 失敗並寄通知）。
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SEEDS = ROOT / "scraper" / "seeds.txt"
OUT = ROOT / "data" / "products.json"

MAX_PRODUCTS = int(os.getenv("MAX_PRODUCTS", "150"))
MIN_DISCOUNT = float(os.getenv("MIN_DISCOUNT_PCT", "5"))
DELAY = (1.5, 3.5)
BLOCK_CODES = {403, 429, 503}
PRODUCT_LINK = re.compile(r"/vp/products/(\d+)")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; coupang-tw-deal-finder/2.0; +https://github.com/a0914150215/coupang-tw-deal-finder)",
    "Accept-Language": "zh-TW,zh;q=0.9",
}


class Blocked(Exception):
    pass


def fetch(session: requests.Session, url: str) -> str:
    r = session.get(url, headers=HEADERS, timeout=20)
    if r.status_code in BLOCK_CODES:
        raise Blocked(f"{r.status_code} {url}")
    r.raise_for_status()
    time.sleep(random.uniform(*DELAY))
    return r.text


def read_seeds() -> list[str]:
    if not SEEDS.exists():
        return []
    return [l.strip() for l in SEEDS.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")]


def product_links(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        if PRODUCT_LINK.search(a["href"]):
            u = urljoin(base, a["href"]).split("#")[0]
            key = urlparse(u).path
            if key not in seen:
                seen.add(key)
                out.append(u)
    return out


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _walk(node):
    if isinstance(node, list):
        for i in node:
            yield from _walk(i)
    elif isinstance(node, dict):
        yield node
        if isinstance(node.get("@graph"), list):
            yield from _walk(node["@graph"])


def parse_product(html: str, url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _walk(data):
            t = node.get("@type")
            if t != "Product" and not (isinstance(t, list) and "Product" in t):
                continue
            offers = node.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = _num(offers.get("price") or offers.get("lowPrice"))
            original = None
            specs = offers.get("priceSpecification") or []
            if isinstance(specs, dict):
                specs = [specs]
            for s in specs:
                kind = str(s.get("priceType", "")).lower()
                if any(k in kind for k in ("list", "strike", "msrp", "original")):
                    original = _num(s.get("price"))
            if original is None:
                original = _num(offers.get("highPrice"))
            # 沒有可驗證的原價就不算折扣商品，不猜測
            if not price or not original or original <= price:
                return None
            pct = round((original - price) / original * 100, 1)
            if pct < MIN_DISCOUNT or pct > 90:
                return None
            img = node.get("image")
            if isinstance(img, list):
                img = img[0] if img else None
            if not (isinstance(img, str) and img.startswith("https://")):
                img = None
            m = PRODUCT_LINK.search(url)
            return {
                "id": m.group(1) if m else url,
                "name": str(node.get("name", "")).strip()[:200],
                "url": url,
                "image": img,
                "price": int(price),
                "original_price": int(original),
                "discount_pct": pct,
                "discount_amount": int(original - price),
                "currency": offers.get("priceCurrency", "TWD"),
            }
    return None


def main() -> int:
    seeds = read_seeds()
    if not seeds:
        print("scraper/seeds.txt 沒有任何網址，請先填入。", file=sys.stderr)
        return 2

    session = requests.Session()
    links: list[str] = []
    products: list[dict] = []
    try:
        for s in seeds:
            for u in product_links(fetch(session, s), s):
                if u not in links:
                    links.append(u)
        print(f"找到 {len(links)} 個商品連結")
        for u in links[:MAX_PRODUCTS]:
            try:
                p = parse_product(fetch(session, u), u)
            except requests.RequestException as e:
                print(f"略過 {u}: {e}", file=sys.stderr)
                continue
            if p:
                products.append(p)
    except Blocked as e:
        print(f"被網站阻擋，停止（不嘗試繞過）：{e}", file=sys.stderr)
        return 2
    except requests.RequestException as e:
        print(f"列表頁讀取失敗：{e}", file=sys.stderr)
        return 2

    if not products:
        print("沒有取得任何可驗證折扣的商品，保留舊資料。", file=sys.stderr)
        return 2

    products.sort(key=lambda p: p["discount_pct"], reverse=True)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(products),
        "products": products,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成：{len(products)} 件折扣商品")
    return 0


if __name__ == "__main__":
    sys.exit(main())
