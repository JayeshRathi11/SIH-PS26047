/** @type {import('tailwindcss').Config} */

/**
 * MediKiosk Tailwind Config Extension (Light Ayurveda Theme)
 * All India Institute of Ayurveda — Patient Kiosk
 */

module.exports = {
  content: [
    './src/**/*.{js,jsx,ts,tsx,html}',
  ],
  theme: {
    screens: {
      kiosk: '800px',
    },
    extend: {
      colors: {
        /* Primitives - Light Ayurveda Material */
        'kora-khadi':     '#F7F4EB',
        'shweta-white':   '#FFFFFF',
        'teak-grey':      '#2C2520',
        'teak-muted':     '#63574E',
        'haritaki-gold':  '#C88A22',
        'haritaki-deep':  '#8F5D12',
        'copper-patina':  '#8C7D6B',
        'copper-border':  '#DDD5C5',
        'manjistha-red':  '#B53826',
        'herbal-green':   '#2E6B39',

        /* Semantic aliases */
        bg:               'var(--color-bg)',
        surface:          'var(--color-surface)',
        'surface-hover':  'var(--color-surface-hover)',
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
      },

      fontFamily: {
        display: ["'Baloo 2'", "'Noto Sans Devanagari'", 'sans-serif'],
        body:    ["'Noto Sans'", "'Noto Sans Devanagari'", 'sans-serif'],
      },

      fontSize: {
        'caption':    ['17px',  { lineHeight: '1.4',  fontWeight: '400' }],
        'step':       ['18px',  { lineHeight: '1.2',  fontWeight: '600' }],
        'body':       ['22px',  { lineHeight: '1.5',  fontWeight: '400' }],
        'btn-sec':    ['20px',  { lineHeight: '1.0',  fontWeight: '600' }],
        'option':     ['26px',  { lineHeight: '1.3',  fontWeight: '500' }],
        'btn-pri':    ['26px',  { lineHeight: '1.0',  fontWeight: '700' }],
        'heading':    ['32px',  { lineHeight: '1.2',  fontWeight: '600' }],
        'title':      ['44px',  { lineHeight: '1.15', fontWeight: '700' }],
        'hero':       ['96px',  { lineHeight: '1.0',  fontWeight: '800' }],
      },

      spacing: {
        'touch': '64px',
        'tap':   '80px',
        'gap-touch': '16px',
      },

      width: {
        kiosk:      '800px',
        'btn-back': '72px',
        'audio':    '72px',
      },
      height: {
        kiosk:          '1280px',
        topbar:         '72px',
        stepbar:        '56px',
        actionbar:      '96px',
        'content-zone': 'calc(1280px - 72px - 56px - 96px)',
        'btn-primary':  '80px',
        'btn-back':     '72px',
        'audio':        '72px',
        'option-min':   '96px',
        touch:          '64px',
      },
      minHeight: {
        touch:        '64px',
        'option':     '96px',
        'btn-primary': '80px',
      },
      minWidth: {
        touch:      '64px',
        'btn-back': '72px',
      },

      borderRadius: {
        'sm':   '6px',
        'card': '10px',
        'btn':  '8px',
      },

      boxShadow: {
        'card':          '0 2px 10px rgba(44, 37, 32, 0.06)',
        'card-elevated': '0 4px 16px rgba(44, 37, 32, 0.10)',
        'actionbar':     '0 -2px 12px rgba(44, 37, 32, 0.08)',
        'option-selected': '0 0 0 2px #C88A22',
      },

      transitionDuration: {
        'tap':    '120ms',
        'screen': '200ms',
        'step':   '250ms',
      },
    },
  },

  plugins: [
    function({ addUtilities }) {
      addUtilities({
        '.touch-safe': {
          'min-width':  '64px',
          'min-height': '64px',
        },
        '.touch-primary': {
          'min-width':  '80px',
          'min-height': '80px',
        },
        '.touch-control': {
          'min-width':  '72px',
          'min-height': '72px',
        },
        '.kiosk-root': {
          'width':    '800px',
          'height':   '1280px',
          'overflow': 'hidden',
          'position': 'fixed',
          'top':      '0',
          'left':     '0',
        },
        '.action-bar': {
          'position':   'fixed',
          'bottom':     '0',
          'left':       '0',
          'width':      '100%',
          'height':     '96px',
          'z-index':    '100',
        },
        '.kiosk-text': {
          '-webkit-font-smoothing': 'antialiased',
          'text-rendering': 'optimizeLegibility',
        },
        '.font-display-deva': {
          'font-family': "'Baloo 2', 'Noto Sans Devanagari', sans-serif",
        },
        '.font-body-deva': {
          'font-family': "'Noto Sans Devanagari', 'Noto Sans', sans-serif",
        },
      });
    },
  ],
};
