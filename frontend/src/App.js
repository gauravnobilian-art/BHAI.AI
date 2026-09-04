import { useState, useRef, useEffect, useCallback } from "react";
import "@/App.css";
import { API, http } from "./http";
import { BuilderProvider, useBuilder } from "./builder/BuilderContext";
import HouseBuild from "./builder/HouseBuild";
import AgentPanel from "./builder/AgentPanel";
import {
  MessageSquare, Mail, Search, Image as ImageIcon, Rocket,
  Send, Download, Copy, Check, Sparkles, Wand2, Mic, Volume2, VolumeX, LogOut, Trash2,
  LayoutDashboard, Shield, Radio, Users, Plus, Hammer,
} from "lucide-react";

const TABS = [
  { id: "build", label: "Builder", icon: Rocket },
  { id: "team", label: "Team", icon: Users },
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "email", label: "Email", icon: Mail },
  { id: "research", label: "Research", icon: Search },
  { id: "image", label: "Images", icon: ImageIcon },
];

function Spinner() { return <span className="jv-spin" />; }

function playBootSound() {
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    const ctx = new AC();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.connect(g); g.connect(ctx.destination);
    o.type = "sine";
    o.frequency.setValueAtTime(140, ctx.currentTime);
    o.frequency.exponentialRampToValueAtTime(560, ctx.currentTime + 1.0);
    g.gain.setValueAtTime(0.0001, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.22, ctx.currentTime + 0.5);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 1.5);
    o.start(); o.stop(ctx.currentTime + 1.6);
  } catch { /* noop */ }
}

function BootScreen() {
  return (
    <div className="jv-boot">
      <img src="/bhaiya-mascot.png" alt="Bhaiya" style={{ width: 150, filter: "drop-shadow(0 0 30px rgba(229,169,60,.4))" }} />
      <div className="jv-hero jv-boot-title" style={{ fontSize: "2.6rem", marginTop: "1rem" }}>Bhai.AI</div>
      <p className="jv-muted jv-mono jv-boot-sub" style={{ marginTop: ".6rem" }}>BHAIYA KO JAGAYA JA RAHA HAI…</p>
    </div>
  );
}

function speak(text) {
  try {
    const u = new SpeechSynthesisUtterance(String(text).slice(0, 3000));
    u.rate = 1.03;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  } catch { /* noop */ }
}

/* ------------------------------- Chat ------------------------------- */
function ChatTab({ readAloud, wakeSignal }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [style, setStyle] = useState("");
  const [loading, setLoading] = useState(false);
  const [rec, setRec] = useState(false);
  const endRef = useRef(null);
  const recogRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  useEffect(() => {
    http.get("/history/chat").then(({ data }) => setMessages(data.messages || [])).catch(() => {});
  }, []);

  const send = async (text) => {
    const content = (text ?? input).trim();
    if (!content || loading) return;
    const next = [...messages, { role: "user", content }];
    setMessages(next); setInput(""); setLoading(true);
    try {
      const { data } = await http.post("/chat", { messages: next, style });
      setMessages([...next, { role: "assistant", content: data.reply }]);
      setStyle("");
      if (readAloud) speak(data.reply);
    } catch {
      setMessages([...next, { role: "assistant", content: "⚠️ Bhai se baat nahi ho paayi." }]);
    } finally { setLoading(false); }
  };

  const mic = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert("Voice input isn't supported in this browser."); return; }
    if (rec) { recogRef.current?.stop(); return; }
    const r = new SR(); recogRef.current = r; r.lang = "en-IN"; r.interimResults = false;
    r.onresult = (e) => { const t = e.results[0][0].transcript; setInput(t); setTimeout(() => send(t), 200); };
    r.onend = () => setRec(false);
    r.onerror = () => setRec(false);
    setRec(true); r.start();
  };

  const clear = async () => { await http.delete("/history/chat").catch(() => {}); setMessages([]); };

  useEffect(() => { if (wakeSignal) { mic(); } // eslint-disable-next-line
  }, [wakeSignal]);

  const presets = [
    { k: "professional", label: "Professional" },
    { k: "summarize", label: "Summarize" },
    { k: "tone", label: "Change Tone" },
  ];

  return (
    <div data-testid="chat-tab">
      <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap", marginBottom: "1rem", alignItems: "center" }}>
        {presets.map((p) => (
          <button key={p.k} data-testid={`chat-preset-${p.k}`}
            className={`jv-preset ${style === p.k ? "active" : ""}`}
            onClick={() => setStyle(style === p.k ? "" : p.k)}>{p.label}</button>
        ))}
        {messages.length > 0 && (
          <button className="jv-preset" onClick={clear} style={{ marginLeft: "auto" }}>
            <Trash2 size={13} /> Clear
          </button>
        )}
      </div>
      <div className="jv-card" style={{ padding: "1rem", minHeight: 340, maxHeight: 440, overflowY: "auto", marginBottom: "1rem" }}>
        {messages.length === 0 && <p className="jv-muted">Bol Bhai — kya poochhna hai? Type or speak your question.</p>}
        {messages.map((m, i) => (
          <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start", marginBottom: ".7rem" }}>
            <div className={`jv-bubble ${m.role}`} style={{ maxWidth: "85%", whiteSpace: "pre-wrap" }}>{m.content}</div>
          </div>
        ))}
        {loading && <div className="jv-muted" style={{ display: "flex", gap: ".5rem", alignItems: "center" }}><Spinner /> Soch raha hoon…</div>}
        <div ref={endRef} />
      </div>
      <div style={{ display: "flex", gap: ".6rem" }}>
        <button data-testid="chat-mic" className={`jv-btn jv-btn-ghost jv-mic ${rec ? "rec" : ""}`} onClick={mic} title="Voice input"><Mic size={16} /></button>
        <input data-testid="chat-input" className="jv-input" placeholder="Bhai se poochho…"
          value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} />
        <button data-testid="chat-send" className="jv-btn" onClick={() => send()} disabled={loading}><Send size={16} /> Send</button>
      </div>
    </div>
  );
}

/* ------------------------------- Email ------------------------------- */
function CopyBtn({ text }) {
  const [state, setState] = useState("idle");
  const copy = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
      else {
        const ta = document.createElement("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
        document.body.appendChild(ta); ta.focus(); ta.select(); document.execCommand("copy"); document.body.removeChild(ta);
      }
      setState("done");
    } catch { setState("fail"); }
    setTimeout(() => setState("idle"), 1800);
  };
  return (
    <button data-testid="copy-btn" className="jv-btn jv-btn-ghost" onClick={copy}>
      {state === "done" ? <Check size={16} /> : <Copy size={16} />} {state === "done" ? "Copied" : state === "fail" ? "Press Ctrl+C" : "Copy"}
    </button>
  );
}

function EmailTab() {
  const [recipient, setRecipient] = useState("");
  const [tone, setTone] = useState("Polite");
  const [context, setContext] = useState("");
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);

  const load = useCallback(() => http.get("/history/emails").then(({ data }) => setHistory(data.emails || [])).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const gen = async () => {
    if (!context.trim() || loading) return;
    setLoading(true); setDraft("");
    try { const { data } = await http.post("/email", { recipient, tone, context }); setDraft(data.draft); load(); }
    catch { setDraft("⚠️ Failed to generate email."); }
    finally { setLoading(false); }
  };

  return (
    <div data-testid="email-tab">
      <div className="jv-grid-2" style={{ marginBottom: ".8rem" }}>
        <input data-testid="email-recipient" className="jv-input" placeholder="Recipient (e.g. Hiring Manager)" value={recipient} onChange={(e) => setRecipient(e.target.value)} />
        <select data-testid="email-tone" className="jv-select" value={tone} onChange={(e) => setTone(e.target.value)}>
          {["Polite", "Urgent", "Casual", "Formal", "Persuasive"].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      <textarea data-testid="email-context" className="jv-textarea" placeholder="What is this email about? What's your goal?" value={context} onChange={(e) => setContext(e.target.value)} />
      <div style={{ marginTop: ".8rem" }}>
        <button data-testid="email-generate" className="jv-btn" onClick={gen} disabled={loading}>{loading ? <Spinner /> : <Sparkles size={16} />} Generate</button>
      </div>
      {draft && (
        <div className="jv-card" style={{ padding: "1rem", marginTop: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: ".6rem" }}><strong>Draft</strong><CopyBtn text={draft} /></div>
          <pre className="jv-mono" data-testid="email-draft" style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: ".85rem" }}>{draft}</pre>
        </div>
      )}
      {history.length > 0 && (
        <div style={{ marginTop: "1.2rem" }}>
          <div className="jv-muted jv-mono" style={{ marginBottom: ".5rem" }}>SAVED DRAFTS ({history.length})</div>
          {history.map((e) => (
            <div key={e.id} className="jv-card" style={{ padding: ".7rem 1rem", marginBottom: ".5rem" }}>
              <strong>{e.recipient || "—"}</strong> <span className="jv-muted">· {e.tone}</span>
              <div className="jv-muted" style={{ fontSize: ".85rem", marginTop: ".2rem" }}>{e.context.slice(0, 90)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------- Research ------------------------------- */
function ResearchTab() {
  const [query, setQuery] = useState(""); const [summary, setSummary] = useState("");
  const [sources, setSources] = useState([]); const [loading, setLoading] = useState(false);
  const go = async () => {
    if (!query.trim() || loading) return;
    setLoading(true); setSummary(""); setSources([]);
    try { const { data } = await http.post("/research", { query }); setSummary(data.summary); setSources(data.sources || []); }
    catch { setSummary("⚠️ Research failed."); }
    finally { setLoading(false); }
  };
  return (
    <div data-testid="research-tab">
      <div style={{ display: "flex", gap: ".6rem" }}>
        <input data-testid="research-query" className="jv-input" placeholder="Scan the live web…" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && go()} />
        <button data-testid="research-go" className="jv-btn" onClick={go} disabled={loading}>{loading ? <Spinner /> : <Search size={16} />} Scan</button>
      </div>
      {summary && <div className="jv-card" data-testid="research-summary" style={{ padding: "1.1rem", marginTop: "1rem", whiteSpace: "pre-wrap" }}>{summary}</div>}
      {sources.length > 0 && (
        <div className="jv-card" style={{ padding: "1rem", marginTop: ".8rem" }}>
          <strong>Sources</strong>
          <ol style={{ margin: ".5rem 0 0", paddingLeft: "1.2rem" }}>
            {sources.map((s, i) => <li key={i} style={{ marginBottom: ".3rem" }}><a href={s.href} target="_blank" rel="noreferrer" style={{ color: "var(--gold)" }}>{s.title || s.href}</a></li>)}
          </ol>
        </div>
      )}
    </div>
  );
}

/* ------------------------------- Image ------------------------------- */
function ImageTab() {
  const [prompt, setPrompt] = useState(""); const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false); const [err, setErr] = useState(false);
  const [w, setW] = useState(1024); const [h, setH] = useState(1024);
  const gen = () => {
    if (!prompt.trim()) return; setLoading(true); setErr(false);
    const seed = Math.floor(Math.random() * 1e6);
    setUrl(`https://image.pollinations.ai/prompt/${encodeURIComponent(prompt.trim())}?width=${w}&height=${h}&nologo=true&seed=${seed}`);
  };
  return (
    <div data-testid="image-tab">
      <textarea data-testid="image-prompt" className="jv-textarea" style={{ minHeight: 90 }} placeholder="Describe your image — a Madhubani-style peacock, vibrant, 8k" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
      <div style={{ display: "flex", gap: ".8rem", alignItems: "center", marginTop: ".8rem", flexWrap: "wrap" }}>
        <select data-testid="image-width" className="jv-select" style={{ width: 130 }} value={w} onChange={(e) => setW(+e.target.value)}>{[512, 768, 1024].map((n) => <option key={n} value={n}>W {n}</option>)}</select>
        <select data-testid="image-height" className="jv-select" style={{ width: 130 }} value={h} onChange={(e) => setH(+e.target.value)}>{[512, 768, 1024].map((n) => <option key={n} value={n}>H {n}</option>)}</select>
        <button data-testid="image-generate" className="jv-btn" onClick={gen}><Wand2 size={16} /> Generate</button>
      </div>
      {url && (
        <div className="jv-card" style={{ padding: "1rem", marginTop: "1rem", textAlign: "center" }}>
          {loading && <div className="jv-muted" style={{ marginBottom: ".5rem", display: "flex", gap: ".5rem", justifyContent: "center" }}><Spinner /> Rendering…</div>}
          {err && <div style={{ color: "var(--red-2)" }} data-testid="image-error">⚠️ Image failed to load. Try again.</div>}
          {!err && <img data-testid="image-result" src={url} alt={prompt} onLoad={() => setLoading(false)} onError={() => { setLoading(false); setErr(true); }} style={{ maxWidth: "100%", borderRadius: 10, border: "1px solid var(--border)" }} />}
          {!err && !loading && <div style={{ marginTop: ".8rem" }}><a data-testid="image-download" className="jv-btn" href={url} target="_blank" rel="noreferrer" download="bhai-image.png"><Download size={16} /> Download</a></div>}
        </div>
      )}
    </div>
  );
}

/* ------------------------------- Builder ------------------------------- */
const IDEA_CHIPS = [
  "An e-commerce store with cart, checkout and admin",
  "A SaaS dashboard with auth, teams and billing",
  "A personal portfolio with projects and a blog",
  "A CRM to manage leads, deals and tasks",
];

function BuildTab() {
  const {
    idea, setIdea, refine, setRefine, building, progress, result, error,
    apps, build, applyRefine,
  } = useBuilder();
  const [openFile, setOpenFile] = useState(null);

  const downloadZip = () => result?.appId && window.open(`${API}/apps/${result.appId}/zip`, "_blank");

  return (
    <div data-testid="build-tab">
      <div className="jv-card" style={{ padding: "1rem 1.2rem", marginBottom: "1rem", display: "flex", gap: "1rem", alignItems: "center" }}>
        <img src="/bhaiya-mascot.png" alt="Bhaiya" style={{ width: 58, height: 58, objectFit: "contain", flex: "none" }} />
        <div>
          <div className="jv-mono jv-muted" style={{ fontSize: ".76rem", marginBottom: ".2rem" }}>ENTERPRISE MULTI-AGENT BUILDER</div>
          <div className="jv-muted">Bataao kya banana hai — Bhaiya ki 8-agent team plans, codes & tests a complete full-stack project, with a live preview.</div>
        </div>
      </div>

      <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap", marginBottom: ".7rem" }}>
        {IDEA_CHIPS.map((c) => (
          <button key={c} className="bhai-idea-chip" onClick={() => setIdea(c)} disabled={building}>{c.split(" ").slice(0, 3).join(" ")}…</button>
        ))}
      </div>

      <textarea data-testid="builder-prompt-input" className="jv-textarea" style={{ minHeight: 90 }}
        placeholder="Describe the app or website you need in detail — features, users, pages, data…"
        value={idea} onChange={(e) => setIdea(e.target.value)} />
      <div style={{ marginTop: ".8rem" }}>
        <button data-testid="builder-submit-button" className="jv-btn" onClick={build} disabled={building || !idea.trim()}>
          {building ? <Spinner /> : <Hammer size={16} />} {building ? "Makan ban raha hai…" : "Build my app"}
        </button>
      </div>

      {error && <div data-testid="build-error" style={{ color: "var(--red-2)", marginTop: ".8rem" }}>{error}</div>}

      <div className="bhai-studio" style={{ marginTop: "1rem" }}>
        {/* center pane */}
        <div style={{ minWidth: 0 }}>
          {(building || result) && <HouseBuild progress={progress} />}

          {result?.preview_html && (
            <>
              <div className="jv-card" style={{ marginTop: "1rem", overflow: "hidden" }}>
                <div style={{ padding: ".6rem 1rem", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: ".5rem", flexWrap: "wrap" }}>
                  <strong>Live Preview</strong>
                  <button data-testid="download-project-zip-button" className="jv-btn" onClick={downloadZip}><Download size={16} /> Download project (.zip)</button>
                </div>
                <iframe data-testid="live-preview-iframe" title="preview" srcDoc={result.preview_html} sandbox="allow-scripts allow-same-origin allow-popups allow-forms allow-modals" style={{ width: "100%", height: 520, border: "none", background: "#fff" }} />
              </div>
              <div style={{ display: "flex", gap: ".6rem", marginTop: ".8rem" }}>
                <input data-testid="build-refine" className="jv-input" placeholder="Refine the preview — add a dark mode toggle and a chart" value={refine} onChange={(e) => setRefine(e.target.value)} onKeyDown={(e) => e.key === "Enter" && applyRefine()} />
                <button data-testid="build-refine-btn" className="jv-btn" onClick={applyRefine} disabled={building}>{building ? <Spinner /> : <Wand2 size={16} />} Apply</button>
              </div>
            </>
          )}

          {result?.plan && (
            <details className="jv-card" style={{ padding: "1rem 1.2rem", marginTop: "1rem" }}>
              <summary style={{ cursor: "pointer", fontWeight: 700 }}>📐 Architecture spec</summary>
              <pre style={{ whiteSpace: "pre-wrap", marginTop: ".6rem", fontSize: ".85rem" }} className="jv-mono">{result.plan}</pre>
            </details>
          )}

          {result?.files?.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <div className="jv-mono jv-muted" style={{ marginBottom: ".5rem", fontSize: ".8rem" }} data-testid="build-filecount">PROJECT FILES ({result.files.length})</div>
              <div data-testid="file-browser-tree">
                {result.files.map((f) => (
                  <div key={f.path} className="jv-card" style={{ marginBottom: ".4rem" }}>
                    <div onClick={() => setOpenFile(openFile === f.path ? null : f.path)} style={{ padding: ".55rem .9rem", cursor: "pointer", display: "flex", justifyContent: "space-between" }} className="jv-mono">
                      <span style={{ fontSize: ".82rem" }}>📄 {f.path}</span><span className="jv-muted">{openFile === f.path ? "▲" : "▼"}</span>
                    </div>
                    {openFile === f.path && <pre style={{ margin: 0, padding: ".8rem 1rem", borderTop: "1px solid var(--border)", overflowX: "auto", fontSize: ".78rem" }}>{f.content}</pre>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {!building && !result && apps.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <div className="jv-muted jv-mono" style={{ marginBottom: ".5rem", fontSize: ".8rem" }}>YOUR PROJECTS ({apps.length})</div>
              {apps.map((a) => (
                <div key={a.id} className="jv-card" style={{ padding: ".7rem 1rem", marginBottom: ".5rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>{a.idea.slice(0, 60)}</span>
                  <button className="jv-btn jv-btn-ghost" onClick={() => window.open(`${API}/apps/${a.id}/zip`, "_blank")}><Download size={15} /> .zip</button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* right side panel: live agent activity */}
        <div className="bhai-panel">
          <div className="jv-card" style={{ padding: ".8rem" }}>
            <div className="jv-mono jv-muted" style={{ fontSize: ".74rem", marginBottom: ".6rem", display: "flex", alignItems: "center", gap: ".4rem" }}>
              <Users size={13} /> AGENT ACTIVITY
            </div>
            <AgentPanel variant="panel" />
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------- Team ------------------------------- */
function TeamTab() {
  const { agents, progress, agentsCfg } = useBuilder();
  const live = agents.length ? agents : agentsCfg.map((a) => ({ ...a, status: "queued" }));
  const working = live.filter((a) => a.status === "working").length;
  const done = live.filter((a) => a.status === "done").length;

  return (
    <div data-testid="agent-team-tab">
      <div className="jv-card" style={{ padding: "1.1rem 1.3rem", marginBottom: "1rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: ".6rem", marginBottom: ".3rem" }}>
          <Users size={20} color="var(--gold)" /><strong className="jv-mono">BHAIYA KI TEAM</strong>
        </div>
        <div className="jv-muted">Eight specialist agents build your app in parallel. Pick the best model for each role.</div>
        <div style={{ display: "flex", gap: "1.4rem", marginTop: ".9rem", flexWrap: "wrap" }}>
          <div><div className="jv-hero" style={{ fontSize: "1.6rem" }}>{progress}%</div><div className="jv-muted jv-mono" style={{ fontSize: ".7rem" }}>PROGRESS</div></div>
          <div><div className="jv-hero" style={{ fontSize: "1.6rem" }}>{working}</div><div className="jv-muted jv-mono" style={{ fontSize: ".7rem" }}>WORKING</div></div>
          <div><div className="jv-hero" style={{ fontSize: "1.6rem" }}>{done}/{live.length}</div><div className="jv-muted jv-mono" style={{ fontSize: ".7rem" }}>COMPLETED</div></div>
        </div>
      </div>
      <AgentPanel variant="grid" />
    </div>
  );
}

/* ------------------------------- HUD ------------------------------- */
function HudTab({ user, go }) {
  const [stats, setStats] = useState({ chat_messages: 0, emails: 0, apps: 0, recent_apps: [] });
  useEffect(() => { http.get("/stats").then(({ data }) => setStats(data)).catch(() => {}); }, []);
  const cards = [
    { label: "Apps Built", value: stats.apps, color: "var(--red)" },
    { label: "Emails Drafted", value: stats.emails, color: "var(--gold)" },
    { label: "Chat Messages", value: stats.chat_messages, color: "var(--henna)" },
  ];
  const actions = [
    { id: "build", label: "Build an App", icon: Rocket },
    { id: "team", label: "Meet the Team", icon: Users },
    { id: "chat", label: "Talk to Bhai", icon: MessageSquare },
    { id: "image", label: "Generate Image", icon: ImageIcon },
  ];
  return (
    <div data-testid="hud-tab">
      <div className="jv-card" style={{ padding: "1.2rem 1.4rem", marginBottom: "1.2rem", display: "flex", gap: "1rem", alignItems: "center" }}>
        <img src="/bhaiya-mascot.png" alt="Bhaiya" style={{ width: 64, height: 64, objectFit: "contain", flex: "none" }} />
        <div>
          <div className="jv-mono jv-muted" style={{ fontSize: ".78rem" }}>NAMASTE</div>
          <div className="jv-hero" style={{ fontSize: "1.8rem" }}>{user.name || "Boss"}</div>
          <div className="jv-muted">Aaj kya banayein? Describe it and Bhaiya's team builds it.</div>
        </div>
      </div>
      <div className="jv-hud-grid" style={{ marginBottom: "1.2rem" }}>
        {cards.map((c) => (
          <div key={c.label} className="jv-card" style={{ padding: "1.2rem", textAlign: "center" }}>
            <div style={{ fontSize: "2.4rem", fontWeight: 800, fontFamily: "'Outfit',sans-serif", color: c.color, textShadow: `0 0 18px ${c.color}55` }}>{c.value}</div>
            <div className="jv-muted jv-mono" style={{ fontSize: ".72rem", marginTop: ".3rem" }}>{c.label.toUpperCase()}</div>
          </div>
        ))}
      </div>
      <div className="jv-mono jv-muted" style={{ marginBottom: ".6rem", fontSize: ".8rem" }}>QUICK ACTIONS</div>
      <div className="jv-hud-grid" style={{ marginBottom: "1.2rem" }}>
        {actions.map((a) => { const I = a.icon; return (
          <button key={a.id} data-testid={`quick-${a.id}`} className="jv-card jv-quick" onClick={() => go(a.id)}>
            <I size={20} /> <span>{a.label}</span>
          </button>
        ); })}
      </div>
      {stats.recent_apps?.length > 0 && (
        <>
          <div className="jv-mono jv-muted" style={{ marginBottom: ".6rem", fontSize: ".8rem" }}>RECENT PROJECTS</div>
          {stats.recent_apps.map((a) => (
            <div key={a.id} className="jv-card" style={{ padding: ".7rem 1rem", marginBottom: ".5rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>{a.idea?.slice(0, 70)}</span>
              <button className="jv-btn jv-btn-ghost" onClick={() => go("build")}>Open Builder</button>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

/* ------------------------------- Admin ------------------------------- */
function AdminTab() {
  const [users, setUsers] = useState([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("user");
  const [msg, setMsg] = useState("");
  const load = useCallback(() => http.get("/admin/users").then(({ data }) => setUsers(data.users || [])).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!email.trim()) return;
    try { await http.post("/admin/users", { email: email.trim(), role }); setEmail(""); setMsg("✅ Access granted."); load(); }
    catch (e) { setMsg("⚠️ " + (e.response?.data?.detail || "Failed.")); }
    setTimeout(() => setMsg(""), 2500);
  };
  const remove = async (em) => {
    try { await http.delete(`/admin/users/${encodeURIComponent(em)}`); load(); }
    catch (e) { setMsg("⚠️ " + (e.response?.data?.detail || "Failed.")); setTimeout(() => setMsg(""), 2500); }
  };

  return (
    <div data-testid="admin-tab">
      <div className="jv-card" style={{ padding: "1.1rem 1.3rem", marginBottom: "1.2rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: ".6rem", marginBottom: ".3rem" }}>
          <Shield size={20} color="var(--gold)" /><strong className="jv-mono">ACCESS CONTROL</strong>
        </div>
        <div className="jv-muted">Only people you allow here can sign in. You are the Super Admin.</div>
      </div>
      <div style={{ display: "flex", gap: ".6rem", marginBottom: ".4rem", flexWrap: "wrap" }}>
        <input data-testid="admin-email" className="jv-input" style={{ flex: "1 1 220px" }} placeholder="person@gmail.com" value={email} onChange={(e) => setEmail(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} />
        <select className="jv-select" style={{ width: 140 }} value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="user">User</option><option value="admin">Admin</option>
        </select>
        <button data-testid="admin-add" className="jv-btn" onClick={add}><Plus size={16} /> Grant Access</button>
      </div>
      {msg && <div className="jv-muted" style={{ marginBottom: ".6rem" }}>{msg}</div>}
      <div style={{ marginTop: ".8rem" }}>
        {users.map((u) => (
          <div key={u.email} className="jv-card" style={{ padding: ".7rem 1rem", marginBottom: ".5rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>{u.email} <span className="jv-chip" style={{ marginLeft: ".4rem" }}>{u.role}</span></span>
            {u.role !== "super_admin" && (
              <button className="jv-btn jv-btn-ghost" onClick={() => remove(u.email)}><Trash2 size={15} /> Revoke</button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------- Login ------------------------------- */
function Login() {
  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  const login = () => {
    const redirectUrl = window.location.origin + "/";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };
  return (
    <div className="jv-app"><div className="jv-login">
      <img src="/bhaiya-mascot.png" alt="Bhaiya" style={{ width: 160, marginBottom: "1rem", filter: "drop-shadow(0 0 30px rgba(229,169,60,.4))" }} />
      <div className="jv-hero" style={{ fontSize: "3rem" }}>Bhai.AI</div>
      <p className="jv-muted" style={{ maxWidth: 480, marginTop: ".5rem" }}>
        Aapka apna full-stack builder. Bataao kya banana hai — Bhaiya ki AI team enterprise-grade apps & websites bana degi.
      </p>
      <div style={{ marginTop: "1.6rem" }}>
        <button data-testid="google-login" className="jv-btn" onClick={login} style={{ fontSize: "1.05rem", padding: ".8rem 1.6rem" }}>Sign in with Google</button>
      </div>
      <p className="jv-muted" style={{ marginTop: "1rem", fontSize: ".8rem" }}>🔒 Private studio — invited access only.</p>
    </div></div>
  );
}

/* ------------------------------- App ------------------------------- */
function App() {
  const [auth, setAuth] = useState(null); // null=checking, obj=user, false=login
  const [tab, setTab] = useState("hud");
  const [readAloud, setReadAloud] = useState(false);
  const [booting, setBooting] = useState(true);
  const [wake, setWake] = useState(false);
  const [wakeSignal, setWakeSignal] = useState(0);
  const wakeRef = useRef(null);

  useEffect(() => {
    const hash = window.location.hash;
    if (hash && hash.includes("session_id=")) {
      const sid = new URLSearchParams(hash.slice(1)).get("session_id");
      http.post("/auth/session", {}, { headers: { "X-Session-ID": sid } })
        .then(({ data }) => { window.history.replaceState(null, "", window.location.pathname); setAuth(data); })
        .catch(() => setAuth(false));
      return;
    }
    http.get("/auth/me").then(({ data }) => setAuth(data)).catch(() => setAuth(false));
  }, []);

  useEffect(() => {
    if (auth && auth !== false && booting) {
      playBootSound();
      const t = setTimeout(() => setBooting(false), 2300);
      return () => clearTimeout(t);
    }
  }, [auth, booting]);

  const toggleWake = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert("Wake word isn't supported in this browser."); return; }
    if (wake) { wakeRef.current?.stop(); setWake(false); return; }
    const r = new SR(); wakeRef.current = r; r.lang = "en-IN"; r.continuous = true; r.interimResults = true;
    r.onresult = (e) => {
      const txt = Array.from(e.results).map((x) => x[0].transcript).join(" ").toLowerCase();
      if (txt.includes("hey bhai") || txt.includes("hey, bhai") || txt.includes("hello bhai")) {
        setTab("chat"); setWakeSignal((n) => n + 1);
      }
    };
    r.onend = () => { if (wakeRef.current) { try { r.start(); } catch { /* noop */ } } };
    r.onerror = () => {};
    setWake(true); r.start();
  };
  useEffect(() => () => { wakeRef.current = null; }, []);

  const logout = async () => { await http.post("/auth/logout").catch(() => {}); setAuth(false); };

  if (auth === null) return <div className="jv-app"><div className="jv-login"><span className="jv-arc" /><p className="jv-muted jv-mono" style={{ marginTop: "1rem" }}>LOADING BHAI.AI…</p></div></div>;
  if (auth === false) return <Login />;
  if (booting) return <div className="jv-app"><BootScreen /></div>;

  const tabs = [
    { id: "hud", label: "Home", icon: LayoutDashboard },
    ...TABS,
    ...(auth.is_admin ? [{ id: "admin", label: "Admin", icon: Shield }] : []),
  ];

  return (
    <BuilderProvider>
      <div className="jv-app">
        <div style={{ maxWidth: 1120, margin: "0 auto", padding: "2rem 1.2rem 4rem", position: "relative", zIndex: 1 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap", marginBottom: "1.2rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: ".9rem" }}>
              <img src="/bhai-logo.png" alt="Bhai.AI" className="jv-logo" />
              <div>
                <div className="jv-hero" style={{ fontSize: "2rem", lineHeight: 1 }}>Bhai.AI</div>
                <p className="jv-muted" style={{ margin: ".2rem 0 0", fontSize: ".88rem" }}>Bihar ka apna builder · online</p>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: ".7rem" }}>
              <button className={`jv-btn jv-btn-ghost ${wake ? "jv-mic rec" : ""}`} onClick={toggleWake} title='Wake word: say "Hey Bhai"'>
                <Radio size={16} />
              </button>
              <button className="jv-btn jv-btn-ghost" onClick={() => setReadAloud(!readAloud)} title="Read replies aloud">
                {readAloud ? <Volume2 size={16} /> : <VolumeX size={16} />}
              </button>
              {auth.picture && <img src={auth.picture} alt="me" style={{ width: 36, height: 36, borderRadius: "50%", border: "2px solid var(--gold)" }} />}
              <button data-testid="logout-btn" className="jv-btn jv-btn-ghost" onClick={logout}><LogOut size={16} /></button>
            </div>
          </div>

          {wake && <div className="jv-muted jv-mono" style={{ marginBottom: ".8rem", color: "var(--red-2)" }}>● listening for "Hey Bhai"…</div>}

          <div style={{ display: "flex", gap: ".35rem", background: "var(--panel)", border: "1px solid var(--border)", borderRadius: 12, padding: ".35rem", marginBottom: "1.4rem", overflowX: "auto" }}>
            {tabs.map((t) => { const Icon = t.icon; return (
              <button key={t.id} data-testid={`workspace-nav-item-${t.id}`} className={`jv-tab ${tab === t.id ? "active" : ""}`} onClick={() => setTab(t.id)} style={{ display: "flex", alignItems: "center", gap: ".4rem" }}>
                <Icon size={16} /> {t.label}
              </button>
            ); })}
          </div>

          {tab === "hud" && <HudTab user={auth} go={setTab} />}
          {tab === "build" && <BuildTab />}
          {tab === "team" && <TeamTab />}
          {tab === "chat" && <ChatTab readAloud={readAloud} wakeSignal={wakeSignal} />}
          {tab === "email" && <EmailTab />}
          {tab === "research" && <ResearchTab />}
          {tab === "image" && <ImageTab />}
          {tab === "admin" && auth.is_admin && <AdminTab />}

          <div className="jv-footer" data-testid="footer">For my ❤️ Itisha Beta</div>
        </div>
      </div>
    </BuilderProvider>
  );
}

export default App;
