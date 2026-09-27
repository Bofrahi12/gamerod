/* CINEVAULT store configuration — edit checkout links here once payment is connected */
const STORE = {
  name: "CineVault",
  tagline: "Digital products for creators",
  currency: "USD",
  // Payment provider: "gumroad" | "payhip" | "stripe" | "custom"
  // Put each product's checkout URL here (Payhip/Gumroad product link or Stripe Payment Link).
  // Until a link is set, the Buy button shows a "coming soon" notice.
  checkoutLinks: {
    // Product 1 — 50 Cinematic LUTs ($15) — live on Payhip since 2026-09-27
    "cinematic-luts-mobile": "https://payhip.com/b/LSaxk",
    "wedding-luts-25": "https://payhip.com/b/Cde8v",
    "cinematic-sfx-30": "https://payhip.com/b/WV8cQ",
    // Product 2 — Sony S-Log3 Cinematic Pack ($15) — live on Payhip since 2026-09-27
    "sony-slog3-luts": "https://payhip.com/b/V50JF",
    // Product 3 — Film Grain + Light Leaks ($14) — live on Payhip since 2026-09-27
    "grain-leaks-pack": "https://payhip.com/b/OcJhe",
    // Product 4 — 50 Seamless Transitions ($16) — live on Payhip since 2026-09-27
    "viral-transitions": "https://payhip.com/b/DxKeM",
    // Complete Bundle — all 6 packs ($87 value → $39) — live on Payhip since 2026-09-27
    "cinevault-complete-bundle": "https://payhip.com/b/Ikv9o",
  },
  checkoutProvider: "payhip",
};
