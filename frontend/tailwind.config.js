/** @type {import('tailwindcss').Config} */
// German-Kanzlei visual system (design spec §3). Restrained, precise, paper-adjacent.
// Deep ledger-green accent (not blue — blue reads "SaaS/AI"), warm neutrals, borders
// over shadows, one accent hue.
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#1A1D21", 2: "#4B5563" },
        paper: "#FBFAF7", // warm off-white app background
        surface: "#FFFFFF",
        line: "#E7E3DB", // warm grey border
        brand: { DEFAULT: "#0F5132", dark: "#0C4429", tint: "#E9F1EC" },
        enter: { DEFAULT: "#059669", tint: "#ECFDF5" }, // recompute "added" flash
        excluded: "#6B7280",
        pending: "#B45309",
        // escalation category tones
        warn: { DEFAULT: "#B91C1C", tint: "#FEF2F2" }, // tax_advice
        amber: "#B45309", // outcome_speculation
        slate: "#475569", // out_of_scope
        violet: "#6D28D9", // unmapped_answer
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        serif: ["Source Serif 4", "Georgia", "serif"],
      },
      keyframes: {
        enterFlash: {
          "0%": { backgroundColor: "#ECFDF5" },
          "100%": { backgroundColor: "transparent" },
        },
      },
      animation: {
        enterFlash: "enterFlash 600ms ease-out",
      },
    },
  },
  plugins: [],
};
