export const formatCurrency = (val?: string | number | null): string => {
  if (val === null || val === undefined || val === '') return '₹0.00';
  const num = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(num)) return '₹0.00';
  return (
    '₹' +
    num.toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
};

export const formatConfidence = (val?: number | null): string => {
  if (val === null || val === undefined) return '0.0%';
  const pct = val <= 1 ? val * 100 : val;
  return `${pct.toFixed(1)}%`;
};

export const formatDateTime = (isoString?: string | null): string => {
  if (!isoString) return '—';
  try {
    let str = String(isoString).trim();
    // Normalize UTC representation if not present
    if (!str.endsWith('Z') && !str.includes('+') && !/-\d\d:\d\d$/.test(str)) {
      str += 'Z';
    }
    const d = new Date(str);
    if (isNaN(d.getTime())) return isoString;

    const pad = (n: number) => String(n).padStart(2, '0');
    const year = d.getFullYear();
    const month = pad(d.getMonth() + 1);
    const day = pad(d.getDate());
    const hours = pad(d.getHours());
    const mins = pad(d.getMinutes());
    const secs = pad(d.getSeconds());
    return `${year}-${month}-${day} ${hours}:${mins}:${secs}`;
  } catch {
    return isoString;
  }
};
