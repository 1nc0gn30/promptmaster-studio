/* ==========================================================================
 * PromptMaster Studio: checkout & unlock configuration
 * --------------------------------------------------------------------------
 * This is the ONLY place payment settings live. index.html reads
 * window.PROMPTMASTER_CONFIG, and nothing else hard-codes a checkout URL.
 *
 * Everything in this file ships to the browser, so it must only hold
 * PUBLIC values. Never put secret keys here (Stripe "sk_live_..." keys,
 * webhook secrets, wallet seed phrases or private keys).
 *
 * Leave a value as "" to switch that option off. The UI then hides or
 * disables that button with a short explanation instead of breaking.
 * ========================================================================== */
window.PROMPTMASTER_CONFIG = {
  product: {
    name: "PromptMaster Studio Pro",
    // Existing price, already used across the site, legal pages and schema.
    // If you change it, also update the static "$19" text in index.html and
    // the JSON-LD "price" field, so search engines see the same number.
    priceUsd: 19,
    priceLabel: "$19",
    billing: "one-time"
  },

  stripe: {
    // REQUIRED for card payments: your Stripe Payment Link (Dashboard -> Payment Links).
    // In that Payment Link, open "After payment", choose "Don't show confirmation page",
    // and redirect to:
    //   https://promptmaster-studio.netlify.app/?checkout=success&session_id={CHECKOUT_SESSION_ID}
    // Stripe swaps in the real session id, and the site unlocks Pro on return.
    paymentLink: "https://buy.stripe.com/cNiaEWaEldKo6Tm1C0fw40D"
  },

  solana: {
    // REQUIRED for crypto payments: the PUBLIC address of the wallet that should
    // receive payments (base58, 32-44 chars). Empty = the crypto option shows as unavailable.
    recipient: "",
    // Amount in units of the token below. 19 USDC matches the $19 price.
    amount: "19",
    // SPL token mint. This default is the official USDC mint on Solana mainnet.
    // Set it to "" to take native SOL instead, and set `amount` in SOL.
    splToken: "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    tokenLabel: "USDC",
    label: "PromptMaster Studio",
    message: "PromptMaster Studio Pro (lifetime)",
    // OPTIONAL: a Solana JSON-RPC URL that allows browser (CORS) requests, e.g. a
    // Helius/QuickNode/Triton endpoint restricted to your domain. When set, the
    // checkout auto-detects the payment by its Solana Pay reference key.
    // When empty, the buyer pastes their transaction signature to unlock.
    rpcUrl: ""
  },

  freeTaste: {
    // How many distinct prompts a visitor can optimize with the FULL output
    // visible (plus copy/export) before results switch to preview mode.
    fullRuns: 1,
    // In preview mode, how many lines of the optimized prompt stay readable.
    previewLines: 6
  },

  license: {
    // OPTIONAL server-side verification of Stripe sessions. Deploy
    // netlify/functions/verify-checkout.mjs with STRIPE_SECRET_KEY set in the
    // Netlify UI, then set this to "/.netlify/functions/verify-checkout".
    // Empty = the unlock is trusted client-side (honour system, see README).
    verifyEndpoint: ""
  },

  supportEmail: "support@nealfrazier.tech"
};
