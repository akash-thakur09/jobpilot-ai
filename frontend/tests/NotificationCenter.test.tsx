import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NotificationCenter } from '../src/features/notifications/NotificationCenter';
import { api } from '../src/lib/api-client';

describe('NotificationCenter Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders notification bell and displays unread count badge', async () => {
    vi.spyOn(api.notifications, 'getUnreadCount').mockResolvedValue({ unread_count: 3 });

    render(<NotificationCenter />);

    await waitFor(() => {
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  it('opens popover on click and renders notifications with mark-read action', async () => {
    const user = userEvent.setup();
    vi.spyOn(api.notifications, 'getUnreadCount').mockResolvedValue({ unread_count: 1 });
    vi.spyOn(api.notifications, 'list').mockResolvedValue({
      items: [
        {
          id: 'notif-1',
          notification_type: 'NEW_MATCH',
          title: 'New Eligible Match: Staff Architect',
          message: 'Acme Corp is hiring for Staff Architect',
          channel: 'IN_APP',
          status: 'DELIVERED',
          is_read: false,
          is_dismissed: false,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          metadata: {},
        },
      ],
      total: 1,
      unread_count: 1,
      limit: 15,
      offset: 0,
    });
    const markReadSpy = vi.spyOn(api.notifications, 'markAsRead').mockResolvedValue({
      success: true,
      notification: {
        id: 'notif-1',
        notification_type: 'NEW_MATCH',
        title: 'New Eligible Match: Staff Architect',
        message: 'Acme Corp is hiring for Staff Architect',
        channel: 'IN_APP',
        status: 'DELIVERED',
        is_read: true,
        is_dismissed: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        metadata: {},
      },
    });

    render(<NotificationCenter />);

    const bellBtn = screen.getByTitle('Notifications');
    await user.click(bellBtn);

    await waitFor(() => {
      expect(screen.getByText('New Eligible Match: Staff Architect')).toBeInTheDocument();
      expect(screen.getByText('Acme Corp is hiring for Staff Architect')).toBeInTheDocument();
    });

    const markBtn = screen.getByTitle('Mark as read');
    await user.click(markBtn);

    expect(markReadSpy).toHaveBeenCalledWith('notif-1');
  });

  it('handles dismiss action correctly', async () => {
    const user = userEvent.setup();
    vi.spyOn(api.notifications, 'getUnreadCount').mockResolvedValue({ unread_count: 1 });
    vi.spyOn(api.notifications, 'list').mockResolvedValue({
      items: [
        {
          id: 'notif-2',
          notification_type: 'RUN_FAILED',
          title: 'Discovery Run Failed',
          message: 'All sources failed due to network error',
          channel: 'IN_APP',
          status: 'DELIVERED',
          is_read: false,
          is_dismissed: false,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          metadata: {},
        },
      ],
      total: 1,
      unread_count: 1,
      limit: 15,
      offset: 0,
    });
    const dismissSpy = vi.spyOn(api.notifications, 'dismiss').mockResolvedValue({
      success: true,
      notification: {
        id: 'notif-2',
        notification_type: 'RUN_FAILED',
        title: 'Discovery Run Failed',
        message: 'All sources failed due to network error',
        channel: 'IN_APP',
        status: 'DELIVERED',
        is_read: true,
        is_dismissed: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        metadata: {},
      },
    });

    render(<NotificationCenter />);

    const bellBtn = screen.getByTitle('Notifications');
    await user.click(bellBtn);

    await waitFor(() => {
      expect(screen.getByText('Discovery Run Failed')).toBeInTheDocument();
    });

    const dismissBtn = screen.getByTitle('Dismiss');
    await user.click(dismissBtn);

    expect(dismissSpy).toHaveBeenCalledWith('notif-2');
  });
});
