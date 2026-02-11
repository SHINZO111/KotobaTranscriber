/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{html,js,svelte,ts}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        brand: "var(--brand)",
        "brand-hover": "var(--brand-hover)",
        surface: "var(--bg-surface)",
        "surface-hover": "var(--bg-surface-hover)",
        "surface-raised": "var(--bg-surface-raised)",
      },
      fontFamily: {
        sans: ["Inter", "Noto Sans JP", "system-ui", "-apple-system", "sans-serif"],
        jp: ["Noto Sans JP", "system-ui", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "8px",
        sm: "6px",
        md: "8px",
        lg: "12px",
        xl: "16px",
      },
      boxShadow: {
        xs: "var(--shadow-xs)",
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
        xl: "var(--shadow-xl)",
        brand: "var(--shadow-brand)",
      },
    },
  },
  plugins: [],
};
