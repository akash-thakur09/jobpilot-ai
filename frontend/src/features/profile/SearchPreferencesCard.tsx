import React, { useState, useEffect } from 'react';
import { JobSearchPreferences, JobSearchPreferencesUpdate } from '../../types';
import { api, ApiError } from '../../lib/api-client';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import {
  SlidersHorizontal,
  Sparkles,
  MapPin,
  Building,
  Ban,
  ShieldAlert,
  CheckCircle2,
  Save,
  Plus,
  X,
  Clock,
  Target,
  Cpu,
} from 'lucide-react';

interface SearchPreferencesCardProps {
  initialPreferences?: JobSearchPreferences | null;
  onPreferencesUpdated?: (updated: JobSearchPreferences) => void;
}

const ROLE_PRESETS = [
  'Full Stack Engineer',
  'AI Engineer',
  'Backend Engineer',
  'Full Stack Developer',
  'Generative AI Engineer',
  'Software Engineer',
];

const MUST_HAVE_PRESETS = [
  'Python',
  'FastAPI',
  'React',
  'TypeScript',
  'SQL',
];

const PREFERRED_SKILL_PRESETS = [
  'Docker',
  'PostgreSQL',
  'Redis',
  'AWS',
  'Git',
  'REST APIs',
];

const AI_SKILL_PRESETS = [
  'LLM',
  'RAG',
  'Agentic AI',
  'Vector Database',
  'Embeddings',
  'LangChain',
  'LangGraph',
  'Semantic Search',
  'MCP',
  'OpenAI API',
  'Prompt Engineering',
];

const LOCATION_PRESETS = [
  'Remote',
  'Bengaluru',
  'Hyderabad',
  'Pune',
  'Gurgaon',
  'Noida',
  'India',
];

export const SearchPreferencesCard: React.FC<SearchPreferencesCardProps> = ({
  initialPreferences,
  onPreferencesUpdated,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form input states
  const [targetRoles, setTargetRoles] = useState<string[]>([]);
  const [roleInput, setRoleInput] = useState('');

  const [roleKeywords, setRoleKeywords] = useState<string[]>([]);
  const [keywordInput, setKeywordInput] = useState('');

  const [mustHaveSkills, setMustHaveSkills] = useState<string[]>([]);
  const [mustHaveInput, setMustHaveInput] = useState('');

  const [preferredSkills, setPreferredSkills] = useState<string[]>([]);
  const [prefSkillInput, setPrefSkillInput] = useState('');

  const [aiFocusSkills, setAiFocusSkills] = useState<string[]>([]);
  const [aiSkillInput, setAiSkillInput] = useState('');

  const [preferredLocations, setPreferredLocations] = useState<string[]>([]);
  const [locationInput, setLocationInput] = useState('');
  const [allowRemote, setAllowRemote] = useState<boolean>(true);

  const [remotePreference, setRemotePreference] = useState<'ANY' | 'REMOTE' | 'HYBRID' | 'ON_SITE'>('REMOTE');
  const [workModes, setWorkModes] = useState<string[]>(['Remote', 'Hybrid']);
  const [minPackageLpa, setMinPackageLpa] = useState<number | ''>('');
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
    const roles = p.target_roles || p.target_titles || [];
    setTargetRoles(roles);
    setRoleKeywords(p.role_keywords || []);

    const mustHaves = p.must_have_skills || p.required_skills || [];
    setMustHaveSkills(mustHaves);
    setPreferredSkills(p.preferred_skills || []);
    const aiSkills = p.ai_genai_focus_skills || p.ai_focus_skills || [];
    setAiFocusSkills(aiSkills);

    setPreferredLocations(p.preferred_locations || []);
    const allowRem =
      p.allow_remote_opportunities !== undefined
        ? p.allow_remote_opportunities
        : p.allow_remote !== undefined
        ? p.allow_remote
        : true;
    setAllowRemote(allowRem);
    setRemotePreference(p.remote_preference || 'REMOTE');
    setWorkModes(p.work_modes || ['Remote', 'Hybrid']);

    const pkg =
      p.minimum_package_lpa !== undefined && p.minimum_package_lpa !== null
        ? p.minimum_package_lpa
        : p.min_salary_lpa !== undefined && p.min_salary_lpa !== null
        ? p.min_salary_lpa
        : p.min_salary && p.min_salary < 200
        ? p.min_salary
        : '';
    setMinPackageLpa(pkg !== '' ? Number(pkg) : '');

    const minYr =
      p.target_min_experience_years ??
      p.preferred_min_years ??
      p.min_experience_years ??
      p.min_years_experience;
    setMinYears(minYr !== undefined && minYr !== null ? minYr : '');

    const maxYr =
      p.target_max_experience_years ??
      p.preferred_max_years ??
      p.max_experience_years ??
      p.max_years_experience;
    setMaxYears(maxYr !== undefined && maxYr !== null ? maxYr : '');

    setPreferredCompanies(p.preferred_companies || []);
    setExcludedCompanies(p.excluded_companies || []);
  };

  useEffect(() => {
    if (initialPreferences && Object.keys(initialPreferences).length > 0) {
      hydrateForm(initialPreferences);
    } else {
      loadPreferences();
    }
  }, [initialPreferences]);

  const addTag = (
    currentList: string[],
    setList: React.Dispatch<React.SetStateAction<string[]>>,
    value: string,
    clearInput?: () => void
  ) => {
    const trimmed = value.trim();
    if (trimmed && !currentList.includes(trimmed)) {
      setList([...currentList, trimmed]);
      if (clearInput) clearInput();
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
      target_roles: targetRoles,
      target_titles: targetRoles,
      role_keywords: roleKeywords,
      must_have_skills: mustHaveSkills,
      required_skills: mustHaveSkills,
      preferred_skills: preferredSkills,
      ai_genai_focus_skills: aiFocusSkills,
      ai_focus_skills: aiFocusSkills,
      preferred_locations: preferredLocations,
      allow_remote_opportunities: allowRemote,
      allow_remote: allowRemote,
      remote_preference: remotePreference,
      work_modes: workModes,
      target_min_experience_years: minYears !== '' ? Number(minYears) : null,
      preferred_min_years: minYears !== '' ? Number(minYears) : null,
      min_experience_years: minYears !== '' ? Number(minYears) : null,
      target_max_experience_years: maxYears !== '' ? Number(maxYears) : null,
      preferred_max_years: maxYears !== '' ? Number(maxYears) : null,
      max_experience_years: maxYears !== '' ? Number(maxYears) : null,
      minimum_package_lpa: minPackageLpa !== '' ? Number(minPackageLpa) : null,
      min_salary_lpa: minPackageLpa !== '' ? Number(minPackageLpa) : null,
      preferred_companies: preferredCompanies,
      excluded_companies: excludedCompanies,
    };

    try {
      const updated = await api.profile.updatePreferences(payload);
      hydrateForm(updated);
      setSuccessMsg('Search preferences saved and all jobs re-scored against target career criteria!');
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
            Drive deterministic discovery relevance for Full Stack Developer moving toward AI/GenAI, RAG, and Agentic AI roles.
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
          <span className="font-semibold text-indigo-200">Fact Separation Guarantee:</span> Search preferences configure opportunity discovery scoring and filtering only. They are never interpreted as verified candidate facts and never injected into tailored resumes without verification.
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
        {/* Section 1: Target Roles & Role Keywords */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Target className="w-3.5 h-3.5 text-blue-400" />
              Target Job Roles & Titles (40% Scoring Weight)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={roleInput}
                onChange={(e) => setRoleInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addTag(targetRoles, setTargetRoles, roleInput, () => setRoleInput(''));
                  }
                }}
                placeholder="e.g. Full Stack Engineer, AI Engineer"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => addTag(targetRoles, setTargetRoles, roleInput, () => setRoleInput(''))}
              >
                <Plus className="w-3.5 h-3.5" />
              </Button>
            </div>

            {/* Quick Presets */}
            <div className="flex flex-wrap gap-1 mt-2">
              <span className="text-[10px] text-slate-500 self-center mr-1">Presets:</span>
              {ROLE_PRESETS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => addTag(targetRoles, setTargetRoles, p)}
                  className="text-[10px] px-2 py-0.5 rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700/60"
                >
                  + {p}
                </button>
              ))}
            </div>

            {/* Selected Tags */}
            <div className="flex flex-wrap gap-1.5 mt-2.5">
              {targetRoles.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs bg-blue-500/15 text-blue-300 border border-blue-500/30"
                >
                  {t}
                  <button
                    type="button"
                    onClick={() => removeTag(targetRoles, setTargetRoles, t)}
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

        {/* Section 2: Three-Tier Priority Skills */}
        <div className="space-y-4 pt-4 border-t border-slate-800/80">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Three-Tier Priority Skills (35% Scoring Weight)
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Must-Have Skills */}
            <div className="p-3.5 rounded-xl bg-slate-950/60 border border-emerald-900/40">
              <label className="block text-xs font-semibold text-emerald-400 mb-1">
                Must-Have Skills (Non-Negotiable)
              </label>
              <div className="flex gap-1.5 mb-2">
                <input
                  type="text"
                  value={mustHaveInput}
                  onChange={(e) => setMustHaveInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addTag(mustHaveSkills, setMustHaveSkills, mustHaveInput, () => setMustHaveInput(''));
                    }
                  }}
                  placeholder="e.g. Python, React"
                  className="flex-1 bg-slate-900 border border-slate-800 rounded px-2.5 py-1 text-xs text-slate-100"
                />
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => addTag(mustHaveSkills, setMustHaveSkills, mustHaveInput, () => setMustHaveInput(''))}
                >
                  <Plus className="w-3 h-3" />
                </Button>
              </div>

              <div className="flex flex-wrap gap-1 mb-2">
                {MUST_HAVE_PRESETS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => addTag(mustHaveSkills, setMustHaveSkills, p)}
                    className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/50 hover:bg-emerald-900/60 text-emerald-300 border border-emerald-800/40"
                  >
                    +{p}
                  </button>
                ))}
              </div>

              <div className="flex flex-wrap gap-1">
                {mustHaveSkills.map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                  >
                    {s}
                    <button
                      type="button"
                      onClick={() => removeTag(mustHaveSkills, setMustHaveSkills, s)}
                      className="hover:text-rose-400"
                    >
                      <X className="w-2.5 h-2.5" />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* Preferred Skills */}
            <div className="p-3.5 rounded-xl bg-slate-950/60 border border-blue-900/40">
              <label className="block text-xs font-semibold text-blue-400 mb-1">
                Preferred Skills (Bonus)
              </label>
              <div className="flex gap-1.5 mb-2">
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
                  placeholder="e.g. Docker, Redis"
                  className="flex-1 bg-slate-900 border border-slate-800 rounded px-2.5 py-1 text-xs text-slate-100"
                />
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => addTag(preferredSkills, setPreferredSkills, prefSkillInput, () => setPrefSkillInput(''))}
                >
                  <Plus className="w-3 h-3" />
                </Button>
              </div>

              <div className="flex flex-wrap gap-1 mb-2">
                {PREFERRED_SKILL_PRESETS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => addTag(preferredSkills, setPreferredSkills, p)}
                    className="text-[9px] px-1.5 py-0.5 rounded bg-blue-950/50 hover:bg-blue-900/60 text-blue-300 border border-blue-800/40"
                  >
                    +{p}
                  </button>
                ))}
              </div>

              <div className="flex flex-wrap gap-1">
                {preferredSkills.map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-blue-500/15 text-blue-300 border border-blue-500/30"
                  >
                    {s}
                    <button
                      type="button"
                      onClick={() => removeTag(preferredSkills, setPreferredSkills, s)}
                      className="hover:text-rose-400"
                    >
                      <X className="w-2.5 h-2.5" />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* AI / GenAI Focus Skills */}
            <div className="p-3.5 rounded-xl bg-slate-950/60 border border-purple-900/40">
              <label className="block text-xs font-semibold text-purple-400 mb-1">
                AI / GenAI Focus (Specialization)
              </label>
              <div className="flex gap-1.5 mb-2">
                <input
                  type="text"
                  value={aiSkillInput}
                  onChange={(e) => setAiSkillInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addTag(aiFocusSkills, setAiFocusSkills, aiSkillInput, () => setAiSkillInput(''));
                    }
                  }}
                  placeholder="e.g. LLM, RAG, Agentic AI"
                  className="flex-1 bg-slate-900 border border-slate-800 rounded px-2.5 py-1 text-xs text-slate-100"
                />
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => addTag(aiFocusSkills, setAiFocusSkills, aiSkillInput, () => setAiSkillInput(''))}
                >
                  <Plus className="w-3 h-3" />
                </Button>
              </div>

              <div className="flex flex-wrap gap-1 mb-2">
                {AI_SKILL_PRESETS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => addTag(aiFocusSkills, setAiFocusSkills, p)}
                    className="text-[9px] px-1.5 py-0.5 rounded bg-purple-950/50 hover:bg-purple-900/60 text-purple-300 border border-purple-800/40"
                  >
                    +{p}
                  </button>
                ))}
              </div>

              <div className="flex flex-wrap gap-1">
                {aiFocusSkills.map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-purple-500/15 text-purple-300 border border-purple-500/30"
                  >
                    {s}
                    <button
                      type="button"
                      onClick={() => removeTag(aiFocusSkills, setAiFocusSkills, s)}
                      className="hover:text-rose-400"
                    >
                      <X className="w-2.5 h-2.5" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Section 3: Location, Remote, and Experience */}
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
              <option value="REMOTE">Fully Remote</option>
              <option value="HYBRID">Hybrid</option>
              <option value="ON_SITE">On-Site Only</option>
              <option value="ANY">Any Remote Mode</option>
            </select>
            <label className="flex items-center gap-2 mt-2 cursor-pointer">
              <input
                type="checkbox"
                checked={allowRemote}
                onChange={(e) => setAllowRemote(e.target.checked)}
                className="rounded border-slate-700 bg-slate-950 text-indigo-500 focus:ring-0"
              />
              <span className="text-[11px] text-slate-300">Allow Remote Opportunities</span>
            </label>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-indigo-400" />
              Target Min Experience (Yrs)
            </label>
            <input
              type="number"
              min={0}
              max={40}
              value={minYears}
              onChange={(e) => setMinYears(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="e.g. 0"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-indigo-400" />
              Target Max Experience (Yrs)
            </label>
            <input
              type="number"
              min={0}
              max={50}
              value={maxYears}
              onChange={(e) => setMaxYears(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="e.g. 6"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
              <span className="text-emerald-400 font-bold text-xs">₹</span>
              Expected Minimum Package (INR LPA)
            </label>
            <input
              type="number"
              min={0}
              step={0.5}
              value={minPackageLpa}
              onChange={(e) => setMinPackageLpa(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="e.g. 8"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <span className="text-[10px] text-slate-500 mt-1 block">
              Enter annual package in Lakhs Per Annum (LPA).
            </span>
          </div>
        </div>

        {/* Section 4: Preferred Locations */}
        <div className="pt-4 border-t border-slate-800/80">
          <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
            <MapPin className="w-3.5 h-3.5 text-indigo-400" />
            Preferred Locations (15% Scoring Weight)
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
              placeholder="e.g. Remote, Bengaluru, Hyderabad, Pune, Gurgaon"
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

          {/* Quick Presets for India and Remote */}
          <div className="flex flex-wrap gap-1 mt-2">
            <span className="text-[10px] text-slate-500 self-center mr-1">India Presets:</span>
            {LOCATION_PRESETS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => addTag(preferredLocations, setPreferredLocations, p)}
                className="text-[10px] px-2 py-0.5 rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700/60"
              >
                + {p}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-1.5 mt-2.5">
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

        {/* Section 5: Company Preferences */}
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
                placeholder="e.g. Canonical, Stripe, GitHub"
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
            <span>{isSaving ? 'Saving & Re-scoring Jobs...' : 'Save Preferences & Re-score Jobs'}</span>
          </Button>
        </div>
      </form>
    </Card>
  );
};
