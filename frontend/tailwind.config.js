/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#0b3b6e',
        ink: '#122033',
        muted: '#64748b',
        panel: '#f6f8fb'
      },
      boxShadow: {
        soft: '0 8px 30px rgba(15, 23, 42, 0.07)'
      }
    }
  },
  plugins: []
}