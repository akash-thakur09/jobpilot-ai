import React, { useEffect, useState } from 'react';
import { ResumeVersion, Job, Application, ResumeIntegrityCheck } from '../../types';
import { api } from '../../lib/api-client';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { LoadingSkeleton } from '../../components/ui/LoadingSkeleton';
import { EmptyState } from '../../components/ui/EmptyState';
import {
  FileText,
  Download,
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Copy,
  Check,
  Building2,
  Sparkles,
  Lock,
} from 'lucide-react';

export const ResumeWorkspace: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [resumeVersions, setResumeVersions] = useState<ResumeVersion[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string>('ALL');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Integrity checks map: versionId -> ResumeIntegrityCheck
  const [integrityResults, setIntegrityResults] = useState<Record<string, ResumeIntegrityCheck>>({});
  const [verifyingVersionId, setVerifyingVersionId] = useState<string | null>(null);
  const [copiedSha, setCopiedSha] = useState<string | null>(null);
  const [generatingForJobId, setGeneratingForJobId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [jobsData, appsData] = await Promise.all([
        api.jobs.list({ limit: 100 }),
        api.applications.list({ limit: 100 }),
      ]);

      const jobsList = jobsData.items || [];
      const appsList = appsData.items || [];

      setJobs(jobsList);

      const versionMap: Record<string, ResumeVersion> = {};

      // 1. Fetch from applications
      const appVersionPromises = appsList
        .filter((app: Application) => !!app.resume_version_id)
        .map((app: Application) =>
          api.resumes.get(app.resume_version_id as string).catch(() => null)
        );

      // 2. Fetch for first 15 jobs to discover standalone generated resumes
      const jobResumesPromises = jobsList
        .slice(0, 15)
        .map((j: Job) => api.resumes.listForJob(j.id).catch(() => []));

      const [appVersions, jobVersionsLists] = await Promise.all([
        Promise.all(appVersionPromises),
        Promise.all(jobResumesPromises),
      ]);

      appVersions.forEach((v: ResumeVersion | null) => {
        if (v) versionMap[v.id] = v;
      });

      jobVersionsLists.forEach((list: ResumeVersion[]) => {
        (list || []).forEach((v: ResumeVersion) => {
          versionMap[v.id] = v;
        });
      });

      const versionsArray = Object.values(versionMap).sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );

      setResumeVersions(versionsArray);
    } catch (err: any) {
      setError(err?.message || 'Failed to load resume workspace');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleVerifyIntegrity = async (versionId: string) => {
    setVerifyingVersionId(versionId);
    setNotice(null);
    try {
      const check = await api.resumes.verifyIntegrity(versionId);
      setIntegrityResults((prev) => ({
        ...prev,
        [versionId]: check,
      }));
      if (check.is_intact) {
        setNotice('Integrity verified! PDF file is bit-for-bit intact and matches SHA-256 hash.');
      } else {
        setNotice('CRITICAL INTEGRITY FAILURE: File on disk has been altered or checksum mismatch!');
      }
    } catch (err: any) {
      setNotice(`Integrity verification failed: ${err?.message || 'Error reading artifact'}`);
    } finally {
      setVerifyingVersionId(null);
    }
  };

  const handleCopySha = (sha: string) => {
    navigator.clipboard.writeText(sha);
    setCopiedSha(sha);
    setTimeout(() => setCopiedSha(null), 2000);
  };

  const handleGenerateForJob = async (jobId: string) => {
    setGeneratingForJobId(jobId);
    setNotice(null);
    try {
      const newVersion = await api.resumes.generate(jobId, true);
      setResumeVersions((prev) => [newVersion, ...prev.filter((v) => v.id !== newVersion.id)]);
      setNotice(`Successfully tailored Resume v${newVersion.version_number} with verified facts!`);
    } catch (err: any) {
      setNotice(`Generation failed: ${err?.message || 'Ensure candidate profile exists.'}`);
    } finally {
      setGeneratingForJobId(null);
    }
  };

  // Filter versions by selected job
  const filteredVersions = resumeVersions.filter((v) => {
    if (selectedJobId === 'ALL') return true;
    return v.job_id === selectedJobId;
  });

  const jobsMap: Record<string, Job> = {};
  jobs.forEach((j) => {
    jobsMap[j.id] = j;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Tailored Resume Workspace</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Immutable, checksum-verified PDF resume artifacts tailored specifically per opportunity.
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

      {notice && (
        <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-700/80 flex items-center justify-between text-xs text-slate-200">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-blue-400" />
            <span>{notice}</span>
          </div>
          <button onClick={() => setNotice(null)} className="text-slate-400 hover:text-slate-200">
            &times;
          </button>
        </div>
      )}

      {/* Filter by Job Bar */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-slate-300">Filter by Opportunity:</span>
            <select
              value={selectedJobId}
              onChange={(e) => setSelectedJobId(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:border-blue-500 focus:outline-none"
            >
              <option value="ALL">All Jobs ({resumeVersions.length} versions)</option>
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.company} - {j.title}
                </option>
              ))}
            </select>
          </div>

          {selectedJobId !== 'ALL' && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleGenerateForJob(selectedJobId)}
              isLoading={generatingForJobId === selectedJobId}
              icon={<Sparkles className="w-3.5 h-3.5 text-blue-400" />}
            >
              Force Generate New Version
            </Button>
          )}
        </div>
      </Card>

      {/* Content */}
      {isLoading ? (
        <LoadingSkeleton count={4} />
      ) : error ? (
        <Card className="p-8 text-center text-red-400">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-red-400" />
          <div className="font-semibold text-sm">Failed to Load Resumes</div>
          <div className="text-xs text-slate-400 mt-1">{error}</div>
          <Button variant="outline" size="sm" onClick={fetchData} className="mt-4">
            Retry
          </Button>
        </Card>
      ) : filteredVersions.length === 0 ? (
        <EmptyState
          title="No Resume Versions Found"
          description={
            selectedJobId !== 'ALL'
              ? 'No tailored resume version has been generated for this specific opportunity yet.'
              : 'No tailored resumes have been generated yet. You can prepare an application or tailor a resume from the Jobs tab.'
          }
          icon={<FileText className="w-6 h-6 text-slate-400" />}
          action={
            selectedJobId !== 'ALL' ? (
              <Button
                variant="primary"
                size="sm"
                onClick={() => handleGenerateForJob(selectedJobId)}
                isLoading={generatingForJobId === selectedJobId}
                icon={<Sparkles className="w-4 h-4" />}
              >
                Generate Tailored Resume
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-4">
          {filteredVersions.map((version) => {
            const job = jobsMap[version.job_id];
            const integrity = integrityResults[version.id];
            const isVerifying = verifyingVersionId === version.id;
            const factResult = version.factual_validation_result;
            const coverageResult = version.keyword_coverage_result;

            const matchedKeywords = [
              ...(coverageResult?.matched_required || []),
              ...(coverageResult?.matched_preferred || []),
            ];
            const missingKeywords = [
              ...(coverageResult?.missing_required || []),
              ...(coverageResult?.missing_preferred || []),
            ];

            return (
              <Card key={version.id} className="p-5 space-y-4">
                {/* Header Row */}
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pb-3 border-b border-slate-800">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-bold text-slate-100">
                        Resume Version {version.version_number}
                      </span>
                      {version.is_submission_ready ? (
                        <Badge variant="success" size="sm" icon={<CheckCircle2 className="w-3 h-3" />}>
                          ATS Submission Ready
                        </Badge>
                      ) : (
                        <Badge variant="warning" size="sm" icon={<AlertTriangle className="w-3 h-3" />}>
                          Needs Revision
                        </Badge>
                      )}
                      {integrity && (
                        <Badge
                          variant={integrity.is_intact ? 'success' : 'danger'}
                          size="sm"
                          icon={
                            integrity.is_intact ? (
                              <ShieldCheck className="w-3 h-3" />
                            ) : (
                              <ShieldAlert className="w-3 h-3" />
                            )
                          }
                        >
                          {integrity.is_intact ? 'Checksum Verified' : 'INTEGRITY MISMATCH'}
                        </Badge>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
                      {job ? (
                        <span className="flex items-center gap-1 font-medium text-slate-300">
                          <Building2 className="w-3.5 h-3.5 text-blue-400" />
                          {job.company} &bull; {job.title}
                        </span>
                      ) : (
                        <span className="font-mono text-slate-500">Job ID: {version.job_id}</span>
                      )}
                      <span>&bull;</span>
                      <span>Created: {new Date(version.created_at).toLocaleString()}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleVerifyIntegrity(version.id)}
                      isLoading={isVerifying}
                      icon={<ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />}
                    >
                      Verify File Integrity
                    </Button>
                    <a
                      href={api.resumes.downloadUrl(version.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      download
                    >
                      <Button
                        variant="primary"
                        size="sm"
                        icon={<Download className="w-3.5 h-3.5" />}
                      >
                        Download PDF
                      </Button>
                    </a>
                  </div>
                </div>

                {/* Cryptographic Hash & Immutability Guarantee */}
                <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-slate-400">
                    <Lock className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    <span>Immutable SHA-256:</span>
                    <span className="font-mono text-slate-300 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                      {version.file_sha256}
                    </span>
                  </div>
                  <button
                    onClick={() => handleCopySha(version.file_sha256)}
                    className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 shrink-0"
                  >
                    {copiedSha === version.file_sha256 ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span>Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span>Copy Checksum</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Validation & Coverage Breakdown */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Factual Validation Card */}
                  <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-300 flex items-center gap-1.5">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                        Factual Claim Validation
                      </span>
                      {factResult?.is_valid ? (
                        <Badge variant="success" size="sm">
                          100% Factually Supported
                        </Badge>
                      ) : (
                        <Badge variant="danger" size="sm">
                          Unsupported Claims Detected
                        </Badge>
                      )}
                    </div>
                    <div className="text-xs text-slate-400">
                      Every statement in this resume is deterministically cross-referenced against your verified candidate profile. No synthetic hallucinations.
                    </div>
                    {factResult && factResult.unsupported_claims && factResult.unsupported_claims.length > 0 && (
                      <div className="p-2 rounded bg-red-950/30 border border-red-900/50 text-[11px] text-red-300 space-y-1">
                        <div className="font-semibold">Unsupported Claims:</div>
                        <ul className="list-disc list-inside">
                          {factResult.unsupported_claims.map((claim: any, idx: number) => (
                            <li key={idx}>{typeof claim === 'string' ? claim : JSON.stringify(claim)}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  {/* Keyword Coverage Card */}
                  <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-300 flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-blue-400" />
                        ATS Keyword Coverage
                      </span>
                      {coverageResult?.coverage_percent != null && (
                        <span className="font-mono font-semibold text-blue-400">
                          {Math.round(coverageResult.coverage_percent)}% Coverage
                        </span>
                      )}
                    </div>

                    {coverageResult && (
                      <div className="space-y-2 text-xs">
                        {matchedKeywords.length > 0 && (
                          <div>
                            <span className="text-[11px] text-slate-400">Matched in Resume: </span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {matchedKeywords.map((kw: string, i: number) => (
                                <span
                                  key={i}
                                  className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-950/40 text-emerald-300 border border-emerald-900/40"
                                >
                                  {kw}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {missingKeywords.length > 0 && (
                          <div>
                            <span className="text-[11px] text-amber-400">Missing from Profile: </span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {missingKeywords.map((kw: string, i: number) => (
                                <span
                                  key={i}
                                  className="px-1.5 py-0.5 rounded text-[10px] bg-amber-950/40 text-amber-300 border border-amber-900/40"
                                >
                                  {kw}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};
