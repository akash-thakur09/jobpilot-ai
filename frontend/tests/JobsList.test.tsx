import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { JobsList } from '../src/features/jobs/JobsList';
import { api } from '../src/lib/api-client';
import { Job, MatchScore } from '../src/types';

describe('JobsList Screen', () => {
  const mockJobs: Job[] = [
    {
      id: 'job-1',
      source_id: 'src-1',
      external_id: 'ext-1',
      title: 'Full Stack Engineer',
      company: 'TechCorp',
      canonical_url: 'http://127.0.0.1:8000/portal',
      description: 'Building scalable React & FastAPI systems.',
      location: 'Remote',
      remote_type: 'REMOTE',
      salary_min: 130000,
      salary_max: 160000,
      salary_currency: 'USD',
      discovered_at: new Date().toISOString(),
      source_name: 'synthetic',
    },
    {
      id: 'job-2',
      source_id: 'src-2',
      external_id: 'ext-2',
      title: 'On-site Hardware Specialist',
      company: 'HardwareInc',
      canonical_url: 'http://127.0.0.1:8000/portal',
      description: 'Requires on-site presence in Austin TX with TS clearance.',
      location: 'Austin, TX',
      remote_type: 'ONSITE',
      discovered_at: new Date().toISOString(),
      source_name: 'synthetic',
    },
  ];

  const mockMatches: MatchScore[] = [
    {
      id: 'm-1',
      job_id: 'job-1',
      candidate_id: 'c-1',
      overall_score: 0.88,
      is_eligible: true,
      eligibility_status: 'ELIGIBLE',
      explanation: 'Verified skills and experience match all requirements.',
      scoring_policy_version: '1.0',
      is_latest: true,
      created_at: new Date().toISOString(),
    },
    {
      id: 'm-2',
      job_id: 'job-2',
      candidate_id: 'c-1',
      overall_score: 0.95, // High match score MUST NOT override disqualification
      is_eligible: false,
      eligibility_status: 'DISQUALIFIED',
      explanation: 'Candidate cannot satisfy mandatory on-site constraint in Austin TX.',
      scoring_policy_version: '1.0',
      is_latest: true,
      created_at: new Date().toISOString(),
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders jobs and displays deterministic eligibility badges', async () => {
    vi.spyOn(api.jobs, 'list').mockResolvedValue({
      items: mockJobs,
      total: 2,
      limit: 100,
      offset: 0,
    });
    vi.spyOn(api.matching, 'listResults').mockResolvedValue(mockMatches);

    render(
      <MemoryRouter>
        <JobsList />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Full Stack Engineer')).toBeInTheDocument();
      expect(screen.getByText('TechCorp')).toBeInTheDocument();
      expect(screen.getByText('Eligible')).toBeInTheDocument();
      expect(screen.getAllByText('Disqualified').length).toBeGreaterThanOrEqual(1);
    });

    // Verify deterministic disqualification banner is shown and explains reason
    expect(
      screen.getByText(/Candidate cannot satisfy mandatory on-site constraint in Austin TX/i)
    ).toBeInTheDocument();

    // Verify Prepare App button is disabled for disqualified job
    const prepareButtons = screen.getAllByRole('button', { name: /Prepare App|Ineligible/i });
    const ineligibleBtn = prepareButtons.find((btn) => btn.textContent?.includes('Ineligible'));
    expect(ineligibleBtn).toBeDisabled();
  });

  it('filters job listings by search text input', async () => {
    vi.spyOn(api.jobs, 'list').mockResolvedValue({
      items: mockJobs,
      total: 2,
      limit: 100,
      offset: 0,
    });
    vi.spyOn(api.matching, 'listResults').mockResolvedValue(mockMatches);

    render(
      <MemoryRouter>
        <JobsList />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('TechCorp')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search title, company/i);
    fireEvent.change(searchInput, { target: { value: 'Hardware' } });

    expect(screen.queryByText('TechCorp')).not.toBeInTheDocument();
    expect(screen.getByText('HardwareInc')).toBeInTheDocument();
  });
});
