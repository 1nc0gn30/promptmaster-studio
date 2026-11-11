/* ==========================================================================
 * PromptMaster Studio: Open-Access & Voluntary Support Configuration
 * --------------------------------------------------------------------------
 * PromptMaster Studio is 100% free, unlocked, and open-source by default
 * with zero license keys and zero telemetry.
 * Voluntary tips via Buy Us a Coffee (Stripe) are optional.
 * ========================================================================== */
window.PROMPTMASTER_CONFIG = {
  product: {
    name: "PromptMaster Studio",
    priceUsd: 0,
    priceLabel: "Free",
    billing: "open-access"
  },

  stripe: {
    paymentLink: "https://buy.stripe.com/3cIfZg27PdKo2D64Ocfw40X"
  },

  solana: {
    recipient: "",
    amount: "",
    splToken: "",
    tokenLabel: "SOL",
    label: "PromptMaster Studio",
    message: "PromptMaster Studio Voluntary Coffee Tip",
    rpcUrl: ""
  },

  freeTaste: {
    fullRuns: 999999,
    previewLines: 999999
  },

  license: {
    verifyEndpoint: ""
  },

  supportEmail: "support@nullai.tech"
};
