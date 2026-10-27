import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Briefcase,
  CheckCircle2,
  Clock,
  AlertCircle,
  HelpCircle,
  Send,
  ArrowRight,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { api, ApiError } from '../../lib/api-client';
import { Application } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { LoadingSkeleton } from '../../components/ui/LoadingSkeleton';
import { formatDate, getApplicationStatusBadge } from '../../lib/formatters';

interface DashboardMetrics {
  discoveredJobs: number;
  eligibleJobs: number;
  readyForReview: number;
  approved: number;
  outcomeUnknown: number;
  submitted: number;
}

export const DashboardOverview: React.FC = () => {
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [recentApplications, setRecentApplications] = useState<Application[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Parallel fetch from verified endpoints
      const [
        jobsRes,
        matchingRes,
        readyApps,
        approvedApps,
        unknownApps,
        submittedApps,
        recentApps,
      ] = await Promise.all([
        api.jobs.list({ limit: 1 }),
        api.matching.listResults({ is_eligible: true, limit: 100 }),
        api.applications.list({ status: 'READY_FOR_REVIEW', limit: 1 }),
        api.applications.list({ status: 'APPROVED', limit: 1 }),
        api.applications.list({ status: 'OUTCOME_UNKNOWN', limit: 1 }),
        api.applications.list({ status: 'SUBMITTED', limit: 1 }),
        api.applications.list({ limit: 5 }),
      ]);

      setMetrics({
        discoveredJobs: jobsRes.total,
        eligibleJobs: matchingRes.length,
        readyForReview: readyApps.total,
        approved: approvedApps.total,
        outcomeUnknown: unknownApps.total,
        submitted: submittedApps.total,
      });

      setRecentApplications(recentApps.items);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Failed to load dashboard metrics. Ensure backend is running.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton count={4} className="h-28" />
        <LoadingSkeleton count={3} className="h-16" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-6 text-center">
        <AlertCircle className="w-8 h-8 text-rose-400 mx-auto mb-3" />
        <h3 className="text-base font-semibold text-rose-300">Connection Error</h3>
        <p className="text-sm text-rose-200/80 mt-1 mb-4">{error}</p>
        <Button onClick={fetchDashboardData} variant="secondary" size="sm">
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-900/40 via-slate-900 to-slate-900 border border-indigo-500/20 p-6 md:p-8">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 mb-3">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>Autonomous Local Assistant</span>
          </div>
          <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
            Job Search Command Center
          </h2>
          <p className="mt-2 text-sm md:text-base text-slate-300 leading-relaxed">
            Discover tailored opportunities, evaluate hard eligibility constraints, review tailored
            ATS resumes, and safely simulate local submissions.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button
              onClick={() => navigate('/jobs')}
              leftIcon={<Briefcase className="w-4 h-4" />}
            >
              Explore Discovered Jobs
            </Button>
            <Button
              onClick={() => navigate('/applications')}
              variant="secondary"
              leftIcon={<CheckCircle2 className="w-4 h-4" />}
            >
              Review Application Queue ({metrics?.readyForReview || 0})
            </Button>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Card className="flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">Discovered Jobs</span>
            <Briefcase className="w-4 h-4 text-indigo-400" />
          </div>
          <span className="text-2xl font-bold text-slate-100">{metrics?.discoveredJobs}</span>
          <span className="text-[11px] text-slate-400 mt-1">From connected boards</span>
        </Card>

        <Card className="flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">Eligible Jobs</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <span className="text-2xl font-bold text-emerald-400">{metrics?.eligibleJobs}</span>
          <span className="text-[11px] text-slate-400 mt-1">Passed hard constraints</span>
        </Card>

        <Card className="flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">Ready for Review</span>
            <Clock className="w-4 h-4 text-indigo-400" />
          </div>
          <span className="text-2xl font-bold text-indigo-400">{metrics?.readyForReview}</span>
          <span className="text-[11px] text-slate-400 mt-1">Awaiting your approval</span>
        </Card>

        <Card className="flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">Approved</span>
            <CheckCircle2 className="w-4 h-4 text-blue-400" />
          </div>
          <span className="text-2xl font-bold text-blue-400">{metrics?.approved}</span>
          <span className="text-[11px] text-slate-400 mt-1">Ready for runner</span>
        </Card>

        <Card className="flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">Submitted (Synth)</span>
            <Send className="w-4 h-4 text-emerald-400" />
          </div>
          <span className="text-2xl font-bold text-emerald-400">{metrics?.submitted}</span>
          <span className="text-[11px] text-slate-400 mt-1">Verified with receipts</span>
        </Card>

        <Card className="flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium">Outcome Unknown</span>
            <HelpCircle className="w-4 h-4 text-purple-400" />
          </div>
          <span className="text-2xl font-bold text-purple-400">{metrics?.outcomeUnknown}</span>
          <span className="text-[11px] text-slate-400 mt-1">Needs reconciliation</span>
        </Card>
      </div>

      {/* Recent Activity Table */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <span>Recent Application Activity</span>
            <button
              onClick={fetchDashboardData}
              className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800 transition"
              title="Refresh Activity"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/applications')}
            rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
          >
            View all applications
          </Button>
        </div>

        {recentApplications.length === 0 ? (
          <Card className="p-8 text-center text-slate-400 text-sm">
            No applications prepared yet. Discover jobs and prepare an application to get started.
          </Card>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/40">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-900 text-slate-400 text-xs uppercase border-b border-slate-800">
                <tr>
                  <th className="px-6 py-3 font-medium">Position</th>
                  <th className="px-6 py-3 font-medium">Employer</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                  <th className="px-6 py-3 font-medium">Updated</th>
                  <th className="px-6 py-3 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {recentApplications.map((app) => {
                  const badge = getApplicationStatusBadge(app.status);
                  return (
                    <tr
                      key={app.id}
                      className="hover:bg-slate-850/50 transition cursor-pointer"
                      onClick={() => navigate('/applications')}
                    >
                      <td className="px-6 py-4 font-medium text-slate-200">
                        {app.job_title || 'Software Engineer'}
                      </td>
                      <td className="px-6 py-4 text-slate-400">{app.company || 'Employer'}</td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ${badge.className}`}
                        >
                          {badge.label}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-slate-400 text-xs">
                        {formatDate(app.updated_at)}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="text-indigo-400 hover:text-indigo-300 text-xs font-medium inline-flex items-center gap-1">
                          View details <ArrowRight className="w-3 h-3" />
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
