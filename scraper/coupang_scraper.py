#!/usr/bin/env python3
"""Conservative public-page collector for Coupang Taiwan.
Only requests ordinary public pages; does not log in, solve challenges, or bypass access controls.
If the site blocks automated access, stop and use an authorized data feed.
"""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://www.tw.coupang.com/"
OUT = Path("data/products.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CoupangTWDealFinder/1.0; +https://github.com/a0914150215/coupang-tw-deal-finder)"}
MAX_PAGES = 12
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def money(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^0-9.]", "", str(value).replace(",", ""))
    try:
        return float(text) if text else None
    except ValueError:
        return None


def walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def product_from_object(obj, page_url):
    if str(obj.get("@type", "")).lower() != "product":
        return None
    name = obj.get("name")
    offers = obj.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        offers = {}
    price = money(offers.get("price") or offers.get("lowPrice"))
    original = money(obj.get("highPrice") or offers.get("highPrice"))
    if original is None:
        original = money(obj.get("priceSpecification", {}).get("price")) if isinstance(obj.get("priceSpecification"), dict) else None
    image = obj.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    url = obj.get("url") or page_url
    if not name or not price or price <= 0:
        return None
    return {"name": str(name).strip(), "price": price, "original_price": original if original and original > price else None,
            "image": urljoin(page_url, image) if image else None, "url": urljoin(page_url, str(url))}


def fetch(url):
    response = SESSION.get(url, timeout=25)
    if response.status_code in (403, 429, 503):
        raise RuntimeError(f"網站回應 HTTP {response.status_code}，停止擷取；不嘗試繞過限制。")
    response.raise_for_status()
    return response.text


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    old = {}
    if OUT.exists():
        try:
            old = {p["url"]: p for p in json.loads(OUT.read_text("utf-8")).get("products", [])}
        except (ValueError, OSError):
            pass

    queue = [BASE]
    visited, found = set(), {}
    while queue and len(visited) < MAX_PAGES:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            html = fetch(url)
        except Exception as exc:
            print(f"Skip {url}: {exc}")
            if "HTTP 403" in str(exc) or "HTTP 429" in str(exc) or "HTTP 503" in str(exc):
                break
            continue
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                payload = json.loads(script.string or script.get_text())
            except (ValueError, TypeError):
                continue
            for obj in walk_json(payload):
                item = product_from_object(obj, url)
                if item:
                    found[item["url"]] = item

        # Follow only same-site links whose paths look like product or category pages.
        for a in soup.select("a[href]"):
            absolute = urljoin(url, a.get("href", "").split("?")[0])
            parsed = urlparse(absolute)
            if parsed.scheme not in ("http", "https") or parsed.netloc not in ("tw.coupang.com", "www.tw.coupang.com"):
                continue
            if absolute not in visited and ("/vp/" in parsed.path or "/np/" in parsed.path or "/categories/" in parsed.path):
                if absolute not in queue:
                    queue.append(absolute)
        time.sleep(1.5)

    now = datetime.now(timezone.utc).isoformat()
    output = []
    for url, item in found.items():
        previous = old.get(url, {})
        item["previous_price"] = previous.get("price")
        item["seen_at"] = now
        # Never infer a discount from a previous crawl price; only publish a discount when page markup provides a list price.
        output.append(item)
    output.sort(key=lambda p: ((1-p["price"]/p["original_price"]) if p.get("original_price") else 0), reverse=True)
    result = {"source": BASE, "updated_at": now, "count": len(output), "products": output}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(output)} products from {len(visited)} public pages.")


if __name__ == "__main__":
    main()