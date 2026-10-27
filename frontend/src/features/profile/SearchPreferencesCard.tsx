import React, { useState, useEffect } from 'react';
import { JobSearchPreferences, JobSearchPreferencesUpdate } from '../../types';
import { api, ApiError } from '../../lib/api-client';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import {
  SlidersHorizontal,
  Briefcase,
  Sparkles,
  MapPin,
  Building,
  DollarSign,
  Ban,
  ShieldAlert,
  CheckCircle2,
  Save,
  Plus,
  X,
  Clock,
} from 'lucide-react';

interface SearchPreferencesCardProps {
  initialPreferences?: JobSearchPreferences | null;
  onPreferencesUpdated?: (updated: JobSearchPreferences) => void;
}

export const SearchPreferencesCard: React.FC<SearchPreferencesCardProps> = ({
  initialPreferences,
  onPreferencesUpdated,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form input states
  const [targetTitles, setTargetTitles] = useState<string[]>([]);
  const [titleInput, setTitleInput] = useState('');

  const [roleKeywords, setRoleKeywords] = useState<string[]>([]);
  const [keywordInput, setKeywordInput] = useState('');

  const [requiredSkills, setRequiredSkills] = useState<string[]>([]);
  const [reqSkillInput, setReqSkillInput] = useState('');

  const [preferredSkills, setPreferredSkills] = useState<string[]>([]);
  const [prefSkillInput, setPrefSkillInput] = useState('');

  const [preferredLocations, setPreferredLocations] = useState<string[]>([]);
  const [locationInput, setLocationInput] = useState('');

  const [remotePreference, setRemotePreference] = useState<'ANY' | 'REMOTE' | 'HYBRID' | 'ON_SITE'>('ANY');
  const [minSalary, setMinSalary] = useState<number | ''>('');
  const [minYears, setMinYears] = useState<number | ''>('');
  const [maxYears, setMaxYears] = useState<number | ''>('');

  const [preferredCompanies, setPreferredCompanies] = useState<string[]>([]);
  const [prefCompanyInput, setPrefCompanyInput] = useState('');

  const [excludedCompanies, setExcludedCompanies] = useState<string[]>([]);
  const [exCompanyInput, setExCompanyInput] = useState('');

  const loadPreferences = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.profile.getPreferences();
      hydrateForm(data || {});
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Failed to load search preferences.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const hydrateForm = (p: JobSearchPreferences) => {
    setTargetTitles(p.target_titles || []);
    setRoleKeywords(p.role_keywords || []);
    setRequiredSkills(p.required_skills || []);
    setPreferredSkills(p.preferred_skills || []);
    setPreferredLocations(p.preferred_locations || []);
    setRemotePreference(p.remote_preference || 'ANY');
    setMinSalary(p.min_salary !== undefined && p.min_salary !== null ? p.min_salary : '');
    setMinYears(p.min_years_experience !== undefined && p.min_years_experience !== null ? p.min_years_experience : '');
    setMaxYears(p.max_years_experience !== undefined && p.max_years_experience !== null ? p.max_years_experience : '');
    setPreferredCompanies(p.preferred_companies || []);
    setExcludedCompanies(p.excluded_companies || []);
  };

  useEffect(() => {
    if (initialPreferences) {
      hydrateForm(initialPreferences);
    } else {
      loadPreferences();
    }
  }, [initialPreferences]);

  const addTag = (
    currentList: string[],
    setList: React.Dispatch<React.SetStateAction<string[]>>,
    value: string,
    clearInput: () => void
  ) => {
    const trimmed = value.trim();
    if (trimmed && !currentList.includes(trimmed)) {
      setList([...currentList, trimmed]);
      clearInput();
    }
  };

  const removeTag = (
    currentList: string[],
    setList: React.Dispatch<React.SetStateAction<string[]>>,
    tagToRemove: string
  ) => {
    setList(currentList.filter((t) => t !== tagToRemove));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    setSuccessMsg(null);

    const payload: JobSearchPreferencesUpdate = {
      target_titles: targetTitles,
      role_keywords: roleKeywords,
      required_skills: requiredSkills,
      preferred_skills: preferredSkills,
      preferred_locations: preferredLocations,
      remote_preference: remotePreference,
      min_salary: minSalary !== '' ? Number(minSalary) : null,
      min_years_experience: minYears !== '' ? Number(minYears) : null,
      max_years_experience: maxYears !== '' ? Number(maxYears) : null,
      preferred_companies: preferredCompanies,
      excluded_companies: excludedCompanies,
    };

    try {
      const updated = await api.profile.updatePreferences(payload);
      hydrateForm(updated);
      setSuccessMsg('Search preferences saved successfully.');
      if (onPreferencesUpdated) {
        onPreferencesUpdated(updated);
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Failed to save search preferences.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="p-6 border-slate-800 bg-slate-900/60 backdrop-blur-md">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-5 h-5 text-indigo-400" />
            <h2 className="text-lg font-bold text-slate-100">Personalized Job Search Preferences</h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Configure target titles, desired job keywords, salary floor, and company filters for discovery and match scoring.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={loadPreferences}
          disabled={isLoading || isSaving}
        >
          Reset
        </Button>
      </div>

      {/* Strict Fact Separation Security Banner */}
      <div className="mt-4 p-3.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-xs text-indigo-300 flex items-start gap-2.5">
        <ShieldAlert className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-indigo-200">Fact Separation Guarantee:</span> Desired skills and keywords defined below guide opportunity matching only. They are never interpreted as verified candidate facts and never injected into tailored resumes.
        </div>
      </div>

      {error && (
        <div className="mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="mt-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="mt-6 space-y-6">
        {/* Role Keywords & Target Titles */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Briefcase className="w-3.5 h-3.5 text-indigo-400" />
              Target Job Titles
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={titleInput}
                onChange={(e) => setTitleInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addTag(targetTitles, setTargetTitles, titleInput, () => setTitleInput(''));
                  }
                }}
                placeholder="e.g. Senior Backend Engineer"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => addTag(targetTitles, setTargetTitles, titleInput, () => setTitleInput(''))}
              >
                <Plus className="w-3.5 h-3.5" />
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {targetTitles.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs bg-indigo-500/15 text-indigo-300 border border-indigo-500/30"
                >
                  {t}
                  <button
                    type="button"
                    onClick={() => removeTag(targetTitles, setTargetTitles, t)}
                    className="hover:text-rose-400"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
              Role Keywords (Match Weighting)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addTag(roleKeywords, setRoleKeywords, keywordInput, () => setKeywordInput(''));
                  }
                }}
                placeholder="e.g. Distributed Systems, Microservices"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => addTag(roleKeywords, setRoleKeywords, keywordInput, () => setKeywordInput(''))}
              >
                <Plus className="w-3.5 h-3.5" />
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {roleKeywords.map((k) => (
                <span
                  key={k}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs bg-slate-800 text-slate-300 border border-slate-700"
                >
                  {k}
                  <button
                    type="button"
                    onClick={() => removeTag(roleKeywords, setRoleKeywords, k)}
                    className="hover:text-rose-400"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Desired Skills: Required vs Preferred */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-slate-800/80">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Required Skills in Jobs
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={reqSkillInput}
                onChange={(e) => setReqSkillInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addTag(requiredSkills, setRequiredSkills, reqSkillInput, () => setReqSkillInput(''));
                  }
                }}
                placeholder="e.g. Python, Docker"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => addTag(requiredSkills, setRequiredSkills, reqSkillInput, () => setReqSkillInput(''))}
              >
                <Plus className="w-3.5 h-3.5" />
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {requiredSkills.map((s) => (
                <span
                  key={s}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                >
                  {s}
                  <button
                    type="button"
                    onClick={() => removeTag(requiredSkills, setRequiredSkills, s)}
                    className="hover:text-rose-400"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Preferred Skills in Jobs
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={prefSkillInput}
                onChange={(e) => setPrefSkillInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addTag(preferredSkills, setPreferredSkills, prefSkillInput, () => setPrefSkillInput(''));
                  }
                }}
                placeholder="e.g. Kubernetes, Rust"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => addTag(preferredSkills, setPreferredSkills, prefSkillInput, () => setPrefSkillInput(''))}
              >
                <Plus className="w-3.5 h-3.5" />
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {preferredSkills.map((s) => (
                <span
                  key={s}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs bg-amber-500/15 text-amber-300 border border-amber-500/30"
                >
                  {s}
                  <button
                    type="button"
                    onClick={() => removeTag(preferredSkills, setPreferredSkills, s)}
                    className="hover:text-rose-400"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Location, Remote, Salary, and Experience */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-4 border-t border-slate-800/80">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
              <MapPin className="w-3.5 h-3.5 text-indigo-400" />
              Remote Preference
            </label>
            <select
              value={remotePreference}
              onChange={(e) => setRemotePreference(e.target.value as any)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
            >
              <option value="ANY">Any Remote Mode</option>
              <option value="REMOTE">Fully Remote</option>
              <option value="HYBRID">Hybrid</option>
              <option value="ON_SITE">On-Site Only</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
              <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
              Minimum Salary (USD)
            </label>
            <input
              type="number"
              min={0}
              step={5000}
              value={minSalary}
              onChange={(e) => setMinSalary(e.target.value ? Number(e.target.value) : '')}
              placeholder="e.g. 150000"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-indigo-400" />
              Min Experience (Years)
            </label>
            <input
              type="number"
              min={0}
              max={40}
              value={minYears}
              onChange={(e) => setMinYears(e.target.value ? Number(e.target.value) : '')}
              placeholder="e.g. 3"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-indigo-400" />
              Max Experience (Years)
            </label>
            <input
              type="number"
              min={0}
              max={50}
              value={maxYears}
              onChange={(e) => setMaxYears(e.target.value ? Number(e.target.value) : '')}
              placeholder="e.g. 10"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        {/* Preferred Locations */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1.5">
            Preferred Locations
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={locationInput}
              onChange={(e) => setLocationInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addTag(preferredLocations, setPreferredLocations, locationInput, () => setLocationInput(''));
                }
              }}
              placeholder="e.g. San Francisco, CA, New York, NY"
              className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => addTag(preferredLocations, setPreferredLocations, locationInput, () => setLocationInput(''))}
            >
              <Plus className="w-3.5 h-3.5" />
            </Button>
          </div>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {preferredLocations.map((loc) => (
              <span
                key={loc}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs bg-slate-800 text-slate-300 border border-slate-700"
              >
                {loc}
                <button
                  type="button"
                  onClick={() => removeTag(preferredLocations, setPreferredLocations, loc)}
                  className="hover:text-rose-400"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        </div>

        {/* Company Preferences: Preferred vs Excluded */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-slate-800/80">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Building className="w-3.5 h-3.5 text-emerald-400" />
              Preferred Companies (+Score Boost)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={prefCompanyInput}
                onChange={(e) => setPrefCompanyInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addTag(preferredCompanies, setPreferredCompanies, prefCompanyInput, () => setPrefCompanyInput(''));
                  }
                }}
                placeholder="e.g. Stripe, GitHub, OpenAI"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => addTag(preferredCompanies, setPreferredCompanies, prefCompanyInput, () => setPrefCompanyInput(''))}
              >
                <Plus className="w-3.5 h-3.5" />
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {preferredCompanies.map((c) => (
                <span
                  key={c}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                >
                  {c}
                  <button
                    type="button"
                    onClick={() => removeTag(preferredCompanies, setPreferredCompanies, c)}
                    className="hover:text-rose-400"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Ban className="w-3.5 h-3.5 text-rose-400" />
              Excluded Companies (-Score Penalty)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={exCompanyInput}
                onChange={(e) => setExCompanyInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addTag(excludedCompanies, setExcludedCompanies, exCompanyInput, () => setExCompanyInput(''));
                  }
                }}
                placeholder="e.g. SpamCo, AggressiveRecruiting"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => addTag(excludedCompanies, setExcludedCompanies, exCompanyInput, () => setExCompanyInput(''))}
              >
                <Plus className="w-3.5 h-3.5" />
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {excludedCompanies.map((c) => (
                <span
                  key={c}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs bg-rose-500/15 text-rose-300 border border-rose-500/30"
                >
                  {c}
                  <button
                    type="button"
                    onClick={() => removeTag(excludedCompanies, setExcludedCompanies, c)}
                    className="hover:text-rose-400"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="pt-4 flex justify-end">
          <Button
            type="submit"
            variant="primary"
            disabled={isSaving}
            className="flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            <span>{isSaving ? 'Saving Preferences...' : 'Save Search Preferences'}</span>
          </Button>
        </div>
      </form>
    </Card>
  );
};
