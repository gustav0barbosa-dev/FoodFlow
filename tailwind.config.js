import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#E11927',
          dark: '#C4171F',
          light: '#FF4C5A',
        },
        ink: {
          DEFAULT: '#3F3E3E',
          soft: '#717171',
        },
        surface: {
          DEFAULT: '#FFFFFF',
          muted: '#F7F7F7',
        },
        star: '#FFB800',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Poppins', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
    },
  },
  plugins: [],
} satisfies Config