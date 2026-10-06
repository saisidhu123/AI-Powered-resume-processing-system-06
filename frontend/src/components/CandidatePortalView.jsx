import React, { useState } from 'react';
import axios from 'axios';
import { Upload, FileText, CheckCircle2, AlertTriangle, ShieldCheck, Sparkles, RefreshCw, Layers } from 'lucide-react';

export default function CandidatePortalView() {
  const [resumeFile, setResumeFile] = useState(null);
  const [jdText, setJdText] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('match'); // match, mismatch, sections, ats, reword

  const handleRunAnalysis = async () => {
    if (!resumeFile || !jdText.trim()) {
      setError('Please upload your resume and paste the target job description.');
      return;
    }

    setLoading(true);
    setError('');

    const formData = new FormData();
    formData.append('resume', resumeFile);
    formData.append('jd_text', jdText);

    try {
      const res = await axios.post('/api/candidate-analysis', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResults(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Candidate analysis failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-400" /> Candidate Resume Intelligence
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Analyze your resume against any Job Description, identify gaps, check ATS readiness, and get grounded rewording suggestions.
            </p>
          </div>
        </div>

        {/* Input Controls */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          {/* Resume Upload */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-300">Upload Your Resume (PDF / DOCX)</label>
            <div className="border-2 border-dashed border-slate-800 hover:border-purple-500/50 rounded-xl p-4 text-center transition-all bg-slate-900/50">
              <input
                type="file"
                accept=".pdf,.docx,.doc"
                onChange={(e) => setResumeFile(e.target.files[0])}
                className="hidden"
                id="cand_resume_upload"
              />
              <label htmlFor="cand_resume_upload" className="cursor-pointer flex flex-col items-center gap-1">
                <Upload className="w-6 h-6 text-purple-400" />
                <span className="text-xs font-medium text-slate-200">
                  {resumeFile ? resumeFile.name : 'Choose Resume File'}
                </span>
                <span className="text-[10px] text-slate-500">PDF, DOCX up to 10MB</span>
              </label>
            </div>
          </div>

          {/* JD Input */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-300">Target Job Description Text</label>
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="Paste target Job Description text here..."
              rows={4}
              className="w-full bg-slate-900/80 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
            />
          </div>
        </div>

        {error && <div className="text-xs text-rose-400 bg-rose-950/40 p-3 rounded-lg border border-rose-800">{error}</div>}

        <button
          onClick={handleRunAnalysis}
          disabled={loading}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-xs shadow-lg shadow-purple-500/20 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
        >
          {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          <span>{loading ? 'Analyzing Resume & JD...' : 'Run Full Candidate Analysis'}</span>
        </button>
      </div>

      {/* Analysis Results View */}
      {results && (
        <div className="space-y-6">
          {/* Sub Navigation Tabs */}
          <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-3">
            {[
              { id: 'match', label: '🔍 Match & Skills' },
              { id: 'mismatch', label: '❌ Mismatch Factors' },
              { id: 'sections', label: '📑 Section Feedback' },
              { id: 'ats', label: '🤖 ATS Compatibility' },
              { id: 'reword', label: '✏️ Wording Improvements' }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                  activeTab === tab.id
                    ? 'bg-purple-600 text-white shadow-md shadow-purple-500/20'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* TAB 1: MATCH & SKILLS */}
          {activeTab === 'match' && (
            <div className="glass-card p-6 rounded-2xl border border-slate-800 space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold text-white">Target Match Score</h3>
                  <p className="text-xs text-slate-400">Based on transparent weighted category scoring</p>
                </div>
                <div className="text-3xl font-black text-purple-400">
                  {results.match_result.overall_match_score}%
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Strengths</h4>
                  {results.match_result.strengths.map((s, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-xs text-slate-200 bg-emerald-950/20 p-2.5 rounded-lg border border-emerald-900/40">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                      <span>{s}</span>
                    </div>
                  ))}
                </div>

                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-amber-400 uppercase tracking-wider">Gaps / Missing Requirements</h4>
                  {results.match_result.gaps.map((g, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-xs text-slate-200 bg-amber-950/20 p-2.5 rounded-lg border border-amber-900/40">
                      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                      <span>{g}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: MISMATCH FACTORS */}
          {activeTab === 'mismatch' && (
            <div className="glass-card p-6 rounded-2xl border border-slate-800 space-y-4">
              <div className="p-3 bg-amber-950/30 border border-amber-800 rounded-xl text-xs text-amber-300">
                💡 <strong>Notice:</strong> These are <strong>POSSIBLE factors</strong> based on automated comparison against the JD text. Only the hiring manager knows actual rejection criteria.
              </div>

              <div className="space-y-3">
                {results.mismatch_reasons.map((r, idx) => (
                  <div key={idx} className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-purple-400">{r.category}</span>
                      <span className="text-[10px] uppercase font-bold text-slate-400">Impact: {r.impact}</span>
                    </div>
                    <p className="text-xs text-slate-200">{r.reason}</p>
                    <p className="text-xs text-slate-400 bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                      <strong>Recommendation:</strong> {r.suggestion}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 3: SECTION FEEDBACK */}
          {activeTab === 'sections' && (
            <div className="glass-card p-6 rounded-2xl border border-slate-800 space-y-4">
              <h3 className="text-sm font-bold text-white">Section-by-Section Analysis</h3>
              <div className="space-y-4">
                {Object.entries(results.section_feedback).map(([sec, fb]) => (
                  <div key={sec} className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 space-y-2">
                    <h4 className="text-xs font-bold text-purple-400">{sec} Section</h4>
                    <p className="text-xs text-slate-300"><strong>Good:</strong> {fb.good}</p>
                    <p className="text-xs text-slate-400"><strong>Weakness:</strong> {fb.weak}</p>
                    <p className="text-xs text-emerald-400 bg-emerald-950/30 p-2.5 rounded-lg border border-emerald-900/40">
                      <strong>Actionable Fix:</strong> {fb.improvement_suggestion}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 4: ATS COMPATIBILITY */}
          {activeTab === 'ats' && (
            <div className="glass-card p-6 rounded-2xl border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white">ATS Compatibility Score</h3>
                <div className="text-xl font-bold text-sky-400">{results.ats_analysis.ats_readiness_score}%</div>
              </div>

              {results.ats_analysis.issues.map((iss, idx) => (
                <div key={idx} className="p-4 bg-amber-950/20 rounded-xl border border-amber-900/40 space-y-1">
                  <span className="text-xs font-bold text-amber-400">[{iss.check}] {iss.finding}</span>
                  <p className="text-xs text-slate-300"><strong>Recommendation:</strong> {iss.recommendation}</p>
                </div>
              ))}
            </div>
          )}

          {/* TAB 5: WORDING IMPROVEMENTS */}
          {activeTab === 'reword' && (
            <div className="glass-card p-6 rounded-2xl border border-slate-800 space-y-4">
              <h3 className="text-sm font-bold text-white">Grounded Bullet Point Rewording</h3>
              <p className="text-xs text-slate-400">Strictly preserves factual accuracy while boosting action verbs and impact.</p>

              <div className="space-y-4">
                {results.bullet_improvements.map((imp, idx) => (
                  <div key={idx} className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 space-y-2">
                    <p className="text-xs text-slate-400"><strong>Original:</strong> {imp.original}</p>
                    <p className="text-xs text-purple-300 bg-purple-950/30 p-3 rounded-lg border border-purple-900/40">
                      <strong>Suggested:</strong> {imp.suggested}
                    </p>
                    <p className="text-[11px] text-slate-500">Rationale: {imp.rationale}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
