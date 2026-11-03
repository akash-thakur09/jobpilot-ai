import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { api } from '../src/lib/api-client';
import { DiscoverySourcesCard } from '../src/features/scheduler/DiscoverySourcesCard';

describe('Indian Job Board Sources & Alert Ingestion UI', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders Indian job board sources with integration status pills and handles alert import', async () => {
    const mockSources = [
      {
        id: 'src_1',
        identifier: 'naukri',
        name: 'Naukri.com',
        base_url: 'https://jobs.example.com',
        source_type: 'job_board',
        integration_status: 'MANUAL_IMPORT_ONLY',
        is_active: true,
        is_enabled: true,
        last_status: 'HEALTHY',
        rate_limit_per_minute: 15,
        jobs_discovered_count: 12,
        jobs_relevant_count: 8,
      },
      {
        id: 'src_2',
        identifier: 'indeed',
        name: 'Indeed India',
        base_url: 'https://jobs.example.com',
        source_type: 'aggregator',
        integration_status: 'CONFIGURATION_REQUIRED',
        is_active: true,
        is_enabled: true,
        last_status: 'IDLE',
        rate_limit_per_minute: 30,
        jobs_discovered_count: 0,
        jobs_relevant_count: 0,
      },
      {
        id: 'src_3',
        identifier: 'linkedin',
        name: 'LinkedIn India',
        base_url: 'https://jobs.example.com',
        source_type: 'aggregator',
        integration_status: 'AUTHORIZATION_REQUIRED',
        is_active: true,
        is_enabled: true,
        last_status: 'IDLE',
        rate_limit_per_minute: 15,
        jobs_discovered_count: 0,
        jobs_relevant_count: 0,
      },
      {
        id: 'src_4',
        identifier: 'hirist',
        name: 'Hirist',
        base_url: 'https://jobs.example.com',
        source_type: 'job_board',
        integration_status: 'AVAILABLE',
        is_active: true,
        is_enabled: true,
        last_status: 'HEALTHY',
        rate_limit_per_minute: 30,
        jobs_discovered_count: 5,
        jobs_relevant_count: 4,
      },
    ];

    vi.spyOn(api.jobs, 'listSources').mockResolvedValue(mockSources as any);
    const importSpy = vi.spyOn(api.jobs, 'importJobs').mockResolvedValue({
      source_identifier: 'naukri',
      items_received: 1,
      items_parsed: 1,
      items_saved: 1,
      items_relevant: 1,
      duplicates_detected: 0,
      errors: [],
    });

    render(<DiscoverySourcesCard />);

    await waitFor(() => {
      expect(screen.getByText('Naukri.com')).toBeInTheDocument();
      expect(screen.getByText('Indeed India')).toBeInTheDocument();
      expect(screen.getByText('LinkedIn India')).toBeInTheDocument();
      expect(screen.getByText('Hirist')).toBeInTheDocument();
    });

    // Check status badges
    expect(screen.getByText('Manual Import / Alert')).toBeInTheDocument();
    expect(screen.getByText('Config Required')).toBeInTheDocument();
    expect(screen.getByText('Auth Required')).toBeInTheDocument();
    expect(screen.getByText('Available')).toBeInTheDocument();

    // Click Import button on the first source (Naukri)
    const importButtons = screen.getAllByRole('button', { name: /import/i });
    fireEvent.click(importButtons[0]);

    // Import modal / panel opens
    await waitFor(() => {
      expect(screen.getByText(/Import Jobs & Email Alerts for Naukri.com/i)).toBeInTheDocument();
    });

    // Fill in textarea
    const textarea = screen.getByPlaceholderText(/Paste alert text or email snippet/i);
    fireEvent.change(textarea, {
      target: {
        value: `Role: Senior AI Engineer\nCompany: Swiggy\nLocation: Bengaluru\nSalary: 30-45 LPA\nExperience: 4-8 Yrs\nURL: https://www.naukri.com/job/swiggy-ai-99`,
      },
    });

    // Submit import
    const submitBtn = screen.getByRole('button', { name: /Ingest & Evaluate/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(importSpy).toHaveBeenCalledWith(
        'naukri',
        expect.objectContaining({
          source_identifier: 'naukri',
          format: 'email_text',
        })
      );
      expect(screen.getByText(/Successfully imported 1 jobs from naukri/i)).toBeInTheDocument();
    });
  });
});

