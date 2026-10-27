import { describe, it, expect } from 'vitest';
import {
  formatSalary,
  formatScore,
  formatEligibilityBadge,
  formatApplicationStatusBadge,
  formatAttemptStatusBadge,
} from '../src/lib/formatters';

describe('Formatters and Enums', () => {
  it('formats salaries with currency symbols and ranges', () => {
    expect(formatSalary(100000, 150000, 'USD')).toBe('$100,000 - $150,000');
    expect(formatSalary(120000, null, 'USD')).toBe('From $120,000');
    expect(formatSalary(null, 180000, 'USD')).toBe('Up to $180,000');
    expect(formatSalary(null, null)).toBe('');
  });

  it('formats match scores accurately', () => {
    expect(formatScore(0.85)).toBe('85%');
    expect(formatScore(92)).toBe('92%');
    expect(formatScore(null)).toBe('—');
  });

  it('maps deterministic eligibility enums accurately', () => {
    expect(formatEligibilityBadge('ELIGIBLE')).toEqual({
      label: 'Eligible',
      variant: 'success',
    });
    expect(formatEligibilityBadge('DISQUALIFIED')).toEqual({
      label: 'Disqualified',
      variant: 'danger',
    });
    expect(formatEligibilityBadge('NEEDS_REVIEW')).toEqual({
      label: 'Needs Review',
      variant: 'warning',
    });
  });

  it('maps application lifecycle statuses with clear synthetic indicator', () => {
    const submitted = formatApplicationStatusBadge('SUBMITTED');
    expect(submitted.label).toContain('Synthetic');
    expect(submitted.variant).toBe('success');

    const review = formatApplicationStatusBadge('READY_FOR_REVIEW');
    expect(review.label).toBe('Ready for Review');
    expect(review.variant).toBe('info');

    const unknown = formatApplicationStatusBadge('OUTCOME_UNKNOWN');
    expect(unknown.label).toBe('Outcome Unknown');
  });

  it('maps submission attempt outcomes correctly', () => {
    expect(formatAttemptStatusBadge('SUCCESS').variant).toBe('success');
    expect(formatAttemptStatusBadge('FAILED').variant).toBe('danger');
    expect(formatAttemptStatusBadge('BLOCKED_SAFETY').variant).toBe('danger');
    expect(formatAttemptStatusBadge('OUTCOME_UNKNOWN').variant).toBe('purple');
  });
});
