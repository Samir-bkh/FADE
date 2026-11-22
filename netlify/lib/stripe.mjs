// Petit client Stripe sans dépendance (API REST officielle, HTTPS).
const API = "https://api.stripe.com/v1/";

function flatten(obj, prefix, out) {
  out = out || new URLSearchParams();
  for (const [k, v] of Object.entries(obj)) {
    if (v === undefined || v === null || v === "") continue;
    const key = prefix ? `${prefix}[${k}]` : k;
    if (typeof v === "object") flatten(v, key, out);
    else out.append(key, String(v));
  }
  return out;
}

export function stripeConfigured() {
  return Boolean(process.env.STRIPE_SECRET_KEY);
}

export async function stripe(method, path, params) {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) throw Object.assign(new Error("Stripe non configuré"), { status: 503 });
  const init = {
    method,
    headers: {
      Authorization: `Bearer ${key}`,
      "Stripe-Version": "2024-06-20"
    }
  };
  let url = API + path;
  if (params && method === "GET") url += "?" + flatten(params).toString();
  else if (params) {
    init.headers["Content-Type"] = "application/x-www-form-urlencoded";
    init.body = flatten(params).toString();
  }
  const res = await fetch(url, init);
  const data = await res.json();
  if (!res.ok) {
    const err = new Error((data.error && data.error.message) || "Erreur Stripe");
    err.status = res.status >= 500 ? 502 : 400;
    throw err;
  }
  return data;
}

export function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" }
  });
}
