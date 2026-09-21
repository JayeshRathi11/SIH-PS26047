import React from 'react';

/**
 * Claymorphic Pill / Badge Primitive
 */
export default function ClayBadge({
  children,
  variant = 'pill', // 'pill' | 'ayush' | 'redflag' | 'success' | 'active' | 'gold'
  icon = null,
  className = '',
  ...props
}) {
  const getBadgeClasses = () => {
    switch (variant) {
      case 'ayush':
        return 'bg-cream-warm text-haritaki-deep border border-haritaki-gold/40 shadow-pill';
      case 'redflag':
        return 'bg-manjistha-red/10 text-manjistha-red border border-manjistha-red/30 shadow-pill font-bold';
      case 'success':
        return 'bg-herbal-green/10 text-herbal-green border border-herbal-green/30 shadow-pill font-semibold';
      case 'gold':
        return 'bg-gradient-to-r from-[#D49E34] to-[#BE8722] text-white shadow-pill font-bold';
      case 'active':
        return 'bg-haritaki-gold text-white shadow-pill font-semibold';
      case 'pill':
      default:
        return 'bg-cream-neutral text-teak-muted border border-copper-border shadow-pill';
    }
  };

  return (
    <span
      className={`clay-pill inline-flex items-center gap-1.5 px-3 py-1 rounded-pill text-caption select-none ${getBadgeClasses()} ${className}`}
      {...props}
    >
      {icon && <span className="flex-shrink-0">{icon}</span>}
      <span>{children}</span>
    </span>
  );
}
