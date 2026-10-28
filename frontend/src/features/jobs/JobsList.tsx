import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Job, MatchScore } from '../../types';
import { api } from '../../lib/api-client';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { LoadingSkeleton } from '../../components/ui/LoadingSkeleton';
import { EmptyState } from '../../components/ui/EmptyState';
import { JobDetailModal } from './JobDetailModal';
import { JobDiscoveryModal } from './JobDiscoveryModal';
import { DuplicateClustersModal } from './DuplicateClustersModal';
import { RankingEvaluationModal } from './RankingEvaluationModal';
import { 
  formatSalary, 
  formatEligibilityBadge, 
  formatScoreBadge 
} from '../../lib/formatters';
import {
  Search,
  Building2,
  MapPin,
  Briefcase,
  DollarSign,
  ChevronRight,
  Compass,
  AlertCircle,
  ShieldCheck,
  RefreshCw,
  Sparkles,
  Layers,
  Activity,
} from 'lucide-react';

export const JobsList: React.FC = () => {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [matchResults, setMatchResults] = useState<Record<string, MatchScore>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [remoteFilter, setRemoteFilter] = useState<string>('ALL');
  const [eligibilityFilter, setEligibilityFilter] = useState<string>('ALL');
  const [sourceFilter, setSourceFilter] = useState<string>('ALL');

  // Modals & Active Selections
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [isDiscoveryOpen, setIsDiscoveryOpen] = useState(false);
  const [isDuplicatesOpen, setIsDuplicatesOpen] = useState(false);
  const [isEvaluationOpen, setIsEvaluationOpen] = useState(false);
  const [evaluatingJobId, setEvaluatingJobId] = useState<string | null>(null);
  const [preparingJobId, setPreparingJobId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [jobsData, matchesData] = await Promise.all([
        api.jobs.list({ limit: 100 }),
        api.matching.listResults({ limit: 100 }).catch(() => []),
      ]);

      setJobs(jobsData.items || []);

      const matchesMap: Record<string, MatchScore> = {};
      (matchesData || []).forEach((m) => {
        matchesMap[m.job_id] = m;
      });
      setMatchResults(matchesMap);
    } catch (err: any) {
      setError(err?.message || 'Failed to load jobs');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Filtered & sorted jobs
  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      // Query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = job.title.toLowerCase().includes(q);
        const matchesCompany = job.company.toLowerCase().includes(q);
        const matchesLocation = job.location?.toLowerCase().includes(q);
        const matchesDesc = job.description?.toLowerCase().includes(q);
        if (!matchesTitle && !matchesCompany && !matchesLocation && !matchesDesc) {
          return false;
        }
      }

      // Remote filter
      if (remoteFilter !== 'ALL' && job.remote_type !== remoteFilter) {
        return false;
      }

      // Source filter
      if (sourceFilter !== 'ALL') {
        const src = job.source_name || job.source_id;
        if (!src.toLowerCase().includes(sourceFilter.toLowerCase())) {
          return false;
        }
      }

      // Eligibility filter
      if (eligibilityFilter !== 'ALL') {
        const match = matchResults[job.id];
        if (eligibilityFilter === 'UNASSESSED' && match) return false;
        if (eligibilityFilter !== 'UNASSESSED' && match?.eligibility_status !== eligibilityFilter) {
          return false;
        }
      }

      return true;
    });
  }, [jobs, matchResults, searchQuery, remoteFilter, eligibilityFilter, sourceFilter]);

  const handleEvaluate = async (e: React.MouseEvent, jobId: string) => {
    e.stopPropagation();
    setEvaluatingJobId(jobId);
    setActionNotice(null);
    try {
      const result = await api.matching.evaluate(jobId);
      setMatchResults((prev) => ({
        ...prev,
        [jobId]: result,
      }));
      setActionNotice(
        `Evaluated "${result.eligibility_status}" (Score: ${Math.round(result.overall_score * 100)}%)`
      );
    } catch (err: any) {
      setActionNotice(`Evaluation failed: ${err?.message || 'Unknown error'}`);
    } finally {
      setEvaluatingJobId(null);
    }
  };

  const handlePrepareApplication = async (jobId: string) => {
    setPreparingJobId(jobId);
    setActionNotice(null);
    try {
      await api.applications.prepare({ job_id: jobId });
      setActionNotice('Application successfully prepared! Redirecting to review queue...');
      setTimeout(() => {
        navigate('/applications');
      }, 700);
    } catch (err: any) {
      setActionNotice(
        `Failed to prepare application: ${err?.message || 'Check eligibility or profile status'}`
      );
    } finally {
      setPreparingJobId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Discovery Trigger */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Job Discovery & Evaluation</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real jobs stored locally, evaluated against your verified profile constraints.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchData}
            icon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsDuplicatesOpen(true)}
            icon={<Layers className="w-3.5 h-3.5 text-purple-400" />}
          >
            Duplicates
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsEvaluationOpen(true)}
            icon={<Activity className="w-3.5 h-3.5 text-blue-400" />}
          >
            Ranking Eval
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsDiscoveryOpen(true)}
            icon={<Compass className="w-4 h-4" />}
          >
            Discover Jobs
          </Button>
        </div>
      </div>

      {actionNotice && (
        <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-700/80 flex items-center justify-between text-xs text-slate-200">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-blue-400" />
            <span>{actionNotice}</span>
          </div>
          <button
            onClick={() => setActionNotice(null)}
            className="text-slate-400 hover:text-slate-200"
          >
            &times;
          </button>
        </div>
      )}

      {/* Search & Filter Controls */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {/* Search Input */}
          <div className="md:col-span-1 relative">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search title, company, keyword..."
              className="w-full pl-9 pr-3 py-2 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Remote Filter */}
          <div>
            <select
              value={remoteFilter}
              onChange={(e) => setRemoteFilter(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-200 focus:border-blue-500 focus:outline-none"
            >
              <option value="ALL">All Work Types</option>
              <option value="REMOTE">Fully Remote</option>
              <option value="HYBRID">Hybrid</option>
              <option value="ONSITE">On-Site</option>
            </select>
          </div>

          {/* Eligibility Filter */}
          <div>
            <select
              value={eligibilityFilter}
              onChange={(e) => setEligibilityFilter(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-200 focus:border-blue-500 focus:outline-none"
            >
              <option value="ALL">All Eligibility Statuses</option>
              <option value="ELIGIBLE">Eligible Only</option>
              <option value="NEEDS_REVIEW">Needs Review</option>
              <option value="DISQUALIFIED">Disqualified</option>
              <option value="UNASSESSED">Not Assessed</option>
            </select>
          </div>

          {/* Source Filter */}
          <div>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-200 focus:border-blue-500 focus:outline-none"
            >
              <option value="ALL">All Sources</option>
              <option value="synthetic">Synthetic Portal (Local)</option>
              <option value="remoteok">RemoteOK</option>
              <option value="arbeitnow">Arbeitnow</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Main List */}
      {isLoading ? (
        <LoadingSkeleton count={5} />
      ) : error ? (
        <Card className="p-8 text-center text-red-400">
          <AlertCircle className="w-8 h-8 mx-auto mb-2 text-red-400" />
          <div className="font-semibold text-sm">Error Loading Jobs</div>
          <div className="text-xs text-slate-400 mt-1">{error}</div>
          <Button variant="outline" size="sm" onClick={fetchData} className="mt-4">
            Retry
          </Button>
        </Card>
      ) : filteredJobs.length === 0 ? (
        <EmptyState
          title="No Jobs Found"
          description={
            jobs.length === 0
              ? 'No jobs are currently in the local database. Run discovery to ingest jobs from verified adapters.'
              : 'No jobs match your current search and filter criteria.'
          }
          icon={<Briefcase className="w-6 h-6 text-slate-400" />}
          action={
            jobs.length === 0 ? (
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsDiscoveryOpen(true)}
                icon={<Compass className="w-4 h-4" />}
              >
                Discover Jobs Now
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSearchQuery('');
                  setRemoteFilter('ALL');
                  setEligibilityFilter('ALL');
                  setSourceFilter('ALL');
                }}
              >
                Clear Filters
              </Button>
            )
          }
        />
      ) : (
        <div className="space-y-3">
          <div className="text-xs text-slate-400 flex items-center justify-between px-1">
            <span>Showing {filteredJobs.length} of {jobs.length} jobs</span>
            <span className="text-[11px] text-slate-500">Click a job to view complete requirements & match breakdown</span>
          </div>

          {filteredJobs.map((job) => {
            const match = matchResults[job.id];
            const eligConfig = match?.eligibility_status
              ? formatEligibilityBadge(match.eligibility_status)
              : null;
            const scoreConfig = match?.overall_score != null
              ? formatScoreBadge(match.overall_score)
              : null;
            const isEvaluating = evaluatingJobId === job.id;
            const isPreparing = preparingJobId === job.id;
            const salary = formatSalary(job.salary_min, job.salary_max, job.salary_currency);

            return (
              <Card
                key={job.id}
                hoverable
                onClick={() => {
                  setSelectedJob(job);
                  setIsDetailOpen(true);
                }}
                className={`p-4 transition-all ${
                  match?.eligibility_status === 'DISQUALIFIED'
                    ? 'border-l-4 border-l-red-500/70'
                    : match?.eligibility_status === 'ELIGIBLE'
                    ? 'border-l-4 border-l-emerald-500/70'
                    : match?.eligibility_status === 'NEEDS_REVIEW'
                    ? 'border-l-4 border-l-amber-500/70'
                    : 'border-l-4 border-l-slate-700'
                }`}
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                  {/* Left Column: Job Meta */}
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-semibold text-slate-100 hover:text-blue-400 transition-colors truncate">
                        {job.title}
                      </h3>
                      {eligConfig && (
                        <Badge variant={eligConfig.variant} size="sm">
                          {eligConfig.label}
                        </Badge>
                      )}
                      {scoreConfig && (
                        <Badge variant={scoreConfig.variant} size="sm">
                          {scoreConfig.label} Match
                        </Badge>
                      )}
                      {job.freshness_status === 'POTENTIALLY_STALE' && (
                        <Badge variant="warning" size="sm">
                          Stale
                        </Badge>
                      )}
                      {job.freshness_status === 'CONFIRMED_CLOSED' && (
                        <Badge variant="danger" size="sm">
                          Closed
                        </Badge>
                      )}
                      {job.duplicate_cluster_id && (
                        <Badge variant="purple" size="sm">
                          Duplicate
                        </Badge>
                      )}
                      <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                        {job.source_name || job.source_id}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
                      <span className="flex items-center gap-1 font-medium text-slate-300">
                        <Building2 className="w-3.5 h-3.5 text-blue-400" />
                        {job.company}
                      </span>
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 text-slate-500" />
                        {job.location || 'Remote'}
                      </span>
                      <span className="flex items-center gap-1">
                        <Briefcase className="w-3.5 h-3.5 text-slate-500" />
                        {job.remote_type ? job.remote_type.replace('_', ' ') : 'Remote'}
                      </span>
                      {salary && (
                        <span className="flex items-center gap-1 text-emerald-400 font-medium">
                          <DollarSign className="w-3.5 h-3.5" />
                          {salary}
                        </span>
                      )}
                    </div>

                    {/* Explanatory note or disqualification banner */}
                    {match?.eligibility_status === 'DISQUALIFIED' && match.explanation && (
                      <div className="text-xs text-red-300/90 bg-red-950/20 px-2.5 py-1 rounded border border-red-900/40">
                        <span className="font-semibold text-red-200">Disqualified: </span>
                        {match.explanation}
                      </div>
                    )}
                  </div>

                  {/* Right Column: Actions */}
                  <div
                    className="flex items-center gap-2 self-end lg:self-center shrink-0"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {!match && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={(e) => handleEvaluate(e, job.id)}
                        isLoading={isEvaluating}
                        icon={<Sparkles className="w-3.5 h-3.5 text-blue-400" />}
                      >
                        Evaluate Match
                      </Button>
                    )}

                    {match && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => handleEvaluate(e, job.id)}
                        isLoading={isEvaluating}
                        icon={<RefreshCw className="w-3 h-3 text-slate-400" />}
                        title="Re-run matching analysis"
                      >
                        Re-evaluate
                      </Button>
                    )}

                    <Button
                      variant={match?.eligibility_status === 'DISQUALIFIED' ? 'outline' : 'primary'}
                      size="sm"
                      onClick={() => handlePrepareApplication(job.id)}
                      isLoading={isPreparing}
                      disabled={match?.eligibility_status === 'DISQUALIFIED'}
                      icon={<ShieldCheck className="w-3.5 h-3.5" />}
                    >
                      {match?.eligibility_status === 'DISQUALIFIED' ? 'Ineligible' : 'Prepare App'}
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setSelectedJob(job);
                        setIsDetailOpen(true);
                      }}
                      icon={<ChevronRight className="w-4 h-4 text-slate-400" />}
                    />
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Job Details Modal */}
      <JobDetailModal
        job={selectedJob}
        matchResult={selectedJob ? matchResults[selectedJob.id] : null}
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
        onPrepareApplication={handlePrepareApplication}
        isPreparing={preparingJobId === selectedJob?.id}
        onFeedbackChanged={fetchData}
      />

      {/* Discovery Modal */}
      <JobDiscoveryModal
        isOpen={isDiscoveryOpen}
        onClose={() => setIsDiscoveryOpen(false)}
        onDiscoveryComplete={() => {
          fetchData();
        }}
      />

      {/* Duplicate Clusters Review Modal */}
      <DuplicateClustersModal
        isOpen={isDuplicatesOpen}
        onClose={() => setIsDuplicatesOpen(false)}
        onRefreshJobs={fetchData}
      />

      {/* Offline Ranking Evaluation Modal */}
      <RankingEvaluationModal
        isOpen={isEvaluationOpen}
        onClose={() => setIsEvaluationOpen(false)}
      />
    </div>
  );
};
