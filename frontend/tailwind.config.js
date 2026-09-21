/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx,html}",
  ],
  theme: {
    screens: {
      kiosk: '800px',
      sm: '640px',
      md: '768px',
      lg: '1024px',
      xl: '1280px',
      '2xl': '1440px',
    },
    extend: {
      colors: {
        /* Primitives - Light Ayurveda Material */
        'kora-khadi':     '#F7F4EB',
        'shweta-white':   '#FCFAF6',
        'cream-warm':     '#F7EEDA',
        'cream-recess':   '#EDE5D3',
        'cream-neutral':  '#FAF6EE',
        'teak-grey':      '#2C2520',
        'teak-muted':     '#64574D',
        'haritaki-gold':  '#C8922A',
        'haritaki-deep':  '#8A5E12',
        'copper-patina':  '#8C7D6B',
        'copper-border':  '#E3D7C1',
        'copper-track':   '#D5CBBA',
        'manjistha-red':  '#B5402E',
        'herbal-green':   '#2E6B39',

        /* Semantic aliases */
        bg:               'var(--color-bg)',
        surface:          'var(--color-surface)',
        'surface-hover':  'var(--color-surface-hover)',
        'surface-recess': 'var(--color-surface-recess)',
        border:           'var(--color-border)',
        'border-subtle':  'var(--color-border-subtle)',

        'text-primary':   'var(--color-text-primary)',
        'text-secondary': 'var(--color-text-secondary)',
        'text-disabled':  'var(--color-text-disabled)',
        'text-on-gold':   'var(--color-text-on-gold)',

        'btn-primary':    'var(--color-btn-primary-bg)',
        'btn-pressed':    'var(--color-btn-primary-bg-pressed)',
        'btn-text':       'var(--color-btn-primary-text)',

        'step-complete':  'var(--color-step-complete)',
        'step-active':    'var(--color-step-active)',
        'step-upcoming':  'var(--color-step-upcoming)',

        error:            'var(--color-status-error)',
        'error-bg':       'var(--color-status-error-bg)',
        success:          'var(--color-status-success)',
        'success-bg':     'var(--color-status-success-bg)',

        /* Legacy backward compatibility */
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
        display: ["'Baloo 2'", "'Noto Sans Devanagari'", 'sans-serif'],
        body:    ["'Noto Sans'", "'Noto Sans Devanagari'", 'sans-serif'],
        sans:    ["'Noto Sans'", "'Plus Jakarta Sans'", 'system-ui', 'sans-serif'],
        serif:   ['Cinzel', 'Georgia', 'serif'],
      },

      fontSize: {
        'caption':    ['14px',  { lineHeight: '1.4',  fontWeight: '400' }],
        'step':       ['16px',  { lineHeight: '1.2',  fontWeight: '600' }],
        'body':       ['16px',  { lineHeight: '1.5',  fontWeight: '400' }],
        'btn-sec':    ['16px',  { lineHeight: '1.0',  fontWeight: '600' }],
        'option':     ['18px',  { lineHeight: '1.3',  fontWeight: '500' }],
        'btn-pri':    ['18px',  { lineHeight: '1.0',  fontWeight: '700' }],
        'heading':    ['24px',  { lineHeight: '1.25', fontWeight: '600' }],
        'title':      ['32px',  { lineHeight: '1.2',  fontWeight: '700' }],
        'hero':       ['48px',  { lineHeight: '1.1',  fontWeight: '800' }],
      },

      spacing: {
        'touch': '48px',
        'tap':   '56px',
        'gap-touch': '16px',
      },

      borderRadius: {
        'sm':   '14px',
        'card': '28px',
        'btn':  '20px',
        'pill': '9999px',
      },

      boxShadow: {
        'card':          '10px 16px 28px rgba(44, 37, 32, 0.09), 2px 4px 10px rgba(44, 37, 32, 0.04), inset 4px 4px 8px rgba(255, 255, 255, 0.9), inset -4px -4px 8px rgba(195, 179, 155, 0.22)',
        'card-elevated': '12px 20px 34px rgba(44, 37, 32, 0.12), 4px 6px 14px rgba(44, 37, 32, 0.06), inset 4px 4px 8px rgba(255, 255, 255, 0.95), inset -4px -4px 8px rgba(195, 179, 155, 0.25)',
        'card-selected': '8px 14px 24px rgba(200, 146, 42, 0.18), inset 3px 3px 6px rgba(255, 255, 255, 0.9), inset -4px -4px 8px rgba(184, 131, 28, 0.25)',
        'card-unselected': '8px 14px 24px rgba(44, 37, 32, 0.06), inset 3px 3px 6px rgba(255, 255, 255, 0.85), inset -3px -3px 6px rgba(195, 180, 158, 0.2)',
        'btn-gold':      '6px 10px 20px rgba(176, 123, 30, 0.38), inset 3px 3px 6px rgba(255, 255, 255, 0.45), inset -4px -4px 8px rgba(114, 76, 10, 0.35)',
        'btn-neutral':   '6px 10px 18px rgba(44, 37, 32, 0.08), inset 3px 3px 6px rgba(255, 255, 255, 0.95), inset -3px -3px 6px rgba(195, 180, 158, 0.25)',
        'pill':          '4px 6px 12px rgba(44, 37, 32, 0.07), inset 2px 2px 4px rgba(255, 255, 255, 0.85), inset -2px -2px 4px rgba(195, 180, 158, 0.2)',
        'inset-recess':  'inset 3px 3px 6px rgba(44, 37, 32, 0.12), inset -2px -2px 5px rgba(255, 255, 255, 0.9), 0 1px 2px rgba(255, 255, 255, 0.6)',
      },

      transitionDuration: {
        'tap':    '180ms',
        'screen': '200ms',
        'step':   '250ms',
      },
    },
  },
  plugins: [],
}
