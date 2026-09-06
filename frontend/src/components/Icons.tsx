import React from 'react';

interface IconProps {
  className?: string;
  size?: number;
}

/**
 * SIH26162 HELIOS Primary Brand Emblem
 * An orbital satellite ring traversing a precision infrared sensor aperture with a radiant thermal core.
 */
export const HeliosLogo: React.FC<IconProps> = ({ className = 'w-6 h-6', size = 24 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 32 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
  >
    <defs>
      <linearGradient id="helios-amber-grad" x1="4" y1="4" x2="28" y2="28" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#f59e0b" />
        <stop offset="50%" stopColor="#ef4444" />
        <stop offset="100%" stopColor="#d97706" />
      </linearGradient>
      <linearGradient id="helios-orbit-grad" x1="2" y1="16" x2="30" y2="16" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.8" />
        <stop offset="50%" stopColor="#38bdf8" stopOpacity="1" />
        <stop offset="100%" stopColor="#0284c7" stopOpacity="0.2" />
      </linearGradient>
      <radialGradient id="helios-core-glow" cx="16" cy="16" r="6" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" />
        <stop offset="40%" stopColor="#fbbf24" />
        <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
      </radialGradient>
    </defs>

    {/* Outer Sensor Reticle Ring */}
    <circle cx="16" cy="16" r="14" stroke="rgba(255,255,255,0.15)" strokeWidth="1" strokeDasharray="2 3" />
    
    {/* Elliptical Satellite Orbit Track */}
    <ellipse
      cx="16"
      cy="16"
      rx="14"
      ry="5.5"
      transform="rotate(-28 16 16)"
      stroke="url(#helios-orbit-grad)"
      strokeWidth="1.4"
      strokeLinecap="round"
    />
    
    {/* Orbiting Satellite Node */}
    <circle cx="27" cy="10" r="1.8" fill="#38bdf8" />
    <circle cx="27" cy="10" r="3.2" stroke="#38bdf8" strokeWidth="0.8" strokeOpacity="0.5" />

    {/* Thermal Infrared Aperture (Outer Diamond) */}
    <polygon
      points="16,6 26,16 16,26 6,16"
      stroke="url(#helios-amber-grad)"
      strokeWidth="1.5"
      strokeLinejoin="round"
      fill="rgba(245, 158, 11, 0.08)"
    />

    {/* Cardinal Alignment Ticks */}
    <line x1="16" y1="2" x2="16" y2="5" stroke="#f59e0b" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="16" y1="27" x2="16" y2="30" stroke="#f59e0b" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="2" y1="16" x2="5" y2="16" stroke="#06b6d4" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="27" y1="16" x2="30" y2="16" stroke="#06b6d4" strokeWidth="1.5" strokeLinecap="round" />

    {/* Central Radiant Thermal Core */}
    <circle cx="16" cy="16" r="5" fill="url(#helios-core-glow)" />
    <circle cx="16" cy="16" r="2" fill="#ffffff" />
  </svg>
);

/**
 * Model A: Source Identity Glyph
 * Industrial thermal emitter with high-temperature combustion cone and optical IR containment.
 */
export const ModelAIcon: React.FC<IconProps> = ({ className = 'w-4 h-4', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <path
      d="M10 2L17 6V14L10 18L3 14V6L10 2Z"
      stroke="#f59e0b"
      strokeWidth="1.4"
      strokeLinejoin="round"
      fill="rgba(245,158,11,0.12)"
    />
    <path d="M10 6V14" stroke="#fbbf24" strokeWidth="1.2" strokeLinecap="round" />
    <path d="M6 10H14" stroke="#fbbf24" strokeWidth="1.2" strokeLinecap="round" />
    <circle cx="10" cy="10" r="2.5" fill="#f59e0b" />
    <circle cx="10" cy="10" r="1.2" fill="#ffffff" />
  </svg>
);

/**
 * Model B: Temporal State Engine Glyph
 * Multi-ring temporal recurrence waveform representing persistent/reactivated operating states.
 */
export const ModelBIcon: React.FC<IconProps> = ({ className = 'w-4 h-4', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <circle cx="10" cy="10" r="8" stroke="rgba(6,182,212,0.3)" strokeWidth="1.2" strokeDasharray="3 2" />
    <circle cx="10" cy="10" r="5" stroke="#06b6d4" strokeWidth="1.4" />
    <circle cx="10" cy="10" r="2.2" fill="#38bdf8" />
    <path d="M10 5V10L13.5 12" stroke="#ffffff" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

/**
 * Model C: Anomaly Detection Engine Glyph
 * Statistical baseline threshold with an elevated thermal spike breaking the boundary.
 */
export const ModelCIcon: React.FC<IconProps> = ({ className = 'w-4 h-4', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <line x1="2" y1="14" x2="18" y2="14" stroke="rgba(239,68,68,0.3)" strokeWidth="1" strokeDasharray="2 2" />
    <path
      d="M3 13L6.5 12L9 4L11.5 10L14 7L17 13"
      stroke="#ef4444"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <circle cx="9" cy="4" r="1.8" fill="#ffffff" stroke="#ef4444" strokeWidth="1" />
  </svg>
);

/**
 * Source Resolver Glyph
 * 750m spatial cluster triangulation nodes.
 */
export const ResolverIcon: React.FC<IconProps> = ({ className = 'w-4 h-4', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <circle cx="10" cy="5" r="2.2" fill="#38bdf8" />
    <circle cx="5" cy="14" r="2.2" fill="#38bdf8" />
    <circle cx="15" cy="14" r="2.2" fill="#38bdf8" />
    <line x1="10" y1="5" x2="5" y2="14" stroke="rgba(56,189,248,0.4)" strokeWidth="1.2" />
    <line x1="10" y1="5" x2="15" y2="14" stroke="rgba(56,189,248,0.4)" strokeWidth="1.2" />
    <line x1="5" y1="14" x2="15" y2="14" stroke="rgba(56,189,248,0.4)" strokeWidth="1.2" />
    <circle cx="10" cy="11" r="1.2" fill="#ffffff" />
  </svg>
);

/**
 * Decision Engine Glyph
 * Tactical operational shield escutcheon with incident targeting reticle.
 */
export const DecisionEngineIcon: React.FC<IconProps> = ({ className = 'w-4 h-4', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <path
      d="M10 2L16 5V10C16 14 13 17 10 18C7 17 4 14 4 10V5L10 2Z"
      stroke="#e11d48"
      strokeWidth="1.4"
      strokeLinejoin="round"
      fill="rgba(225,29,72,0.1)"
    />
    <circle cx="10" cy="10" r="3" stroke="#fb7185" strokeWidth="1.2" />
    <line x1="10" y1="6" x2="10" y2="14" stroke="#fb7185" strokeWidth="1.2" />
    <line x1="6" y1="10" x2="14" y2="10" stroke="#fb7185" strokeWidth="1.2" />
  </svg>
);
