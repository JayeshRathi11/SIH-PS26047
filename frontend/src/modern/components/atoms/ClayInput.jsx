import React from 'react';

/**
 * Claymorphic Recessed Input Primitive
 */
export default function ClayInput({
  label,
  value,
  onChange,
  placeholder = '',
  type = 'text',
  error = null,
  icon = null,
  readOnly = false,
  onFocus,
  className = '',
  required = false,
  maxLength,
  ...props
}) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {label && (
        <label className="text-caption font-semibold text-teak-grey flex items-center justify-between">
          <span>{label}</span>
          {required && <span className="text-manjistha-red text-xs">* अनिवार्य / Required</span>}
        </label>
      )}
      <div className="relative flex items-center">
        {icon && (
          <span className="absolute left-4 text-copper-patina pointer-events-none">
            {icon}
          </span>
        )}
        <input
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          readOnly={readOnly}
          onFocus={onFocus}
          maxLength={maxLength}
          className={`w-full min-h-[52px] bg-cream-recess text-teak-grey placeholder:text-teak-muted/60 font-body text-body rounded-btn border transition-all ${
            icon ? 'pl-11 pr-4' : 'px-4'
          } ${
            error
              ? 'border-manjistha-red focus:ring-2 focus:ring-manjistha-red/30'
              : 'border-copper-border focus:border-haritaki-gold focus:ring-2 focus:ring-haritaki-gold/30'
          } shadow-inset-recess outline-none`}
          {...props}
        />
      </div>
      {error && (
        <p className="text-xs text-manjistha-red font-medium mt-0.5">{error}</p>
      )}
    </div>
  );
}
