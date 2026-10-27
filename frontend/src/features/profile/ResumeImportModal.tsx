import React, { useState } from 'react';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { api } from '../../lib/api-client';
import { ResumeImportResult } from '../../types';
import { 
  UploadCloud, 
  CheckCircle2, 
  AlertTriangle, 
  ShieldAlert, 
  Info
} from 'lucide-react';

interface ResumeImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportConfirmed: () => void;
}

export const ResumeImportModal: React.FC<ResumeImportModalProps> = ({
  isOpen,
  onClose,
  onImportConfirmed,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [importResult, setImportResult] = useState<ResumeImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const resetState = () => {
    setSelectedFile(null);
    setIsParsing(false);
    setIsConfirming(false);
    setImportResult(null);
    setError(null);
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setError('Only PDF resumes are supported.');
        return;
      }
      setSelectedFile(file);
      setError(null);
    }
  };

  const handleUploadAndParse = async () => {
    if (!selectedFile) return;
    setIsParsing(true);
    setError(null);

    try {
      const result = await api.profile.importResume(selectedFile);
      setImportResult(result);
    } catch (err: any) {
      setError(err?.message || 'Failed to parse resume PDF. Ensure the file is a valid PDF.');
    } finally {
      setIsParsing(false);
    }
  };

  const handleConfirmDraft = async () => {
    if (!importResult?.draft_profile) return;
    setIsConfirming(true);
    setError(null);

    try {
      await api.profile.confirmImport(importResult.draft_profile);
      resetState();
      onImportConfirmed();
    } catch (err: any) {
      setError(err?.message || 'Failed to save confirmed profile. Server rejected the request.');
    } finally {
      setIsConfirming(false);
    }
  };

  const draft = importResult?.draft_profile;

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Import Master Resume (PDF)"
      size="xl"
      footer={
        <div className="flex items-center justify-between w-full">
          <div className="text-xs text-slate-500">
            {draft ? (
              <span className="text-amber-400 font-medium flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                Draft extracted. Unsaved until confirmed.
              </span>
            ) : (
              'Upload a text-based master PDF resume.'
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={handleClose} disabled={isParsing || isConfirming}>
              Cancel
            </Button>
            {!draft ? (
              <Button
                variant="primary"
                onClick={handleUploadAndParse}
                disabled={!selectedFile}
                isLoading={isParsing}
                icon={<UploadCloud className="w-4 h-4" />}
              >
                Parse Resume
              </Button>
            ) : (
              <Button
                variant="primary"
                onClick={handleConfirmDraft}
                isLoading={isConfirming}
                icon={<CheckCircle2 className="w-4 h-4" />}
              >
                Confirm & Save Profile
              </Button>
            )}
          </div>
        </div>
      }
    >
      <div className="space-y-5">
        {error && (
          <div className="p-3.5 rounded-lg bg-red-950/30 border border-red-900/50 flex items-start gap-2.5 text-xs text-red-300">
            <ShieldAlert className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Upload Step */}
        {!draft && (
          <div className="space-y-4">
            <div className="border-2 border-dashed border-slate-700/80 rounded-xl p-8 text-center hover:border-slate-600 transition-colors bg-slate-900/40">
              <UploadCloud className="w-10 h-10 mx-auto mb-3 text-slate-400" />
              <div className="text-sm font-semibold text-slate-200">
                {selectedFile ? selectedFile.name : 'Select a master resume PDF'}
              </div>
              <div className="text-xs text-slate-400 mt-1">
                {selectedFile
                  ? `${(selectedFile.size / 1024).toFixed(1)} KB`
                  : 'PDF format only. Maximum file size 10MB.'}
              </div>
              <label className="mt-4 inline-block">
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <span className="cursor-pointer px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 transition-colors">
                  {selectedFile ? 'Change File' : 'Browse Computer'}
                </span>
              </label>
            </div>

            <div className="p-3 rounded-lg bg-blue-950/20 border border-blue-900/40 text-xs text-slate-300 flex items-start gap-2">
              <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-blue-300">Deterministic Fact Verification: </span>
                Extracts factual profile data (skills, positions, education) into an unverified draft. You will have full opportunity to review and confirm the extracted data before saving.
              </div>
            </div>
          </div>
        )}

        {/* Parsed Draft Review Step */}
        {draft && (
          <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
            <div className="p-3.5 rounded-lg bg-amber-950/20 border border-amber-900/50 flex items-start gap-2 text-xs text-amber-300">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold">Review Extracted Draft</div>
                <div>
                  This data has not been saved yet. Review the extracted details below, then click &ldquo;Confirm &amp; Save Profile&rdquo; to persist into your verified candidate profile.
                </div>
              </div>
            </div>

            {/* Extracted Header */}
            <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-2">
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Candidate Information
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-slate-500">Full Name:</span>{' '}
                  <span className="font-semibold text-slate-200">{draft.full_name || 'Not detected'}</span>
                </div>
                <div>
                  <span className="text-slate-500">Email:</span>{' '}
                  <span className="font-mono text-slate-200">{draft.email || 'Not detected'}</span>
                </div>
                <div>
                  <span className="text-slate-500">Phone:</span>{' '}
                  <span className="text-slate-200">{draft.phone || 'Not detected'}</span>
                </div>
                <div>
                  <span className="text-slate-500">Location:</span>{' '}
                  <span className="text-slate-200">{draft.location || 'Not detected'}</span>
                </div>
              </div>
              {draft.summary && (
                <div className="text-xs text-slate-300 pt-2 border-t border-slate-800">
                  <span className="text-slate-500">Summary:</span> {draft.summary}
                </div>
              )}
            </div>

            {/* Extracted Skills */}
            {draft.skills && draft.skills.length > 0 && (
              <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-2">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Detected Skills ({draft.skills.length})</span>
                  <span className="text-[10px] text-amber-400">Draft - Unverified</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {draft.skills.map((s, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded text-xs bg-slate-800 text-slate-200 border border-slate-700"
                    >
                      {s.skill_name} <span className="text-[10px] text-slate-400">({s.years_experience}y)</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Extracted Experiences */}
            {draft.experiences && draft.experiences.length > 0 && (
              <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Work Experience ({draft.experiences.length})
                </div>
                <div className="space-y-2.5">
                  {draft.experiences.map((exp, idx) => (
                    <div key={idx} className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs">
                      <div className="font-semibold text-slate-200">{exp.role}</div>
                      <div className="text-slate-400">
                        {exp.company} &bull; {exp.location || 'Remote'}
                      </div>
                      {exp.verified_bullets && exp.verified_bullets.length > 0 && (
                        <ul className="list-disc list-inside mt-1.5 text-slate-300 space-y-0.5">
                          {exp.verified_bullets.slice(0, 3).map((h, hIdx) => (
                            <li key={hIdx}>{h}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Extracted Education */}
            {draft.educations && draft.educations.length > 0 && (
              <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-2">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Education ({draft.educations.length})
                </div>
                <div className="space-y-1.5 text-xs text-slate-300">
                  {draft.educations.map((edu, idx) => (
                    <div key={idx} className="flex justify-between">
                      <span className="font-medium text-slate-200">{edu.degree} in {edu.field_of_study}</span>
                      <span className="text-slate-400">{edu.institution}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
};
