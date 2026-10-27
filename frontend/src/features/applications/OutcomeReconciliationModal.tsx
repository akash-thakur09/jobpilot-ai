import React, { useState } from 'react';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { api } from '../../lib/api-client';
import {
  HelpCircle,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';

interface OutcomeReconciliationModalProps {
  applicationId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onReconciliationComplete: () => void;
}

export const OutcomeReconciliationModal: React.FC<OutcomeReconciliationModalProps> = ({
  applicationId,
  isOpen,
  onClose,
  onReconciliationComplete,
}) => {
  const [targetStatus, setTargetStatus] = useState<'SUBMITTED' | 'FAILED_SUBMISSION'>('SUBMITTED');
  const [confirmationNumber, setConfirmationNumber] = useState('');
  const [notes, setNotes] = useState('');
  const [evidenceMethod, setEvidenceMethod] = useState<'email' | 'portal_check' | 'other'>('email');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !applicationId) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await api.applications.reconcile(applicationId, {
        target_status: targetStatus,
        reconciliation_evidence: {
          verification_method: evidenceMethod,
          confirmation_number: confirmationNumber.trim() || undefined,
          reconciled_by: 'human_operator',
          reconciled_at: new Date().toISOString(),
        },
        notes: notes.trim() || undefined,
      });

      onReconciliationComplete();
      onClose();
    } catch (err: any) {
      setError(err?.message || 'Failed to reconcile application outcome.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Guarded Outcome Reconciliation"
      size="lg"
      footer={
        <div className="flex items-center justify-between w-full">
          <div className="text-xs text-slate-500">
            Never retries blindly. Authoritative state transition.
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleSubmit}
              isLoading={isSubmitting}
              icon={<ShieldCheck className="w-4 h-4" />}
            >
              Confirm Reconciliation
            </Button>
          </div>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-900/50 flex items-start gap-2.5 text-xs text-amber-300">
          <HelpCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-amber-200">Ambiguous / Unknown Submission Outcome</div>
            <p className="mt-0.5">
              The browser runner stopped or timed out during submission before receiving definitive proof.
              To prevent accidental duplicate applications, automatic retry is permanently blocked.
              Review the employer portal or your email, then record your verified resolution below.
            </p>
          </div>
        </div>

        {error && (
          <div className="p-3.5 rounded-xl bg-red-950/30 border border-red-900/50 flex items-start gap-2 text-xs text-red-300">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-2">
            Verified Resolution
          </label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setTargetStatus('SUBMITTED')}
              className={`p-3 rounded-xl border text-left transition-all ${
                targetStatus === 'SUBMITTED'
                  ? 'bg-emerald-950/30 border-emerald-500/80 text-emerald-200'
                  : 'bg-slate-900/50 border-slate-800 text-slate-400 hover:border-slate-700'
              }`}
            >
              <div className="font-semibold text-xs flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                Confirmed Submitted
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Employer email receipt or portal confirmation received.
              </div>
            </button>

            <button
              type="button"
              onClick={() => setTargetStatus('FAILED_SUBMISSION')}
              className={`p-3 rounded-xl border text-left transition-all ${
                targetStatus === 'FAILED_SUBMISSION'
                  ? 'bg-red-950/30 border-red-500/80 text-red-200'
                  : 'bg-slate-900/50 border-slate-800 text-slate-400 hover:border-slate-700'
              }`}
            >
              <div className="font-semibold text-xs flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                Confirmed Failed
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Application was not received; safe to re-prepare if appropriate.
              </div>
            </button>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Verification Evidence Method
          </label>
          <select
            value={evidenceMethod}
            onChange={(e) => setEvidenceMethod(e.target.value as any)}
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:border-blue-500 focus:outline-none"
          >
            <option value="email">Confirmation Email from Employer</option>
            <option value="portal_check">Manually Checked Portal / Dashboard</option>
            <option value="other">Other External Evidence</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Confirmation Reference / Receipt ID (Optional)
          </label>
          <input
            type="text"
            value={confirmationNumber}
            onChange={(e) => setConfirmationNumber(e.target.value)}
            placeholder="e.g. APP-948194, Email subject / message ID"
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:border-blue-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Auditing Notes & Details
          </label>
          <textarea
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Document reason for reconciliation (e.g. checked email inbox, confirmation arrived 5 minutes later)"
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:border-blue-500 focus:outline-none"
          />
        </div>
      </form>
    </Modal>
  );
};
