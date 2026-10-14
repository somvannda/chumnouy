import uiPreset from "../../packages/ui/tailwind-preset.js";

/** @type {import('tailwindcss').Config} */
export default {
  presets: [uiPreset],
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "Niradei", "Noto Sans Khmer Web", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        soft: "0 14px 40px rgba(28, 31, 42, .07)",
        panel: "0 28px 70px rgba(28, 31, 42, .12)",
      },
    },
  },
  plugins: [],
};
