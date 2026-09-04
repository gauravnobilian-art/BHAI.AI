import { useState, useRef, useEffect, useCallback } from "react";
import "@/App.css";
import axios from "axios";
import {
  MessageSquare, Mail, Search, Image as ImageIcon, Rocket,
  Send, Download, Copy, Check, Sparkles, Wand2, Mic, Volume2, VolumeX, LogOut, Trash2,
  LayoutDashboard, Shield, Radio, Zap, Plus,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const http = axios.create({ baseURL: API, withCredentials: true });

const TABS = [
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "email", label: "Email", icon: Mail },
  { id: "research", label: "Research", icon: Search },
  { id: "image", label: "Images", icon: ImageIcon },
  { id: "build", label: "Builder", icon: Rocket },
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
    o.frequency.setValueAtTime(90, ctx.currentTime);
    o.frequency.exponentialRampToValueAtTime(520, ctx.currentTime + 1.1);
    g.gain.setValueAtTime(0.0001, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.5);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 1.6);
    o.start(); o.stop(ctx.currentTime + 1.7);
  } catch { /* noop */ }
}

function BootScreen() {
  return (
    <div className="jv-boot">
      <span className="jv-arc jv-boot-arc" />
      <div className="jv-hero jv-boot-title" style={{ fontSize: "2.6rem", marginTop: "1.4rem" }}>JARVIS</div>
      <p className="jv-muted jv-mono jv-boot-sub" style={{ marginTop: ".6rem" }}>INITIALIZING ARC REACTOR…</p>
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
      setMessages([...next, { role: "assistant", content: "⚠️ Failed to reach J.A.R.V.I.S." }]);
    } finally { setLoading(false); }
  };

  const mic = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert("Voice input isn't supported in this browser."); return; }
    if (rec) { recogRef.current?.stop(); return; }
    const r = new SR(); recogRef.current = r; r.lang = "en-US"; r.interimResults = false;
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
        {messages.length === 0 && <p className="jv-muted">Speak or type — J.A.R.V.I.S. is listening, sir.</p>}
        {messages.map((m, i) => (
          <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start", marginBottom: ".7rem" }}>
            <div className={`jv-bubble ${m.role}`} style={{ maxWidth: "85%", whiteSpace: "pre-wrap" }}>{m.content}</div>
          </div>
        ))}
        {loading && <div className="jv-muted" style={{ display: "flex", gap: ".5rem", alignItems: "center" }}><Spinner /> Processing…</div>}
        <div ref={endRef} />
      </div>
      <div style={{ display: "flex", gap: ".6rem" }}>
        <button data-testid="chat-mic" className={`jv-btn jv-btn-ghost jv-mic ${rec ? "rec" : ""}`} onClick={mic} title="Voice input"><Mic size={16} /></button>
        <input data-testid="chat-input" className="jv-input" placeholder="Message J.A.R.V.I.S.…"
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
          <pre className="jv-mono" data-testid="email-draft" style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: ".85rem", fontFamily: "'Rajdhani',monospace" }}>{draft}</pre>
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
            {sources.map((s, i) => <li key={i} style={{ marginBottom: ".3rem" }}><a href={s.href} target="_blank" rel="noreferrer" style={{ color: "var(--arc)" }}>{s.title || s.href}</a></li>)}
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
      <textarea data-testid="image-prompt" className="jv-textarea" style={{ minHeight: 90 }} placeholder="Describe your image — neon arc-reactor core, cinematic, 8k" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
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
          {!err && !loading && <div style={{ marginTop: ".8rem" }}><a data-testid="image-download" className="jv-btn" href={url} target="_blank" rel="noreferrer" download="jarvis-image.png"><Download size={16} /> Download</a></div>}
        </div>
      )}
    </div>
  );
}

/* ------------------------------- Build ------------------------------- */
function BuildTab() {
  const [idea, setIdea] = useState(""); const [refine, setRefine] = useState("");
  const [html, setHtml] = useState(""); const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(""); const [apps, setApps] = useState([]);
  const load = useCallback(() => http.get("/history/apps").then(({ data }) => setApps(data.apps || [])).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const build = async () => {
    if (!idea.trim() || loading) return; setLoading(true); setErr("");
    try { const { data } = await http.post("/build", { idea }); setHtml(data.html); load(); }
    catch { setErr("⚠️ Build failed — please try again."); }
    finally { setLoading(false); }
  };
  const applyRefine = async () => {
    if (!refine.trim() || loading) return; setLoading(true); setErr("");
    try { const { data } = await http.post("/build", { idea, refine, current_html: html }); setHtml(data.html); setRefine(""); load(); }
    catch { setErr("⚠️ Update failed — please try again."); }
    finally { setLoading(false); }
  };
  const download = () => { const b = new Blob([html], { type: "text/html" }); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "index.html"; a.click(); };

  return (
    <div data-testid="build-tab">
      <textarea data-testid="build-idea" className="jv-textarea" style={{ minHeight: 80 }} placeholder="Describe an app — e.g. a habit tracker with streaks, charts and dark mode" value={idea} onChange={(e) => setIdea(e.target.value)} />
      <div style={{ marginTop: ".8rem" }}><button data-testid="build-run" className="jv-btn" onClick={build} disabled={loading}>{loading ? <Spinner /> : <Rocket size={16} />} Build it live</button></div>
      {err && <div data-testid="build-error" style={{ color: "var(--red-2)", marginTop: ".8rem" }}>{err}</div>}
      {html && (
        <>
          <div className="jv-card" style={{ marginTop: "1rem", overflow: "hidden" }}>
            <div style={{ padding: ".6rem 1rem", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong>Live Preview</strong><button className="jv-btn jv-btn-ghost" onClick={download}><Download size={16} /> index.html</button>
            </div>
            <iframe data-testid="build-preview" title="preview" srcDoc={html} sandbox="allow-scripts allow-same-origin allow-popups allow-forms allow-modals" style={{ width: "100%", height: 520, border: "none", background: "#fff" }} />
          </div>
          <div style={{ display: "flex", gap: ".6rem", marginTop: ".8rem" }}>
            <input data-testid="build-refine" className="jv-input" placeholder="Refine — add a dark mode toggle and a chart" value={refine} onChange={(e) => setRefine(e.target.value)} onKeyDown={(e) => e.key === "Enter" && applyRefine()} />
            <button data-testid="build-refine-btn" className="jv-btn" onClick={applyRefine} disabled={loading}>{loading ? <Spinner /> : <Wand2 size={16} />} Apply</button>
          </div>
        </>
      )}
      {apps.length > 0 && (
        <div style={{ marginTop: "1.2rem" }}>
          <div className="jv-muted jv-mono" style={{ marginBottom: ".5rem" }}>YOUR APPS ({apps.length})</div>
          {apps.map((a) => (
            <div key={a.id} className="jv-card" style={{ padding: ".7rem 1rem", marginBottom: ".5rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>{a.idea.slice(0, 70)}</span>
              <button className="jv-btn jv-btn-ghost" onClick={() => { setHtml(a.html); setIdea(a.idea); }}>Open</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------- HUD ------------------------------- */
function HudTab({ user, go }) {
  const [stats, setStats] = useState({ chat_messages: 0, emails: 0, apps: 0, recent_apps: [] });
  useEffect(() => { http.get("/stats").then(({ data }) => setStats(data)).catch(() => {}); }, []);
  const cards = [
    { label: "Chat Messages", value: stats.chat_messages, color: "var(--arc)" },
    { label: "Emails Drafted", value: stats.emails, color: "var(--gold)" },
    { label: "Apps Built", value: stats.apps, color: "var(--red-2)" },
  ];
  const actions = [
    { id: "chat", label: "Talk to Jarvis", icon: MessageSquare },
    { id: "research", label: "Web Research", icon: Search },
    { id: "image", label: "Generate Image", icon: ImageIcon },
    { id: "build", label: "Build an App", icon: Rocket },
  ];
  return (
    <div data-testid="hud-tab">
      <div className="jv-card" style={{ padding: "1.2rem 1.4rem", marginBottom: "1.2rem" }}>
        <div className="jv-mono jv-muted" style={{ fontSize: ".8rem" }}>WELCOME BACK</div>
        <div className="jv-hero" style={{ fontSize: "1.8rem" }}>{user.name || "Sir"}</div>
        <div className="jv-muted">All systems online. What are we building today?</div>
      </div>
      <div className="jv-hud-grid" style={{ marginBottom: "1.2rem" }}>
        {cards.map((c) => (
          <div key={c.label} className="jv-card" style={{ padding: "1.2rem", textAlign: "center" }}>
            <div className="jv-mono" style={{ fontSize: "2.4rem", color: c.color, textShadow: `0 0 18px ${c.color}55` }}>{c.value}</div>
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
          <div className="jv-mono jv-muted" style={{ marginBottom: ".6rem", fontSize: ".8rem" }}>RECENT APPS</div>
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
      <span className="jv-arc" style={{ width: 72, height: 72, marginBottom: "1.5rem" }} />
      <div className="jv-hero" style={{ fontSize: "3rem" }}>JARVIS</div>
      <p className="jv-muted" style={{ maxWidth: 460, marginTop: ".5rem" }}>
        Just A Rather Very Intelligent System. Welcome to the lab — sign in to access your command console.
      </p>
      <div style={{ marginTop: "1.6rem" }}>
        <button data-testid="google-login" className="jv-btn" onClick={login} style={{ fontSize: "1.05rem", padding: ".8rem 1.6rem" }}>Sign in with Google</button>
      </div>
      <p className="jv-muted" style={{ marginTop: "1rem", fontSize: ".8rem" }}>🔒 Private console — owner access only.</p>
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

  // boot animation + sound (once, after auth resolves to a user)
  useEffect(() => {
    if (auth && auth !== false && booting) {
      playBootSound();
      const t = setTimeout(() => setBooting(false), 2300);
      return () => clearTimeout(t);
    }
  }, [auth, booting]);

  // wake-word listener: "hey jarvis"
  const toggleWake = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert("Wake word isn't supported in this browser."); return; }
    if (wake) { wakeRef.current?.stop(); setWake(false); return; }
    const r = new SR(); wakeRef.current = r; r.lang = "en-US"; r.continuous = true; r.interimResults = true;
    r.onresult = (e) => {
      const txt = Array.from(e.results).map((x) => x[0].transcript).join(" ").toLowerCase();
      if (txt.includes("hey jarvis") || txt.includes("hey, jarvis")) {
        setTab("chat"); setWakeSignal((n) => n + 1);
      }
    };
    r.onend = () => { if (wakeRef.current) { try { r.start(); } catch { /* noop */ } } };
    r.onerror = () => {};
    setWake(true); r.start();
  };
  useEffect(() => () => { wakeRef.current = null; }, []);

  const logout = async () => { await http.post("/auth/logout").catch(() => {}); setAuth(false); };

  if (auth === null) return <div className="jv-app"><div className="jv-login"><span className="jv-arc" /><p className="jv-muted jv-mono" style={{ marginTop: "1rem" }}>BOOTING J.A.R.V.I.S…</p></div></div>;
  if (auth === false) return <Login />;
  if (booting) return <div className="jv-app"><BootScreen /></div>;

  const tabs = [
    { id: "hud", label: "HUD", icon: LayoutDashboard },
    ...TABS,
    ...(auth.is_admin ? [{ id: "admin", label: "Admin", icon: Shield }] : []),
  ];

  return (
    <div className="jv-app">
      <div style={{ maxWidth: 980, margin: "0 auto", padding: "2rem 1.2rem 4rem", position: "relative", zIndex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap", marginBottom: "1.2rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <span className="jv-arc" />
            <div>
              <div className="jv-hero" style={{ fontSize: "2.2rem", lineHeight: 1 }}>JARVIS</div>
              <p className="jv-muted" style={{ margin: ".2rem 0 0", fontSize: ".9rem" }}>Tony's Lab · online</p>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: ".7rem" }}>
            <button className={`jv-btn jv-btn-ghost ${wake ? "jv-mic rec" : ""}`} onClick={toggleWake} title='Wake word: say "Hey Jarvis"'>
              <Radio size={16} />
            </button>
            <button className="jv-btn jv-btn-ghost" onClick={() => setReadAloud(!readAloud)} title="Read replies aloud">
              {readAloud ? <Volume2 size={16} /> : <VolumeX size={16} />}
            </button>
            {auth.picture && <img src={auth.picture} alt="me" style={{ width: 36, height: 36, borderRadius: "50%", border: "2px solid var(--gold)" }} />}
            <button data-testid="logout-btn" className="jv-btn jv-btn-ghost" onClick={logout}><LogOut size={16} /></button>
          </div>
        </div>

        {wake && <div className="jv-muted jv-mono" style={{ marginBottom: ".8rem", color: "var(--red-2)" }}>● listening for "Hey Jarvis"…</div>}

        <div style={{ display: "flex", gap: ".35rem", background: "var(--panel)", border: "1px solid var(--border)", borderRadius: 12, padding: ".35rem", marginBottom: "1.4rem", overflowX: "auto" }}>
          {tabs.map((t) => { const Icon = t.icon; return (
            <button key={t.id} data-testid={`tab-${t.id}`} className={`jv-tab ${tab === t.id ? "active" : ""}`} onClick={() => setTab(t.id)} style={{ display: "flex", alignItems: "center", gap: ".4rem" }}>
              <Icon size={16} /> {t.label}
            </button>
          ); })}
        </div>

        {tab === "hud" && <HudTab user={auth} go={setTab} />}
        {tab === "chat" && <ChatTab readAloud={readAloud} wakeSignal={wakeSignal} />}
        {tab === "email" && <EmailTab />}
        {tab === "research" && <ResearchTab />}
        {tab === "image" && <ImageTab />}
        {tab === "build" && <BuildTab />}
        {tab === "admin" && auth.is_admin && <AdminTab />}

        <div className="jv-footer" data-testid="footer">For my ❤️ Itisha Beta</div>
      </div>
    </div>
  );
}

export default App;
