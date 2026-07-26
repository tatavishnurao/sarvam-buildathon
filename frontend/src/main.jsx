import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ArrowRight,
  BadgeCheck,
  CircleAlert,
  FileAudio,
  FileText,
  Languages,
  Link2,
  LoaderCircle,
  ShieldCheck,
  Upload,
  XCircle,
} from 'lucide-react';
import {
  createJob,
  getArtifacts,
  getJob,
  getReport,
  runJob,
  saveCorrection,
  uploadJob,
} from './api';
import './styles.css';

const languages = [
  ['Telugu', 'te-IN'],
  ['Hindi', 'hi-IN'],
  ['Tamil', 'ta-IN'],
  ['Kannada', 'kn-IN'],
  ['Bengali', 'bn-IN'],
  ['Marathi', 'mr-IN'],
  ['Gujarati', 'gu-IN'],
  ['Malayalam', 'ml-IN'],
  ['Punjabi', 'pa-IN'],
  ['Odia', 'od-IN'],
  ['Assamese', 'as-IN'],
];

const terminal = new Set(['complete', 'failed', 'awaiting_source', 'awaiting_dubbed_artifact']);

function Pill({ children, tone = 'neutral' }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

function Transcript({ title, icon: Icon, transcript, empty }) {
  return (
    <article className="artifact-card">
      <div className="artifact-head">
        <div className="artifact-icon"><Icon size={18} /></div>
        <div><h3>{title}</h3><p>Speaker-aware normalized transcript</p></div>
        <Pill tone={transcript ? 'success' : 'neutral'}>{transcript ? 'ready' : 'pending'}</Pill>
      </div>
      <div className="transcript-preview">
        {transcript?.segments?.map((segment) => (
          <p key={segment.segment_id}>
            <b>{segment.speaker?.split(':').at(-1) || 'S?'}</b>
            {segment.text}
          </p>
        ))}
        {!transcript && <p className="muted">{empty}</p>}
      </div>
    </article>
  );
}

function App() {
  const [url, setUrl] = useState('https://youtube.com/shorts/hkvERAuoaI8');
  const [targetLanguage, setTargetLanguage] = useState('te-IN');
  const [authorised, setAuthorised] = useState(false);
  const [sourceFile, setSourceFile] = useState(null);
  const [targetFile, setTargetFile] = useState(null);
  const [job, setJob] = useState(null);
  const [artifacts, setArtifacts] = useState({});
  const [report, setReport] = useState(null);
  const [correctionText, setCorrectionText] = useState({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const canStart = authorised && (sourceFile || url.trim());
  const languageName = useMemo(
    () => languages.find(([, code]) => code === targetLanguage)?.[0] || targetLanguage,
    [targetLanguage],
  );

  useEffect(() => {
    if (!job || terminal.has(job.status)) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const next = await getJob(job.job_id);
        setJob(next);
        if (next.status === 'complete') {
          const [artifactResponse, reportResponse] = await Promise.all([
            getArtifacts(next.job_id),
            getReport(next.job_id),
          ]);
          setArtifacts(artifactResponse.artifacts);
          setReport(reportResponse);
          setBusy(false);
        }
        if (next.status === 'failed') {
          setError(next.error || 'Review failed');
          setBusy(false);
        }
      } catch (pollError) {
        setError(pollError.message);
        setBusy(false);
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [job?.job_id, job?.status]);

  async function startReview() {
    setError('');
    setReport(null);
    setArtifacts({});
    setBusy(true);
    try {
      let current;
      if (sourceFile) {
        current = await uploadJob({
          sourceFile,
          targetFile,
          targetLanguage,
          creatorAuthorised: authorised,
        });
      } else {
        current = await createJob({
          source_url: url,
          creator_authorised: authorised,
          source_language: 'en-IN',
          target_language: targetLanguage,
          expected_speakers: 2,
        });
        if (targetFile) {
          current = await uploadJob({
            jobId: current.job_id,
            targetFile,
            targetLanguage,
            creatorAuthorised: authorised,
          });
        }
      }
      setJob(current);
      if (!current.has_source) {
        setBusy(false);
        setError('The URL was recorded, but URL downloading is disabled. Upload the local source MP4.');
        return;
      }
      if (!current.has_target) {
        setBusy(false);
        setError('Upload the Sarvam Creator Studio dubbed WAV or MP4 to continue.');
        return;
      }
      setJob(await runJob(current.job_id));
    } catch (requestError) {
      setError(requestError.message);
      setBusy(false);
    }
  }

  async function labelFinding(finding, label, approved = false) {
    try {
      await saveCorrection(job.job_id, {
        finding_id: finding.finding_id,
        label,
        suggested_target_text: correctionText[finding.finding_id] || null,
        approved,
      });
      setReport((current) => ({
        ...current,
        findings: current.findings.map((item) => (
          item.finding_id === finding.finding_id ? { ...item, reviewer_label: label } : item
        )),
      }));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  const sourceTranscript = report?.source_transcript || artifacts['source_transcript.normalized.json'];
  const targetTranscript = report?.target_transcript || artifacts['target_transcript.normalized.json'];
  const activeStep = job?.status || 'created';

  return (
    <main>
      <nav className="nav shell">
        <div className="brand"><div className="brand-mark">D</div><span>DubPatch</span></div>
        <div className="nav-copy">Evidence-first review for Indic-dubbed short-form video</div>
        <Pill tone="beta">Local reviewer</Pill>
      </nav>

      <section className="hero shell">
        <div className="eyebrow"><ShieldCheck size={15} /> Reviewer, not certifier</div>
        <h1>Preserve the creator.<br />Inspect every drift.</h1>
        <p className="hero-copy">
          Upload creator-authorised source media and a Sarvam-dubbed artifact. The backend
          transcribes both, back-translates the dub, aligns dialogue, and returns exact evidence.
        </p>

        <div className="composer">
          <div className="url-row">
            <Link2 size={19} />
            <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="YouTube Short, watch, or youtu.be URL" />
            <select value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)}>
              {languages.map(([name, code]) => <option value={code} key={code}>{name}</option>)}
            </select>
            <button className="primary" disabled={!canStart || busy} onClick={startReview}>
              {busy ? <><LoaderCircle className="spin" size={17} /> Processing {job?.progress || 0}%</> : <>Start review <ArrowRight size={17} /></>}
            </button>
          </div>
          <div className="upload-grid">
            <label><Upload size={16} /><span>Source MP4</span><input type="file" accept="video/mp4" onChange={(event) => setSourceFile(event.target.files?.[0] || null)} /><small>{sourceFile?.name || 'Required when URL ingest is disabled'}</small></label>
            <label><FileAudio size={16} /><span>Dubbed WAV/MP4</span><input type="file" accept=".wav,video/mp4,audio/wav" onChange={(event) => setTargetFile(event.target.files?.[0] || null)} /><small>{targetFile?.name || 'Manual Sarvam artifact'}</small></label>
          </div>
          <label className="authorisation">
            <input type="checkbox" checked={authorised} onChange={(event) => setAuthorised(event.target.checked)} />
            I own this content or have explicit permission to process it.
          </label>
          {error && <div className="input-error">{error}</div>}
        </div>
      </section>

      <section className="pipeline shell">
        <div className="section-heading"><div><span className="kicker">Job progress</span><h2>{job?.message || 'Ready for local artifacts'}</h2></div>{job && <Pill>{job.status}</Pill>}</div>
        <div className="steps">
          {[
            ['01', 'Source', ['created', 'extracting_audio']],
            ['02', 'Transcripts', ['transcribing_source', 'transcribing_target']],
            ['03', 'Back-translation', ['back_translating']],
            ['04', 'Fidelity report', ['comparing', 'complete']],
          ].map(([number, label, states]) => (
            <div className={`step ${states.includes(activeStep) ? 'active' : ''}`} key={number}>
              <span>{number}</span><div><b>{label}</b><small>{states.includes(activeStep) ? 'In progress' : 'Evidence-backed stage'}</small></div>
            </div>
          ))}
        </div>
      </section>

      <section className="workspace shell">
        <div className="section-heading compact"><div><span className="kicker">Artifacts</span><h2>Actual transcripts</h2></div><Pill tone={report ? 'success' : 'neutral'}>{languageName}</Pill></div>
        <div className="artifact-grid">
          <Transcript title="English source transcript" icon={FileText} transcript={sourceTranscript} empty="Run a job to generate the source transcript." />
          <Transcript title={`${languageName} dubbed transcript`} icon={Languages} transcript={targetTranscript} empty="Upload and process the dubbed artifact." />
        </div>
      </section>

      <section className="review shell">
        <div className="section-heading compact">
          <div><span className="kicker">Fidelity report</span><h2>{report ? `${report.misinterpreted_items.length} items require review` : 'No generated report yet'}</h2></div>
          {report && <Pill tone={report.status === 'preserved' ? 'success' : 'danger'}>{report.status}</Pill>}
        </div>
        {!report ? (
          <div className="empty-state"><CircleAlert size={26} /><h3>Waiting for real evidence</h3><p>No mock findings are rendered in this path.</p></div>
        ) : (
          <div className="review-layout">
            <div className="issues">
              {report.findings.map((finding) => (
                <article className={`issue issue-${finding.severity}`} key={finding.finding_id}>
                  <div className="issue-body">
                    <div className="issue-title-row"><div><Pill tone={finding.preserved ? 'success' : finding.severity === 'critical' ? 'danger' : 'warning'}>{finding.severity}</Pill><h3>{finding.category}</h3></div></div>
                    <div className="compare-grid">
                      <div><small>Source</small><p>{finding.source_text || '—'}</p></div>
                      <div><small>Dubbed</small><p>{finding.target_text || '—'}</p></div>
                      <div><small>Back-translation</small><p>{finding.english_back_translation || '—'}</p></div>
                    </div>
                    <p className="issue-note">{finding.evidence}</p>
                    <input
                      className="correction-input"
                      value={correctionText[finding.finding_id] || ''}
                      onChange={(event) => setCorrectionText((current) => ({
                        ...current,
                        [finding.finding_id]: event.target.value,
                      }))}
                      placeholder="Optional corrected target text"
                    />
                    <div className="issue-actions">
                      <button className="secondary" onClick={() => labelFinding(finding, 'true_issue')}><BadgeCheck size={15} /> Accept issue</button>
                      <button className="secondary" onClick={() => labelFinding(finding, 'false_alarm')}><XCircle size={15} /> False alarm</button>
                      <button className="secondary" onClick={() => labelFinding(finding, 'cannot_judge')}>Cannot judge</button>
                      <button className="secondary" disabled={!correctionText[finding.finding_id]} onClick={() => labelFinding(finding, 'true_issue', true)}>Approve correction</button>
                      {finding.reviewer_label && <Pill>{finding.reviewer_label}</Pill>}
                    </div>
                  </div>
                </article>
              ))}
            </div>
            <aside className="ledger">
              <span className="kicker">Review ledger</span>
              <h3>Exact findings</h3>
              <div className="ledger-list">
                {report.misinterpreted_items.map((finding) => (
                  <div className="ledger-row fail" key={finding.finding_id}><XCircle size={17} /><span>{finding.category}</span></div>
                ))}
              </div>
              <p className="ledger-foot">{report.note}</p>
            </aside>
          </div>
        )}
      </section>

      <footer className="footer shell"><div><b>DubPatch</b><span>Local media, cached provider responses, human review.</span></div><span>UTF-8 · {targetLanguage}</span></footer>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
