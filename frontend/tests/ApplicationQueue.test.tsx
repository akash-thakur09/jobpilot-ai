import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ApplicationQueue } from '../src/features/applications/ApplicationQueue';
import { api, ApiError } from '../src/lib/api-client';
import { Application, ApplicationReviewPayload } from '../src/types';

describe('ApplicationQueue and Approval Workflow', () => {
  const mockApplications: Application[] = [
    {
      id: 'app-review-1',
      candidate_id: 'cand-1',
      job_id: 'job-1',
      status: 'READY_FOR_REVIEW',
      submission_method: 'synthetic',
      job_title: 'Backend Engineer',
      company: 'DataFlow Systems',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'app-approved-1',
      candidate_id: 'cand-1',
      job_id: 'job-2',
      status: 'APPROVED',
      submission_method: 'synthetic',
      approval_fingerprint: 'a'.repeat(64),
      job_title: 'Full Stack Architect',
      company: 'CloudWorks',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'app-unknown-1',
      candidate_id: 'cand-1',
      job_id: 'job-3',
      status: 'OUTCOME_UNKNOWN',
      submission_method: 'synthetic',
      job_title: 'AI Platform Engineer',
      company: 'Frontier Labs',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ];

  const mockReviewPayload: ApplicationReviewPayload = {
    application_id: 'app-review-1',
    candidate_id: 'cand-1',
    job_id: 'job-1',
    status: 'READY_FOR_REVIEW',
    employer: 'DataFlow Systems',
    job_title: 'Backend Engineer',
    job_url: 'http://127.0.0.1:8000/portal/job-1',
    job_fingerprint: 'b'.repeat(64),
    eligibility_status: 'ELIGIBLE',
    eligibility_reason: 'All requirements verified',
    match_score: 0.92,
    match_explanation: 'Strong alignment',
    selected_resume_version_id: 'rv-1',
    resume_sha256: 'c'.repeat(64),
    resume_integrity_valid: true,
    resume_factual_validation_valid: true,
    keyword_coverage_summary: { coverage_percent: 88 },
    canonical_approval_fingerprint: 'canonical-hash-1234567890abcdef',
    prepared_form_data: {
      full_name: { value: 'Alex Developer', provenance: 'candidate_profile', is_verified: true },
      email: { value: 'alex@example.com', provenance: 'candidate_profile', is_verified: true },
    },
    unanswered_questions: [],
    review_warnings: [],
    is_approvable: true,
    approvable_reason: 'All checks passed',
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders application list across status tabs', async () => {
    vi.spyOn(api.applications, 'list').mockResolvedValue({
      items: mockApplications,
      total: 3,
      limit: 100,
      offset: 0,
    });
    vi.spyOn(api.jobs, 'list').mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });

    render(
      <MemoryRouter>
        <ApplicationQueue />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('DataFlow Systems')).toBeInTheDocument();
      expect(screen.getByText('CloudWorks')).toBeInTheDocument();
      expect(screen.getByText('Frontier Labs')).toBeInTheDocument();
    });

    // Check action buttons for different statuses
    expect(screen.getByRole('button', { name: /Review & Approve/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Execute Synthetic Run/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reconcile Outcome/i })).toBeInTheDocument();
  });

  it('opens review modal, displays canonical fingerprint, and approves application', async () => {
    vi.spyOn(api.applications, 'list').mockResolvedValue({
      items: mockApplications,
      total: 3,
      limit: 100,
      offset: 0,
    });
    vi.spyOn(api.jobs, 'list').mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
    vi.spyOn(api.applications, 'review').mockResolvedValue(mockReviewPayload);
    const approveSpy = vi.spyOn(api.applications, 'approve').mockResolvedValue({
      ...mockApplications[0],
      status: 'APPROVED',
    });

    render(
      <MemoryRouter>
        <ApplicationQueue />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Review & Approve/i })).toBeInTheDocument();
    });

    // Click Review & Approve
    fireEvent.click(screen.getByRole('button', { name: /Review & Approve/i }));

    await waitFor(() => {
      expect(screen.getByText('canonical-hash-1234567890abcdef')).toBeInTheDocument();
      expect(screen.getByText('100% Fact Checked')).toBeInTheDocument();
      expect(screen.getByText('Approve Application')).toBeInTheDocument();
    });

    // Click Approve Application button
    fireEvent.click(screen.getByText('Approve Application'));

    await waitFor(() => {
      expect(approveSpy).toHaveBeenCalledWith('app-review-1', {
        reviewed_fingerprint: 'canonical-hash-1234567890abcdef',
        approval_metadata: expect.objectContaining({
          ui_version: 'jobpilot-frontend-v1',
        }),
      });
    });
  });

  it('handles stale approval error (HTTP 409) with informative error message', async () => {
    vi.spyOn(api.applications, 'list').mockResolvedValue({
      items: mockApplications,
      total: 3,
      limit: 100,
      offset: 0,
    });
    vi.spyOn(api.jobs, 'list').mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
    vi.spyOn(api.applications, 'review').mockResolvedValue(mockReviewPayload);
    vi.spyOn(api.applications, 'approve').mockRejectedValue(
      new ApiError(409, 'Approval fingerprint has changed. Candidate profile was modified.')
    );

    render(
      <MemoryRouter>
        <ApplicationQueue />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Review & Approve/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Review & Approve/i }));

    await waitFor(() => {
      expect(screen.getByText('Approve Application')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Approve Application'));

    await waitFor(() => {
      expect(screen.getByText(/STALE APPROVAL ERROR/i)).toBeInTheDocument();
      expect(screen.getByText(/Reload Fresh Snapshot/i)).toBeInTheDocument();
    });
  });
});
