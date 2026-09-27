/* CINEVAULT storefront engine — renders catalog from data/products.json */
let PRODUCTS = [];

async function loadProducts() {
  if (PRODUCTS.length) return PRODUCTS;
  const r = await fetch("data/products.json");
  PRODUCTS = await r.json();
  return PRODUCTS;
}

function money(n) {
  return "$" + Number(n).toFixed(n % 1 ? 2 : 0);
}

function coverHTML(p) {
  const badge = p.badge ? `<span class="badge${p.badge === "Bundle" ? " bundle" : ""}">${p.badge}</span>` : "";
  const art = p.cover
    ? `<img src="${p.cover}" alt="${esc(p.title || p.short)}" loading="lazy">`
    : `<div class="css-art" style="background:${p.artBg || "linear-gradient(135deg,#232c44,#141a29)"}">
         <div class="art-icon">${p.icon || "✦"}</div>
         <div class="art-title">${esc(p.short || p.title)}</div>
       </div>`;
  return `<div class="cover">${art}${badge}</div>`;
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function cardHTML(p) {
  const old = p.oldPrice ? `<s>${money(p.oldPrice)}</s>` : "";
  return `<a class="card" href="product.html?id=${p.id}">
    ${coverHTML(p)}
    <div class="card-body">
      <div class="card-cat">${esc(p.category)}</div>
      <h3>${esc(p.title || p.short)}</h3>
      <p class="card-desc">${esc(p.tagline)}</p>
      <div class="card-meta">
        <span class="price">${old}${money(p.price)}</span>
        <span class="btn small">View</span>
      </div>
    </div>
  </a>`;
}

async function renderFeatured() {
  const list = await loadProducts();
  const el = document.getElementById("featured");
  if (!el) return;
  el.innerHTML = list.filter(p => p.featured).slice(0, 8).map(cardHTML).join("");
}

async function renderCatalog() {
  const list = await loadProducts();
  const grid = document.getElementById("catalog-grid");
  const pills = document.getElementById("cat-pills");
  if (!grid) return;
  const cats = ["All", ...new Set(list.map(p => p.category))];
  let active = "All", q = "";
  const search = document.getElementById("q");
  const draw = () => {
    const items = list.filter(p =>
      (active === "All" || p.category === active) &&
      (!q || (p.title + " " + p.tagline + " " + p.category).toLowerCase().includes(q)));
    grid.innerHTML = items.length ? items.map(cardHTML).join("")
      : `<p style="color:var(--muted)">No products match your search.</p>`;
  };
  pills.innerHTML = cats.map(c =>
    `<button class="pill${c === "All" ? " on" : ""}" data-c="${esc(c)}">${esc(c)}</button>`).join("");
  pills.querySelectorAll(".pill").forEach(b => b.onclick = () => {
    pills.querySelectorAll(".pill").forEach(x => x.classList.remove("on"));
    b.classList.add("on"); active = b.dataset.c; draw();
  });
  if (search) search.oninput = e => { q = e.target.value.trim().toLowerCase(); draw(); };
  draw();
}

async function renderProduct() {
  const id = new URLSearchParams(location.search).get("id");
  const list = await loadProducts();
  const p = list.find(x => x.id === id) || list[0];
  if (!p) return;
  document.title = (p.title || p.short) + " — CineVault";
  document.getElementById("pd").innerHTML = `
    <div class="pd-gallery">${coverHTML(p)}</div>
    <div class="pd-info">
      <div class="card-cat">${esc(p.category)}</div>
      <h1>${esc(p.title || p.short)}</h1>
      <p class="lede">${esc(p.tagline)}</p>
      <div class="buybox">
        <div class="row">
          <span class="price">${p.oldPrice ? `<s>${money(p.oldPrice)}</s> ` : ""}${money(p.price)}</span>
          ${p.oldPrice ? `<span class="badge">Save ${money(p.oldPrice - p.price)}</span>` : ""}
        </div>
        <button class="btn big" style="width:100%" onclick="buy('${p.id}')">Buy now — instant download</button>
        <p style="color:var(--muted);font-size:13px;margin-top:12px;text-align:center">Secure checkout · Instant delivery · ${esc(p.license || "Commercial license included")}</p>
      </div>
      <h3 style="margin-bottom:6px">What's inside</h3>
      <ul class="includes">${p.includes.map(i => `<li>${esc(i)}</li>`).join("")}</ul>
      <h3 style="margin:18px 0 6px">Details</h3>
      <p style="color:var(--muted)">${esc(p.description)}</p>
    </div>`;
  const rel = list.filter(x => x.id !== p.id && x.category === p.category).slice(0, 4);
  const relEl = document.getElementById("related");
  if (relEl && rel.length) relEl.innerHTML = rel.map(cardHTML).join("");
}

function buy(id) {
  const url = STORE.checkoutLinks[id];
  if (url) { window.open(url, "_blank"); return; }
  const m = document.getElementById("soon-modal");
  if (m) m.classList.add("show");
}
function closeModal() {
  document.getElementById("soon-modal").classList.remove("show");
}

document.addEventListener("DOMContentLoaded", () => {
  renderFeatured(); renderCatalog(); renderProduct();
  const y = document.getElementById("year");
  if (y) y.textContent = new Date().getFullYear();
});
