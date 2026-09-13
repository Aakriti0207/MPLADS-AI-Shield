/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Government-portal palette -- matches the approved MPLADS AI
        // Shield visual reference exactly (see src/lib/theme.js, the
        // single source of truth these hexes are also exported from for
        // Recharts / inline-style consumers).
        navy: '#0b3355',
        navy700: '#123a5c',
        ink: '#16232e',
        muted: '#55636e',
        panel: '#f3f5f7',
        line: '#dce2e8',
        blue: '#1d63a8',
        good: '#1b8a5a',
        warn: '#b7791f',
        bad: '#c0392b',
        high: '#b4552e',
        info: '#2b6cb0',
        // Light tint backgrounds for badges/callouts -- paired 1:1 with
        // the tones above so badge text/background always come from the
        // same semantic pair instead of drifting to generic Tailwind hues.
        'good-bg': '#e7f4ec',
        'warn-bg': '#fbf0de',
        'bad-bg': '#fadcd8',
        'high-bg': '#fbe7df',
        'info-bg': '#e4eef9',
        'navy-bg': '#eef3f8',
      },
      borderRadius: {
        // Restrained radius scale (6-10px) per the government-portal
        // design direction -- deliberately overrides Tailwind's more
        // rounded defaults (lg/xl/2xl) so the whole app can keep using
        // familiar utility names without any component re-opting-in.
        DEFAULT: '4px',
        sm: '4px',
        md: '6px',
        lg: '8px',
        xl: '10px',
        '2xl': '10px',
        full: '9999px', // pills/avatars only -- used sparingly by design
      },
      boxShadow: {
        soft: '0 1px 2px rgba(15, 23, 42, 0.05), 0 1px 1px rgba(15, 23, 42, 0.03)',
      },
      fontSize: {
        // A slightly denser type scale than Tailwind's default, matching
        // the data-dense government-monitoring reference (13px body,
        // not 16px marketing-site body).
        xs: ['11.5px', '16px'],
        sm: ['12.5px', '18px'],
        base: ['13.5px', '20px'],
      },
    },
  },
  plugins: [],
}