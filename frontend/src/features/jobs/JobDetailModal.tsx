import React, { useState, useEffect } from 'react';
import { Job, MatchScore, JobFeedback, FeedbackType } from '../../types';
import { api } from '../../lib/api-client';
import { Modal } from '../../components/ui/Modal';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { 
  Building2, 
  MapPin, 
  DollarSign, 
  Briefcase, 
  Calendar, 
  ExternalLink, 
  Sparkles,
  ThumbsUp,
  ThumbsDown,
  CheckSquare,
  Ban,
  Copy,
  Clock,
  Layers,
} from 'lucide-react';
import { formatSalary, formatEligibilityBadge, formatScoreBadge } from '../../lib/formatters';

interface JobDetailModalProps {
  job: Job | null;
  matchResult?: MatchScore | null;
  isOpen: boolean;
  onClose: () => void;
  onPrepareApplication?: (jobId: string) => void;
  isPreparing?: boolean;
  onFeedbackChanged?: () => void;
}

export const JobDetailModal: React.FC<JobDetailModalProps> = ({
  job,
  matchResult,
  isOpen,
  onClose,
  onPrepareApplication,
  isPreparing = false,
  onFeedbackChanged,
}) => {
  const [feedback, setFeedback] = useState<JobFeedback | null>(null);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);

  useEffect(() => {
    if (job?.id && isOpen) {
      api.jobs.getFeedback(job.id).then((fb) => setFeedback(fb)).catch(() => setFeedback(null));
    } else {
      setFeedback(null);
    }
  }, [job?.id, isOpen]);

  const [freshnessStatus, setFreshnessStatus] = useState<string>(job?.freshness_status || 'ACTIVE');
  const [freshnessReason, setFreshnessReason] = useState<string | null | undefined>(job?.freshness_reason);
  const [isVerifyingFreshness, setIsVerifyingFreshness] = useState(false);

  useEffect(() => {
    if (job) {
      setFreshnessStatus(job.freshness_status || 'ACTIVE');
      setFreshnessReason(job.freshness_reason);
    }
  }, [job?.id]);

  if (!job) return null;

  const eligConfig = matchResult?.eligibility_status 
    ? formatEligibilityBadge(matchResult.eligibility_status)
    : null;
  const scoreConfig = matchResult?.overall_score != null 
    ? formatScoreBadge(matchResult.overall_score)
    : null;

  const salaryDisplay = formatSalary(job.salary_min, job.salary_max, job.salary_currency);

  const handleFeedback = async (type: FeedbackType) => {
    if (!job) return;
    setIsSubmittingFeedback(true);
    try {
      if (feedback?.feedback_type === type) {
        // Toggle off
        await api.jobs.deleteFeedback(job.id);
        setFeedback(null);
      } else {
        const updated = await api.jobs.submitFeedback(job.id, type);
        setFeedback(updated);
      }
      if (onFeedbackChanged) onFeedbackChanged();
    } catch (err) {
      console.error('Failed to submit feedback', err);
    } finally {
      setIsSubmittingFeedback(false);
    }
  };


  const handleVerifyFreshness = async () => {
    if (!job) return;
    setIsVerifyingFreshness(true);
    try {
      const res = await api.jobs.verifyFreshness(job.id);
      setFreshnessStatus(res.freshness_status);
      if (res.freshness_reason) setFreshnessReason(res.freshness_reason);
    } catch (err) {
      console.error('Failed to verify live freshness', err);
    } finally {
      setIsVerifyingFreshness(false);
    }
  };

  const getFreshnessBadge = (status?: string) => {
    switch (status) {
      case 'ACTIVE':
        return <Badge variant="success" size="sm">Verified Active</Badge>;
      case 'POTENTIALLY_STALE':
        return <Badge variant="warning" size="sm">Potentially Stale</Badge>;
      case 'CONFIRMED_CLOSED':
        return <Badge variant="danger" size="sm">Confirmed Closed</Badge>;
      default:
        return <Badge variant="default" size="sm">Verification Pending</Badge>;
    }
  };


  const breakdown = matchResult?.scoring_breakdown;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={job.title}
      size="xl"
      footer={
        <div className="flex items-center justify-between w-full">
          <div className="text-xs text-slate-500">
            Source: <span className="font-mono text-slate-400">{job.source_name || job.source_id}</span>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="ghost" onClick={onClose}>
              Close
            </Button>
            {onPrepareApplication && (
              <Button
                variant="primary"
                onClick={() => onPrepareApplication(job.id)}
                isLoading={isPreparing}
                icon={<Sparkles className="w-4 h-4" />}
                disabled={matchResult?.eligibility_status === 'DISQUALIFIED'}
              >
                {matchResult?.eligibility_status === 'DISQUALIFIED'
                  ? 'Disqualified (Ineligible)'
                  : 'Prepare Application'}
              </Button>
            )}
          </div>
        </div>
      }
    >
      <div className="space-y-5">
        {/* Job metadata header */}
        <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300 pb-3 border-b border-slate-800">
          <div className="flex items-center gap-1.5 text-slate-200 font-medium">
            <Building2 className="w-4 h-4 text-blue-400" />
            {job.company}
          </div>
          <div className="flex items-center gap-1.5">
            <MapPin className="w-4 h-4 text-slate-400" />
            {job.location || 'Remote'}
          </div>
          {salaryDisplay && (
            <div className="flex items-center gap-1.5 text-emerald-400">
              <DollarSign className="w-4 h-4" />
              {salaryDisplay}
            </div>
          )}
          <div className="flex items-center gap-1.5">
            <Briefcase className="w-4 h-4 text-slate-400" />
            {job.remote_type ? job.remote_type.replace('_', ' ') : 'Remote'}
          </div>
          <div className="flex items-center gap-1.5 text-slate-400">
            <Calendar className="w-4 h-4" />
            Discovered {new Date(job.discovered_at).toLocaleDateString()}
          </div>
        </div>

        {/* Freshness & Duplicate Badges */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-xs text-slate-400">Freshness:</span>
              {getFreshnessBadge(freshnessStatus)}
            </div>
            {freshnessReason && (
              <span className="text-[11px] text-slate-400 italic">({freshnessReason})</span>
            )}
            {job.duplicate_cluster_id && (
              <div className="flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-purple-400" />
                <Badge variant="purple" size="sm">Cross-Source Duplicate Group</Badge>
              </div>
            )}
          </div>
          <div className="flex items-center gap-3">
            {job.last_seen_at && (
              <div className="text-[11px] text-slate-500 font-mono">
                Verified: {new Date(job.last_seen_at).toLocaleDateString()}
              </div>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleVerifyFreshness}
              isLoading={isVerifyingFreshness}
              className="text-xs py-1 px-2.5 h-7"
            >
              Verify Live Status
            </Button>
          </div>
        </div>


        {/* User Recommendation Feedback Controls */}
        <div className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-800/80 space-y-2">
          <div className="text-xs font-semibold text-slate-300 flex items-center justify-between">
            <span>Candidate Recommendation Feedback</span>
            {feedback && (
              <span className="text-[11px] font-normal text-blue-400">
                Active: {feedback.feedback_type.replace('_', ' ')}
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => handleFeedback('RELEVANT')}
              disabled={isSubmittingFeedback}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors border ${
                feedback?.feedback_type === 'RELEVANT'
                  ? 'bg-emerald-950 text-emerald-300 border-emerald-700'
                  : 'bg-slate-800/60 text-slate-400 border-slate-700 hover:text-slate-200'
              }`}
            >
              <ThumbsUp className="w-3.5 h-3.5" />
              Relevant
            </button>
            <button
              onClick={() => handleFeedback('NOT_RELEVANT')}
              disabled={isSubmittingFeedback}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors border ${
                feedback?.feedback_type === 'NOT_RELEVANT'
                  ? 'bg-red-950 text-red-300 border-red-700'
                  : 'bg-slate-800/60 text-slate-400 border-slate-700 hover:text-slate-200'
              }`}
            >
              <ThumbsDown className="w-3.5 h-3.5" />
              Not Relevant
            </button>
            <button
              onClick={() => handleFeedback('ALREADY_APPLIED')}
              disabled={isSubmittingFeedback}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors border ${
                feedback?.feedback_type === 'ALREADY_APPLIED'
                  ? 'bg-blue-950 text-blue-300 border-blue-700'
                  : 'bg-slate-800/60 text-slate-400 border-slate-700 hover:text-slate-200'
              }`}
            >
              <CheckSquare className="w-3.5 h-3.5" />
              Already Applied
            </button>
            <button
              onClick={() => handleFeedback('NOT_INTERESTED')}
              disabled={isSubmittingFeedback}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors border ${
                feedback?.feedback_type === 'NOT_INTERESTED'
                  ? 'bg-amber-950 text-amber-300 border-amber-700'
                  : 'bg-slate-800/60 text-slate-400 border-slate-700 hover:text-slate-200'
              }`}
            >
              <Ban className="w-3.5 h-3.5" />
              Not Interested
            </button>
            <button
              onClick={() => handleFeedback('DUPLICATE_LISTING')}
              disabled={isSubmittingFeedback}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors border ${
                feedback?.feedback_type === 'DUPLICATE_LISTING'
                  ? 'bg-purple-950 text-purple-300 border-purple-700'
                  : 'bg-slate-800/60 text-slate-400 border-slate-700 hover:text-slate-200'
              }`}
            >
              <Copy className="w-3.5 h-3.5" />
              Duplicate Listing
            </button>
          </div>
        </div>

        {/* Deterministic Eligibility & Match Score Card */}
        {matchResult && (
          <div className={`p-4 rounded-xl border ${
            matchResult.eligibility_status === 'DISQUALIFIED'
              ? 'bg-red-950/20 border-red-900/50'
              : matchResult.eligibility_status === 'ELIGIBLE'
              ? 'bg-emerald-950/20 border-emerald-900/50'
              : 'bg-amber-950/20 border-amber-900/50'
          }`}>
            <div className="flex items-start justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
                  Deterministic Eligibility & Match Evaluation
                </div>
                <div className="flex items-center gap-2">
                  {eligConfig && <Badge variant={eligConfig.variant}>{eligConfig.label}</Badge>}
                  {scoreConfig && (
                    <Badge variant={scoreConfig.variant}>
                      Match Score: {scoreConfig.label}
                    </Badge>
                  )}
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                    Policy v{matchResult.scoring_policy_version || '1.1.0'}
                  </span>
                </div>
              </div>
            </div>

            {/* Explanation / Disqualification rationale */}
            {matchResult.explanation && (
              <div className="mt-3 pt-3 border-t border-slate-800/80 text-sm text-slate-300">
                <span className="font-semibold text-slate-200">Analysis: </span>
                {matchResult.explanation}
              </div>
            )}

            {/* Explainable Contributions Breakdown */}
            {breakdown && (
              <div className="mt-3 pt-3 border-t border-slate-800/80 space-y-2 text-xs">
                {breakdown.positive_contributions && breakdown.positive_contributions.length > 0 && (
                  <div className="space-y-1">
                    <span className="font-semibold text-emerald-400">Positive Factors:</span>
                    <ul className="list-disc list-inside text-slate-300 space-y-0.5">
                      {breakdown.positive_contributions.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {breakdown.negative_contributions && breakdown.negative_contributions.length > 0 && (
                  <div className="space-y-1 pt-1">
                    <span className="font-semibold text-red-400">Deductions / Concerns:</span>
                    <ul className="list-disc list-inside text-slate-300 space-y-0.5">
                      {breakdown.negative_contributions.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {breakdown.missing_information && breakdown.missing_information.length > 0 && (
                  <div className="space-y-1 pt-1">
                    <span className="font-semibold text-amber-400">Missing Information:</span>
                    <ul className="list-disc list-inside text-slate-400 space-y-0.5">
                      {breakdown.missing_information.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Requirements */}
        {job.requirements && job.requirements.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-slate-200 mb-2">Requirements</h4>
            <div className="flex flex-wrap gap-2">
              {job.requirements.map((req, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 rounded-md text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700/60"
                >
                  <span className="text-slate-500 font-mono text-[10px] uppercase mr-1">{req.requirement_type}:</span>
                  {req.value}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Description */}
        <div>
          <h4 className="text-sm font-semibold text-slate-200 mb-2">Job Description</h4>
          <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 text-sm text-slate-300 leading-relaxed whitespace-pre-line max-h-96 overflow-y-auto">
            {job.description}
          </div>
        </div>

        {/* Source URL if available */}
        {job.canonical_url && (
          <div className="pt-2">
            <a
              href={job.canonical_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 underline"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              View original job posting ({job.source_name || job.source_id})
            </a>
          </div>
        )}
      </div>
    </Modal>
  );
};
