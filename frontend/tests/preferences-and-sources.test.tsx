import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { api } from '../src/lib/api-client';
import { SearchPreferencesCard } from '../src/features/profile/SearchPreferencesCard';
import { DiscoverySourcesCard } from '../src/features/scheduler/DiscoverySourcesCard';
import { NotificationSettingsModal } from '../src/features/notifications/NotificationSettingsModal';

describe('Phase 9 Frontend: API Client Extensions', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('calls getPreferences and updatePreferences with correct payload', async () => {
    const mockPrefs = {
      target_titles: ['Staff Python Engineer'],
      min_salary: 160000,
      remote_preference: 'REMOTE' as const,
      preferred_companies: ['Acme Corp'],
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockPrefs,
    });

    const getRes = await api.profile.getPreferences();
    expect(getRes).toEqual(mockPrefs);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/profile/preferences'),
      expect.anything()
    );

    const updateRes = await api.profile.updatePreferences(mockPrefs);
    expect(updateRes).toEqual(mockPrefs);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/profile/preferences'),
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify(mockPrefs),
      })
    );
  });

  it('calls getSource and updateSource with validated board identifier', async () => {
    const mockSource = {
      id: 'src_gh_1',
      identifier: 'greenhouse',
      name: 'Greenhouse Job Board',
      base_url: 'https://boards-api.greenhouse.io',
      is_active: true,
      is_enabled: true,
      board_identifier: 'airbnb',
      rate_limit_per_minute: 60,
      last_status: 'HEALTHY',
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockSource,
    });

    const src = await api.jobs.getSource('greenhouse');
    expect(src.identifier).toBe('greenhouse');

    const updated = await api.jobs.updateSource('greenhouse', {
      is_enabled: true,
      board_token: 'stripe',
    });
    expect(updated).toEqual(mockSource);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/jobs/sources/greenhouse'),
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ is_enabled: true, board_token: 'stripe' }),
      })
    );
  });

  it('calls notification preferences, email status, and test-email endpoints', async () => {
    const mockNotifPrefs = {
      email_enabled: true,
      recipient_email: 'alerts@jobpilot.test',
      notify_new_matches: true,
      delivery_mode: 'IMMEDIATE',
      min_match_score: 80,
    };

    const mockEmailStatus = {
      configured: true,
      provider: 'mock',
      from_address: 'jobpilot@example.com',
      use_tls: true,
    };

    const mockTestRes = {
      success: true,
      message: 'Test alert sent successfully to alerts@jobpilot.test.',
      recipient: 'alerts@jobpilot.test',
      provider: 'mock',
    };

    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockNotifPrefs,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockEmailStatus,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTestRes,
      });

    const prefs = await api.notifications.getPreferences();
    expect(prefs.email_enabled).toBe(true);

    const status = await api.notifications.getEmailStatus();
    expect(status.provider).toBe('mock');

    const testResult = await api.notifications.sendTestEmail('alerts@jobpilot.test');
    expect(testResult.success).toBe(true);
    expect(testResult.provider).toBe('mock');
  });
});

describe('Phase 9 UI Components', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders SearchPreferencesCard and displays fact separation banner', async () => {
    vi.spyOn(api.profile, 'getPreferences').mockResolvedValue({
      target_titles: ['Senior Python Engineer'],
      role_keywords: ['FastAPI'],
      required_skills: ['Docker'],
      min_salary: 150000,
      remote_preference: 'REMOTE',
      preferred_companies: ['GoodCorp'],
      excluded_companies: ['SpamCo'],
    });

    render(<SearchPreferencesCard />);

    await waitFor(() => {
      expect(screen.getByText('Personalized Job Search Preferences')).toBeInTheDocument();
    });

    // Fact separation security banner
    expect(
      screen.getByText(/Fact Separation Guarantee:/i)
    ).toBeInTheDocument();

    // Verify tag rendering
    expect(screen.getByText('Senior Python Engineer')).toBeInTheDocument();
    expect(screen.getByText('FastAPI')).toBeInTheDocument();
    expect(screen.getByText('Docker')).toBeInTheDocument();
    expect(screen.getByText('GoodCorp')).toBeInTheDocument();
    expect(screen.getByText('SpamCo')).toBeInTheDocument();
  });

  it('renders DiscoverySourcesCard with health badges and toggle action', async () => {
    const mockSources = [
      {
        id: 'gh_1',
        identifier: 'greenhouse',
        name: 'Greenhouse Public Board',
        base_url: 'https://boards-api.greenhouse.io',
        is_active: true,
        is_enabled: true,
        source_type: 'greenhouse',
        board_identifier: 'airbnb',
        last_status: 'HEALTHY',
        rate_limit_per_minute: 60,
        jobs_discovered_count: 14,
        last_error_summary: null,
      },
      {
        id: 'lever_1',
        identifier: 'lever',
        name: 'Lever Public Board',
        base_url: 'https://api.lever.co',
        is_active: true,
        is_enabled: false,
        source_type: 'lever',
        board_identifier: 'netflix',
        last_status: 'FAILED',
        rate_limit_per_minute: 60,
        jobs_discovered_count: 0,
        last_error_summary: 'HTTP 404 Board not found: netflix',
      },
    ];

    vi.spyOn(api.jobs, 'listSources').mockResolvedValue(mockSources as any);
    const updateSpy = vi.spyOn(api.jobs, 'updateSource').mockResolvedValue({
      ...mockSources[0],
      is_enabled: false,
    } as any);

    render(<DiscoverySourcesCard />);

    await waitFor(() => {
      expect(screen.getByText('Greenhouse Public Board')).toBeInTheDocument();
      expect(screen.getByText('Lever Public Board')).toBeInTheDocument();
    });

    // Badges
    expect(screen.getByText('Healthy')).toBeInTheDocument();
    expect(screen.getByText('Failed Run')).toBeInTheDocument();

    // Toggle enabled button for first source
    const enabledButtons = screen.getAllByRole('button', { name: /enabled/i });
    fireEvent.click(enabledButtons[0]);

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith('greenhouse', { is_enabled: false });
    });
  });

  it('renders NotificationSettingsModal with email status, settings, and safe test-email workflow', async () => {
    vi.spyOn(api.notifications, 'getPreferences').mockResolvedValue({
      email_enabled: true,
      recipient_email: 'candidate@example.com',
      notify_new_matches: true,
      notify_partial_discovery: true,
      notify_discovery_failures: true,
      notify_workflow_blockers: true,
      delivery_mode: 'IMMEDIATE',
      min_match_score: 75,
    });

    vi.spyOn(api.notifications, 'getEmailStatus').mockResolvedValue({
      configured: true,
      provider: 'mock',
      from_address: 'alerts@jobpilot.test',
      use_tls: true,
    });

    const testEmailSpy = vi.spyOn(api.notifications, 'sendTestEmail').mockResolvedValue({
      success: true,
      message: 'Test email successfully dispatched',
      recipient: 'candidate@example.com',
      provider: 'mock',
    });

    render(<NotificationSettingsModal isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Smart Alerts & Notification Delivery')).toBeInTheDocument();
    });

    // Security banner and provider status
    expect(screen.getByText(/Zero credential exposure/i)).toBeInTheDocument();
    expect(screen.getByText(/Provider Ready/i)).toBeInTheDocument();

    // Threshold indicator
    expect(screen.getByText('75%')).toBeInTheDocument();

    // Trigger Test Email
    const sendTestBtn = screen.getByRole('button', { name: /Send Test Alert/i });
    fireEvent.click(sendTestBtn);

    await waitFor(() => {
      expect(testEmailSpy).toHaveBeenCalledWith('candidate@example.com');
      expect(screen.getByText(/Test email successfully dispatched/i)).toBeInTheDocument();
    });
  });

  it('displays provider rejection on failed test email dispatch without false positives', async () => {
    vi.spyOn(api.notifications, 'getPreferences').mockResolvedValue({
      email_enabled: false,
      recipient_email: 'invalid@example.com',
      notify_new_matches: true,
      notify_partial_discovery: false,
      notify_discovery_failures: false,
      notify_workflow_blockers: false,
      delivery_mode: 'IMMEDIATE',
      min_match_score: 50,
    });

    vi.spyOn(api.notifications, 'getEmailStatus').mockResolvedValue({
      configured: false,
      provider: 'none',
      use_tls: false,
    });

    vi.spyOn(api.notifications, 'sendTestEmail').mockResolvedValue({
      success: false,
      message: 'SMTP Host connection refused: 127.0.0.1:1025',
      recipient: 'invalid@example.com',
      provider: 'smtp',
    });

    render(<NotificationSettingsModal isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Smart Alerts & Notification Delivery')).toBeInTheDocument();
    });

    const sendTestBtn = screen.getByRole('button', { name: /Send Test Alert/i });
    fireEvent.click(sendTestBtn);

    await waitFor(() => {
      expect(screen.getByText(/SMTP Host connection refused/i)).toBeInTheDocument();
    });
  });
});
