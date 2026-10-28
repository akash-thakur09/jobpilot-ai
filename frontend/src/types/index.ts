/**
 * JobPilot AI - Centralized TypeScript Domain Types
 * Exactly matches backend schemas and enum contracts.
 */

export type ApplicationStatus =
  | 'PREPARING'
  | 'READY_FOR_REVIEW'
  | 'NEEDS_HUMAN_ACTION'
  | 'APPROVED'
  | 'IN_PROGRESS'
  | 'SUBMITTED'
  | 'OUTCOME_UNKNOWN'
  | 'SHORTLISTED'
  | 'INTERVIEW_SCHEDULED'
  | 'REJECTED'
  | 'WITHDRAWN'
  | 'FAILED';

export type EligibilityStatus = 'ELIGIBLE' | 'DISQUALIFIED' | 'NEEDS_REVIEW' | 'UNKNOWN';

export type SubmissionOutcome =
  | 'SUCCESS'
  | 'FAILED'
  | 'NEEDS_HUMAN_ACTION'
  | 'OUTCOME_UNKNOWN'
  | 'BLOCKED_SAFETY';

// ---------------------------------------------------------------------------
// Candidate Profile
// ---------------------------------------------------------------------------

export interface CandidateSkill {
  id?: string;
  candidate_id?: string;
  skill_name: string;
  category?: string | null;
  years_experience?: number | null;
  is_verified: boolean;
  evidence?: Record<string, any> | null;
}

export interface CandidateExperience {
  id?: string;
  candidate_id?: string;
  company: string;
  role: string;
  location?: string | null;
  start_date: string;
  end_date?: string | null;
  is_current: boolean;
  verified_bullets?: string[];
  raw_bullets?: string[];
}

export interface CandidateEducation {
  id?: string;
  candidate_id?: string;
  institution: string;
  degree: string;
  field_of_study?: string | null;
  graduation_year?: number | null;
}

export interface CandidateProject {
  id?: string;
  candidate_id?: string;
  name: string;
  description?: string | null;
  technologies?: string[];
  url?: string | null;
}

export interface CandidateProfile {
  id: string;
  full_name: string;
  email: string;
  phone?: string | null;
  location?: string | null;
  work_authorization: string;
  summary?: string | null;
  years_of_experience?: number | null;
  target_titles?: string[];
  target_locations?: string[];
  min_salary?: number | null;
  target_salary?: number | null;
  remote_preference?: string | null;
  linkedin_url?: string | null;
  github_url?: string | null;
  portfolio_url?: string | null;
  skills: CandidateSkill[];
  experiences: CandidateExperience[];
  educations: CandidateEducation[];
  projects: CandidateProject[];
  search_preferences?: JobSearchPreferences | null;
  notification_preferences?: NotificationPreferences | null;
  created_at: string;
  updated_at: string;
}

export interface JobSearchPreferences {
  target_titles?: string[];
  role_keywords?: string[];
  required_skills?: string[];
  preferred_skills?: string[];
  preferred_locations?: string[];
  remote_preference?: 'ANY' | 'REMOTE' | 'HYBRID' | 'ON_SITE';
  min_years_experience?: number | null;
  max_years_experience?: number | null;
  min_salary?: number | null;
  preferred_companies?: string[];
  excluded_companies?: string[];
}

export interface JobSearchPreferencesUpdate {
  target_titles?: string[];
  role_keywords?: string[];
  required_skills?: string[];
  preferred_skills?: string[];
  preferred_locations?: string[];
  remote_preference?: 'ANY' | 'REMOTE' | 'HYBRID' | 'ON_SITE';
  min_years_experience?: number | null;
  max_years_experience?: number | null;
  min_salary?: number | null;
  preferred_companies?: string[];
  excluded_companies?: string[];
}

export interface CandidateProfileUpdate {
  full_name?: string;
  email?: string;
  phone?: string | null;
  location?: string | null;
  work_authorization?: string;
  summary?: string | null;
  years_of_experience?: number | null;
  target_titles?: string[];
  target_locations?: string[];
  min_salary?: number | null;
  target_salary?: number | null;
  remote_preference?: string | null;
  linkedin_url?: string | null;
  github_url?: string | null;
  portfolio_url?: string | null;
}

export interface ResumeImportResult {
  filename: string;
  file_size: number;
  extracted_text_length: number;
  draft_profile: Partial<CandidateProfile>;
  confidence_score: number;
  parsing_warnings: string[];
}

// ---------------------------------------------------------------------------
// Jobs
// ---------------------------------------------------------------------------

export interface JobRequirement {
  id: string;
  requirement_type: string;
  value: string;
  weight: number;
}

export interface Job {
  id: string;
  source_id: string;
  external_id: string;
  title: string;
  company: string;
  canonical_url: string;
  description: string;
  location?: string | null;
  remote_type?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency?: string | null;
  discovered_at: string;
  source_name?: string | null;
  requirements?: JobRequirement[];
}

export interface JobListResponse {
  items: Job[];
  total: number;
  limit: number;
  offset: number;
}

export interface JobSource {
  id: string;
  identifier: string;
  name: string;
  base_url: string;
  is_active: boolean;
  rate_limit_per_minute: number;
  last_discovered_at?: string | null;
  is_enabled?: boolean;
  source_type?: string;
  board_identifier?: string;
  last_run_at?: string | null;
  last_status?: string | null;
  last_error_summary?: string | null;
  jobs_discovered_count?: number;
}

export interface JobSourceConfigUpdate {
  is_enabled?: boolean;
  board_token?: string;
}

export interface JobDiscoveryResponse {
  source_identifier: string;
  total_discovered: number;
  new_jobs_added: number;
  duplicate_jobs_skipped: number;
  failed_records: number;
  error_details: string[];
}

// ---------------------------------------------------------------------------
// Matching & Scoring
// ---------------------------------------------------------------------------

export interface MatchScore {
  id: string;
  job_id: string;
  candidate_id: string;
  overall_score: number;
  is_eligible: boolean;
  eligibility_status: EligibilityStatus;
  eligibility_checks?: Record<string, any>;
  scoring_breakdown?: Record<string, any>;
  matching_skills?: string[];
  missing_skills?: string[];
  matched_required_skills?: string[];
  missing_required_skills?: string[];
  matched_preferred_skills?: string[];
  missing_preferred_skills?: string[];
  warnings?: string[];
  explanation: string;
  scoring_policy_version: string;
  is_latest: boolean;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Resumes
// ---------------------------------------------------------------------------

export interface ResumeVersion {
  id: string;
  candidate_id: string;
  job_id: string;
  version_number: number;
  pdf_file_path: string;
  file_sha256: string;
  is_ats_valid: boolean;
  is_submission_ready: boolean;
  keyword_coverage_result?: {
    coverage_percent?: number;
    matched_required?: string[];
    missing_required?: string[];
    matched_preferred?: string[];
    missing_preferred?: string[];
  } | null;
  factual_validation_result?: {
    is_valid: boolean;
    unsupported_claims?: string[];
  } | null;
  created_at: string;
}

export interface ResumeIntegrityCheck {
  version_id: string;
  is_intact: boolean;
  recorded_sha256: string;
  file_path: string;
  is_submission_ready: boolean;
}

// ---------------------------------------------------------------------------
// Applications
// ---------------------------------------------------------------------------

export interface Application {
  id: string;
  candidate_id: string;
  job_id: string;
  resume_version_id?: string | null;
  selected_resume_sha256?: string | null;
  status: ApplicationStatus;
  submission_method: string;
  submitted_at?: string | null;
  confirmation_evidence?: Record<string, any> | null;
  approval_fingerprint?: string | null;
  approved_at?: string | null;
  approval_metadata?: Record<string, any>;
  job_title?: string | null;
  company?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationListResponse {
  items: Application[];
  total: number;
  limit: number;
  offset: number;
}

export interface PreparedFormField {
  value: any;
  provenance: string;
  is_verified: boolean;
  description?: string | null;
}

export interface ApplicationReviewPayload {
  application_id: string;
  candidate_id: string;
  job_id: string;
  status: string;
  employer: string;
  job_title: string;
  job_url: string;
  job_fingerprint: string;
  eligibility_status: string;
  eligibility_reason: string;
  match_score: number;
  match_explanation: string;
  selected_resume_version_id: string;
  resume_sha256: string;
  resume_integrity_valid: boolean;
  resume_factual_validation_valid: boolean;
  keyword_coverage_summary: Record<string, any>;
  canonical_approval_fingerprint: string;
  prepared_form_data: Record<string, PreparedFormField>;
  unanswered_questions: string[];
  review_warnings: string[];
  is_approvable: boolean;
  approvable_reason: string;
  approved_at?: string | null;
  approved_fingerprint?: string | null;
}

export interface ApplicationEvent {
  id: string;
  application_id: string;
  from_status?: string | null;
  to_status: string;
  actor: string;
  payload: Record<string, any>;
  created_at: string;
}

export interface ApplicationEventListResponse {
  items: ApplicationEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface SubmissionAttempt {
  id: string;
  application_id: string;
  attempt_number: number;
  adapter_identifier: string;
  selected_resume_version_id: string;
  uploaded_artifact_sha256: string;
  outcome: SubmissionOutcome;
  started_at: string;
  completed_at?: string | null;
  confirmation_reference?: string | null;
  confirmation_payload: Record<string, any>;
  sanitized_diagnostics: Record<string, any>;
  reconciliation_metadata: Record<string, any>;
}

export interface SubmissionAttemptListResponse {
  items: SubmissionAttempt[];
  total: number;
  limit: number;
  offset: number;
}

// ---------------------------------------------------------------------------
// Scheduler & Automation Runs
// ---------------------------------------------------------------------------

export interface AutomationRunItem {
  id: string;
  run_type: string;
  status: 'RUNNING' | 'COMPLETED' | 'PARTIAL_SUCCESS' | 'FAILED' | 'CANCELLED' | string;
  items_processed: number;
  items_succeeded: number;
  items_failed: number;
  error_summary?: string | null;
  started_at: string;
  completed_at?: string | null;
  metadata: {
    trigger?: string;
    sources_requested?: string[];
    sources_attempted?: string[];
    successful_sources?: string[];
    failed_sources?: string[];
    source_diagnostics?: Record<string, any>;
    jobs_discovered?: number;
    jobs_inserted?: number;
    jobs_updated?: number;
    jobs_evaluated?: number;
    jobs_eligible?: number;
    new_relevant_matches?: number;
    notifications_created?: number;
    [key: string]: any;
  };
}

export interface AutomationRunListResponse {
  items: AutomationRunItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface SchedulerStatus {
  is_enabled: boolean;
  scheduler_running: boolean;
  is_active_run: boolean;
  interval_minutes: number;
  next_run_time?: string | null;
  last_run?: AutomationRunItem | null;
}

export interface SchedulerConfigUpdate {
  enabled?: boolean;
  interval_minutes?: number;
}

export interface SchedulerRunRequest {
  sources?: string[];
  use_ai_matching?: boolean;
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

export type NotificationType =
  | 'NEW_MATCH'
  | 'RUN_FAILED'
  | 'PARTIAL_FAILURE'
  | 'WORKFLOW_BLOCKER'
  | string;

export interface Notification {
  id: string;
  notification_type: NotificationType;
  title: string;
  message: string;
  channel: string;
  status: string;
  is_read: boolean;
  is_dismissed: boolean;
  job_id?: string | null;
  application_id?: string | null;
  run_id?: string | null;
  dedup_key?: string | null;
  created_at: string;
  updated_at: string;
  metadata: Record<string, any>;
}

export interface NotificationListResponse {
  items: Notification[];
  total: number;
  unread_count: number;
  limit: number;
  offset: number;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export type DeliveryMode = 'IMMEDIATE' | 'DAILY_DIGEST' | 'WEEKLY_DIGEST';

export interface NotificationPreferences {
  email_enabled: boolean;
  recipient_email?: string | null;
  notify_new_matches: boolean;
  notify_partial_discovery: boolean;
  notify_discovery_failures: boolean;
  notify_workflow_blockers: boolean;
  delivery_mode: DeliveryMode;
  min_match_score: number;
  timezone?: string;
}

export interface NotificationPreferencesUpdate {
  email_enabled?: boolean;
  recipient_email?: string | null;
  notify_new_matches?: boolean;
  notify_partial_discovery?: boolean;
  notify_discovery_failures?: boolean;
  notify_workflow_blockers?: boolean;
  delivery_mode?: DeliveryMode;
  min_match_score?: number;
  timezone?: string;
}

export interface EmailConfigStatus {
  is_available?: boolean;
  configured?: boolean;
  provider: string;
  from_address?: string | null;
  recipient?: string | null;
  email_notifications_enabled?: boolean;
  timezone?: string;
  is_simulated?: boolean;
  host?: string | null;
  port?: number | null;
  use_tls?: boolean;
}

export interface DigestStatus {
  email_enabled: boolean;
  delivery_mode: string;
  timezone: string;
  is_provider_configured: boolean;
  provider: string;
  recipient?: string | null;
  min_match_score: number;
  pending_matches_count: number;
  next_digest_at?: string | null;
  last_digest_at?: string | null;
  last_digest_status?: string | null;
}

export interface DeliveryHistoryItem {
  id: string;
  title: string;
  channel: string;
  status: string;
  status_detail?: string | null;
  provider: string;
  recipient?: string | null;
  sent_at?: string | null;
  created_at: string;
  attempt_count: number;
  attempts: Array<{
    attempt: number;
    timestamp: string;
    status: string;
    detail?: string;
    error?: string;
    is_transient?: boolean;
  }>;
  error?: string | null;
  is_simulated: boolean;
  digest_id?: string | null;
  matches_count?: number | null;
}

export interface DeliveryHistoryResponse {
  items: DeliveryHistoryItem[];
  total: number;
}

export interface TestEmailResponse {
  success: boolean;
  message: string;
  recipient: string;
  provider: string;
  delivery_status?: string;
}

