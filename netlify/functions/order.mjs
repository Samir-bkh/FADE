// GET /api/order?session_id=cs_... — vérifie côté serveur qu'une commande est bien payée.
import { stripe, json } from "../lib/stripe.mjs";

export default async (req) => {
  const id = new URL(req.url).searchParams.get("session_id") || "";
  if (!/^cs_(test|live)_[A-Za-z0-9]{10,}$/.test(id)) return json({ error: "Commande introuvable" }, 400);
  try {
    const s = await stripe("GET", `checkout/sessions/${id}`, { expand: ["line_items"] });
    const d = s.customer_details || {};
    return json({
      order: s.client_reference_id,
      paid: s.payment_status === "paid",
      status: s.payment_status,
      total: s.amount_total / 100,
      shipping: (s.shipping_cost && s.shipping_cost.amount_total / 100) || 0,
      name: d.name || "",
      email: d.email || "",
      delivery: (s.metadata && s.metadata.livraison) || "",
      items: ((s.line_items && s.line_items.data) || []).map((l) => ({ name: l.description, qty: l.quantity, total: l.amount_total / 100 }))
    });
  } catch (e) {
    return json({ error: "Impossible de vérifier la commande." }, e.status || 500);
  }
};

export const config = { path: "/api/order" };
