import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { JobsList } from '../src/features/jobs/JobsList';
import { DuplicateClustersModal } from '../src/features/jobs/DuplicateClustersModal';
import { RankingEvaluationModal } from '../src/features/jobs/RankingEvaluationModal';
import { JobDetailModal } from '../src/features/jobs/JobDetailModal';
import { api } from '../src/lib/api-client';
import { Job, MatchScore, JobDuplicateCluster, RankingEvaluationSummary } from '../src/types';

describe('Phase 11: Job Intelligence, Deduplication, and Ranking Quality UI', () => {
  const mockJobs: Job[] = [
    {
      id: 'job-active-1',
      source_id: 'src-1',
      external_id: 'ext-1',
      title: 'Senior Python Engineer',
      company: 'Acme Corp',
      canonical_url: 'https://acme.example.com/jobs/1',
      description: 'FastAPI and PostgreSQL engineer.',
      location: 'Remote',
      remote_type: 'REMOTE',
      discovered_at: new Date().toISOString(),
      freshness_status: 'ACTIVE',
      duplicate_cluster_id: 'cluster-101',
      source_name: 'greenhouse',
    },
    {
      id: 'job-stale-2',
      source_id: 'src-2',
      external_id: 'ext-2',
      title: 'Legacy Python Dev',
      company: 'OldCorp',
      canonical_url: 'https://old.example.com/jobs/2',
      description: 'Legacy services maintenance.',
      location: 'Remote',
      remote_type: 'REMOTE',
      discovered_at: new Date().toISOString(),
      freshness_status: 'POTENTIALLY_STALE',
      freshness_reason: 'Unseen for 18 days',
      source_name: 'lever',
    },
    {
      id: 'job-closed-3',
      source_id: 'src-1',
      external_id: 'ext-3',
      title: 'Closed Developer Role',
      company: 'DoneCorp',
      canonical_url: 'https://done.example.com/jobs/3',
      description: 'Expired position.',
      location: 'Remote',
      remote_type: 'REMOTE',
      discovered_at: new Date().toISOString(),
      freshness_status: 'CONFIRMED_CLOSED',
      freshness_reason: 'HTTP 404 job closed',
      source_name: 'greenhouse',
    },
  ];

  const mockMatch: MatchScore = {
    id: 'm-1',
    job_id: 'job-active-1',
    candidate_id: 'c-1',
    overall_score: 92.0,
    is_eligible: true,
    eligibility_status: 'ELIGIBLE',
    explanation: 'Candidate verified skills match required criteria.',
    scoring_policy_version: '1.1.0',
    scoring_breakdown: {
      final_score: 92.0,
      positive_contributions: ['Matched core Python skill (+40%)'],
      negative_contributions: [],
      missing_information: ['Compensation details not disclosed'],
    },
    is_latest: true,
    created_at: new Date().toISOString(),
  };

  const mockCluster: JobDuplicateCluster = {
    id: 'cluster-101',
    canonical_job_id: 'job-active-1',
    cluster_status: 'DETECTED',
    confidence: 'HIGH_CONFIDENCE',
    confidence_score: 0.95,
    match_reasons: ['Identical canonical URL across postings'],
    created_at: new Date().toISOString(),
    jobs: [mockJobs[0]],
  };

  const mockEvaluationSummary: RankingEvaluationSummary = {
    evaluation_dataset_version: '1.1.0',
    dataset_size: 12,
    scoring_policy_version: '1.1.0',
    evaluated_at: new Date().toISOString(),
    metrics: {
      ranking: {
        precision_at_3: 1.0,
        precision_at_5: 0.8,
        recall_at_3: 0.6,
        recall_at_5: 0.8,
        ndcg_at_3: 1.0,
        ndcg_at_5: 0.92,
      },
      duplicate_detection: {
        precision: 1.0,
        recall: 1.0,
        f1: 1.0,
        true_positives: 3,
        predicted_count: 3,
        ground_truth_count: 3,
      },
      freshness_accuracy: 1.0,
    },
    ranked_results: [
      {
        job_id: 'job-1',
        title: 'Senior Python Engineer',
        company: 'Acme Corp',
        is_eligible: true,
        eligibility_status: 'ELIGIBLE',
        score: 94.0,
        effective_rank_score: 94.0,
        ground_truth_relevance: 3.0,
        freshness_status: 'ACTIVE',
        positive_contributions: ['Matched core skills'],
        negative_contributions: [],
        warnings: [],
      },
    ],
    limitations_and_assumptions: ['Evaluated against synthetic benchmark fixtures.'],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(api.jobs, 'list').mockResolvedValue({
      items: mockJobs,
      total: 3,
      limit: 100,
      offset: 0,
    });
    vi.spyOn(api.matching, 'listResults').mockResolvedValue([mockMatch]);
    vi.spyOn(api.jobs, 'listDuplicates').mockResolvedValue([mockCluster]);
    vi.spyOn(api.jobs, 'reviewDuplicate').mockResolvedValue({
      ...mockCluster,
      cluster_status: 'CONFIRMED',
    });
    vi.spyOn(api.jobs, 'getFeedback').mockResolvedValue(null);
    vi.spyOn(api.jobs, 'submitFeedback').mockResolvedValue({
      id: 'fb-1',
      candidate_id: 'c-1',
      job_id: 'job-active-1',
      feedback_type: 'RELEVANT',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    vi.spyOn(api.matching, 'evaluateRanking').mockResolvedValue(mockEvaluationSummary);
  });

  it('renders JobsList with freshness indicators and duplicate group badges', async () => {
    render(
      <MemoryRouter>
        <JobsList />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Senior Python Engineer')).toBeInTheDocument();
    });

    // Check duplicate badge
    expect(screen.getByText('Duplicate')).toBeInTheDocument();

    // Check stale badge
    expect(screen.getByText('Stale')).toBeInTheDocument();

    // Check closed badge
    expect(screen.getByText('Closed')).toBeInTheDocument();
  });

  it('opens and reviews duplicate clusters in DuplicateClustersModal', async () => {
    render(
      <DuplicateClustersModal
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Cluster \(HIGH CONFIDENCE\)/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Identical canonical URL across postings/i)).toBeInTheDocument();

    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(api.jobs.reviewDuplicate).toHaveBeenCalledWith('cluster-101', 'CONFIRM');
    });
  });

  it('submits recommendation feedback in JobDetailModal', async () => {
    render(
      <JobDetailModal
        job={mockJobs[0]}
        matchResult={mockMatch}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('Senior Python Engineer')).toBeInTheDocument();
    expect(screen.getByText('Verified Active')).toBeInTheDocument();
    expect(screen.getByText('Cross-Source Duplicate Group')).toBeInTheDocument();

    // Positive contributions check
    expect(screen.getByText(/Matched core Python skill/i)).toBeInTheDocument();

    // Click Relevant feedback
    const relevantButton = screen.getByRole('button', { name: /^relevant$/i });
    fireEvent.click(relevantButton);

    await waitFor(() => {
      expect(api.jobs.submitFeedback).toHaveBeenCalledWith('job-active-1', 'RELEVANT');
    });
  });

  it('executes offline ranking evaluation and presents metrics in RankingEvaluationModal', async () => {
    render(
      <RankingEvaluationModal
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    const runButton = screen.getByRole('button', { name: /run evaluation suite/i });
    fireEvent.click(runButton);

    await waitFor(() => {
      expect(api.matching.evaluateRanking).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getAllByText(/100%/)[0]).toBeInTheDocument(); // Precision@3
      expect(screen.getByText('v1.1.0')).toBeInTheDocument(); // Policy version
      expect(screen.getByText(/Top Ranked Benchmark Fixtures/i)).toBeInTheDocument();
    });
  });
});
