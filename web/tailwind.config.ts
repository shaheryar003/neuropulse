import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#05060a',
        surface: '#0d0f17',
        surface2: '#131620',
        border: '#1e2235',
        accent: '#4af4b0',
        accent2: '#7b5cfa',
        accent3: '#f46a4a',
        text: '#e8eaf2',
        muted: '#7a7f9a',
        dim: '#3d4260',
      },
      fontFamily: {
        heading: ['Syne', 'sans-serif'],
        body: ['DM Mono', 'monospace'],
        serif: ['Libre Baskerville', 'serif'],
      },
    },
  },
  plugins: [],
};

export default config;
