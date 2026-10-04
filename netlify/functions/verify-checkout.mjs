// Netlify Function: GET /.netlify/functions/verify-checkout?session_id=cs_...
//
// Optional server-side check that a Stripe Checkout Session (created by the
// Payment Link) was really paid. It's only called when
// window.PROMPTMASTER_CONFIG.license.verifyEndpoint is set in public/config.js.
//
// Required environment variables (set in Netlify UI -> Site configuration ->
// Environment variables; NEVER commit them):
//   STRIPE_SECRET_KEY        a restricted key with read access to Checkout Sessions
// Optional:
//   STRIPE_PAYMENT_LINK_ID   plink_... (only sessions from this Payment Link count)
//
// Responses: 200 {paid:true|false}, 400 bad id, 404 unknown session,
// 501 not configured (the site then falls back to client-side trust).
// No dependencies: uses the Stripe REST API via fetch (Node 18+).

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });

export default async (req) => {
  const sessionId = new URL(req.url).searchParams.get("session_id") || "";
  if (!/^cs_(live|test)_[A-Za-z0-9]{10,}$/.test(sessionId)) {
    return json({ paid: false, error: "invalid_session_id" }, 400);
  }
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) return json({ paid: false, error: "not_configured" }, 501);

  let res;
  try {
    res = await fetch(`https://api.stripe.com/v1/checkout/sessions/${encodeURIComponent(sessionId)}`, {
      headers: { Authorization: `Bearer ${key}` },
    });
  } catch {
    return json({ paid: false, error: "stripe_unreachable" }, 502);
  }
  if (res.status === 404) return json({ paid: false, error: "not_found" }, 404);
  if (!res.ok) return json({ paid: false, error: "stripe_error" }, 502);

  const session = await res.json();
  const wantLink = process.env.STRIPE_PAYMENT_LINK_ID;
  const linkMatches = !wantLink || session.payment_link === wantLink;
  const paid = session.status === "complete" && session.payment_status === "paid" && linkMatches;
  return json({ paid });
};
