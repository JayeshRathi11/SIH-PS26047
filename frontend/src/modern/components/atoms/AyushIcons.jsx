import React from 'react';

export function AIIALogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="24" cy="24" r="22" fill="#C8922A" fillOpacity="0.15" stroke="#C8922A" strokeWidth="2.5" />
      <path d="M24 8V40M12 20C12 20 18 16 24 16C30 16 36 20 36 20M14 28C14 28 19 25 24 25C29 25 34 28 34 28" stroke="#8A5E12" strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="24" cy="14" r="3" fill="#C8922A" />
      <path d="M18 36C21 34 27 34 30 36" stroke="#8A5E12" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function DrCharakaAvatar({ className = 'w-12 h-12', isSpeaking = false }) {
  return (
    <div className={`relative flex items-center justify-center rounded-full bg-cream-warm border-2 border-haritaki-gold shadow-pill ${className}`}>
      <svg viewBox="0 0 36 36" fill="none" className="w-8 h-8 text-haritaki-deep">
        <circle cx="18" cy="13" r="6" stroke="currentColor" strokeWidth="2" fill="#FAF6EE" />
        <path d="M18 10V14M16 12H20" stroke="#B5402E" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M8 29C8 23.5 12.5 20 18 20C23.5 20 28 23.5 28 29" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
      {isSpeaking && (
        <span className="absolute -bottom-1 -right-1 flex h-3.5 w-3.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-herbal-green opacity-75"></span>
          <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-herbal-green border-2 border-white"></span>
        </span>
      )}
    </div>
  );
}

export function ComplianceShield({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      <path d="m9 12 2 2 4-4"/>
    </svg>
  );
}

export function HospitalSahayak({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <line x1="19" x2="19" y1="8" y2="14"/>
      <line x1="22" x2="16" y1="11" y2="11"/>
    </svg>
  );
}

export const AshtavidhaIcons = {
  nadi: ({ className = 'w-6 h-6' }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  mutra: ({ className = 'w-6 h-6' }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  mala: ({ className = 'w-6 h-6' }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="9" strokeLinecap="round"/>
      <path d="M12 7v5l3 3" strokeLinecap="round"/>
    </svg>
  ),
  jihva: ({ className = 'w-6 h-6' }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 4v16m-6-8c0 4.418 2.686 8 6 8s6-3.582 6-8" strokeLinecap="round"/>
    </svg>
  ),
  shabda: ({ className = 'w-6 h-6' }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M11 5L6 9H2v6h4l5 4V5z"/>
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>
    </svg>
  ),
  sparsha: ({ className = 'w-6 h-6' }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 11V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v5"/>
      <path d="M14 10V4a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v8"/>
      <path d="M10 10.5V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v8"/>
      <path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/>
    </svg>
  ),
  drik: ({ className = 'w-6 h-6' }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  ),
  akriti: ({ className = 'w-6 h-6' }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="5" r="3"/>
      <path d="M12 8v8M8 12h8M9 21l3-5 3 5"/>
    </svg>
  )
};
