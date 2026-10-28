import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NotificationSettingsModal } from '../src/features/notifications/NotificationSettingsModal';
import { api } from '../src/lib/api-client';

describe('Phase 10: Digest Scheduling and Delivery Reliability UI', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockPreferences = {
    email_enabled: true,
    recipient_email: 'sarah@example.com',
    notify_new_matches: true,
    notify_partial_discovery: true,
    notify_discovery_failures: true,
    notify_workflow_blockers: true,
    delivery_mode: 'DAILY_DIGEST' as const,
    min_match_score: 80,
    timezone: 'America/New_York',
  };

  const mockEmailStatus = {
    is_available: true,
    provider: 'smtp',
    from_address: 'alerts@jobpilot.local',
    recipient: 'sarah@example.com',
    email_notifications_enabled: true,
    timezone: 'America/New_York',
    is_simulated: false,
  };

  const mockDigestStatus = {
    email_enabled: true,
    delivery_mode: 'DAILY_DIGEST',
    timezone: 'America/New_York',
    is_provider_configured: true,
    provider: 'smtp',
    recipient: 'sarah@example.com',
    min_match_score: 80,
    pending_matches_count: 3,
    next_digest_at: '2026-10-29T13:00:00Z',
    last_digest_at: '2026-10-28T13:00:00Z',
    last_digest_status: 'SENT',
  };

  const mockDeliveryHistory = {
    items: [
      {
        id: 'hist-1',
        title: 'JobPilot AI Daily Digest: 2 Matches',
        channel: 'EMAIL',
        status: 'SENT',
        status_detail: 'Accepted by SMTP transport for relay',
        provider: 'smtp',
        recipient: 'sarah@example.com',
        sent_at: '2026-10-28T13:00:00Z',
        created_at: '2026-10-28T13:00:00Z',
        attempt_count: 1,
        attempts: [{ attempt: 1, timestamp: '2026-10-28T13:00:00Z', status: 'SENT' }],
        error: null,
        is_simulated: false,
      },
      {
        id: 'hist-2',
        title: 'JobPilot Match: Python Lead',
        channel: 'EMAIL',
        status: 'SIMULATED',
        status_detail: 'Simulated via mock provider',
        provider: 'mock',
        recipient: 'sarah@example.com',
        sent_at: '2026-10-28T10:00:00Z',
        created_at: '2026-10-28T10:00:00Z',
        attempt_count: 1,
        attempts: [{ attempt: 1, timestamp: '2026-10-28T10:00:00Z', status: 'SIMULATED' }],
        error: null,
        is_simulated: true,
      },
      {
        id: 'hist-3',
        title: 'JobPilot AI Daily Digest: 1 Match',
        channel: 'EMAIL',
        status: 'FAILED',
        status_detail: 'SMTP authentication failed',
        provider: 'smtp',
        recipient: 'sarah@example.com',
        sent_at: '2026-10-27T13:00:00Z',
        created_at: '2026-10-27T13:00:00Z',
        attempt_count: 1,
        attempts: [{ attempt: 1, timestamp: '2026-10-27T13:00:00Z', status: 'FAILED' }],
        error: '535 Authentication failed',
        is_simulated: false,
      },
    ],
    total: 3,
  };

  it('renders digest status telemetry, pending matches count, and accurate delivery badges', async () => {
    vi.spyOn(api.notifications, 'getPreferences').mockResolvedValue(mockPreferences);
    vi.spyOn(api.notifications, 'getEmailStatus').mockResolvedValue(mockEmailStatus);
    vi.spyOn(api.notifications, 'getDigestStatus').mockResolvedValue(mockDigestStatus);
    vi.spyOn(api.notifications, 'getDeliveryHistory').mockResolvedValue(mockDeliveryHistory);

    render(<NotificationSettingsModal isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Smart Alerts & Notification Delivery')).toBeInTheDocument();
      expect(screen.getByText('Scheduled Digest Telemetry')).toBeInTheDocument();
      expect(screen.getByText('3 waiting')).toBeInTheDocument();
      // Badges
      expect(screen.getAllByText('Relay Accepted').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Simulated')).toBeInTheDocument();
      expect(screen.getByText('Failed')).toBeInTheDocument();
      expect(screen.getByText('535 Authentication failed')).toBeInTheDocument();
    });
  });

  it('triggers manual digest and updates feedback banner', async () => {
    const user = userEvent.setup();
    vi.spyOn(api.notifications, 'getPreferences').mockResolvedValue(mockPreferences);
    vi.spyOn(api.notifications, 'getEmailStatus').mockResolvedValue(mockEmailStatus);
    vi.spyOn(api.notifications, 'getDigestStatus').mockResolvedValue(mockDigestStatus);
    vi.spyOn(api.notifications, 'getDeliveryHistory').mockResolvedValue(mockDeliveryHistory);

    const triggerSpy = vi.spyOn(api.notifications, 'triggerDigest').mockResolvedValue({
      success: true,
      message: 'Digest processed with status: SENT',
      notification: null,
    });

    render(<NotificationSettingsModal isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Trigger Digest Now')).toBeInTheDocument();
    });

    const triggerBtn = screen.getByText('Trigger Digest Now');
    await user.click(triggerBtn);

    await waitFor(() => {
      expect(triggerSpy).toHaveBeenCalledWith(false);
      expect(screen.getByText('Digest processed with status: SENT')).toBeInTheDocument();
    });
  });

  it('displays simulated mode indicator when mock/console provider is configured', async () => {
    const mockSimulatedStatus = {
      ...mockEmailStatus,
      provider: 'mock',
      is_simulated: true,
    };

    vi.spyOn(api.notifications, 'getPreferences').mockResolvedValue(mockPreferences);
    vi.spyOn(api.notifications, 'getEmailStatus').mockResolvedValue(mockSimulatedStatus);
    vi.spyOn(api.notifications, 'getDigestStatus').mockResolvedValue({
      ...mockDigestStatus,
      provider: 'mock',
    });
    vi.spyOn(api.notifications, 'getDeliveryHistory').mockResolvedValue({ items: [], total: 0 });

    render(<NotificationSettingsModal isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Simulated Mode (mock)')).toBeInTheDocument();
      expect(screen.getByText('Simulated (No Network)')).toBeInTheDocument();
    });
  });
});
