/**
 * JobPilot AI - Formatting and Display Utilities
 */

import { ApplicationStatus, EligibilityStatus, SubmissionOutcome } from '../types';

export function formatDate(dateString?: string | null): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return dateString;
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateString;
  }
}

export function formatScore(score?: number | null): string {
  if (score === undefined || score === null) return '—';
  const val = score <= 1.0 ? Math.round(score * 100) : Math.round(score);
  return `${val}%`;
}

export function formatSalary(min?: number | null, max?: number | null, currency: string | null = 'USD'): string {
  if (!min && !max) return '';
  const curr = currency || 'USD';
  const sym = curr === 'USD' ? '$' : `${curr} `;
  if (min && max) {
    return `${sym}${min.toLocaleString('en-US')} - ${sym}${max.toLocaleString('en-US')}`;
  }
  if (min) return `From ${sym}${min.toLocaleString('en-US')}`;
  if (max) return `Up to ${sym}${max.toLocaleString('en-US')}`;
  return '';
}

export function formatEligibilityBadge(status?: EligibilityStatus | string): {
  label: string;
  variant: 'success' | 'warning' | 'danger' | 'default';
} {
  switch (status) {
    case 'ELIGIBLE':
      return { label: 'Eligible', variant: 'success' };
    case 'DISQUALIFIED':
      return { label: 'Disqualified', variant: 'danger' };
    case 'NEEDS_REVIEW':
      return { label: 'Needs Review', variant: 'warning' };
    default:
      return { label: status || 'Not Evaluated', variant: 'default' };
  }
}

export function formatScoreBadge(score?: number | null): {
  label: string;
  variant: 'success' | 'warning' | 'danger' | 'default';
} {
  if (score === undefined || score === null) {
    return { label: '—', variant: 'default' };
  }
  const pct = score <= 1.0 ? Math.round(score * 100) : Math.round(score);
  if (pct >= 80) return { label: `${pct}%`, variant: 'success' };
  if (pct >= 60) return { label: `${pct}%`, variant: 'warning' };
  return { label: `${pct}%`, variant: 'danger' };
}

export function formatApplicationStatusBadge(status?: ApplicationStatus | string): {
  label: string;
  variant: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'purple';
} {
  switch (status) {
    case 'READY_FOR_REVIEW':
      return { label: 'Ready for Review', variant: 'info' };
    case 'APPROVED':
      return { label: 'Approved', variant: 'purple' };
    case 'IN_PROGRESS':
      return { label: 'In Progress', variant: 'warning' };
    case 'SYNTHETIC_SUBMISSION_IN_PROGRESS':
      return { label: 'Simulation In Progress', variant: 'warning' };
    case 'SUBMITTED_SIMULATION':
    case 'SYNTHETICALLY_SUBMITTED':
      return { label: 'Submitted (Simulation)', variant: 'purple' };
    case 'REAL_SUBMITTED':
      return { label: 'Submitted (Real)', variant: 'success' };
    case 'SUBMITTED':
      return { label: 'Submitted (Synthetic)', variant: 'success' };
    case 'NEEDS_HUMAN_ACTION':
      return { label: 'Action Required', variant: 'warning' };
    case 'OUTCOME_UNKNOWN':
      return { label: 'Outcome Unknown', variant: 'warning' };
    case 'FAILED':
    case 'FAILED_SUBMISSION':
      return { label: 'Failed Submission', variant: 'danger' };
    case 'PREPARING':
      return { label: 'Preparing', variant: 'default' };
    default:
      return { label: status || 'Unknown', variant: 'default' };
  }
}

export function formatAttemptStatusBadge(outcome?: SubmissionOutcome | string): {
  label: string;
  variant: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'purple';
} {
  switch (outcome) {
    case 'SUBMITTED_SIMULATION':
      return { label: 'Simulation Completed', variant: 'purple' };
    case 'SUCCESS':
      return { label: 'Success', variant: 'success' };
    case 'FAILED':
      return { label: 'Failed', variant: 'danger' };
    case 'NEEDS_HUMAN_ACTION':
      return { label: 'Action Required', variant: 'warning' };
    case 'OUTCOME_UNKNOWN':
      return { label: 'Outcome Unknown', variant: 'purple' };
    case 'BLOCKED_SAFETY':
      return { label: 'Blocked (Safety)', variant: 'danger' };
    default:
      return { label: outcome || 'Unknown', variant: 'default' };
  }
}

export function getEligibilityBadge(status?: EligibilityStatus | string): {
  label: string;
  className: string;
} {
  switch (status) {
    case 'ELIGIBLE':
      return {
        label: 'Eligible',
        className: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
      };
    case 'DISQUALIFIED':
      return {
        label: 'Disqualified',
        className: 'bg-rose-500/10 text-rose-400 border border-rose-500/20',
      };
    case 'NEEDS_REVIEW':
      return {
        label: 'Needs Review',
        className: 'bg-amber-500/10 text-amber-400 border border-amber-500/20',
      };
    default:
      return {
        label: status || 'Not Evaluated',
        className: 'bg-slate-800 text-slate-400 border border-slate-700',
      };
  }
}

export function getApplicationStatusBadge(status?: ApplicationStatus | string): {
  label: string;
  className: string;
} {
  switch (status) {
    case 'READY_FOR_REVIEW':
      return {
        label: 'Ready for Review',
        className: 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20',
      };
    case 'APPROVED':
      return {
        label: 'Approved',
        className: 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
      };
    case 'IN_PROGRESS':
      return {
        label: 'In Progress',
        className: 'bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse',
      };
    case 'SUBMITTED':
      return {
        label: 'Submitted (Synthetic)',
        className: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
      };
    case 'NEEDS_HUMAN_ACTION':
      return {
        label: 'Action Required',
        className: 'bg-amber-500/10 text-amber-300 border border-amber-500/30',
      };
    case 'OUTCOME_UNKNOWN':
      return {
        label: 'Outcome Unknown',
        className: 'bg-purple-500/10 text-purple-400 border border-purple-500/20',
      };
    case 'FAILED':
      return {
        label: 'Failed',
        className: 'bg-rose-500/10 text-rose-400 border border-rose-500/20',
      };
    case 'PREPARING':
      return {
        label: 'Preparing',
        className: 'bg-slate-500/10 text-slate-400 border border-slate-500/20',
      };
    default:
      return {
        label: status || 'Unknown',
        className: 'bg-slate-800 text-slate-400 border border-slate-700',
      };
  }
}

export function getOutcomeBadge(outcome?: SubmissionOutcome | string): {
  label: string;
  className: string;
} {
  switch (outcome) {
    case 'SUCCESS':
      return {
        label: 'Success',
        className: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
      };
    case 'FAILED':
      return {
        label: 'Failed',
        className: 'bg-rose-500/10 text-rose-400 border border-rose-500/20',
      };
    case 'NEEDS_HUMAN_ACTION':
      return {
        label: 'Needs Human Action',
        className: 'bg-amber-500/10 text-amber-400 border border-amber-500/20',
      };
    case 'OUTCOME_UNKNOWN':
      return {
        label: 'Outcome Unknown',
        className: 'bg-purple-500/10 text-purple-400 border border-purple-500/20',
      };
    case 'BLOCKED_SAFETY':
      return {
        label: 'Blocked (Safety)',
        className: 'bg-red-500/10 text-red-400 border border-red-500/20',
      };
    default:
      return {
        label: outcome || 'Unknown',
        className: 'bg-slate-800 text-slate-400 border border-slate-700',
      };
  }
}
