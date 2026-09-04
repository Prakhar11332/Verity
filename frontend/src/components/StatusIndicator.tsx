import React from 'react';

interface StatusIndicatorProps {
  status: string;
  label?: string;
  style?: React.CSSProperties;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({ status, label, style }) => {
  const normalized = (status || '').toUpperCase().replace(/-/g, '_');

  let color = '#15181C';
  let displayLabel = label || status;

  if (
    normalized === 'MATCHED' ||
    normalized === 'AUTO_RESOLVE' ||
    normalized === 'AUTO_RESOLVED' ||
    normalized === 'APPROVED'
  ) {
    color = '#1F6F54'; // ledger-green
    displayLabel =
      label ||
      (normalized.startsWith('AUTO')
        ? 'Auto-resolved'
        : normalized === 'APPROVED'
        ? 'Approved'
        : 'Matched');
  } else if (
    normalized === 'REVIEW_REQUIRED' ||
    normalized === 'LIKELY_MATCH' ||
    normalized === 'PENDING'
  ) {
    color = '#B5791A'; // signal-amber
    displayLabel =
      label ||
      (normalized === 'REVIEW_REQUIRED'
        ? 'Review required'
        : normalized === 'LIKELY_MATCH'
        ? 'Likely match'
        : 'Pending');
  } else if (
    normalized === 'UNRESOLVED' ||
    normalized === 'EXCEPTION' ||
    normalized === 'REJECTED' ||
    normalized.includes('MISMATCH')
  ) {
    color = '#A5352A'; // signal-red
    displayLabel =
      label ||
      (normalized === 'UNRESOLVED'
        ? 'Unresolved'
        : normalized === 'REJECTED'
        ? 'Rejected'
        : 'Exception');
  }

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        fontSize: '12px',
        fontWeight: 400,
        color: '#15181C',
        fontFamily: "'Space Grotesk', sans-serif",
        ...style,
      }}
    >
      <span
        style={{
          width: '7px',
          height: '7px',
          backgroundColor: color,
          display: 'inline-block',
          flexShrink: 0,
        }}
      />
      <span>{displayLabel}</span>
    </span>
  );
};
