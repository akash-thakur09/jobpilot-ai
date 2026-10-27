import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SchedulerManager } from '../src/features/scheduler/SchedulerManager';
import { api } from '../src/lib/api-client';

describe('SchedulerManager Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders scheduler status, interval configuration, and run history', async () => {
    vi.spyOn(api.scheduler, 'getStatus').mockResolvedValue({
      is_enabled: true,
      scheduler_running: true,
      is_active_run: false,
      interval_minutes: 180,
      next_run_time: new Date(Date.now() + 3600000).toISOString(),
      last_run: {
        id: 'run-1',
        run_type: 'discovery_scheduled',
        status: 'COMPLETED',
        items_processed: 10,
        items_succeeded: 10,
        items_failed: 0,
        started_at: new Date().toISOString(),
        metadata: {
          trigger: 'scheduled',
          jobs_eligible: 3,
        },
      },
    });

    vi.spyOn(api.scheduler, 'listRuns').mockResolvedValue({
      items: [
        {
          id: 'run-1',
          run_type: 'discovery_scheduled',
          status: 'COMPLETED',
          items_processed: 10,
          items_succeeded: 10,
          items_failed: 0,
          started_at: new Date().toISOString(),
          metadata: {
            trigger: 'scheduled',
            jobs_inserted: 8,
            jobs_eligible: 3,
          },
        },
      ],
      total: 1,
      limit: 10,
      offset: 0,
    });

    render(<SchedulerManager />);

    await waitFor(() => {
      expect(screen.getByText('Discovery Scheduler')).toBeInTheDocument();
      expect(screen.getByText('Active / Enabled')).toBeInTheDocument();
      expect(screen.getByDisplayValue('180')).toBeInTheDocument();
      expect(screen.getAllByText('Success').length).toBeGreaterThan(0);
      expect(screen.getByText('10 jobs')).toBeInTheDocument();
      expect(screen.getByText('Run Discovery Now')).toBeInTheDocument();
    });
  });

  it('allows triggering a manual discovery run with feedback', async () => {
    const user = userEvent.setup();
    vi.spyOn(api.scheduler, 'getStatus').mockResolvedValue({
      is_enabled: false,
      scheduler_running: false,
      is_active_run: false,
      interval_minutes: 240,
    });
    vi.spyOn(api.scheduler, 'listRuns').mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });

    const runSpy = vi.spyOn(api.scheduler, 'run').mockResolvedValue({
      run_id: 'new-run-99',
      status: 'COMPLETED',
      inserted: 4,
      jobs_eligible: 2,
    });

    render(<SchedulerManager />);

    await waitFor(() => {
      expect(screen.getByText('Run Discovery Now')).toBeInTheDocument();
    });

    const triggerBtn = screen.getByText('Run Discovery Now');
    await user.click(triggerBtn);

    expect(runSpy).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByText(/4 new jobs discovered, 2 eligible matches/i)).toBeInTheDocument();
    });
  });

  it('allows saving updated discovery interval', async () => {
    const user = userEvent.setup();
    vi.spyOn(api.scheduler, 'getStatus').mockResolvedValue({
      is_enabled: false,
      scheduler_running: false,
      is_active_run: false,
      interval_minutes: 240,
    });
    vi.spyOn(api.scheduler, 'listRuns').mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });

    const configSpy = vi.spyOn(api.scheduler, 'updateConfig').mockResolvedValue({
      is_enabled: false,
      scheduler_running: false,
      is_active_run: false,
      interval_minutes: 60,
    });

    render(<SchedulerManager />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('240')).toBeInTheDocument();
    });

    const input = screen.getByDisplayValue('240');
    await user.clear(input);
    await user.type(input, '60');

    const saveBtn = screen.getByText('Save Interval');
    await user.click(saveBtn);

    expect(configSpy).toHaveBeenCalledWith({ interval_minutes: 60 });
    await waitFor(() => {
      expect(screen.getByText('Interval updated to 60 minutes.')).toBeInTheDocument();
    });
  });
});
