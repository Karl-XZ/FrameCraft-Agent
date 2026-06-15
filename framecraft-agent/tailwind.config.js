/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'bg-main': '#070A12',
        'bg-panel': 'rgba(255,255,255,0.06)',
        'bg-panel-strong': 'rgba(255,255,255,0.10)',
        'bg-card': 'rgba(15,23,42,0.72)',
        primary: { DEFAULT: '#7C3AED', light: '#A78BFA', 600: '#7C3AED', 500: '#8B5CF6' },
        secondary: '#06B6D4',
        accent: '#F472B6',
        'text-main': '#F8FAFC',
        'text-secondary': '#CBD5E1',
        'text-muted': '#64748B',
        success: '#22C55E',
        warning: '#F59E0B',
        error: '#EF4444',
        info: '#38BDF8',
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans SC', 'sans-serif'],
      },
      borderRadius: {
        sm: '8px',
        md: '12px',
        lg: '20px',
        xl: '28px',
      },
      boxShadow: {
        glass: '0 20px 60px rgba(0,0,0,0.35)',
        glow: '0 0 30px rgba(124,58,237,0.4)',
        'glow-cyan': '0 0 30px rgba(6,182,212,0.4)',
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #7C3AED 0%, #06B6D4 50%, #F472B6 100%)',
        'btn-gradient': 'linear-gradient(135deg, #8B5CF6 0%, #06B6D4 100%)',
      },
    },
  },
  plugins: [],
};
