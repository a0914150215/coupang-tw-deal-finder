# Coupang Taiwan Deal Finder

每日自動抓取 Coupang 台灣公開商品頁（JSON-LD 結構化資料），整理成折扣排行靜態網頁。

## 設定（一次即可）
1. 編輯 `scraper/seeds.txt`，填入要追蹤的公開列表／分類／搜尋頁網址（每行一個）。
2. Settings → Actions → General → Workflow permissions 選 **Read and write permissions**。
3. Settings → Pages → Deploy from a branch → `main` / `(root)`。
4. Actions → **Update Coupang Taiwan deals** → Run workflow 先手動跑一次。

之後每天 UTC 00:00（台灣 08:00）自動執行。

## 行為
- 只計入頁面有「可驗證原價」的商品；沒有原價不會被當成折扣商品。
- 遇到 403/429/503 立即停止，不繞過；此時保留舊資料，並讓 workflow 顯示失敗（GitHub 會寄通知）。
- 環境變數：`MAX_PRODUCTS`（預設 150）、`MIN_DISCOUNT_PCT`（預設 5）。

## 本機測試
    pip install -r scraper/requirements.txt
    python scraper/coupang_scraper.py
    python -m http.server 8000

非官方個人工具，價格以 Coupang 商品頁為準，請遵守網站條款。
