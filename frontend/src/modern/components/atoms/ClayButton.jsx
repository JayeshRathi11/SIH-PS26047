import React from 'react';

/**
 * Claymorphic Button Primitive (Light Ayurveda System)
 * Adheres to 1:1 visual tokens with tactile depression micro-interaction.
 */
export default function ClayButton({
  children,
  variant = 'primary-gold', // 'primary-gold' | 'neutral' | 'back' | 'skip' | 'agree' | 'decline' | 'proceed'
  size = 'md', // 'sm' | 'md' | 'lg' | 'touch'
  onClick,
  disabled = false,
  loading = false,
  icon = null,
  type = 'button',
  className = '',
  ...props
}) {
  const getVariantClasses = () => {
    switch (variant) {
      case 'primary-gold':
      case 'primary':
      case 'agree':
      case 'proceed':
        return 'btn-primary text-white shadow-btn-gold border-none';
      case 'neutral':
      case 'secondary':
      case 'back':
      case 'skip':
      case 'decline':
        return 'btn-secondary text-teak-grey shadow-btn-neutral border border-[#E4DAC6]';
      case 'danger':
        return 'bg-manjistha-red text-white shadow-btn-gold border-none';
      default:
        return 'btn-primary text-white shadow-btn-gold';
    }
  };

  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return 'min-h-[40px] px-3.5 py-1.5 text-caption rounded-sm font-semibold';
      case 'touch':
      case 'lg':
        return 'min-h-[56px] px-6 py-3 text-btn-pri rounded-btn font-display font-bold';
      case 'md':
      default:
        return 'min-h-[48px] px-5 py-2.5 text-btn-sec rounded-btn font-display font-bold';
    }
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`touch-target inline-flex items-center justify-center gap-2 select-none transition-all active:scale-[0.97] active:translate-y-[2px] disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none cursor-pointer ${getVariantClasses()} ${getSizeClasses()} ${className}`}
      {...props}
    >
      {loading ? (
        <span className="inline-block w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin mr-1" />
      ) : (
        icon && <span className="flex-shrink-0">{icon}</span>
      )}
      <span>{children}</span>
    </button>
  );
}
