/* CINEVAULT store configuration — edit checkout links here once payment is connected */
const STORE = {
  name: "CineVault",
  tagline: "Digital products for creators",
  email: "support@gamerod.store",
  currency: "USD",
  // Payment provider: "gumroad" | "payhip" | "stripe" | "custom"
  // Put each product's checkout URL here (Payhip/Gumroad product link or Stripe Payment Link).
  // Until a link is set, the Buy button shows a "coming soon" notice.
  checkoutLinks: {
    // Product 1 — 50 Cinematic LUTs ($15) — live on Payhip since 2026-09-27
    "cinematic-luts-mobile": "https://payhip.com/b/LSaxk",
  },
  checkoutProvider: "payhip",
};
