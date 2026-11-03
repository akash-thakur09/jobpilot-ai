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
  JobSourceConfigUpdate,
  JobImportRequest,
  JobImportResponse,
  JobSearchPreferences,
  JobSearchPreferencesUpdate,
  MatchScore,
  ResumeImportResult,
  ResumeIntegrityCheck,
  ResumeVersion,
  SubmissionAttempt,
  SubmissionAttemptListResponse,
  SchedulerStatus,
  SchedulerConfigUpdate,
  SchedulerRunRequest,
  AutomationRunItem,
  AutomationRunListResponse,
  Notification,
  NotificationListResponse,
  NotificationPreferences,
  NotificationPreferencesUpdate,
  EmailConfigStatus,
  TestEmailResponse,
  UnreadCountResponse,
  DigestStatus,
  DeliveryHistoryResponse,
  JobDuplicateCluster,
  JobFeedback,
  FeedbackType,
  RankingEvaluationSummary,
  JobRelevanceRead,
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
    getPreferences: () =>
      request<JobSearchPreferences>('/api/v1/profile/preferences'),
    updatePreferences: (prefs: JobSearchPreferencesUpdate) =>
      request<JobSearchPreferences>('/api/v1/profile/preferences', {
        method: 'PUT',
        body: JSON.stringify(prefs),
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
      relevance_classification?: string;
      min_relevance_score?: number;
      include_synthetic?: boolean;
      limit?: number;
      offset?: number;
    } = {}) => {
      const query = new URLSearchParams();
      if (params.company) query.set('company', params.company);
      if (params.remote_type) query.set('remote_type', params.remote_type);
      if (params.search) query.set('search', params.search);
      if (params.relevance_classification) query.set('relevance_classification', params.relevance_classification);
      if (params.min_relevance_score !== undefined) query.set('min_relevance_score', params.min_relevance_score.toString());
      if (params.include_synthetic !== undefined) query.set('include_synthetic', params.include_synthetic.toString());
      if (params.limit !== undefined) query.set('limit', params.limit.toString());
      if (params.offset !== undefined) query.set('offset', params.offset.toString());
      const qs = query.toString();
      return request<JobListResponse>(`/api/v1/jobs${qs ? `?${qs}` : ''}`);
    },
    get: (jobId: string) => request<Job>(`/api/v1/jobs/${jobId}`),
    getRelevance: (jobId: string) => request<JobRelevanceRead>(`/api/v1/jobs/${jobId}/relevance`),
    reEvaluateRelevance: () =>
      request<{
        total_evaluated: number;
        highly_relevant_count: number;
        potentially_relevant_count: number;
        low_relevance_count: number;
        status: string;
      }>('/api/v1/jobs/re-evaluate-relevance', { method: 'POST' }),
    listSources: () => request<JobSource[]>('/api/v1/jobs/sources'),
    getSource: (identifier: string) =>
      request<JobSource>(`/api/v1/jobs/sources/${identifier}`),
    updateSource: (identifier: string, data: JobSourceConfigUpdate) =>
      request<JobSource>(`/api/v1/jobs/sources/${identifier}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    importJobs: (identifier: string, data: JobImportRequest) =>
      request<JobImportResponse>(`/api/v1/jobs/sources/${identifier}/import`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    discover: (
      sourceIdentifier: string,
      params: {
        board_token?: string;
        board_tokens?: string[];
        site_token?: string;
        site_tokens?: string[];
        count?: number;
      } = {}
    ) =>
      request<JobDiscoveryResponse>('/api/v1/jobs/discover', {
        method: 'POST',
        body: JSON.stringify({ source_identifier: sourceIdentifier, ...params }),
      }),
    listDuplicates: (clusterStatus?: string) => {
      const qs = clusterStatus ? `?cluster_status=${clusterStatus}` : '';
      return request<JobDuplicateCluster[]>(`/api/v1/jobs/duplicates${qs}`);
    },
    reviewDuplicate: (clusterId: string, action: 'CONFIRM' | 'DISMISS', notes?: string) =>
      request<JobDuplicateCluster>(`/api/v1/jobs/duplicates/${clusterId}/review`, {
        method: 'POST',
        body: JSON.stringify({ action, notes }),
      }),
    getFreshness: (jobId: string) =>
      request<{
        job_id: string;
        freshness_status: string;
        freshness_reason?: string | null;
        first_seen_at?: string | null;
        last_seen_at?: string | null;
        last_verified_at?: string | null;
        posted_at?: string | null;
      }>(`/api/v1/jobs/${jobId}/freshness`),
    verifyFreshness: (jobId: string) =>
      request<{
        job_id: string;
        freshness_status: string;
        freshness_reason?: string | null;
        last_verified_at?: string | null;
        verified_live: boolean;
      }>(`/api/v1/jobs/${jobId}/freshness/verify`, {
        method: 'POST',
      }),
    submitFeedback: (jobId: string, feedbackType: FeedbackType, reason?: string, details?: Record<string, any>) =>
      request<JobFeedback>(`/api/v1/jobs/${jobId}/feedback`, {
        method: 'POST',
        body: JSON.stringify({
          feedback_type: feedbackType,
          reason,
          structured_details: details || {},
        }),
      }),
    getFeedback: (jobId: string) => request<JobFeedback | null>(`/api/v1/jobs/${jobId}/feedback`),
    deleteFeedback: (jobId: string) =>
      request<void>(`/api/v1/jobs/${jobId}/feedback`, { method: 'DELETE' }),
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
    evaluateRanking: () =>
      request<RankingEvaluationSummary>('/api/v1/matching/evaluate-ranking', {
        method: 'POST',
      }),
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

  // -------------------------------------------------------------------------
  // Scheduler & Automation Runs
  // -------------------------------------------------------------------------
  scheduler: {
    getStatus: () => request<SchedulerStatus>('/api/v1/scheduler/status'),
    updateConfig: (config: SchedulerConfigUpdate) =>
      request<SchedulerStatus>('/api/v1/scheduler/config', {
        method: 'POST',
        body: JSON.stringify(config),
      }),
    run: (params: SchedulerRunRequest = {}) =>
      request<any>('/api/v1/scheduler/run', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    listRuns: (params: { limit?: number; offset?: number; status?: string } = {}) => {
      const query = new URLSearchParams();
      if (params.limit !== undefined) query.set('limit', String(params.limit));
      if (params.offset !== undefined) query.set('offset', String(params.offset));
      if (params.status) query.set('status', params.status);
      const qs = query.toString();
      return request<AutomationRunListResponse>(`/api/v1/scheduler/runs${qs ? `?${qs}` : ''}`);
    },
    getRun: (runId: string) =>
      request<AutomationRunItem>(`/api/v1/scheduler/runs/${runId}`),
  },

  // -------------------------------------------------------------------------
  // Notifications
  // -------------------------------------------------------------------------
  notifications: {
    list: (params: {
      is_read?: boolean;
      is_dismissed?: boolean;
      notification_type?: string;
      limit?: number;
      offset?: number;
    } = {}) => {
      const query = new URLSearchParams();
      if (params.is_read !== undefined) query.set('is_read', String(params.is_read));
      if (params.is_dismissed !== undefined) query.set('is_dismissed', String(params.is_dismissed));
      if (params.notification_type) query.set('notification_type', params.notification_type);
      if (params.limit !== undefined) query.set('limit', String(params.limit));
      if (params.offset !== undefined) query.set('offset', String(params.offset));
      const qs = query.toString();
      return request<NotificationListResponse>(`/api/v1/notifications${qs ? `?${qs}` : ''}`);
    },
    getUnreadCount: () =>
      request<UnreadCountResponse>('/api/v1/notifications/unread-count'),
    markAsRead: (notificationId: string) =>
      request<{ success: boolean; notification: Notification }>(
        `/api/v1/notifications/${notificationId}/read`,
        { method: 'POST' }
      ),
    markAllAsRead: () =>
      request<{ success: boolean; updated_count: number }>(
        '/api/v1/notifications/read-all',
        { method: 'POST' }
      ),
    dismiss: (notificationId: string) =>
      request<{ success: boolean; notification: Notification }>(
        `/api/v1/notifications/${notificationId}/dismiss`,
        { method: 'POST' }
      ),
    getPreferences: () =>
      request<NotificationPreferences>('/api/v1/notifications/preferences'),
    updatePreferences: (prefs: NotificationPreferencesUpdate) =>
      request<NotificationPreferences>('/api/v1/notifications/preferences', {
        method: 'PUT',
        body: JSON.stringify(prefs),
      }),
    getEmailStatus: () =>
      request<EmailConfigStatus>('/api/v1/notifications/email-status'),
    sendTestEmail: (recipient: string) =>
      request<TestEmailResponse>('/api/v1/notifications/test-email', {
        method: 'POST',
        body: JSON.stringify({ recipient }),
      }),
    getDigestStatus: () =>
      request<DigestStatus>('/api/v1/notifications/digest/status'),
    triggerDigest: (force: boolean = false) =>
      request<{ success: boolean; message: string; notification: Notification | null }>(
        `/api/v1/notifications/digest/trigger${force ? '?force=true' : ''}`,
        { method: 'POST' }
      ),
    getDeliveryHistory: (limit: number = 20) =>
      request<DeliveryHistoryResponse>(`/api/v1/notifications/delivery-history?limit=${limit}`),
  },
};

