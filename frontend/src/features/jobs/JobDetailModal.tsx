import React from 'react';
import { Job, MatchScore } from '../../types';
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
} from 'lucide-react';
import { formatSalary, formatEligibilityBadge, formatScoreBadge } from '../../lib/formatters';

interface JobDetailModalProps {
  job: Job | null;
  matchResult?: MatchScore | null;
  isOpen: boolean;
  onClose: () => void;
  onPrepareApplication?: (jobId: string) => void;
  isPreparing?: boolean;
}

export const JobDetailModal: React.FC<JobDetailModalProps> = ({
  job,
  matchResult,
  isOpen,
  onClose,
  onPrepareApplication,
  isPreparing = false,
}) => {
  if (!job) return null;

  const eligConfig = matchResult?.eligibility_status 
    ? formatEligibilityBadge(matchResult.eligibility_status)
    : null;
  const scoreConfig = matchResult?.overall_score != null 
    ? formatScoreBadge(matchResult.overall_score)
    : null;

  const salaryDisplay = formatSalary(job.salary_min, job.salary_max, job.salary_currency);

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
      <div className="space-y-6">
        {/* Job metadata header */}
        <div className="flex flex-wrap items-center gap-4 text-sm text-slate-300 pb-4 border-b border-slate-800">
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
            {new Date(job.discovered_at).toLocaleDateString()}
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

            {/* Score Breakdown */}
            {matchResult.scoring_breakdown && (
              <div className="mt-4 pt-3 border-t border-slate-800/80 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                {Object.entries(matchResult.scoring_breakdown).map(([k, v]) => (
                  <div key={k} className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                    <div className="text-slate-400 mb-0.5 capitalize">{k.replace('_', ' ')}</div>
                    <div className="text-base font-semibold text-blue-400">
                      {typeof v === 'number' ? `${Math.round(v * 100)}%` : String(v)}
                    </div>
                  </div>
                ))}
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
