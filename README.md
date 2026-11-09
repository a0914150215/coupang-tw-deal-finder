# Coupang Taiwan Deal Finder

台灣 Coupang 公開商品資訊折扣排行頁面。支援關鍵字搜尋、折扣率／折扣金額／價格排序，並以 GitHub Actions 每日更新資料。

## 功能

- 靜態網頁：商品卡片、圖片、售價、可辨識原價與折扣率。
- 前端篩選與排序：折扣率、折扣金額、價格、更新時間。
- 每日排程：台灣時間約 08:00（UTC 00:00）。
- 手動執行：GitHub → Actions → Update Coupang Taiwan deals → Run workflow。
- 資料檔：`data/products.json`，Git 歷史可追蹤每日資料變化。

## 啟用 GitHub Pages

1. 開啟 Repository → Settings → Pages。
2. 在 Build and deployment 選擇 **Deploy from a branch**。
3. Branch 選 `main`，資料夾選 `/ (root))，按 Save。
4. 等待部署完成後，Pages 網址會顯示在該頁面。

## 執行更新

Actions 頁面選擇 **Update Coupang Taiwan deals**，按 **Run workflow** 可手動執行。排程為 UTC 00:00（台灣時間 08:00）；GitHub 排程可能延遲，並非準點保證。

## 資料來源與限制

擷取程式只讀取不需登入的公開頁面及其 JSON-LD Product 結構化資料，不使用帳號、不繞過 CAPTCHA、登入牆或反爬限制。若網站回應 403／429／503，程式會停止或略過，不會嘗試規避。Coupang 網站結構或服務條款變更可能令擷取失效。

Coupang 官方 Open API 主要提供賣家／合作夥伴管理商品與訂單等功能，並非消費者端全站折扣搜尋 API。因此本專案不宣稱有官方消費者商品搜尋 API。若公開頁面沒有提供可驗證的原價，商品不會被計算成折扣商品；不會用猜測價格製造折扣率。

## 本機測試

```bash
python -m pip install -r scraper/requirements.txt
python scraper/coupang_scraper.py
python -m http.server 8000
```

瀏覽 `http://localhost:8000`。

## 一鍵重新載入 vs. 觸發爬蟲

網頁的「重新載入」會重新讀取最新已提交的 JSON 資料，不會在瀏覽器內啟動爬蟲。要立即重新抓取資料，請使用 GitHub Actions 的 **Run workflow**。不把 GitHub Personal Access Token 放在公開網頁，避免憑證外洩。

## Disclaimer

本專案為非官方個人整理工具。商品售價、庫存、折扣資格及配送條件以 Coupang 台灣商品頁面為準。請遵守網站使用條款與適用法規。