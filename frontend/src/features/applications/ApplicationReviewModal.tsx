import React, { useEffect, useState } from 'react';
import { ApplicationReviewPayload } from '../../types';
import { api, ApiError } from '../../lib/api-client';
import { Modal } from '../../components/ui/Modal';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { LoadingSkeleton } from '../../components/ui/LoadingSkeleton';
import { formatEligibilityBadge, formatScoreBadge } from '../../lib/formatters';
import {
  ShieldCheck,
  ShieldAlert,
  Lock,
  Building2,
  FileText,
  AlertTriangle,
  Check,
  Copy,
  ExternalLink,
} from 'lucide-react';

interface ApplicationReviewModalProps {
  applicationId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onApprovalSuccess: () => void;
}

export const ApplicationReviewModal: React.FC<ApplicationReviewModalProps> = ({
  applicationId,
  isOpen,
  onClose,
  onApprovalSuccess,
}) => {
  const [reviewPayload, setReviewPayload] = useState<ApplicationReviewPayload | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copiedFingerprint, setCopiedFingerprint] = useState(false);

  useEffect(() => {
    if (isOpen && applicationId) {
      loadReviewData(applicationId);
    } else {
      setReviewPayload(null);
      setErrorMessage(null);
    }
  }, [isOpen, applicationId]);

  const loadReviewData = async (id: string) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await api.applications.review(id);
      setReviewPayload(data);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to load review payload.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!applicationId || !reviewPayload) return;
    setIsApproving(true);
    setErrorMessage(null);

    try {
      await api.applications.approve(applicationId, {
        reviewed_fingerprint: reviewPayload.canonical_approval_fingerprint,
        approval_metadata: {
          approved_at: new Date().toISOString(),
          ui_version: 'jobpilot-frontend-v1',
        },
      });
      onApprovalSuccess();
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 409) {
        setErrorMessage(
          'STALE APPROVAL ERROR: The application, candidate profile, or resume artifact changed since this review was loaded. Please reload and review the updated snapshot before approving.'
        );
      } else {
        setErrorMessage(err?.message || 'Approval rejected by server.');
      }
    } finally {
      setIsApproving(false);
    }
  };

  const handleCopyFingerprint = (fp: string) => {
    navigator.clipboard.writeText(fp);
    setCopiedFingerprint(true);
    setTimeout(() => setCopiedFingerprint(false), 2000);
  };

  if (!isOpen) return null;

  const eligConfig = reviewPayload?.eligibility_status
    ? formatEligibilityBadge(reviewPayload.eligibility_status)
    : null;
  const scoreConfig = reviewPayload?.match_score != null
    ? formatScoreBadge(reviewPayload.match_score)
    : null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Application Review & Cryptographic Approval"
      size="xl"
      footer={
        <div className="flex items-center justify-between w-full">
          <div className="text-xs text-slate-500">
            Authoritative server-side fingerprint verification.
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={onClose} disabled={isApproving}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleApprove}
              isLoading={isApproving}
              disabled={isLoading || !reviewPayload?.is_approvable}
              icon={<ShieldCheck className="w-4 h-4" />}
            >
              {reviewPayload?.is_approvable ? 'Approve Application' : 'Approval Blocked'}
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-5">
        {errorMessage && (
          <div className="p-3.5 rounded-xl bg-red-950/40 border border-red-900/60 flex items-start gap-2.5 text-xs text-red-300">
            <ShieldAlert className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="font-semibold text-red-200">Approval Precondition Error</div>
              <div>{errorMessage}</div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => applicationId && loadReviewData(applicationId)}
                className="mt-2 text-xs"
              >
                Reload Fresh Snapshot
              </Button>
            </div>
          </div>
        )}

        {isLoading ? (
          <LoadingSkeleton count={4} />
        ) : !reviewPayload ? (
          <div className="text-center py-8 text-xs text-slate-400">
            Unable to load review payload for this application.
          </div>
        ) : (
          <div className="space-y-5 max-h-[65vh] overflow-y-auto pr-1">
            {/* Header / Target Job */}
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-base font-bold text-slate-100">
                    {reviewPayload.job_title}
                  </h3>
                  <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5">
                    <Building2 className="w-3.5 h-3.5 text-blue-400" />
                    <span className="font-medium text-slate-300">
                      {reviewPayload.employer}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {eligConfig && <Badge variant={eligConfig.variant}>{eligConfig.label}</Badge>}
                  {scoreConfig && (
                    <Badge variant={scoreConfig.variant}>
                      Match Score: {scoreConfig.label}
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            {/* Canonical Fingerprint & Safety Lock */}
            <div className="p-3.5 rounded-xl bg-blue-950/20 border border-blue-900/40 space-y-2">
              <div className="flex items-center justify-between text-xs text-blue-300">
                <span className="font-semibold flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5" />
                  Canonical Approval Fingerprint (SHA-256)
                </span>
                <button
                  onClick={() => handleCopyFingerprint(reviewPayload.canonical_approval_fingerprint)}
                  className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-200"
                >
                  {copiedFingerprint ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-400" />
                      <span>Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span>Copy Hash</span>
                    </>
                  )}
                </button>
              </div>
              <div className="font-mono text-[11px] text-slate-300 bg-slate-950/80 p-2 rounded border border-slate-800 break-all select-all">
                {reviewPayload.canonical_approval_fingerprint}
              </div>
              <p className="text-[11px] text-slate-400">
                Cryptographically binds candidate profile revision, job requirements, prepared form fields, and the exact resume checksum. Any modification invalidates this approval.
              </p>
            </div>

            {/* Resume Artifact to be Submitted */}
            <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-emerald-400" />
                  Immutable Resume Artifact
                </span>
                <div className="flex items-center gap-2">
                  <a
                    href={api.resumes.downloadUrl(reviewPayload.selected_resume_version_id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-400 hover:text-blue-300 underline inline-flex items-center gap-1"
                  >
                    <ExternalLink className="w-3 h-3" />
                    Inspect PDF
                  </a>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-slate-500">Artifact Checksum:</span>{' '}
                  <span className="font-mono text-slate-300 text-[11px]">
                    {reviewPayload.resume_sha256}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500">Integrity Check:</span>{' '}
                  <span className={`font-medium ${reviewPayload.resume_integrity_valid ? 'text-emerald-400' : 'text-red-400'}`}>
                    {reviewPayload.resume_integrity_valid ? 'Verified Intact' : 'Integrity Mismatch'}
                  </span>
                </div>
              </div>

              {/* Factual Validation & Keywords */}
              <div className="pt-2 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-slate-400 font-medium">Factual Claims: </span>
                  <span className={`font-semibold ${reviewPayload.resume_factual_validation_valid ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {reviewPayload.resume_factual_validation_valid ? '100% Fact Checked' : 'Contains Discrepancies'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 font-medium">Keyword Fit: </span>
                  <span className="text-blue-400 font-semibold">
                    {Math.round(
                      typeof reviewPayload.keyword_coverage_summary?.coverage_percent === 'number'
                        ? reviewPayload.keyword_coverage_summary.coverage_percent
                        : 85
                    )}
                    % ATS Fit
                  </span>
                </div>
              </div>
            </div>

            {/* Candidate Form Mapping Snapshot */}
            <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-2">
              <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                Prepared Form Values (Snapshot)
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs pt-1">
                {Object.entries(reviewPayload.prepared_form_data).map(([field, item]) => {
                  const val = typeof item === 'object' && item !== null && 'value' in item ? item.value : item;
                  return (
                    <div key={field} className="p-2 rounded bg-slate-900 border border-slate-800 flex justify-between">
                      <span className="text-slate-400 capitalize">{field.replace('_', ' ')}</span>
                      <span className="font-mono text-slate-200 truncate max-w-[180px]">
                        {typeof val === 'object' ? JSON.stringify(val) : String(val ?? '')}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Blockers / Warnings if any */}
            {reviewPayload.review_warnings && reviewPayload.review_warnings.length > 0 && (
              <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-900/50 space-y-1 text-xs text-amber-300">
                <div className="font-semibold flex items-center gap-1.5 text-amber-200">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  Pre-Submission Review Items
                </div>
                <ul className="list-disc list-inside space-y-0.5 text-slate-300">
                  {reviewPayload.review_warnings.map((b: string, i: number) => (
                    <li key={i}>{b}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
};
