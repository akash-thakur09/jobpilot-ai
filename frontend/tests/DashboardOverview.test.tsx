import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DashboardOverview } from '../src/features/dashboard/DashboardOverview';
import { api } from '../src/lib/api-client';

describe('DashboardOverview Screen', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading skeleton while fetching data', () => {
    vi.spyOn(api.jobs, 'list').mockReturnValue(new Promise(() => {}));
    vi.spyOn(api.matching, 'listResults').mockReturnValue(new Promise(() => {}));
    vi.spyOn(api.applications, 'list').mockReturnValue(new Promise(() => {}));

    const { container } = render(
      <MemoryRouter>
        <DashboardOverview />
      </MemoryRouter>
    );

    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  it('renders metrics derived from live backend endpoints', async () => {
    vi.spyOn(api.jobs, 'list').mockResolvedValue({
      items: [],
      total: 14,
      limit: 1,
      offset: 0,
    });
    vi.spyOn(api.matching, 'listResults').mockResolvedValue([
      {
        id: 'm1',
        job_id: 'j1',
        candidate_id: 'c1',
        overall_score: 0.9,
        is_eligible: true,
        eligibility_status: 'ELIGIBLE',
        explanation: 'Strong match',
        scoring_policy_version: '1.0',
        is_latest: true,
        created_at: new Date().toISOString(),
      },
    ]);
    vi.spyOn(api.applications, 'list').mockImplementation(async (params) => {
      if (params?.status === 'READY_FOR_REVIEW') {
        return { items: [], total: 3, limit: 1, offset: 0 };
      }
      if (params?.status === 'APPROVED') {
        return { items: [], total: 2, limit: 1, offset: 0 };
      }
      if (params?.status === 'OUTCOME_UNKNOWN') {
        return { items: [], total: 1, limit: 1, offset: 0 };
      }
      if (params?.status === 'SUBMITTED') {
        return { items: [], total: 4, limit: 1, offset: 0 };
      }
      return {
        items: [
          {
            id: 'app-1',
            candidate_id: 'c1',
            job_id: 'j1',
            status: 'READY_FOR_REVIEW',
            submission_method: 'synthetic',
            job_title: 'Senior Python Engineer',
            company: 'Acme AI',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        total: 10,
        limit: 5,
        offset: 0,
      };
    });

    render(
      <MemoryRouter>
        <DashboardOverview />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('14')).toBeInTheDocument(); // Discovered Jobs
      expect(screen.getAllByText('1').length).toBeGreaterThan(0);  // Eligible Jobs
      expect(screen.getByText('3')).toBeInTheDocument();  // Awaiting Review
      expect(screen.getByText('Acme AI')).toBeInTheDocument();
      expect(screen.getByText('Senior Python Engineer')).toBeInTheDocument();
    });
  });

  it('renders an error banner when backend requests fail', async () => {
    vi.spyOn(api.jobs, 'list').mockRejectedValue(new Error('Connection refused'));

    render(
      <MemoryRouter>
        <DashboardOverview />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Failed to load dashboard metrics/i)).toBeInTheDocument();
    });
  });
});
