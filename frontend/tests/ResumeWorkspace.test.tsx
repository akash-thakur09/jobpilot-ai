import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ResumeWorkspace } from '../src/features/resumes/ResumeWorkspace';
import { api } from '../src/lib/api-client';
import { ResumeVersion } from '../src/types';

describe('ResumeWorkspace Screen', () => {
  const mockResumeVersion: ResumeVersion = {
    id: 'rv-1',
    candidate_id: 'c-1',
    job_id: 'job-1',
    version_number: 1,
    pdf_file_path: 'resumes/rv-1.pdf',
    file_sha256: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
    is_ats_valid: true,
    is_submission_ready: true,
    keyword_coverage_result: {
      coverage_percent: 85,
      matched_required: ['React', 'TypeScript', 'FastAPI'],
      missing_required: [],
      matched_preferred: ['Docker'],
      missing_preferred: ['Kubernetes'],
    },
    factual_validation_result: {
      is_valid: true,
      unsupported_claims: [],
    },
    created_at: new Date().toISOString(),
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders resume versions with SHA-256 hash and ATS submission readiness badge', async () => {
    vi.spyOn(api.jobs, 'list').mockResolvedValue({
      items: [
        {
          id: 'job-1',
          source_id: 'src-1',
          external_id: 'ext-1',
          title: 'Senior Software Engineer',
          company: 'Nexus AI',
          canonical_url: 'http://127.0.0.1:8000',
          description: 'Desc',
          discovered_at: new Date().toISOString(),
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });
    vi.spyOn(api.applications, 'list').mockResolvedValue({
      items: [
        {
          id: 'app-1',
          candidate_id: 'c-1',
          job_id: 'job-1',
          resume_version_id: 'rv-1',
          status: 'READY_FOR_REVIEW',
          submission_method: 'synthetic',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });
    vi.spyOn(api.resumes, 'get').mockResolvedValue(mockResumeVersion);

    render(
      <MemoryRouter>
        <ResumeWorkspace />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Resume Version 1')).toBeInTheDocument();
      expect(screen.getByText('ATS Submission Ready')).toBeInTheDocument();
      expect(screen.getByText('9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08')).toBeInTheDocument();
      expect(screen.getByText('100% Factually Supported')).toBeInTheDocument();
      expect(screen.getByText('85% Coverage')).toBeInTheDocument();
    });
  });

  it('verifies resume file integrity against recorded SHA-256 hash', async () => {
    vi.spyOn(api.jobs, 'list').mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
    vi.spyOn(api.applications, 'list').mockResolvedValue({
      items: [
        {
          id: 'app-1',
          candidate_id: 'c-1',
          job_id: 'job-1',
          resume_version_id: 'rv-1',
          status: 'READY_FOR_REVIEW',
          submission_method: 'synthetic',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });
    vi.spyOn(api.resumes, 'get').mockResolvedValue(mockResumeVersion);
    const verifySpy = vi.spyOn(api.resumes, 'verifyIntegrity').mockResolvedValue({
      version_id: 'rv-1',
      is_intact: true,
      recorded_sha256: mockResumeVersion.file_sha256,
      file_path: 'resumes/rv-1.pdf',
      is_submission_ready: true,
    });

    render(
      <MemoryRouter>
        <ResumeWorkspace />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Verify File Integrity/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Verify File Integrity/i }));

    await waitFor(() => {
      expect(verifySpy).toHaveBeenCalledWith('rv-1');
      expect(screen.getByText(/Integrity verified! PDF file is bit-for-bit intact/i)).toBeInTheDocument();
      expect(screen.getByText('Checksum Verified')).toBeInTheDocument();
    });
  });

  it('displays critical integrity failure badge and notice when file is modified', async () => {
    vi.spyOn(api.jobs, 'list').mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
    vi.spyOn(api.applications, 'list').mockResolvedValue({
      items: [
        {
          id: 'app-1',
          candidate_id: 'c-1',
          job_id: 'job-1',
          resume_version_id: 'rv-1',
          status: 'READY_FOR_REVIEW',
          submission_method: 'synthetic',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });
    vi.spyOn(api.resumes, 'get').mockResolvedValue(mockResumeVersion);
    vi.spyOn(api.resumes, 'verifyIntegrity').mockResolvedValue({
      version_id: 'rv-1',
      is_intact: false, // Tampered / corrupted
      recorded_sha256: mockResumeVersion.file_sha256,
      file_path: 'resumes/rv-1.pdf',
      is_submission_ready: false,
    });

    render(
      <MemoryRouter>
        <ResumeWorkspace />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Verify File Integrity/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Verify File Integrity/i }));

    await waitFor(() => {
      expect(screen.getByText(/CRITICAL INTEGRITY FAILURE/i)).toBeInTheDocument();
      expect(screen.getByText('INTEGRITY MISMATCH')).toBeInTheDocument();
    });
  });
});
