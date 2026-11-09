const DATA_URL = "data/products.json";
const $ = (id) => document.getElementById(id);
let products = [];

function money(value) {
  if (value === null || value === undefined || value === "") return "—";
  return new Intl.NumberFormat("zh-TW", {style:"currency",currency:"TWD",maximumFractionDigits:0}).format(Number(value));
}
function discountRate(p) {
  return p.original_price > p.price && p.price > 0 ? Math.round((1-p.price/p.original_price)*100) : 0;
}
function render() {
  const keyword = $("search-input").value.trim().toLocaleLowerCase();
  const sort = $("sort-select").value;
  const filtered = products.filter(p => (p.name || "").toLocaleLowerCase().includes(keyword));
  filtered.sort((a,b) => {
    if (sort === "saving") return (b.original_price-b.price)-(a.original_price-a.price);
    if (sort === "price-asc") return a.price-b.price;
    if (sort === "price-desc") return b.price-a.price;
    if (sort === "newest") return new Date(b.seen_at || 0)-new Date(a.seen_at || 0);
    return discountRate(b)-discountRate(a);
  });
  $("product-grid").replaceChildren();
  for (const p of filtered) {
    const card = document.createElement("article"); card.className = "product-card";
    const imageWrap = document.createElement("div"); imageWrap.className = "product-image";
    if (p.image) { const img = document.createElement("img"); img.src = p.image; img.alt = p.name || "商品圖片"; img.loading = "lazy"; img.referrerPolicy = "no-referrer"; img.onerror = () => img.remove(); imageWrap.append(img); }
    if (discountRate(p)) { const badge = document.createElement("span"); badge.className = "discount"; badge.textContent = "-" + discountRate(p) + "%"; imageWrap.append(badge); }
    const info = document.createElement("div"); info.className = "product-info";
    const name = document.createElement("h3"); name.className = "product-name"; name.textContent = p.name || "未命名商品";
    const prices = document.createElement("div"); prices.className = "price-line";
    const sale = document.createElement("strong"); sale.className = "sale-price"; sale.textContent = money(p.price);
    prices.append(sale);
    if (p.original_price) { const original = document.createElement("span"); original.className = "original-price"; original.textContent = money(p.original_price); prices.append(original); }
    const saving = document.createElement("div"); saving.className = "saving"; saving.textContent = discountRate(p) ? "現省 " + money(p.original_price-p.price) : "價格資訊以商品頁為準";
    const link = document.createElement("a"); link.className = "product-link"; link.href = p.url; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = "查看 Coupang 商品 ↗";
    info.append(name,prices,saving,link); card.append(imageWrap,info); $("product-grid").append(card);
  }
  $("result-count").textContent = filtered.length + " 件商品";
  $("empty-state").hidden = filtered.length !== 0;
}
async function loadData() {
  const button = $("refresh-button"); button.disabled = true; button.innerHTML = "<span>↻</span> 載入中";
  $("status").textContent = "正在讀取商品資料…";
  try {
    const response = await fetch(DATA_URL + "?v=" + Date.now(), {cache:"no-store"});
    if (!response.ok) throw new Error("商品資料尚未建立（HTTP " + response.status + "）");
    const data = await response.json(); products = Array.isArray(data.products) ? data.products : [];
    $("total-count").textContent = products.length;
    const best = products.reduce((max,p) => Math.max(max,discountRate(p)),0);
    $("best-discount").textContent = best ? best + "%" : "—";
    $("updated-at").textContent = data.updated_at ? new Date(data.updated_at).toLocaleString("zh-TW",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}) : "—";
    $("status").textContent = products.length ? "資料載入完成。折扣僅依可驗證的原價與售價計算。" : "資料來源目前未回傳可辨識的商品；請稍後再試。";
    render();
  } catch (error) {
    $("status").textContent = error.message + "。請確認 GitHub Actions 已成功執行資料更新。";
    products = []; render(); $("total-count").textContent = "0"; $("best-discount").textContent = "—";
  } finally { button.disabled = false; button.innerHTML = "<span>↻</span> 重新載入"; }
}
$("search-input").addEventListener("input",render);
$("sort-select").addEventListener("change",render);
$("refresh-button").addEventListener("click",loadData);
loadData();