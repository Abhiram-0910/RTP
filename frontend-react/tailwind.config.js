/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Outfit', 'system-ui', 'sans-serif'],
        body: ['Space Grotesk', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        midnight: {
          50:  '#e8eaf0',
          100: '#c5c9d8',
          200: '#9ea5be',
          300: '#7780a3',
          400: '#596590',
          500: '#3b4a7d',
          600: '#344375',
          700: '#2b3a6a',
          800: '#233160',
          900: '#15204d',
          950: '#0a0e1a',
        },
        accent: {
          DEFAULT: '#f59e0b',
          light:   '#fbbf24',
          dark:    '#d97706',
          glow:    'rgba(245, 158, 11, 0.15)',
        },
        cinema: {
          gold:    '#d4a853',
          crimson: '#dc2626',
          neon:    '#06b6d4',
          violet:  '#8b5cf6',
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic':  'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'glass-gradient':  'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.01) 100%)',
        'hero-gradient':   'linear-gradient(160deg, #0a0e1a 0%, #15204d 40%, #1a1040 70%, #0a0e1a 100%)',
        'card-shimmer':    'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.04) 50%, transparent 100%)',
      },
      boxShadow: {
        'glass':    '0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05)',
        'glow-sm':  '0 0 15px rgba(245,158,11,0.15)',
        'glow-md':  '0 0 30px rgba(245,158,11,0.2)',
        'glow-lg':  '0 0 60px rgba(245,158,11,0.25)',
        'neon':     '0 0 20px rgba(6,182,212,0.3)',
        'card':     '0 4px 24px rgba(0,0,0,0.4)',
        'card-hover': '0 12px 48px rgba(0,0,0,0.6), 0 0 0 1px rgba(245,158,11,0.1)',
      },
      borderRadius: {
        '4xl': '2rem',
      },
      animation: {
        'shimmer':       'shimmer 2s infinite',
        'float':         'float 6s ease-in-out infinite',
        'glow-pulse':    'glow-pulse 3s ease-in-out infinite',
        'iris-open':     'iris-open 1.2s cubic-bezier(0.16,1,0.3,1) forwards',
        'grain':         'grain 0.5s steps(1) infinite',
        'fade-up':       'fade-up 0.6s ease-out',
        'slide-in-right':'slide-in-right 0.4s cubic-bezier(0.16,1,0.3,1)',
        'typewriter':    'typewriter 2s steps(30) forwards',
        'border-pulse':  'border-pulse 4s ease-in-out infinite',
        'spin-slow':     'spin 3s linear infinite',
      },
      keyframes: {
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%':      { transform: 'translateY(-12px)' },
        },
        'glow-pulse': {
          '0%, 100%': { opacity: '0.4' },
          '50%':      { opacity: '1' },
        },
        'iris-open': {
          '0%':   { clipPath: 'circle(0% at 50% 50%)' },
          '100%': { clipPath: 'circle(100% at 50% 50%)' },
        },
        grain: {
          '0%':  { transform: 'translate(0,0)' },
          '10%': { transform: 'translate(-2%,-2%)' },
          '20%': { transform: 'translate(2%,2%)' },
          '30%': { transform: 'translate(-1%,1%)' },
          '40%': { transform: 'translate(1%,-1%)' },
          '50%': { transform: 'translate(-2%,2%)' },
          '60%': { transform: 'translate(2%,-2%)' },
          '70%': { transform: 'translate(-1%,-1%)' },
          '80%': { transform: 'translate(1%,1%)' },
          '90%': { transform: 'translate(-2%,-1%)' },
          '100%':{ transform: 'translate(2%,1%)' },
        },
        'fade-up': {
          '0%':   { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          '0%':   { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        typewriter: {
          '0%':   { width: '0' },
          '100%': { width: '100%' },
        },
        'border-pulse': {
          '0%, 100%': { borderColor: 'rgba(245,158,11,0.2)' },
          '50%':      { borderColor: 'rgba(245,158,11,0.5)' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
};
