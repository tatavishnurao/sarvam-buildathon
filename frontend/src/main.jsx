import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ArrowRight,
  BadgeCheck,
  CircleAlert,
  FileAudio,
  FileText,
  Languages,
  Link2,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Upload,
  WandSparkles,
  XCircle,
} from 'lucide-react';
import './styles.css';

const languages = [
  'Telugu', 'Hindi', 'Tamil', 'Kannada', 'Bengali', 'Marathi',
  'Gujarati', 'Malayalam', 'Punjabi', 'Odia', 'Assamese'
];

const demoIssues = [
  {
    severity: 'critical',
    label: 'Unsupported dialogue',
    source: '“Stradman does.”',
    dubbed: '“నా ముక్కు మీద కొట్టు.”',
    note: 'The target line introduces meaning that does not exist in the source.',
    time: '00:03–00:05',
  },
  {
    severity: 'critical',
    label: 'Technical term drift',
    source: '“It’s rear-wheel drive.”',
    dubbed: '“మాన్స్టర్ వీల్ డ్రైవ్.”',
    note: 'Rear-wheel drive is not preserved as an automotive term.',
    time: '00:20–00:22',
  },
  {
    severity: 'major',
    label: 'Entity pronunciation',
    source: '“Lamborghini Gallardo”',
    dubbed: '“ల్యాంబోర్కిని గ్వాడో”',
    note: 'Brand and model identity are phonetically corrupted.',
    time: '00:00–00:02',
  },
  {
    severity: 'minor',
    label: 'Creator register drift',
    source: '“mate”',
    dubbed: '“బాస్”',
    note: 'The conversational persona changes from “mate” to “boss”.',
    time: '00:18–00:19',
  },
];

function Pill({ children, tone = 'neutral' }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

function ArtifactCard({ icon: Icon, title, meta, state, children }) {
  return (
    <article className="artifact-card">
      <div className="artifact-head">
        <div className="artifact-icon"><Icon size={18} /></div>
        <div>
          <h3>{title}</h3>
          <p>{meta}</p>
        </div>
        <Pill tone={state === 'ready' ? 'success' : 'neutral'}>{state}</Pill>
      </div>
      {children}
    </article>
  );
}

function App() {
  const [url, setUrl] = useState('https://youtube.com/shorts/hkvERAuoaI8');
  const [language, setLanguage] = useState('Telugu');
  const [running, setRunning] = useState(false);
  const [complete, setComplete] = useState(false);

  const valid = useMemo(() => /^https?:\/\/(www\.)?(youtube\.com|youtu\.be)\//i.test(url), [url]);

  function runDemo() {
    if (!valid) return;
    setRunning(true);
    setComplete(false);
    window.setTimeout(() => {
      setRunning(false);
      setComplete(true);
      document.getElementById('review')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 1600);
  }

  return (
    <main>
      <nav className="nav shell">
        <div className="brand"><div className="brand-mark">D</div><span>DubPatch</span></div>
        <div className="nav-copy">Authenticity review for Indic-dubbed short-form video</div>
        <Pill tone="beta">Buildathon prototype</Pill>
      </nav>

      <section className="hero shell">
        <div className="eyebrow"><Sparkles size={15}/> Sarvam-powered dubbing review</div>
        <h1>Preserve the creator.<br/>Not just the translation.</h1>
        <p className="hero-copy">
          Paste a creator-authorised YouTube Short, generate an Indic dub, and review exactly where facts,
          technical terms, speaker attribution, tone or punchlines drifted.
        </p>

        <div className="composer">
          <div className="url-row">
            <Link2 size={19} />
            <input
              aria-label="YouTube Short URL"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Paste a YouTube Short link"
            />
            <select value={language} onChange={(e) => setLanguage(e.target.value)} aria-label="Target language">
              {languages.map((item) => <option key={item}>{item}</option>)}
            </select>
            <button className="primary" disabled={!valid || running} onClick={runDemo}>
              {running ? <><RefreshCw className="spin" size={17}/> Analysing</> : <>Start review <ArrowRight size={17}/></>}
            </button>
          </div>
          {!valid && <div className="input-error">Enter a valid YouTube or youtu.be URL.</div>}
          <div className="composer-foot">
            <span><ShieldCheck size={15}/> Use content you own or have permission to process.</span>
            <button className="text-button"><Upload size={15}/> Upload a local video instead</button>
          </div>
        </div>
      </section>

      <section className="pipeline shell">
        <div className="section-heading">
          <div>
            <span className="kicker">Golden path</span>
            <h2>One short. Two evidence streams. One review ledger.</h2>
          </div>
        </div>
        <div className="steps">
          <div className="step active"><span>01</span><div><b>Source capture</b><small>Video, English transcript, speakers and timestamps</small></div></div>
          <ArrowRight className="step-arrow" size={18}/>
          <div className="step"><span>02</span><div><b>Sarvam dub</b><small>{language} transcript, dubbed WAV and timing blocks</small></div></div>
          <ArrowRight className="step-arrow" size={18}/>
          <div className="step"><span>03</span><div><b>Fidelity judge</b><small>Facts, entities, attribution, register and narrative structure</small></div></div>
          <ArrowRight className="step-arrow" size={18}/>
          <div className="step"><span>04</span><div><b>Human-approved patch</b><small>Regenerate only affected dialogue blocks</small></div></div>
        </div>
      </section>

      <section className="workspace shell">
        <div className="section-heading compact">
          <div>
            <span className="kicker">Artifacts</span>
            <h2>Everything the judge needs</h2>
          </div>
          <Pill tone="success"><BadgeCheck size={13}/> auditable</Pill>
        </div>
        <div className="artifact-grid">
          <ArtifactCard icon={Play} title="Source Short" meta="Creator-authorised media" state="ready">
            <div className="video-placeholder">
              <div className="video-gradient"></div>
              <button className="play-button"><Play size={18} fill="currentColor"/></button>
              <div className="video-caption">A sad story… #stradman #lamborghini</div>
            </div>
          </ArtifactCard>
          <ArtifactCard icon={FileText} title="English transcript" meta="Speaker-aware semantic source" state="ready">
            <div className="transcript-preview">
              <p><b>S1</b> I just built the fastest Lamborghini Gallardo.</p>
              <p><b>S2</b> No, you didn’t.</p>
              <p><b>S1</b> Why?</p>
              <p><b>S2</b> Stradman does.</p>
              <p className="fade-line">…</p>
            </div>
          </ArtifactCard>
          <ArtifactCard icon={Languages} title={`${language} transcript`} meta="Round-trip transcript from dubbed audio" state={complete ? 'ready' : 'pending'}>
            <div className="transcript-preview target">
              <p><b>S1</b> నేను ఫాస్టెస్ట్ ల్యాంబోర్కిని గ్వాడో చేశాను.</p>
              <p><b>S1</b> లేదు, ఎందుకు? నా ముక్కు మీద కొట్టు.</p>
              <p><b>S2</b> కానీ నాది వెయ్యి హార్స్ పవర్.</p>
              <p className="fade-line">…</p>
            </div>
          </ArtifactCard>
          <ArtifactCard icon={FileAudio} title="Dubbed audio" meta="24 kHz mono WAV · 31.25 seconds" state={complete ? 'ready' : 'pending'}>
            <div className="waveform" aria-label="Decorative audio waveform">
              {[14,28,20,44,34,58,22,46,26,62,39,52,18,36,48,24,60,43,29,54,31,45,21,34,56,28,47,38,20,50,33,42].map((h,i)=><i key={i} style={{height:`${h}px`}}></i>)}
            </div>
            <div className="audio-actions"><button><Play size={15}/> Play dub</button><button><FileAudio size={15}/> Download WAV</button></div>
          </ArtifactCard>
        </div>
      </section>

      <section id="review" className="review shell">
        <div className="section-heading compact">
          <div>
            <span className="kicker">Fidelity report</span>
            <h2>{complete ? 'Four segments require review' : 'Run the review to generate findings'}</h2>
          </div>
          {complete && <div className="summary-pills"><Pill tone="danger">2 critical</Pill><Pill tone="warning">1 major</Pill><Pill>1 minor</Pill></div>}
        </div>

        {!complete ? (
          <div className="empty-state">
            <WandSparkles size={26}/>
            <h3>No review generated yet</h3>
            <p>The interface is ready. Start the demo analysis above to reveal the judge workflow.</p>
          </div>
        ) : (
          <div className="review-layout">
            <div className="issues">
              {demoIssues.map((issue, idx) => (
                <article className={`issue issue-${issue.severity}`} key={issue.label}>
                  <div className="issue-number">{String(idx + 1).padStart(2, '0')}</div>
                  <div className="issue-body">
                    <div className="issue-title-row">
                      <div><Pill tone={issue.severity === 'critical' ? 'danger' : issue.severity === 'major' ? 'warning' : 'neutral'}>{issue.severity}</Pill><h3>{issue.label}</h3></div>
                      <span>{issue.time}</span>
                    </div>
                    <div className="compare-grid">
                      <div><small>Source</small><p>{issue.source}</p></div>
                      <div><small>Dubbed</small><p>{issue.dubbed}</p></div>
                    </div>
                    <p className="issue-note">{issue.note}</p>
                    <div className="issue-actions">
                      <button className="secondary"><Play size={15}/> Compare audio</button>
                      <button className="secondary"><FileText size={15}/> Edit translation</button>
                      <button className="patch"><WandSparkles size={15}/> Patch block</button>
                    </div>
                  </div>
                </article>
              ))}
            </div>

            <aside className="ledger">
              <span className="kicker">Authenticity ledger</span>
              <h3>What survived?</h3>
              <div className="ledger-list">
                <div className="ledger-row ok"><BadgeCheck size={17}/><span>1,000 horsepower</span></div>
                <div className="ledger-row ok"><BadgeCheck size={17}/><span>1,300 horsepower</span></div>
                <div className="ledger-row ok"><BadgeCheck size={17}/><span>Twin-turbo comparison</span></div>
                <div className="ledger-row warn"><CircleAlert size={17}/><span>Lamborghini Gallardo</span></div>
                <div className="ledger-row fail"><XCircle size={17}/><span>Stradman attribution</span></div>
                <div className="ledger-row fail"><XCircle size={17}/><span>Rear-wheel drive</span></div>
                <div className="ledger-row ok"><BadgeCheck size={17}/><span>Subscriber punchline</span></div>
              </div>
              <div className="ledger-score"><div><strong>71%</strong><span>critical atoms preserved</span></div></div>
              <button className="primary wide"><WandSparkles size={16}/> Generate reviewed version</button>
              <p className="ledger-foot">Human approval remains mandatory before export.</p>
            </aside>
          </div>
        )}
      </section>

      <footer className="footer shell">
        <div><b>DubPatch</b><span>Built around Sarvam Dubbing for creator-controlled, Indic short-form localisation.</span></div>
        <span>Frontend prototype · no live API calls</span>
      </footer>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
