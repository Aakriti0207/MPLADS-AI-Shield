/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Aligned with the approved design reference: a restrained
        // government-blue palette rather than a generic SaaS/startup look.
        navy: '#0b3355',
        navy700: '#123a5c',
        ink: '#16232e',
        muted: '#55636e',
        panel: '#f3f5f7',
        line: '#dce2e8'
      },
      boxShadow: {
        // Subtle -- borders carry most of the separation, shadow is a hint.
        soft: '0 1px 2px rgba(15, 23, 42, 0.05), 0 1px 1px rgba(15, 23, 42, 0.03)'
      }
    }
  },
  plugins: []
}