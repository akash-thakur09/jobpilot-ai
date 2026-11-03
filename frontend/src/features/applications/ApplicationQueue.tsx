import React, { useEffect, useState } from 'react';
import { Application, Job } from '../../types';
import { api } from '../../lib/api-client';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { LoadingSkeleton } from '../../components/ui/LoadingSkeleton';
import { EmptyState } from '../../components/ui/EmptyState';
import { ApplicationReviewModal } from './ApplicationReviewModal';
import { OutcomeReconciliationModal } from './OutcomeReconciliationModal';
import { ApplicationHistoryDrawer } from './ApplicationHistoryDrawer';
import { formatApplicationStatusBadge } from '../../lib/formatters';
import {
  FileText,
  Building2,
  Play,
  ShieldCheck,
  AlertTriangle,
  HelpCircle,
  History,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';

export const ApplicationQueue: React.FC = () => {
  const [applications, setApplications] = useState<Application[]>([]);
  const [jobsMap, setJobsMap] = useState<Record<string, Job>>({});
  const [activeTab, setActiveTab] = useState<string>('ALL');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals & Active selections
  const [selectedAppForReview, setSelectedAppForReview] = useState<string | null>(null);
  const [selectedAppForReconciliation, setSelectedAppForReconciliation] = useState<string | null>(null);
  const [selectedAppForHistory, setSelectedAppForHistory] = useState<Application | null>(null);

  // Synthetic execution runner state
  const [attemptingAppId, setAttemptingAppId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [appsData, jobsData] = await Promise.all([
        api.applications.list({ limit: 100 }),
        api.jobs.list({ limit: 100 }).catch(() => ({ items: [], total: 0 })),
      ]);

      setApplications(appsData.items || []);

      const jMap: Record<string, Job> = {};
      (jobsData.items || []).forEach((j: Job) => {
        jMap[j.id] = j;
      });
      setJobsMap(jMap);
    } catch (err: any) {
      setError(err?.message || 'Failed to load applications');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleExecuteSyntheticAttempt = async (appId: string) => {
    setAttemptingAppId(appId);
    setActionNotice(null);
    try {
      const result = await api.applications.attempt(appId);
      const isSim = result.outcome === 'SUBMITTED_SIMULATION' || (result.reconciliation_metadata as any)?.simulation;
      setActionNotice(
        `${isSim ? 'Synthetic Simulation Completed' : 'Synthetic Run Completed'}: Status ${result.outcome}${
          result.confirmation_reference ? ` (Confirmation: ${result.confirmation_reference})` : ''
        }${isSim ? '. No external job board was contacted.' : ''}`
      );
      fetchData();
    } catch (err: any) {
      setActionNotice(`Submission Attempt Failed: ${err?.message || 'Error occurred'}`);
      fetchData();
    } finally {
      setAttemptingAppId(null);
    }
  };

  // Filter applications by tab
  const isSubmittedStatus = (status: string) =>
    status === 'SUBMITTED' ||
    status === 'SUBMITTED_SIMULATION' ||
    status === 'REAL_SUBMITTED' ||
    status === 'SYNTHETICALLY_SUBMITTED';

  const filteredApps = applications.filter((app) => {
    if (activeTab === 'ALL') return true;
    if (activeTab === 'REVIEW') return app.status === 'READY_FOR_REVIEW';
    if (activeTab === 'APPROVED') return app.status === 'APPROVED';
    if (activeTab === 'SUBMITTED') return isSubmittedStatus(app.status);
    if (activeTab === 'ACTION_REQUIRED') {
      return (
        app.status === 'OUTCOME_UNKNOWN' ||
        app.status === 'NEEDS_HUMAN_ACTION' ||
        (app.status as string) === 'FAILED_SUBMISSION'
      );
    }
    return true;
  });

  const reviewCount = applications.filter((a) => a.status === 'READY_FOR_REVIEW').length;
  const approvedCount = applications.filter((a) => a.status === 'APPROVED').length;
  const submittedCount = applications.filter((a) => isSubmittedStatus(a.status)).length;
  const actionCount = applications.filter((a) =>
    ['OUTCOME_UNKNOWN', 'NEEDS_HUMAN_ACTION', 'FAILED_SUBMISSION', 'FAILED'].includes(a.status)
  ).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Application Queue & Tracking</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Strict lifecycle state machine, human approval fingerprints, and synthetic browser execution.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchData}
            icon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {actionNotice && (
        <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-700/80 flex items-center justify-between text-xs text-slate-200">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
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

      {/* Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 pb-3">
        <button
          onClick={() => setActiveTab('ALL')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            activeTab === 'ALL'
              ? 'bg-blue-600/20 text-blue-400 border border-blue-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          All Applications ({applications.length})
        </button>

        <button
          onClick={() => setActiveTab('REVIEW')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
            activeTab === 'REVIEW'
              ? 'bg-amber-600/20 text-amber-300 border border-amber-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>Review Queue</span>
          {reviewCount > 0 && (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-amber-500/30 text-amber-300">
              {reviewCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('APPROVED')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
            activeTab === 'APPROVED'
              ? 'bg-blue-600/20 text-blue-400 border border-blue-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>Approved (Ready to Run)</span>
          {approvedCount > 0 && (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-blue-500/30 text-blue-300">
              {approvedCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('SUBMITTED')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
            activeTab === 'SUBMITTED'
              ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>Submitted</span>
          {submittedCount > 0 && (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-emerald-500/30 text-emerald-300">
              {submittedCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('ACTION_REQUIRED')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
            activeTab === 'ACTION_REQUIRED'
              ? 'bg-red-600/20 text-red-400 border border-red-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>Action Required / Unknown</span>
          {actionCount > 0 && (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-red-500/30 text-red-300">
              {actionCount}
            </span>
          )}
        </button>
      </div>

      {/* Main List */}
      {isLoading ? (
        <LoadingSkeleton count={4} />
      ) : error ? (
        <Card className="p-8 text-center text-red-400">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-red-400" />
          <div className="font-semibold text-sm">Failed to Load Applications</div>
          <div className="text-xs text-slate-400 mt-1">{error}</div>
          <Button variant="outline" size="sm" onClick={fetchData} className="mt-4">
            Retry
          </Button>
        </Card>
      ) : filteredApps.length === 0 ? (
        <EmptyState
          title="No Applications in this View"
          description={
            applications.length === 0
              ? 'No applications have been prepared yet. Go to the Jobs tab to discover opportunities and prepare your first application.'
              : 'There are no applications matching the selected status filter.'
          }
          icon={<FileText className="w-6 h-6 text-slate-400" />}
        />
      ) : (
        <div className="space-y-3">
          {filteredApps.map((app) => {
            const job = jobsMap[app.job_id];
            const statusConfig = formatApplicationStatusBadge(app.status);
            const isAttempting = attemptingAppId === app.id;

            return (
              <Card
                key={app.id}
                className={`p-4 space-y-3 transition-all ${
                  app.status === 'OUTCOME_UNKNOWN'
                    ? 'border-l-4 border-l-amber-500'
                    : app.status === 'READY_FOR_REVIEW'
                    ? 'border-l-4 border-l-blue-500'
                    : app.status === 'APPROVED'
                    ? 'border-l-4 border-l-purple-500'
                    : app.status === 'SUBMITTED_SIMULATION' || (app.status as string) === 'SYNTHETICALLY_SUBMITTED'
                    ? 'border-l-4 border-l-purple-500'
                    : app.status === 'SUBMITTED'
                    ? 'border-l-4 border-l-emerald-500'
                    : 'border-l-4 border-l-slate-700'
                }`}
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
                  {/* Left Column */}
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-bold text-slate-100">
                        {app.job_title || job?.title || 'Target Opportunity'}
                      </h3>
                      <Badge variant={statusConfig.variant} size="sm">
                        {statusConfig.label}
                      </Badge>
                      {app.status === 'OUTCOME_UNKNOWN' && (
                        <span className="text-[10px] font-semibold text-amber-400 bg-amber-950/40 border border-amber-900/60 px-1.5 py-0.5 rounded">
                          Action Required: Verify Outcome
                        </span>
                      )}
                      {(app.status === 'SUBMITTED_SIMULATION' || (app.status as string) === 'SYNTHETICALLY_SUBMITTED') && (
                        <span className="text-[10px] font-semibold text-purple-300 bg-purple-950/60 border border-purple-800/60 px-2 py-0.5 rounded flex items-center gap-1">
                          Simulation Mode &bull; No External Calls
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
                      <span className="flex items-center gap-1 font-medium text-slate-300">
                        <Building2 className="w-3.5 h-3.5 text-blue-400" />
                        {app.company || job?.company || 'Employer'}
                      </span>
                      <span>&bull;</span>
                      <span>Created: {new Date(app.created_at).toLocaleDateString()}</span>
                      {app.resume_version_id && (
                        <>
                          <span>&bull;</span>
                          <span className="font-mono text-slate-400 text-[11px]">
                            Resume Ref: {app.resume_version_id.slice(0, 8)}...
                          </span>
                        </>
                      )}
                    </div>

                    {app.notes && (
                      <div className="text-xs text-slate-400 bg-slate-900/60 px-2.5 py-1 rounded border border-slate-800">
                        <span className="text-slate-500">Note: </span>
                        {app.notes}
                      </div>
                    )}

                    {(app.status === 'SUBMITTED_SIMULATION' || (app.status as string) === 'SYNTHETICALLY_SUBMITTED') && (
                      <div className="text-xs text-purple-300 bg-purple-950/40 px-2.5 py-1.5 rounded border border-purple-800/50 flex flex-wrap items-center gap-2">
                        <span className="font-semibold">Local Simulation:</span>
                        {app.confirmation_evidence?.confirmation_reference && (
                          <span className="font-mono text-purple-200">
                            Ref: {app.confirmation_evidence.confirmation_reference}
                          </span>
                        )}
                        <span className="text-purple-400/80 text-[11px]">
                          — Verified local mock execution, no external job board contacted.
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Right Column: Contextual Action Buttons */}
                  <div className="flex flex-wrap items-center gap-2 self-end lg:self-center">
                    {/* Ready for Review -> Review & Approve */}
                    {app.status === 'READY_FOR_REVIEW' && (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => setSelectedAppForReview(app.id)}
                        icon={<ShieldCheck className="w-3.5 h-3.5" />}
                      >
                        Review & Approve
                      </Button>
                    )}

                    {/* Approved -> Execute Synthetic Run */}
                    {app.status === 'APPROVED' && (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleExecuteSyntheticAttempt(app.id)}
                        isLoading={isAttempting}
                        icon={<Play className="w-3.5 h-3.5" />}
                      >
                        Execute Synthetic Run
                      </Button>
                    )}

                    {/* Outcome Unknown -> Guarded Reconciliation */}
                    {app.status === 'OUTCOME_UNKNOWN' && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setSelectedAppForReconciliation(app.id)}
                        icon={<HelpCircle className="w-3.5 h-3.5 text-amber-400" />}
                      >
                        Reconcile Outcome
                      </Button>
                    )}

                    {/* History / Audit Drawer */}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedAppForHistory(app)}
                      icon={<History className="w-3.5 h-3.5" />}
                    >
                      Audit History
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Review Modal */}
      <ApplicationReviewModal
        applicationId={selectedAppForReview}
        isOpen={!!selectedAppForReview}
        onClose={() => setSelectedAppForReview(null)}
        onApprovalSuccess={() => {
          setSelectedAppForReview(null);
          setActionNotice('Application approved with cryptographic fingerprint! Ready for runner.');
          fetchData();
        }}
      />

      {/* Outcome Reconciliation Modal */}
      <OutcomeReconciliationModal
        applicationId={selectedAppForReconciliation}
        isOpen={!!selectedAppForReconciliation}
        onClose={() => setSelectedAppForReconciliation(null)}
        onReconciliationComplete={() => {
          setSelectedAppForReconciliation(null);
          setActionNotice('Application outcome reconciled and audited successfully.');
          fetchData();
        }}
      />

      {/* Audit History Drawer */}
      <ApplicationHistoryDrawer
        application={selectedAppForHistory}
        isOpen={!!selectedAppForHistory}
        onClose={() => setSelectedAppForHistory(null)}
      />
    </div>
  );
};
