import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ArrowRight, BadgeCheck, CircleAlert, FileAudio, FileText, Languages, Link2,
  LoaderCircle, ShieldCheck, Upload, XCircle,
} from 'lucide-react';
import {
  confirmSourceLanguage, createJob, getArtifacts, getCapabilities, getJob,
  getReport, runJob, saveCorrection, uploadDubbedArtifact, uploadJob,
} from './api';
import './styles.css';

const terminal = new Set([
  'complete', 'failed', 'awaiting_source', 'awaiting_dubbing',
  'source_language_confirmation_required',
]);

function languageName(code) {
  if (code === 'auto') return 'Auto-detect';
  try { return new Intl.DisplayNames(['en'], { type: 'language' }).of(code.split('-')[0]) || code; }
  catch { return code; }
}

function Pill({ children, tone = 'neutral' }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

function Transcript({ title, icon: Icon, transcript, empty }) {
  return (
    <article className="artifact-card">
      <div className="artifact-head"><div className="artifact-icon"><Icon size={18} /></div>
        <div><h3>{title}</h3><p>Speaker-aware normalized transcript</p></div>
        <Pill tone={transcript ? 'success' : 'neutral'}>{transcript ? 'ready' : 'pending'}</Pill>
      </div>
      <div className="transcript-preview">
        {transcript?.segments?.map((segment) => <p key={segment.segment_id}><b>{segment.speaker?.split(':').at(-1) || 'S?'}</b>{segment.text}</p>)}
        {!transcript && <p className="muted">{empty}</p>}
      </div>
    </article>
  );
}

function App() {
  const [url, setUrl] = useState('https://youtube.com/shorts/hkvERAuoaI8');
  const [capabilities, setCapabilities] = useState(null);
  const [targetLanguage, setTargetLanguage] = useState('');
  const [sourceLanguage, setSourceLanguage] = useState('auto');
  const [expectedSpeakers, setExpectedSpeakers] = useState('');
  const [authorised, setAuthorised] = useState(false);
  const [sourceFile, setSourceFile] = useState(null);
  const [dubbedFile, setDubbedFile] = useState(null);
  const [job, setJob] = useState(null);
  const [artifacts, setArtifacts] = useState({});
  const [report, setReport] = useState(null);
  const [correctionText, setCorrectionText] = useState({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getCapabilities().then((value) => {
      setCapabilities(value);
      setTargetLanguage((current) => current || value.enabled_dubbing_target_languages[0] || '');
    }).catch((reason) => setError(reason.message));
  }, []);

  async function refreshArtifacts(jobId, includeReport = false) {
    const artifactResponse = await getArtifacts(jobId);
    setArtifacts(artifactResponse.artifacts);
    if (includeReport) setReport(await getReport(jobId));
  }

  useEffect(() => {
    if (!job || terminal.has(job.status)) {
      if (job && ['awaiting_dubbing', 'source_language_confirmation_required', 'complete'].includes(job.status)) {
        refreshArtifacts(job.job_id, job.status === 'complete').catch((reason) => setError(reason.message));
      }
      return undefined;
    }
    const timer = window.setInterval(async () => {
      try {
        const next = await getJob(job.job_id);
        setJob(next);
        if (terminal.has(next.status)) {
          await refreshArtifacts(next.job_id, next.status === 'complete');
          setBusy(false);
          if (next.status === 'failed') setError(next.error || 'Review failed');
        }
      } catch (reason) { setError(reason.message); setBusy(false); }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [job?.job_id, job?.status]);

  const canStart = Boolean(capabilities && authorised && targetLanguage && (sourceFile || url.trim()));
  const activeStep = job?.status || 'created';
  const sourceTranscript = report?.source_transcript || artifacts['source_transcript.normalized.json'];
  const targetTranscript = report?.target_transcript || artifacts['target_transcript.normalized.json'];
  const effectiveSourceLanguage = job?.detected_source_language || job?.source_language || sourceLanguage;

  async function startReview() {
    setError(''); setReport(null); setArtifacts({}); setBusy(true);
    try {
      const speakers = expectedSpeakers ? Number(expectedSpeakers) : null;
      let current;
      if (sourceFile) {
        current = await uploadJob({ sourceFile, targetLanguage, sourceLanguage, expectedSpeakers: speakers, creatorAuthorised: authorised });
      } else {
        current = await createJob({ source_url: url, creator_authorised: authorised, source_language: sourceLanguage, target_language: targetLanguage, expected_speakers: speakers });
      }
      setJob(current);
      if (!current.has_source) {
        setBusy(false);
        setError('URL ingestion is disabled locally. Upload the creator-authorised source MP4 to continue.');
        return;
      }
      setJob(await runJob(current.job_id));
    } catch (reason) { setError(reason.message); setBusy(false); }
  }

  async function continueWithDub() {
    if (!job || !dubbedFile) return;
    setBusy(true); setError('');
    try { setJob(await uploadDubbedArtifact(job.job_id, dubbedFile)); }
    catch (reason) { setError(reason.message); setBusy(false); }
  }

  async function confirmLanguage() {
    if (!job) return;
    setBusy(true); setError('');
    try { setJob(await confirmSourceLanguage(job.job_id, sourceLanguage)); }
    catch (reason) { setError(reason.message); setBusy(false); }
  }

  async function labelFinding(finding, label, approved = false) {
    try {
      await saveCorrection(job.job_id, { finding_id: finding.finding_id, label, suggested_target_text: correctionText[finding.finding_id] || null, approved });
      setReport((current) => ({ ...current, findings: current.findings.map((item) => item.finding_id === finding.finding_id ? { ...item, reviewer_label: label } : item) }));
    } catch (reason) { setError(reason.message); }
  }

  const sourceOptions = capabilities?.source_stt_languages || [];
  const targetOptions = capabilities?.enabled_dubbing_target_languages || [];
  return (
    <main>
      <nav className="nav shell"><div className="brand"><div className="brand-mark">D</div><span>DubPatch</span></div><div className="nav-copy">Evidence-first review for Indic-dubbed short-form video</div><Pill tone="beta">Local reviewer</Pill></nav>
      <section className="hero shell">
        <div className="eyebrow"><ShieldCheck size={15} /> Reviewer, not certifier</div>
        <h1>Preserve the creator.<br />Inspect every drift.</h1>
        <p className="hero-copy">Provide creator-authorised source media. DubPatch detects its language, transcribes it, then guides an evidence-backed review of the selected-language dub.</p>
        <div className="composer">
          <div className="url-row"><Link2 size={19} /><input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="YouTube Short, watch, or youtu.be URL" />
            <button className="primary" disabled={!canStart || busy} onClick={startReview}>{busy ? <><LoaderCircle className="spin" size={17} /> Processing {job?.progress || 0}%</> : <>Start dubbing and review <ArrowRight size={17} /></>}</button>
          </div>
          <div className="upload-grid single-source"><label><Upload size={16} /><span>Source MP4</span><input type="file" accept="video/mp4" onChange={(event) => setSourceFile(event.target.files?.[0] || null)} /><small>{sourceFile?.name || 'Creator-authorised local source video'}</small></label></div>
          <div className="language-grid">
            <label>Source language<select value={sourceLanguage} onChange={(event) => setSourceLanguage(event.target.value)}><option value="auto">Auto-detect</option>{sourceOptions.map((code) => <option value={code} key={code}>{languageName(code)} · {code}</option>)}</select></label>
            <label>Target language<select value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)}>{targetOptions.map((code) => <option value={code} key={code}>{languageName(code)} · {code}</option>)}</select></label>
            <label>Expected speakers<select value={expectedSpeakers} onChange={(event) => setExpectedSpeakers(event.target.value)}><option value="">Auto</option>{[1, 2, 3, 4, 5, 6].map((value) => <option value={value} key={value}>{value}</option>)}</select></label>
          </div>
          <label className="authorisation"><input type="checkbox" checked={authorised} onChange={(event) => setAuthorised(event.target.checked)} />I own this content or have explicit permission to process it.</label>
          {error && <div className="input-error">{error}</div>}
        </div>
      </section>
      <section className="pipeline shell"><div className="section-heading"><div><span className="kicker">Job progress</span><h2>{job?.message || 'Ready for source media'}</h2></div>{job && <Pill>{job.status}</Pill>}</div>
        <div className="steps">{[
          ['01', 'Source ingestion', ['created', 'awaiting_source', 'extracting_audio']], ['02', 'Language detection', ['transcribing_source', 'source_language_confirmation_required']], ['03', 'Source transcription', ['transcribing_source']], ['04', 'Dubbing', ['awaiting_dubbing']], ['05', 'Target transcription', ['transcribing_target']], ['06', 'Fidelity comparison', ['back_translating', 'comparing']], ['07', 'Human review', ['complete']], ['08', 'Patched export', []],
        ].map(([number, label, states]) => <div className={`step ${states.includes(activeStep) ? 'active' : ''}`} key={number}><span>{number}</span><div><b>{label}</b><small>{states.includes(activeStep) ? 'Current stage' : 'Evidence-backed stage'}</small></div></div>)}</div>
        {job && <p className="locale-note">Source: {languageName(effectiveSourceLanguage)} · {effectiveSourceLanguage} &nbsp; Target: {languageName(job.target_language)} · {job.target_language}</p>}
      </section>
      {job?.status === 'source_language_confirmation_required' && <section className="continuation shell"><div><span className="kicker">Language confirmation</span><h2>Confirm source language</h2><p>Audio-language detection confidence was low. Select the source language before starting dubbing.</p></div><button className="primary" disabled={busy || sourceLanguage === 'auto'} onClick={confirmLanguage}>Confirm {sourceLanguage === 'auto' ? 'source language' : `${languageName(sourceLanguage)} · ${sourceLanguage}`}</button></section>}
      {job?.status === 'awaiting_dubbing' && <section className="continuation shell"><div><span className="kicker">Dubbing continuation</span><h2>Source processed successfully.</h2><p>Automatic Sarvam Dubbing is not enabled for this account. Create the {languageName(job.target_language)} · {job.target_language} dub in Sarvam Creator Studio, then upload the exported WAV or MP4.</p></div><div className="continuation-actions"><a className="secondary" href="https://studio.sarvam.ai/" target="_blank" rel="noreferrer">Open Sarvam Creator Studio</a><label className="secondary"><FileAudio size={15} />Upload exported dubbed WAV/MP4<input hidden type="file" accept=".wav,video/mp4,audio/wav" onChange={(event) => setDubbedFile(event.target.files?.[0] || null)} /></label><button className="primary" disabled={!dubbedFile || busy} onClick={continueWithDub}>Resume review</button></div></section>}
      <section className="workspace shell"><div className="section-heading compact"><div><span className="kicker">Artifacts</span><h2>Actual transcripts</h2></div><Pill tone={report ? 'success' : 'neutral'}>{languageName(job?.target_language || targetLanguage)}</Pill></div><div className="artifact-grid"><Transcript title={`${languageName(effectiveSourceLanguage)} source transcript`} icon={FileText} transcript={sourceTranscript} empty="Run source processing to generate the source transcript." /><Transcript title={`${languageName(job?.target_language || targetLanguage)} dubbed transcript`} icon={Languages} transcript={targetTranscript} empty="Upload the Creator Studio export after source processing." /></div></section>
      <section className="review shell"><div className="section-heading compact"><div><span className="kicker">Fidelity report</span><h2>{report ? `${report.misinterpreted_items.length} items require review` : 'No generated report yet'}</h2></div>{report && <Pill tone={report.status === 'preserved' ? 'success' : 'danger'}>{report.status}</Pill>}</div>{!report ? <div className="empty-state"><CircleAlert size={26} /><h3>Waiting for real evidence</h3><p>No mock findings are rendered in this path.</p></div> : <div className="review-layout"><div className="issues">{report.findings.map((finding) => <article className={`issue issue-${finding.severity}`} key={finding.finding_id}><div className="issue-body"><div className="issue-title-row"><div><Pill tone={finding.preserved ? 'success' : finding.severity === 'critical' ? 'danger' : 'warning'}>{finding.severity}</Pill><h3>{finding.category}</h3></div></div><div className="compare-grid"><div><small>Source</small><p>{finding.source_text || '—'}</p></div><div><small>Dubbed</small><p>{finding.target_text || '—'}</p></div><div><small>Back-translation</small><p>{finding.english_back_translation || '—'}</p></div></div><p className="issue-note">{finding.evidence}</p><input className="correction-input" value={correctionText[finding.finding_id] || ''} onChange={(event) => setCorrectionText((current) => ({ ...current, [finding.finding_id]: event.target.value }))} placeholder="Optional corrected target text" /><div className="issue-actions"><button className="secondary" onClick={() => labelFinding(finding, 'true_issue')}><BadgeCheck size={15} />Accept issue</button><button className="secondary" onClick={() => labelFinding(finding, 'false_alarm')}><XCircle size={15} />False alarm</button><button className="secondary" onClick={() => labelFinding(finding, 'cannot_judge')}>Cannot judge</button><button className="secondary" disabled={!correctionText[finding.finding_id]} onClick={() => labelFinding(finding, 'true_issue', true)}>Approve correction</button>{finding.reviewer_label && <Pill>{finding.reviewer_label}</Pill>}</div></div></article>)}</div><aside className="ledger"><span className="kicker">Review ledger</span><h3>Exact findings</h3><div className="ledger-list">{report.misinterpreted_items.map((finding) => <div className="ledger-row fail" key={finding.finding_id}><XCircle size={17} /><span>{finding.category}</span></div>)}</div><p className="ledger-foot">{report.note}</p></aside></div>}</section>
      <footer className="footer shell"><div><b>DubPatch</b><span>Local media, cached provider responses, human review.</span></div><span>UTF-8 · {job?.target_language || targetLanguage}</span></footer>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
