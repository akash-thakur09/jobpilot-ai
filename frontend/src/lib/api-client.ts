/**
 * JobPilot AI - Centralized Typed API Client
 * Configures base URL from environment (VITE_API_BASE_URL) and provides
 * typed endpoints for profile, jobs, matching, resumes, and applications.
 */

import {
  Application,
  ApplicationEventListResponse,
  ApplicationListResponse,
  ApplicationReviewPayload,
  CandidateProfile,
  CandidateProfileUpdate,
  CandidateSkill,
  CandidateExperience,
  CandidateEducation,
  CandidateProject,
  Job,
  JobDiscoveryResponse,
  JobListResponse,
  JobSource,
  MatchScore,
  ResumeImportResult,
  ResumeIntegrityCheck,
  ResumeVersion,
  SubmissionAttempt,
  SubmissionAttemptListResponse,
} from '../types';

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: any) {
    throw new ApiError(
      0,
      `Backend unavailable: Unable to connect to ${API_BASE_URL}. Ensure the FastAPI server is running.`
    );
  }

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errorJson = await response.json();
      if (typeof errorJson.detail === 'string') {
        errorDetail = errorJson.detail;
      } else if (Array.isArray(errorJson.detail)) {
        errorDetail = errorJson.detail.map((e: any) => e.msg || JSON.stringify(e)).join(', ');
      } else if (errorJson.message) {
        errorDetail = errorJson.message;
      }
    } catch {
      // Failed to parse JSON error, fall back to statusText
    }
    throw new ApiError(response.status, errorDetail);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  // -------------------------------------------------------------------------
  // Health
  // -------------------------------------------------------------------------
  health: {
    check: () => request<{ status: string; app: string }>('/health'),
    checkApiV1: () =>
      request<{ status: string; service: string; version: string }>('/api/v1/health'),
  },

  // -------------------------------------------------------------------------
  // Candidate Profile
  // -------------------------------------------------------------------------
  profile: {
    get: () => request<CandidateProfile>('/api/v1/profile'),
    create: (data: Partial<CandidateProfile>) =>
      request<CandidateProfile>('/api/v1/profile', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (data: CandidateProfileUpdate) =>
      request<CandidateProfile>('/api/v1/profile', {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    addSkill: (skill: Omit<CandidateSkill, 'id' | 'candidate_id'>) =>
      request<CandidateSkill>('/api/v1/profile/skills', {
        method: 'POST',
        body: JSON.stringify(skill),
      }),
    deleteSkill: (skillId: string) =>
      request<void>(`/api/v1/profile/skills/${skillId}`, { method: 'DELETE' }),
    addExperience: (exp: Omit<CandidateExperience, 'id' | 'candidate_id'>) =>
      request<CandidateExperience>('/api/v1/profile/experiences', {
        method: 'POST',
        body: JSON.stringify(exp),
      }),
    deleteExperience: (expId: string) =>
      request<void>(`/api/v1/profile/experiences/${expId}`, { method: 'DELETE' }),
    addEducation: (edu: Omit<CandidateEducation, 'id' | 'candidate_id'>) =>
      request<CandidateEducation>('/api/v1/profile/educations', {
        method: 'POST',
        body: JSON.stringify(edu),
      }),
    deleteEducation: (eduId: string) =>
      request<void>(`/api/v1/profile/educations/${eduId}`, { method: 'DELETE' }),
    addProject: (proj: Omit<CandidateProject, 'id' | 'candidate_id'>) =>
      request<CandidateProject>('/api/v1/profile/projects', {
        method: 'POST',
        body: JSON.stringify(proj),
      }),
    deleteProject: (projId: string) =>
      request<void>(`/api/v1/profile/projects/${projId}`, { method: 'DELETE' }),
    importResume: (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return request<ResumeImportResult>('/api/v1/profile/import-resume', {
        method: 'POST',
        body: formData,
      });
    },
    confirmImport: (confirmedProfile: Partial<CandidateProfile>) =>
      request<CandidateProfile>('/api/v1/profile/import-resume/confirm', {
        method: 'POST',
        body: JSON.stringify({ confirmed_profile: confirmedProfile }),
      }),
  },

  // -------------------------------------------------------------------------
  // Jobs
  // -------------------------------------------------------------------------
  jobs: {
    list: (params: {
      company?: string;
      remote_type?: string;
      search?: string;
      limit?: number;
      offset?: number;
    } = {}) => {
      const query = new URLSearchParams();
      if (params.company) query.set('company', params.company);
      if (params.remote_type) query.set('remote_type', params.remote_type);
      if (params.search) query.set('search', params.search);
      if (params.limit !== undefined) query.set('limit', params.limit.toString());
      if (params.offset !== undefined) query.set('offset', params.offset.toString());
      const qs = query.toString();
      return request<JobListResponse>(`/api/v1/jobs${qs ? `?${qs}` : ''}`);
    },
    get: (jobId: string) => request<Job>(`/api/v1/jobs/${jobId}`),
    listSources: () => request<JobSource[]>('/api/v1/jobs/sources'),
    discover: (
      sourceIdentifier: string,
      params: { board_token?: string; site_token?: string; count?: number } = {}
    ) =>
      request<JobDiscoveryResponse>('/api/v1/jobs/discover', {
        method: 'POST',
        body: JSON.stringify({ source_identifier: sourceIdentifier, ...params }),
      }),
  },

  // -------------------------------------------------------------------------
  // Matching
  // -------------------------------------------------------------------------
  matching: {
    evaluate: (jobId: string, useAi: boolean = false) =>
      request<MatchScore>(`/api/v1/matching/evaluate/${jobId}?use_ai=${useAi}`, {
        method: 'POST',
      }),
    evaluateAll: (useAi: boolean = false) =>
      request<{ total_evaluated: number; eligible_count: number; disqualified_count: number }>(
        `/api/v1/matching/evaluate-all?use_ai=${useAi}`,
        { method: 'POST' }
      ),
    listResults: (params: {
      is_eligible?: boolean;
      min_score?: number;
      is_latest?: boolean;
      limit?: number;
      offset?: number;
    } = {}) => {
      const query = new URLSearchParams();
      if (params.is_eligible !== undefined) query.set('is_eligible', String(params.is_eligible));
      if (params.min_score !== undefined) query.set('min_score', String(params.min_score));
      if (params.is_latest !== undefined) query.set('is_latest', String(params.is_latest));
      if (params.limit !== undefined) query.set('limit', String(params.limit));
      if (params.offset !== undefined) query.set('offset', String(params.offset));
      const qs = query.toString();
      return request<MatchScore[]>(`/api/v1/matching/results${qs ? `?${qs}` : ''}`);
    },
    getForJob: (jobId: string) => request<MatchScore>(`/api/v1/matching/results/${jobId}`),
    health: () =>
      request<{ status: string; engine: string; ai_provider: string; ai_available: boolean }>(
        '/api/v1/matching/health'
      ),
  },

  // -------------------------------------------------------------------------
  // Resumes
  // -------------------------------------------------------------------------
  resumes: {
    generate: (jobId: string, forceRegenerate: boolean = false) =>
      request<ResumeVersion>('/api/v1/resumes/generate', {
        method: 'POST',
        body: JSON.stringify({
          job_id: jobId,
          use_ai: false,
          force_regenerate: forceRegenerate,
        }),
      }),
    get: (versionId: string) => request<ResumeVersion>(`/api/v1/resumes/${versionId}`),
    listForJob: (jobId: string) =>
      request<ResumeVersion[]>(`/api/v1/resumes/job/${jobId}`),
    downloadUrl: (versionId: string) => `${API_BASE_URL}/api/v1/resumes/${versionId}/download`,
    verifyIntegrity: (versionId: string) =>
      request<ResumeIntegrityCheck>(`/api/v1/resumes/${versionId}/integrity`),
  },

  // -------------------------------------------------------------------------
  // Applications
  // -------------------------------------------------------------------------
  applications: {
    prepare: (
      jobOrParams: string | { job_id: string; candidate_id?: string; force_regenerate_resume?: boolean },
      candidateId?: string,
      forceRegenerateResume: boolean = false
    ) => {
      let body: any;
      if (typeof jobOrParams === 'object') {
        body = {
          job_id: jobOrParams.job_id,
          candidate_id: jobOrParams.candidate_id,
          force_regenerate_resume: jobOrParams.force_regenerate_resume ?? false,
        };
      } else {
        body = {
          job_id: jobOrParams,
          candidate_id: candidateId,
          force_regenerate_resume: forceRegenerateResume,
        };
      }
      return request<ApplicationReviewPayload>('/api/v1/applications/prepare', {
        method: 'POST',
        body: JSON.stringify(body),
      });
    },
    list: (params: {
      status?: string;
      candidate_id?: string;
      limit?: number;
      offset?: number;
    } = {}) => {
      const query = new URLSearchParams();
      if (params.status) query.set('status', params.status);
      if (params.candidate_id) query.set('candidate_id', params.candidate_id);
      if (params.limit !== undefined) query.set('limit', String(params.limit));
      if (params.offset !== undefined) query.set('offset', String(params.offset));
      const qs = query.toString();
      return request<ApplicationListResponse>(`/api/v1/applications${qs ? `?${qs}` : ''}`);
    },
    get: (applicationId: string) =>
      request<Application>(`/api/v1/applications/${applicationId}`),
    review: (applicationId: string) =>
      request<ApplicationReviewPayload>(`/api/v1/applications/${applicationId}/review`),
    approve: (
      applicationId: string,
      fingerprintOrData: string | { reviewed_fingerprint: string; approval_metadata?: Record<string, any> },
      metadata?: Record<string, any>
    ) => {
      let body: any;
      if (typeof fingerprintOrData === 'object') {
        body = fingerprintOrData;
      } else {
        body = {
          reviewed_fingerprint: fingerprintOrData,
          approval_metadata: metadata,
        };
      }
      return request<Application>(`/api/v1/applications/${applicationId}/approve`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
    },
    attempt: (applicationId: string, targetUrl?: string) =>
      request<SubmissionAttempt>(`/api/v1/applications/${applicationId}/attempt`, {
        method: 'POST',
        body: JSON.stringify({ target_url: targetUrl }),
      }),
    listEvents: (applicationId: string, limit: number = 50, offset: number = 0) =>
      request<ApplicationEventListResponse>(
        `/api/v1/applications/${applicationId}/events?limit=${limit}&offset=${offset}`
      ),
    listAttempts: (applicationId: string, limit: number = 50, offset: number = 0) =>
      request<SubmissionAttemptListResponse>(
        `/api/v1/applications/${applicationId}/attempts?limit=${limit}&offset=${offset}`
      ),
    reconcile: (
      applicationId: string,
      statusOrData: string | { target_status: string; reconciliation_evidence?: Record<string, any>; notes?: string },
      evidence: Record<string, any> = {},
      notes?: string
    ) => {
      let body: any;
      if (typeof statusOrData === 'object') {
        body = statusOrData;
      } else {
        body = {
          target_status: statusOrData,
          reconciliation_evidence: evidence,
          notes,
        };
      }
      return request<Application>(`/api/v1/applications/${applicationId}/reconcile`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
    },
  },
};
