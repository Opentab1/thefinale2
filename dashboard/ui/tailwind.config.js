/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'pulse-blue': '#3b82f6',
        'pulse-green': '#10b981',
        'pulse-red': '#ef4444',
        'pulse-yellow': '#f59e0b',
      }
    },
  },
  plugins: [],
}
