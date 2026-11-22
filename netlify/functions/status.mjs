// GET /api/status — indique au site si le paiement en ligne est actif.
import { stripeConfigured, json } from "../lib/stripe.mjs";

export default async () => {
  const key = process.env.STRIPE_SECRET_KEY || "";
  return json({ payments: stripeConfigured(), mode: key.startsWith("sk_live") || key.startsWith("rk_live") ? "live" : key ? "test" : "off" });
};

export const config = { path: "/api/status" };
