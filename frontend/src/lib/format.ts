import type { Numeric } from './api';

export function numericValue(value: Numeric): number | null {
  if (value === null || value === undefined || value === '') return null;
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatNumber(value: Numeric, digits = 2): string {
  const parsed = numericValue(value);
  return parsed === null ? 'N/A' : new Intl.NumberFormat('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(parsed);
}

export function formatInteger(value: Numeric): string {
  const parsed = numericValue(value);
  return parsed === null ? 'N/A' : new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(parsed);
}

export function formatCurrency(value: Numeric, digits = 2): string {
  const parsed = numericValue(value);
  return parsed === null ? 'INSUFFICIENT DATA' : `₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(parsed)}`;
}

export function formatSignedCurrency(value: Numeric): string {
  const parsed = numericValue(value);
  if (parsed === null) return 'INSUFFICIENT DATA';
  const sign = parsed > 0 ? '+' : parsed < 0 ? '−' : '';
  return `${sign}₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(Math.abs(parsed))}`;
}

export function formatPercent(value: Numeric, digits = 2): string {
  const parsed = numericValue(value);
  return parsed === null ? 'INSUFFICIENT DATA' : `${new Intl.NumberFormat('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(parsed * 100)}%`;
}

export function formatDate(value: string | null | undefined, options: Intl.DateTimeFormatOptions = { day: '2-digit', month: 'short', year: 'numeric' }): string {
  if (!value) return 'N/A';
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.valueOf()) ? 'N/A' : new Intl.DateTimeFormat('en-GB', options).format(parsed);
}

export function formatShortDate(value: string | null | undefined): string {
  return formatDate(value, { day: '2-digit', month: 'short' });
}

export function compactContract(contractId: string): string {
  const [symbol, expiry] = contractId.split('|');
  return expiry ? `${symbol} · ${formatShortDate(expiry)}` : contractId;
}

export function titleCaseStatus(value: string | null | undefined): string {
  if (!value) return 'N/A';
  return value.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}