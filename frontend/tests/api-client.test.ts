import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api, ApiError } from '../src/lib/api-client';

describe('API Client', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('handles successful JSON requests correctly', async () => {
    const mockHealth = { status: 'healthy', app: 'JobPilot AI' };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockHealth,
    });

    const result = await api.health.check();
    expect(result).toEqual(mockHealth);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/health'),
      expect.anything()
    );
  });

  it('throws typed ApiError on HTTP 404 response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: 'Candidate profile does not exist yet.' }),
    });

    await expect(api.profile.get()).rejects.toThrow(ApiError);
    try {
      await api.profile.get();
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(404);
      expect(err.message).toBe('Candidate profile does not exist yet.');
    }
  });

  it('handles FastAPI validation error arrays cleanly', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      json: async () => ({
        detail: [
          { loc: ['body', 'job_id'], msg: 'Field required', type: 'missing' },
        ],
      }),
    });

    try {
      await api.applications.prepare({ job_id: '' });
    } catch (err: any) {
      expect(err.status).toBe(422);
      expect(err.message).toContain('Field required');
    }
  });

  it('handles network unreachable error gracefully', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(api.health.check()).rejects.toThrow(ApiError);
    try {
      await api.health.check();
    } catch (err: any) {
      expect(err.status).toBe(0);
      expect(err.message).toContain('Backend unavailable');
    }
  });

  it('serializes query parameters correctly for job search', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 0, limit: 10, offset: 0 }),
    });

    await api.jobs.list({ search: 'react engineer', remote_type: 'REMOTE', limit: 10 });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/jobs\?remote_type=REMOTE&search=react\+engineer&limit=10/),
      expect.anything()
    );
  });
});
