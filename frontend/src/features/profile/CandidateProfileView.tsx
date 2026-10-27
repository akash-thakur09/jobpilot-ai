import React, { useEffect, useState } from 'react';
import { CandidateProfile } from '../../types';
import { api, ApiError } from '../../lib/api-client';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { LoadingSkeleton } from '../../components/ui/LoadingSkeleton';
import { EmptyState } from '../../components/ui/EmptyState';
import { ResumeImportModal } from './ResumeImportModal';
import {
  User,
  Mail,
  Phone,
  MapPin,
  Briefcase,
  DollarSign,
  GraduationCap,
  Code,
  FolderGit2,
  UploadCloud,
  CheckCircle2,
  ShieldCheck,
  AlertTriangle,
  Plus,
  Trash2,
  RefreshCw,
  Save,
} from 'lucide-react';

export const CandidateProfileView: React.FC = () => {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);

  // Edit basic fields state
  const [isEditingBasic, setIsEditingBasic] = useState(false);
  const [editFullName, setEditFullName] = useState('');
  const [editEmail, setEditEmail] = useState('');
  const [editPhone, setEditPhone] = useState('');
  const [editLocation, setEditLocation] = useState('');
  const [editSummary, setEditSummary] = useState('');
  const [editWorkAuth, setEditWorkAuth] = useState('');
  const [editMinSalary, setEditMinSalary] = useState<number | undefined>(undefined);
  const [editRemotePref, setEditRemotePref] = useState('ALL');
  const [isSavingBasic, setIsSavingBasic] = useState(false);

  // Add skill state
  const [newSkillName, setNewSkillName] = useState('');
  const [newSkillYears, setNewSkillYears] = useState(3);
  const [newSkillCategory, setNewSkillCategory] = useState('technical');
  const [isAddingSkill, setIsAddingSkill] = useState(false);

  // Status message
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchProfile = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.profile.get();
      setProfile(data);
      populateEditForm(data);
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 404) {
        setProfile(null);
      } else {
        setError(err?.message || 'Failed to load candidate profile');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const populateEditForm = (data: CandidateProfile) => {
    setEditFullName(data.full_name || '');
    setEditEmail(data.email || '');
    setEditPhone(data.phone || '');
    setEditLocation(data.location || '');
    setEditSummary(data.summary || '');
    setEditWorkAuth(data.work_authorization || '');
    setEditMinSalary(data.min_salary || undefined);
    setEditRemotePref(data.remote_preference || 'ALL');
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleSaveBasic = async () => {
    setIsSavingBasic(true);
    setStatusMessage(null);
    try {
      const updated = await api.profile.update({
        full_name: editFullName.trim() || undefined,
        email: editEmail.trim() || undefined,
        phone: editPhone.trim() || undefined,
        location: editLocation.trim() || undefined,
        summary: editSummary.trim() || undefined,
        work_authorization: editWorkAuth.trim() || undefined,
        min_salary: editMinSalary ? Number(editMinSalary) : undefined,
        remote_preference: editRemotePref,
      });
      setProfile(updated);
      setIsEditingBasic(false);
      setStatusMessage({ type: 'success', text: 'Candidate profile updated successfully.' });
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err?.message || 'Failed to update profile.' });
    } finally {
      setIsSavingBasic(false);
    }
  };

  const handleAddSkill = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSkillName.trim()) return;
    setIsAddingSkill(true);
    setStatusMessage(null);
    try {
      const created = await api.profile.addSkill({
        skill_name: newSkillName.trim(),
        category: newSkillCategory,
        years_experience: Number(newSkillYears),
        is_verified: true,
      });
      setProfile((prev) =>
        prev
          ? {
              ...prev,
              skills: [...prev.skills, created],
            }
          : null
      );
      setNewSkillName('');
      setStatusMessage({ type: 'success', text: `Skill "${created.skill_name}" added to verified profile.` });
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err?.message || 'Failed to add skill.' });
    } finally {
      setIsAddingSkill(false);
    }
  };

  const handleDeleteSkill = async (skillId: string, skillName: string) => {
    if (!confirm(`Remove skill "${skillName}" from profile?`)) return;
    try {
      await api.profile.deleteSkill(skillId);
      setProfile((prev) =>
        prev
          ? {
              ...prev,
              skills: prev.skills.filter((s) => s.id !== skillId),
            }
          : null
      );
      setStatusMessage({ type: 'success', text: `Skill "${skillName}" removed.` });
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err?.message || 'Failed to remove skill.' });
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Candidate Profile & Master Resume</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Verified candidate facts used for deterministic eligibility and truthful resume tailoring.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchProfile}
            icon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsImportModalOpen(true)}
            icon={<UploadCloud className="w-4 h-4" />}
          >
            Import Master Resume
          </Button>
        </div>
      </div>

      {statusMessage && (
        <div
          className={`p-3.5 rounded-xl border flex items-center justify-between text-xs ${
            statusMessage.type === 'success'
              ? 'bg-emerald-950/30 border-emerald-900/50 text-emerald-300'
              : 'bg-red-950/30 border-red-900/50 text-red-300'
          }`}
        >
          <div className="flex items-center gap-2">
            {statusMessage.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-red-400" />
            )}
            <span>{statusMessage.text}</span>
          </div>
          <button
            onClick={() => setStatusMessage(null)}
            className="text-slate-400 hover:text-slate-200"
          >
            &times;
          </button>
        </div>
      )}

      {isLoading ? (
        <LoadingSkeleton count={4} />
      ) : error ? (
        <Card className="p-8 text-center text-red-400">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-red-400" />
          <div className="font-semibold text-sm">Failed to Load Profile</div>
          <div className="text-xs text-slate-400 mt-1">{error}</div>
          <Button variant="outline" size="sm" onClick={fetchProfile} className="mt-4">
            Retry
          </Button>
        </Card>
      ) : !profile ? (
        <EmptyState
          title="No Candidate Profile Found"
          description="Your local database does not have an active candidate profile yet. Import a master resume PDF to get started."
          icon={<User className="w-6 h-6 text-slate-400" />}
          action={
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsImportModalOpen(true)}
              icon={<UploadCloud className="w-4 h-4" />}
            >
              Import Master Resume
            </Button>
          }
        />
      ) : (
        <div className="space-y-6">
          {/* Identity & Contact Card */}
          <Card className="p-6">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 pb-4 border-b border-slate-800">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-bold text-slate-100">{profile.full_name}</h3>
                  <Badge variant="success" size="sm" icon={<ShieldCheck className="w-3 h-3" />}>
                    Verified Profile
                  </Badge>
                </div>
                <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400 pt-1">
                  <span className="flex items-center gap-1 font-mono text-slate-300">
                    <Mail className="w-3.5 h-3.5 text-blue-400" />
                    {profile.email}
                  </span>
                  {profile.phone && (
                    <span className="flex items-center gap-1">
                      <Phone className="w-3.5 h-3.5 text-slate-500" />
                      {profile.phone}
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5 text-slate-500" />
                    {profile.location || 'Not specified'}
                  </span>
                  <span className="flex items-center gap-1 text-slate-300">
                    <Briefcase className="w-3.5 h-3.5 text-slate-500" />
                    Work Auth: {profile.work_authorization || 'Standard'}
                  </span>
                  {profile.min_salary && (
                    <span className="flex items-center gap-1 text-emerald-400 font-medium">
                      <DollarSign className="w-3.5 h-3.5" />
                      Min ${profile.min_salary.toLocaleString()}/yr
                    </span>
                  )}
                </div>
              </div>

              <Button
                variant={isEditingBasic ? 'ghost' : 'outline'}
                size="sm"
                onClick={() => {
                  if (isEditingBasic) {
                    populateEditForm(profile);
                  }
                  setIsEditingBasic(!isEditingBasic);
                }}
              >
                {isEditingBasic ? 'Cancel Edit' : 'Edit Details'}
              </Button>
            </div>

            {/* Editable Form */}
            {isEditingBasic ? (
              <div className="mt-4 pt-2 space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="block text-slate-400 mb-1">Full Name</label>
                    <input
                      type="text"
                      value={editFullName}
                      onChange={(e) => setEditFullName(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Email</label>
                    <input
                      type="email"
                      value={editEmail}
                      onChange={(e) => setEditEmail(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Phone</label>
                    <input
                      type="text"
                      value={editPhone}
                      onChange={(e) => setEditPhone(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Location</label>
                    <input
                      type="text"
                      value={editLocation}
                      onChange={(e) => setEditLocation(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Work Authorization</label>
                    <input
                      type="text"
                      value={editWorkAuth}
                      onChange={(e) => setEditWorkAuth(e.target.value)}
                      placeholder="e.g. US Citizen, Green Card, H-1B"
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Minimum Base Salary (USD/yr)</label>
                    <input
                      type="number"
                      value={editMinSalary || ''}
                      onChange={(e) => setEditMinSalary(e.target.value ? Number(e.target.value) : undefined)}
                      placeholder="e.g. 120000"
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Professional Summary</label>
                  <textarea
                    rows={3}
                    value={editSummary}
                    onChange={(e) => setEditSummary(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-200"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleSaveBasic}
                    isLoading={isSavingBasic}
                    icon={<Save className="w-3.5 h-3.5" />}
                  >
                    Save Changes
                  </Button>
                </div>
              </div>
            ) : (
              profile.summary && (
                <div className="mt-4 text-xs text-slate-300 leading-relaxed bg-slate-900/50 p-3.5 rounded-xl border border-slate-800">
                  <span className="font-semibold text-slate-200">Summary: </span>
                  {profile.summary}
                </div>
              )
            )}
          </Card>

          {/* Verified Skills Section */}
          <Card className="p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <Code className="w-4 h-4 text-blue-400" />
                  Verified Skills ({profile.skills.length})
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Factual skill claims verified from your master resume or manual additions.
                </p>
              </div>
            </div>

            {/* Add Skill Form */}
            <form onSubmit={handleAddSkill} className="mb-4 p-3 rounded-xl bg-slate-900/60 border border-slate-800 grid grid-cols-1 sm:grid-cols-4 gap-2">
              <input
                type="text"
                placeholder="Skill name (e.g. React, Python)"
                value={newSkillName}
                onChange={(e) => setNewSkillName(e.target.value)}
                className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-200 focus:outline-none"
              />
              <select
                value={newSkillCategory}
                onChange={(e) => setNewSkillCategory(e.target.value)}
                className="px-2 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-200 focus:outline-none"
              >
                <option value="technical">Technical</option>
                <option value="soft">Soft Skill</option>
                <option value="domain">Domain</option>
              </select>
              <div className="flex items-center gap-1.5">
                <input
                  type="number"
                  min="0"
                  max="40"
                  value={newSkillYears}
                  onChange={(e) => setNewSkillYears(Number(e.target.value))}
                  className="w-16 px-2 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-200 focus:outline-none"
                />
                <span className="text-[11px] text-slate-400">years</span>
              </div>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={isAddingSkill}
                icon={<Plus className="w-3.5 h-3.5" />}
              >
                Add Skill
              </Button>
            </form>

            {/* Skills List */}
            <div className="flex flex-wrap gap-2">
              {profile.skills.map((skill) => (
                <div
                  key={skill.id || skill.skill_name}
                  className="group flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs hover:border-slate-700 transition-colors"
                >
                  <span className="font-medium text-slate-200">{skill.skill_name}</span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {skill.years_experience}y
                  </span>
                  {skill.is_verified && (
                    <span title="Verified Fact" className="text-emerald-400">
                      &#10003;
                    </span>
                  )}
                  {skill.id && (
                    <button
                      onClick={() => handleDeleteSkill(skill.id as string, skill.skill_name)}
                      className="ml-1 opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 transition-opacity"
                      title="Remove skill"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </Card>

          {/* Experience Section */}
          <Card className="p-6">
            <h3 className="text-sm font-bold text-slate-100 mb-4 flex items-center gap-2">
              <Briefcase className="w-4 h-4 text-emerald-400" />
              Work History ({profile.experiences.length})
            </h3>
            <div className="space-y-4">
              {profile.experiences.map((exp) => (
                <div
                  key={exp.id || `${exp.company}-${exp.role}`}
                  className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold text-slate-200 text-sm">{exp.role}</h4>
                      <div className="text-slate-400">
                        {exp.company} &bull; {exp.location || 'Remote'}
                      </div>
                    </div>
                    <div className="text-right text-[11px] text-slate-500 font-mono">
                      {exp.start_date} - {exp.end_date || (exp.is_current ? 'Present' : 'Ended')}
                    </div>
                  </div>

                  {exp.verified_bullets && exp.verified_bullets.length > 0 && (
                    <ul className="list-disc list-inside text-slate-300 space-y-1 pt-1">
                      {exp.verified_bullets.map((h, i) => (
                        <li key={i}>{h}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </Card>

          {/* Education & Projects Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Educations */}
            <Card className="p-6">
              <h3 className="text-sm font-bold text-slate-100 mb-4 flex items-center gap-2">
                <GraduationCap className="w-4 h-4 text-purple-400" />
                Education ({profile.educations.length})
              </h3>
              <div className="space-y-3">
                {profile.educations.map((edu) => (
                  <div key={edu.id || `${edu.institution}-${edu.degree}`} className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 text-xs">
                    <div className="font-semibold text-slate-200">
                      {edu.degree} in {edu.field_of_study || 'Degree'}
                    </div>
                    <div className="text-slate-400 mt-0.5">{edu.institution}</div>
                  </div>
                ))}
              </div>
            </Card>

            {/* Projects */}
            <Card className="p-6">
              <h3 className="text-sm font-bold text-slate-100 mb-4 flex items-center gap-2">
                <FolderGit2 className="w-4 h-4 text-amber-400" />
                Demonstrable Projects ({profile.projects.length})
              </h3>
              <div className="space-y-3">
                {profile.projects.map((proj) => (
                  <div key={proj.id || proj.name} className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 text-xs">
                    <div className="font-semibold text-slate-200">{proj.name}</div>
                    {proj.description && (
                      <div className="text-slate-400 mt-1 line-clamp-2">{proj.description}</div>
                    )}
                    {proj.technologies && proj.technologies.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {proj.technologies.map((s, idx) => (
                          <span
                            key={idx}
                            className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Resume Import Modal */}
      <ResumeImportModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        onImportConfirmed={() => {
          setIsImportModalOpen(false);
          fetchProfile();
          setStatusMessage({
            type: 'success',
            text: 'Master resume successfully imported and confirmed into verified profile.',
          });
        }}
      />
    </div>
  );
};
