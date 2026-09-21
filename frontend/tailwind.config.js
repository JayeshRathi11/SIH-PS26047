/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ayush: {
          primary: '#1b4332',
          primaryLight: '#2d6a4f',
          primaryDark: '#081c15',
          accent: '#c9a227',
          accentLight: '#dfb841',
          parchment: '#fdfbf7',
          card: '#ffffff',
          dark: '#1e293b',
          crimson: '#b91c1c',
          crimsonLight: '#fee2e2',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        serif: ['Cinzel', 'Georgia', 'serif'],
      },
    },
  },
  plugins: [],
}
