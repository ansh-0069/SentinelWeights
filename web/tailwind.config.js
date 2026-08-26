/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#14110F",
          800: "#2A2622",
          600: "#5C564E",
          400: "#8A8278",
        },
        paper: {
          DEFAULT: "#F3EFE8",
          card: "#FFFcf8",
          line: "#E6E0D6",
        },
        forest: {
          DEFAULT: "#1F6F5B",
          dim: "#E7F2EE",
        },
        rust: {
          DEFAULT: "#B42318",
          dim: "#F8E8E6",
        },
        clay: {
          DEFAULT: "#C2410C",
          dim: "#F8EDE4",
        },
        // Pastel accent families used to colour-code panels by meaning.
        lavender: { DEFAULT: "#6366F1", soft: "#C7CCFF", dim: "#EEF0FF" },
        mint: { DEFAULT: "#0E9F7E", soft: "#A7E3CD", dim: "#E6F6F0" },
        sky: { DEFAULT: "#2E7DD1", soft: "#B6D9FB", dim: "#E8F2FE" },
        blush: { DEFAULT: "#D94F70", soft: "#F9C9D4", dim: "#FDEDF1" },
        butter: { DEFAULT: "#B07D0C", soft: "#FBE3A2", dim: "#FEF6E0" },
      },
      fontFamily: {
        sans: ["Segoe UI", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Georgia", "Iowan Old Style", "Times New Roman", "serif"],
        mono: ["Cascadia Mono", "Segoe UI Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 10px 30px rgba(20,17,15,0.04), 0 1px 0 rgba(20,17,15,0.04)",
        lift: "0 18px 40px -12px rgba(20,17,15,0.18), 0 2px 6px rgba(20,17,15,0.06)",
        shell: "0 40px 90px -30px rgba(20,17,15,0.35), 0 8px 24px -12px rgba(20,17,15,0.12)",
        glow: "0 0 0 1px rgba(255,255,255,0.6) inset, 0 12px 30px -14px rgba(99,102,241,0.45)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(14px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.96)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "slide-right": {
          "0%": { opacity: "0", transform: "translateX(-10px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        shimmer: {
          "0%": { transform: "translateX(-120%)" },
          "100%": { transform: "translateX(220%)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-7px)" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.85)", opacity: "0.65" },
          "70%": { transform: "scale(1.7)", opacity: "0" },
          "100%": { transform: "scale(1.7)", opacity: "0" },
        },
        "gradient-pan": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        "bar-grow": {
          "0%": { transform: "scaleY(0)" },
          "100%": { transform: "scaleY(1)" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.25" },
        },
      },
      animation: {
        // `backwards` (not `both`) so the settled transform reverts to the base
        // value and :hover lifts still apply once the entrance finishes.
        "fade-up": "fade-up 0.5s cubic-bezier(0.22,1,0.36,1) backwards",
        "fade-in": "fade-in 0.45s ease-out backwards",
        "scale-in": "scale-in 0.4s cubic-bezier(0.22,1,0.36,1) backwards",
        "slide-right": "slide-right 0.4s cubic-bezier(0.22,1,0.36,1) backwards",
        shimmer: "shimmer 2.2s ease-in-out infinite",
        float: "float 6s ease-in-out infinite",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(0.24,0,0.38,1) infinite",
        "gradient-pan": "gradient-pan 9s ease infinite",
        "bar-grow": "bar-grow 0.7s cubic-bezier(0.22,1,0.36,1) both",
        blink: "blink 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
