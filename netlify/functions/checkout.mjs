// POST /api/checkout — crée une session de paiement Stripe Checkout.
// Les prix sont TOUJOURS recalculés ici à partir du catalogue : le navigateur
// n'envoie que des identifiants et des quantités, il ne peut pas modifier un prix.
import catalog from "../../assets/js/products.js";
import CFG from "../../assets/js/config.js";
import { stripe, json } from "../lib/stripe.mjs";

const cents = (n) => Math.round(n * 100);
const clean = (s, max = 200) => String(s || "").replace(/[\u0000-\u001f]/g, " ").trim().slice(0, max);

export default async (req) => {
  if (req.method !== "POST") return json({ error: "Méthode non autorisée" }, 405);

  let body;
  try { body = await req.json(); } catch { return json({ error: "Requête invalide" }, 400); }

  // Panier : uniquement des produits existants, quantités 1..99, 30 lignes max.
  const items = Array.isArray(body.items) ? body.items.slice(0, 30) : [];
  const lines = [];
  for (const it of items) {
    const p = catalog.products.find((x) => x.id === it.id);
    const qty = Math.floor(Number(it.qty));
    if (!p || !(qty >= 1 && qty <= 99)) return json({ error: "Panier invalide, rechargez la page." }, 400);
    lines.push({ p, qty });
  }
  if (!lines.length) return json({ error: "Votre panier est vide." }, 400);

  const ship = CFG.shipping.find((s) => s.id === body.shipping) || CFG.shipping[0];
  const subtotal = lines.reduce((s, l) => s + l.p.price * l.qty, 0);
  const shipCost = ship.price > 0 && CFG.freeShippingFrom && subtotal >= CFG.freeShippingFrom ? 0 : ship.price;

  const origin = process.env.URL || new URL(req.url).origin;
  const c = body.customer || {};
  const orderNo = clean(body.orderNo, 40) || "FADE-" + Date.now().toString(36).toUpperCase();
  const note = clean(c.note, 450);

  const params = {
    mode: "payment",
    locale: "fr",
    success_url: `${origin}/merci.html?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${origin}/commande.html?annule=1`,
    client_reference_id: orderNo,
    customer_email: /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(c.email || "") ? clean(c.email, 120) : undefined,
    phone_number_collection: { enabled: true },
    billing_address_collection: "auto",
    line_items: lines.map((l, i) => ({
      quantity: l.qty,
      price_data: {
        currency: "eur",
        unit_amount: cents(l.p.price),
        product_data: {
          name: l.p.name,
          description: l.p.size,
          metadata: { product_id: l.p.id }
        }
      }
    })),
    shipping_options: [{
      shipping_rate_data: {
        type: "fixed_amount",
        display_name: ship.label,
        fixed_amount: { amount: cents(shipCost), currency: "eur" }
      }
    }],
    metadata: { commande: orderNo, livraison: ship.id, nom: clean(c.name, 100), telephone: clean(c.phone, 30), note },
    payment_intent_data: {
      description: `Commande ${orderNo}`,
      metadata: { commande: orderNo, livraison: ship.id }
    },
    custom_text: {
      submit: { message: ship.needsAddress ? "Expédition sous 48 h ouvrées après paiement." : "Nous vous contactons pour fixer le créneau de retrait au salon." }
    }
  };
  if (ship.needsAddress) params.shipping_address_collection = { allowed_countries: ["FR"] };

  try {
    const session = await stripe("POST", "checkout/sessions", params);
    return json({ url: session.url, id: session.id });
  } catch (e) {
    return json({ error: e.status === 503 ? "Le paiement en ligne n'est pas encore activé." : e.message, code: e.status }, e.status || 500);
  }
};

export const config = { path: "/api/checkout" };
