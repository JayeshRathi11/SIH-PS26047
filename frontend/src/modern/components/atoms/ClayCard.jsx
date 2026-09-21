import React from 'react';

/**
 * Claymorphic Card Primitive (Pillowy 28px corners, double specular highlight)
 */
export default function ClayCard({
  children,
  selected = false,
  elevated = false,
  recessed = false,
  interactive = false,
  onClick,
  className = '',
  ...props
}) {
  const getCardClasses = () => {
    if (recessed) {
      return 'clay-inset-recess bg-cream-recess text-teak-grey border border-copper-border/40';
    }
    if (selected) {
      return 'clay-card-selected bg-cream-warm border-[2.5px] border-haritaki-gold';
    }
    if (elevated) {
      return 'clay-surface shadow-card-elevated border border-copper-border';
    }
    return 'clay-card-unselected bg-[#FBF9F4] border-[1.5px] border-[#EBE2D2]';
  };

  return (
    <div
      onClick={interactive || onClick ? onClick : undefined}
      className={`rounded-card transition-all ${
        interactive || onClick ? 'touch-target cursor-pointer active:scale-[0.98] active:translate-y-[2px]' : ''
      } ${getCardClasses()} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
