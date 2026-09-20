import type { Config } from "tailwindcss";

export default {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#f8f8fb",
        foreground: "#202238",
        border: "#e8e7ee",
        primary: { DEFAULT: "#d80b79", foreground: "#ffffff" },
        muted: { DEFAULT: "#f5f4f8", foreground: "#6f7082" },
      },
      boxShadow: {
        panel: "0 8px 24px rgba(31, 31, 51, .055), 0 1px 3px rgba(31, 31, 51, .06)",
      },
    },
  },
  plugins: [],
} satisfies Config;
