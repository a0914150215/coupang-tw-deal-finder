# Coupang Taiwan Deal Finder

每日透過 BigGo 取得酷澎(Coupang)台灣商品價格與歷史價，列出「現價低於近 30 日最高價」的商品，以靜態網頁呈現。

## 設定
1. 編輯 `scraper/keywords.txt`，列出要追蹤的關鍵字。
2. Settings → Actions → General → Workflow permissions 選 **Read and write permissions**。
3. Settings → Pages → Deploy from a branch → `main` / `(root)`。
4. **先跑 Actions → Probe BigGo coverage**，確認 BigGo 有收錄酷澎商品（看 log 的「符合」筆數）。
5. 再手動跑 **Update Coupang Taiwan deals**。之後每天 UTC 00:00（台灣 08:00）自動執行。

## 說明
- 參考價是 BigGo 記錄的「近 N 日最高價」(`REF_DAYS`，預設 30)，不是 Coupang 頁面的劃線原價。
- 其他環境變數：`STORE_FILTER`（預設 `coupang,酷澎`）、`MIN_DISCOUNT_PCT`（5）、`MAX_PRODUCTS`（200）。
- 被阻擋（401/403/429/503）即停止、不繞過；保留舊資料並讓 workflow 失敗以便收到通知。
- 使用的是 BigGo 網站所用的公開端點，非官方文件化 API；請留意 BigGo 的使用條款。

## 本機測試
    pip install -r scraper/requirements.txt
    python scraper/update_deals.py --probe 衛生紙
    python scraper/update_deals.py
    python -m http.server 8000

非官方個人工具，價格以 Coupang 商品頁為準。
