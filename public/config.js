/* ==========================================================================
 * PromptMaster Studio: Open-Access & Voluntary Support Configuration
 * --------------------------------------------------------------------------
 * PromptMaster Studio is 100% free, unlocked, and open-access by default
 * with zero paywalls, zero license keys, and zero telemetry.
 * Voluntary tips via Buy Us a Coffee (Stripe) or Solana are optional.
 * ========================================================================== */
window.PROMPTMASTER_CONFIG = {
  product: {
    name: "PromptMaster Studio",
    priceUsd: 0,
    priceLabel: "100% Free & Open Access",
    billing: "open-access"
  },

  stripe: {
    paymentLink: "https://buy.stripe.com/3cIfZg27PdKo2D64Ocfw40X"
  },

  solana: {
    recipient: "GG2eQbVh8ut1BK6j1A2tz7pSySdLpD38BgyEhGcxdXoK",
    amount: "",
    splToken: "",
    tokenLabel: "SOL",
    label: "PromptMaster Studio",
    message: "PromptMaster Studio Voluntary Coffee Tip",
    rpcUrl: ""
  },

  supportEmail: "support@nullai.tech"
};
