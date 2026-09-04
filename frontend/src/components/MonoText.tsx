import React from 'react';

export const MonoText: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
}> = ({ children, style, className = '' }) => (
  <span
    className={`font-mono tabular-nums ${className}`}
    style={{
      fontFamily: "'IBM Plex Mono', monospace",
      fontVariantNumeric: 'tabular-nums',
      letterSpacing: '-0.02em',
      ...style,
    }}
  >
    {children}
  </span>
);

export default MonoText;
