import React, { useEffect, useState } from 'react';
import { Application, ApplicationEvent, SubmissionAttempt } from '../../types';
import { api } from '../../lib/api-client';
import { Modal } from '../../components/ui/Modal';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { LoadingSkeleton } from '../../components/ui/LoadingSkeleton';
import { formatApplicationStatusBadge, formatAttemptStatusBadge } from '../../lib/formatters';
import { Terminal } from 'lucide-react';

interface ApplicationHistoryDrawerProps {
  application: Application | null;
  isOpen: boolean;
  onClose: () => void;
}

export const ApplicationHistoryDrawer: React.FC<ApplicationHistoryDrawerProps> = ({
  application,
  isOpen,
  onClose,
}) => {
  const [events, setEvents] = useState<ApplicationEvent[]>([]);
  const [attempts, setAttempts] = useState<SubmissionAttempt[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'events' | 'attempts'>('events');

  useEffect(() => {
    if (isOpen && application) {
      loadHistory(application.id);
    }
  }, [isOpen, application]);

  const loadHistory = async (id: string) => {
    setIsLoading(true);
    try {
      const [eventsRes, attemptsRes] = await Promise.all([
        api.applications.listEvents(id).catch(() => ({ items: [], total: 0 })),
        api.applications.listAttempts(id).catch(() => ({ items: [], total: 0 })),
      ]);
      setEvents(eventsRes.items || []);
      setAttempts(attemptsRes.items || []);
    } catch {
      // Ignored
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen || !application) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Application Audit History & Timeline"
      size="xl"
      footer={
        <div className="flex justify-end w-full">
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
          <button
            onClick={() => setActiveTab('events')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === 'events'
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Append-Only Event Timeline ({events.length})
          </button>
          <button
            onClick={() => setActiveTab('attempts')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === 'attempts'
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Submission Attempts ({attempts.length})
          </button>
        </div>

        {isLoading ? (
          <LoadingSkeleton count={3} />
        ) : activeTab === 'events' ? (
          /* Events Timeline */
          events.length === 0 ? (
            <div className="text-center py-8 text-xs text-slate-500">
              No audit events recorded for this application.
            </div>
          ) : (
            <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
              {events.map((evt, idx) => {
                const toBadge = formatApplicationStatusBadge(evt.to_status);
                const fromBadge = evt.from_status
                  ? formatApplicationStatusBadge(evt.from_status)
                  : null;

                return (
                  <div key={evt.id || idx} className="relative group">
                    {/* Circle marker */}
                    <div className="absolute -left-6 top-1 w-2.5 h-2.5 rounded-full bg-blue-500 ring-4 ring-slate-900" />

                    <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs space-y-1.5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 font-medium text-slate-200">
                          {fromBadge && (
                            <>
                              <Badge variant={fromBadge.variant} size="sm">
                                {fromBadge.label}
                              </Badge>
                              <span className="text-slate-500">&rarr;</span>
                            </>
                          )}
                          <Badge variant={toBadge.variant} size="sm">
                            {toBadge.label}
                          </Badge>
                        </div>
                        <div className="text-[11px] text-slate-500 font-mono">
                          {new Date(evt.created_at).toLocaleString()}
                        </div>
                      </div>

                      <div className="text-[11px] font-mono text-slate-400">
                        Actor: {evt.actor}
                      </div>

                      {evt.payload && Object.keys(evt.payload).length > 0 && (
                        <div className="p-2 rounded bg-slate-950 font-mono text-[10px] text-slate-400 overflow-x-auto max-h-32">
                          <pre>{JSON.stringify(evt.payload, null, 2)}</pre>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )
        ) : (
          /* Submission Attempts */
          attempts.length === 0 ? (
            <div className="text-center py-8 text-xs text-slate-500">
              No browser submission runs have been initiated for this application yet.
            </div>
          ) : (
            <div className="space-y-3">
              {attempts.map((att) => {
                const attBadge = formatAttemptStatusBadge(att.outcome);

                return (
                  <div
                    key={att.id}
                    className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 text-xs space-y-2.5"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-800">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-200">
                          Attempt #{att.attempt_number}
                        </span>
                        <Badge variant={attBadge.variant} size="sm">
                          {attBadge.label}
                        </Badge>
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        {new Date(att.started_at).toLocaleString()}
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-slate-300">
                      <div>
                        <span className="text-slate-500">Adapter: </span>
                        <span className="font-mono text-slate-200 text-[11px]">
                          {att.adapter_identifier}
                        </span>
                      </div>
                      {att.completed_at && (
                        <div>
                          <span className="text-slate-500">Duration: </span>
                          <span className="font-mono text-slate-200">
                            {(
                              (new Date(att.completed_at).getTime() -
                                new Date(att.started_at).getTime()) /
                              1000
                            ).toFixed(1)}
                            s
                          </span>
                        </div>
                      )}
                      {att.confirmation_reference && (
                        <div className="sm:col-span-2 text-emerald-400 font-mono">
                          Confirmation: {att.confirmation_reference}
                        </div>
                      )}
                    </div>

                    {/* Sanitized diagnostics */}
                    {att.sanitized_diagnostics && Object.keys(att.sanitized_diagnostics).length > 0 && (
                      <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 max-h-36 overflow-y-auto">
                        <div className="text-[10px] text-slate-500 mb-1 flex items-center gap-1">
                          <Terminal className="w-3 h-3" />
                          Sanitized Diagnostics
                        </div>
                        <pre className="whitespace-pre-wrap">
                          {JSON.stringify(att.sanitized_diagnostics, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )
        )}
      </div>
    </Modal>
  );
};
