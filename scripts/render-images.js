// Génère les visuels PNG des produits (pour Google et les partages) : node scripts/render-images.js
// Nécessite Playwright. À relancer après ajout d'un produit sans photo.
const { chromium } = require("playwright");
const path = require("path");
const { products } = require("../assets/js/products.js");
(async () => {
  const root = path.join(__dirname, "..");
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 800, height: 1000 } });
  await p.goto("file://" + path.join(root, "index.html"));
  await p.waitForTimeout(1500);
  for (const prod of products) {
    if (prod.images && prod.images.length) continue;
    await p.evaluate((id) => {
      const prod = window.FADE_PRODUCTS.find((x) => x.id === id);
      document.body.innerHTML = '<div id="shot" style="width:800px;height:1000px;background:#efefec">' + window.FADE.art(prod) + "</div>";
      document.querySelector("#shot svg").style.cssText = "width:100%;height:100%";
    }, prod.id);
    await (await p.$("#shot")).screenshot({ path: path.join(root, "assets/img/products", prod.id + ".png") });
  }
  await b.close();
})();
