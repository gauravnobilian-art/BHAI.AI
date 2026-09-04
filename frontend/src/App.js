import { useState, useRef, useEffect, useCallback } from "react";
import "@/App.css";
import { API, http } from "./http";
import { BuilderProvider, useBuilder } from "./builder/BuilderContext";
import BuildScene from "./builder/BuildScene";
import AgentPanel from "./builder/AgentPanel";
import {
  MessageSquare, Mail, Search, Image as ImageIcon, Rocket,
  Send, Download, Copy, Check, Sparkles, Wand2, Mic, Volume2, VolumeX, LogOut, Trash2,
  LayoutDashboard, Shield, Radio, Users, Plus, Hammer, ExternalLink, Camera, Upload, Globe, Save,
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
function resizeToDataUrl(file, max = 1024) {
  return new Promise((resolve, reject) => {
    const img = new window.Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      let { width, height } = img;
      if (width > max || height > max) {
        const r = Math.min(max / width, max / height);
        width = Math.round(width * r); height = Math.round(height * r);
      }
      const canvas = document.createElement("canvas");
      canvas.width = width; canvas.height = height;
      canvas.getContext("2d").drawImage(img, 0, 0, width, height);
      resolve(canvas.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = reject;
    img.src = url;
  });
}

function ImageTab() {
  const [mode, setMode] = useState("text");
  // text->image (Pollinations)
  const [prompt, setPrompt] = useState(""); const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false); const [err, setErr] = useState(false);
  const [w, setW] = useState(1024); const [h, setH] = useState(1024);
  // photo->image (Nano Banana)
  const [photo, setPhoto] = useState(""); const [pPrompt, setPPrompt] = useState("");
  const [pResult, setPResult] = useState(""); const [pLoading, setPLoading] = useState(false);
  const [pErr, setPErr] = useState("");
  const camRef = useRef(null); const galRef = useRef(null);

  const gen = () => {
    if (!prompt.trim()) return; setLoading(true); setErr(false);
    const seed = Math.floor(Math.random() * 1e6);
    setUrl(`https://image.pollinations.ai/prompt/${encodeURIComponent(prompt.trim())}?width=${w}&height=${h}&nologo=true&seed=${seed}`);
  };

  const onFile = async (e) => {
    const file = e.target.files?.[0]; if (!file) return;
    setPErr(""); setPResult("");
    try { setPhoto(await resizeToDataUrl(file)); }
    catch { setPErr("⚠️ Couldn't read that image."); }
    e.target.value = "";
  };

  const editPhoto = async (override) => {
    const usePrompt = (override ?? pPrompt).trim();
    if (!photo || !usePrompt || pLoading) return;
    setPLoading(true); setPErr(""); setPResult("");
    try {
      const { data } = await http.post("/image/edit", { image_base64: photo, prompt: usePrompt });
      setPResult(data.image);
    } catch (e) {
      setPErr("⚠️ " + (e.response?.data?.detail || "Image edit failed. Try again."));
    } finally { setPLoading(false); }
  };

  const RESTYLE_PRESETS = [
    { label: "Madhubani", prompt: "Restyle this photo as a traditional Madhubani / Mithila folk painting with bold outlines and vibrant natural colors." },
    { label: "Cartoon", prompt: "Turn this photo into a fun, clean cartoon illustration with bold outlines." },
    { label: "Festive Diwali", prompt: "Add a warm festive Diwali background with glowing diyas and marigold garlands." },
    { label: "3D Pixar", prompt: "Restyle as a cute 3D Pixar-style animated character render." },
    { label: "Watercolor", prompt: "Repaint this photo as a soft, artistic watercolor painting." },
    { label: "Pencil Sketch", prompt: "Convert this photo into a detailed black-and-white pencil sketch." },
  ];

  return (
    <div data-testid="image-tab">
      <div style={{ display: "flex", gap: ".5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <button data-testid="image-mode-text" className={`jv-preset ${mode === "text" ? "active" : ""}`} onClick={() => setMode("text")}>Text → Image</button>
        <button data-testid="image-mode-photo" className={`jv-preset ${mode === "photo" ? "active" : ""}`} onClick={() => setMode("photo")}>Photo → Image</button>
      </div>

      {mode === "text" && (
        <>
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
        </>
      )}

      {mode === "photo" && (
        <>
          <div className="jv-card" style={{ padding: "1rem 1.2rem" }}>
            <div className="jv-muted" style={{ marginBottom: ".7rem" }}>Apni photo daalo (camera ya gallery se) aur bataao kaise badalna hai — Bhaiya nayi image bana dega.</div>
            <input ref={camRef} type="file" accept="image/*" capture="environment" onChange={onFile} style={{ display: "none" }} data-testid="image-camera-input" />
            <input ref={galRef} type="file" accept="image/*" onChange={onFile} style={{ display: "none" }} data-testid="image-gallery-input" />
            <div style={{ display: "flex", gap: ".6rem", flexWrap: "wrap" }}>
              <button data-testid="image-take-photo" className="jv-btn jv-btn-ghost" onClick={() => camRef.current?.click()}><Camera size={16} /> Take photo</button>
              <button data-testid="image-choose-gallery" className="jv-btn jv-btn-ghost" onClick={() => galRef.current?.click()}><Upload size={16} /> Choose from gallery</button>
            </div>
            {photo && <img data-testid="image-uploaded-preview" src={photo} alt="uploaded" style={{ maxWidth: "100%", maxHeight: 260, marginTop: ".9rem", borderRadius: 10, border: "1px solid var(--border)" }} />}
          </div>

          <textarea data-testid="image-edit-prompt" className="jv-textarea" style={{ minHeight: 80, marginTop: ".8rem" }} placeholder="e.g. make it a Madhubani painting, add a festive background, turn into a cartoon…" value={pPrompt} onChange={(e) => setPPrompt(e.target.value)} />
          <div style={{ display: "flex", gap: ".4rem", flexWrap: "wrap", marginTop: ".6rem" }} data-testid="restyle-presets">
            {RESTYLE_PRESETS.map((p) => (
              <button key={p.label} className="jv-preset" data-testid={`restyle-${p.label.toLowerCase().split(" ")[0]}`}
                disabled={!photo || pLoading}
                onClick={() => { setPPrompt(p.prompt); editPhoto(p.prompt); }}>
                <Wand2 size={12} style={{ marginRight: 4 }} />{p.label}
              </button>
            ))}
          </div>
          <div style={{ marginTop: ".8rem" }}>
            <button data-testid="image-edit-generate" className="jv-btn" onClick={() => editPhoto()} disabled={pLoading || !photo || !pPrompt.trim()}>{pLoading ? <Spinner /> : <Wand2 size={16} />} {pLoading ? "Ban raha hai…" : "Generate from photo"}</button>
          </div>
          {pErr && <div style={{ color: "var(--red-2)", marginTop: ".8rem" }} data-testid="image-edit-error">{pErr}</div>}
          {pResult && (
            <div className="jv-card" style={{ padding: "1rem", marginTop: "1rem", textAlign: "center" }}>
              <img data-testid="image-edit-result" src={pResult} alt="result" style={{ maxWidth: "100%", borderRadius: 10, border: "1px solid var(--border)" }} />
              <div style={{ marginTop: ".8rem" }}><a data-testid="image-edit-download" className="jv-btn" href={pResult} download="bhai-edited.png"><Download size={16} /> Download</a></div>
            </div>
          )}
        </>
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

function ChatterFeed({ banter, progress, building, voice }) {
  const spokenRef = useRef(-1);
  const count = banter.length
    ? Math.min(banter.length, Math.max(building ? 1 : 0, Math.ceil((progress / 100) * banter.length)))
    : 0;
  const shown = banter.slice(0, count);

  useEffect(() => {
    if (!voice || shown.length === 0) return;
    const last = shown.length - 1;
    if (last > spokenRef.current) {
      spokenRef.current = last;
      try {
        const line = shown[last];
        const u = new SpeechSynthesisUtterance(line.text);
        u.lang = "hi-IN";
        // give each crew member their own voice character
        const voices = window.speechSynthesis.getVoices();
        const pool = voices.filter((v) => v.lang && (v.lang.startsWith("hi") || v.lang.includes("IN")));
        const list = pool.length ? pool : voices;
        let h = 0; const from = line.from || "B";
        for (let i = 0; i < from.length; i++) h = (h * 31 + from.charCodeAt(i)) % 997;
        if (list.length) u.voice = list[h % list.length];
        u.pitch = 0.8 + (h % 5) * 0.12;   // 0.80 – 1.28
        u.rate = 0.92 + (h % 3) * 0.08;   // 0.92 – 1.08
        window.speechSynthesis.speak(u);
      } catch { /* noop */ }
    }
  }, [shown, voice]);

  if (shown.length === 0) return null;
  return (
    <div className="jv-card" style={{ padding: ".8rem 1rem", marginTop: "1rem" }} data-testid="chatter-feed">
      <div className="jv-mono jv-muted" style={{ fontSize: ".72rem", marginBottom: ".6rem" }}>💬 SITE PE BAATCHEET (BHOJPURI)</div>
      <div className="bhai-chatter">
        {shown.map((b, i) => (
          <div className="bhai-chat-line" key={i}>
            <div className="bhai-chat-av">{(b.from || "B").slice(0, 1)}</div>
            <div className="bhai-chat-bubble">
              <div className="bhai-chat-from">{b.from}</div>
              <div className="bhai-chat-text">{b.text}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function BuildTab() {
  const {
    idea, setIdea, extra, setExtra, refine, setRefine, building, progress,
    theme, themeLabel, banter, result, error, apps, build, applyRefine, deployApp,
  } = useBuilder();
  const [openFile, setOpenFile] = useState(null);
  const [voice, setVoice] = useState(false);
  const [deployOpen, setDeployOpen] = useState(false);
  const [nToken, setNToken] = useState(() => localStorage.getItem("netlify_token") || "");
  const [deploying, setDeploying] = useState(false);
  const [deployUrl, setDeployUrl] = useState("");
  const [deployErr, setDeployErr] = useState("");
  const active = building || progress > 0 || result;

  const zipUrl = result?.appId ? `${API}/apps/${result.appId}/zip` : "";
  const previewUrl = result?.appId ? `${API}/apps/${result.appId}/preview` : "";

  const doDeploy = async () => {
    if (!nToken.trim() || deploying) return;
    setDeploying(true); setDeployErr(""); setDeployUrl("");
    try {
      localStorage.setItem("netlify_token", nToken.trim());
      const url = await deployApp(result.appId, nToken.trim());
      setDeployUrl(url);
    } catch (e) {
      setDeployErr("⚠️ " + (e.response?.data?.detail || "Deploy failed. Check your token and retry."));
    } finally { setDeploying(false); }
  };

  return (
    <div data-testid="build-tab">
      <div className="jv-card" style={{ padding: "1rem 1.2rem", marginBottom: "1rem", display: "flex", gap: "1rem", alignItems: "center" }}>
        <img src="/bhaiya-mascot.png" alt="Bhaiya" style={{ width: 58, height: 58, objectFit: "contain", flex: "none" }} />
        <div>
          <div className="jv-mono jv-muted" style={{ fontSize: ".76rem", marginBottom: ".2rem" }}>ENTERPRISE MULTI-AGENT BUILDER</div>
          <div className="jv-muted">Bataao kya banana hai — Bhaiya ki team ek project-themed crew banaake, ek complete full-stack app banati hai, live preview ke saath.</div>
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
          {building ? <Spinner /> : <Hammer size={16} />} {building ? "Kaam chal raha hai…" : "Build my app"}
        </button>
      </div>

      {error && <div data-testid="build-error" style={{ color: "var(--red-2)", marginTop: ".8rem" }}>{error}</div>}

      {active && (
        <>
          {/* dynamic themed construction animation */}
          <div style={{ marginTop: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center", gap: ".6rem", flexWrap: "wrap" }}>
            <div className="jv-mono jv-muted" style={{ fontSize: ".74rem" }}>
              🏗️ {themeLabel || "NIRMAAN"} {theme && theme !== "app" ? `· ${theme.toUpperCase()}` : ""}
            </div>
            <button className={`jv-btn jv-btn-ghost ${voice ? "jv-mic rec" : ""}`} onClick={() => setVoice(!voice)} title="Bhojpuri voice" data-testid="chatter-voice-toggle">
              {voice ? <Volume2 size={15} /> : <VolumeX size={15} />} <span style={{ fontSize: ".8rem" }}>Bhojpuri voice</span>
            </button>
          </div>
          <BuildScene progress={progress} theme={theme} />

          {/* crew — horizontal line below the animation */}
          <div className="jv-mono jv-muted" style={{ margin: "1rem 0 .5rem", fontSize: ".74rem", display: "flex", alignItems: "center", gap: ".4rem" }}>
            <Users size={13} /> AAJ KI TEAM — kaun kya kar raha hai
          </div>
          <AgentPanel variant="row" />

          <ChatterFeed banter={banter} progress={progress} building={building} voice={voice} />

          {/* extra instructions section */}
          <div className="jv-card" style={{ padding: ".8rem 1rem", marginTop: "1rem" }}>
            <div className="jv-mono jv-muted" style={{ fontSize: ".72rem", marginBottom: ".5rem" }}>➕ AUR KOI INSTRUCTION? (added to your next build)</div>
            <textarea data-testid="builder-extra-instructions" className="jv-textarea" style={{ minHeight: 60 }}
              placeholder="e.g. add a dark theme, use rupees ₹, add an admin login…"
              value={extra} onChange={(e) => setExtra(e.target.value)} />
          </div>
        </>
      )}

      {result?.preview_html && (
        <>
          <div className="jv-card" style={{ marginTop: "1rem", overflow: "hidden" }}>
            <div style={{ padding: ".6rem 1rem", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: ".5rem", flexWrap: "wrap" }}>
              <strong>Live Preview</strong>
              <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap" }}>
                <a data-testid="open-preview-newtab" className="jv-btn jv-btn-ghost" href={previewUrl} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Open in new tab</a>
                <button data-testid="deploy-open-btn" className="jv-btn jv-btn-ghost" onClick={() => setDeployOpen(!deployOpen)}><Globe size={15} /> Publish live</button>
                <a data-testid="download-project-zip-button" className="jv-btn" href={zipUrl}><Download size={16} /> Download project (.zip)</a>
              </div>
            </div>
            {deployOpen && (
              <div style={{ padding: ".9rem 1rem", borderBottom: "1px solid var(--border)", background: "#1C1512" }} data-testid="deploy-panel">
                <div className="jv-muted" style={{ fontSize: ".82rem", marginBottom: ".5rem" }}>
                  Publish the interactive demo live for free on Netlify. Paste a Netlify access token
                  (<a href="https://app.netlify.com/user/applications#personal-access-tokens" target="_blank" rel="noreferrer" style={{ color: "var(--gold)" }}>get one here</a>) — you'll get a public *.netlify.app link.
                </div>
                <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap" }}>
                  <input data-testid="netlify-token-input" className="jv-input" type="password" placeholder="Netlify access token" value={nToken} onChange={(e) => setNToken(e.target.value)} style={{ flex: "1 1 240px" }} />
                  <button data-testid="deploy-run-btn" className="jv-btn" onClick={doDeploy} disabled={deploying || !nToken.trim()}>{deploying ? <Spinner /> : <Globe size={16} />} {deploying ? "Publishing…" : "Publish"}</button>
                </div>
                {deployErr && <div style={{ color: "var(--red-2)", marginTop: ".5rem" }} data-testid="deploy-error">{deployErr}</div>}
                {deployUrl && (
                  <div style={{ marginTop: ".6rem" }} data-testid="deploy-result">
                    ✅ Live at <a href={deployUrl} target="_blank" rel="noreferrer" style={{ color: "var(--gold)", fontWeight: 700 }}>{deployUrl}</a>
                  </div>
                )}
              </div>
            )}
            <iframe data-testid="live-preview-iframe" title="preview" srcDoc={result.preview_html} sandbox="allow-scripts allow-same-origin allow-popups allow-forms allow-modals" style={{ width: "100%", height: 520, border: "none", background: "#fff" }} />
          </div>
          <div style={{ display: "flex", gap: ".6rem", marginTop: ".8rem" }}>
            <input data-testid="build-refine" className="jv-input" placeholder="Ask for a change — add a dark mode toggle and a chart" value={refine} onChange={(e) => setRefine(e.target.value)} onKeyDown={(e) => e.key === "Enter" && applyRefine()} />
            <button data-testid="build-refine-btn" className="jv-btn" onClick={applyRefine} disabled={building}>{building ? <Spinner /> : <Wand2 size={16} />} Apply change</button>
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
          <div className="jv-mono jv-muted" style={{ marginBottom: ".5rem", fontSize: ".8rem" }} data-testid="build-filecount">PROJECT FILES ({result.files.length}) — includes README, DOCUMENTATION.md & Dockerfiles</div>
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

      {!active && apps.length > 0 && (
        <div style={{ marginTop: "1rem" }}>
          <div className="jv-muted jv-mono" style={{ marginBottom: ".5rem", fontSize: ".8rem" }}>YOUR PROJECTS ({apps.length})</div>
          {apps.map((a) => (
            <div key={a.id} className="jv-card" style={{ padding: ".7rem 1rem", marginBottom: ".5rem", display: "flex", justifyContent: "space-between", alignItems: "center", gap: ".5rem", flexWrap: "wrap" }}>
              <span>{a.idea.slice(0, 60)}</span>
              <div style={{ display: "flex", gap: ".4rem" }}>
                <a className="jv-btn jv-btn-ghost" href={`${API}/apps/${a.id}/preview`} target="_blank" rel="noreferrer"><ExternalLink size={15} /></a>
                <a className="jv-btn jv-btn-ghost" href={`${API}/apps/${a.id}/zip`}><Download size={15} /> .zip</a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------- Team ------------------------------- */
function TeamTab() {
  const { agents, progress, agentsCfg, presets, savePreset, applyPreset, deletePreset } = useBuilder();
  const [presetName, setPresetName] = useState("");
  const live = agents.length ? agents : agentsCfg.map((a) => ({ ...a, status: "queued" }));
  const working = live.filter((a) => a.status === "working").length;
  const done = live.filter((a) => a.status === "done").length;

  const save = () => { savePreset(presetName.trim() || "My Crew"); setPresetName(""); };

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

      {/* Save My Crew */}
      <div className="jv-card" style={{ padding: ".9rem 1.1rem", marginBottom: "1rem" }} data-testid="crew-presets">
        <div className="jv-mono jv-muted" style={{ fontSize: ".74rem", marginBottom: ".55rem" }}>💾 MERI PASANDIDA TEAM — save your model line-up & reuse it</div>
        <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap" }}>
          <input data-testid="crew-preset-name" className="jv-input" placeholder="Name this crew (e.g. Fast & Cheap)" value={presetName} onChange={(e) => setPresetName(e.target.value)} style={{ flex: "1 1 220px" }} onKeyDown={(e) => e.key === "Enter" && save()} />
          <button data-testid="crew-preset-save" className="jv-btn" onClick={save}><Save size={15} /> Save crew</button>
        </div>
        {presets.length > 0 && (
          <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap", marginTop: ".7rem" }}>
            {presets.map((p) => (
              <div key={p.id} className="jv-chip" style={{ display: "flex", alignItems: "center", gap: ".4rem", padding: ".3rem .5rem .3rem .75rem" }} data-testid={`crew-preset-${p.id}`}>
                <button className="jv-mono" style={{ background: "none", border: "none", color: "var(--gold)", cursor: "pointer", fontWeight: 700 }} onClick={() => applyPreset(p)} title="Apply this crew">{p.name}</button>
                <button style={{ background: "none", border: "none", color: "var(--red-2)", cursor: "pointer" }} onClick={() => deletePreset(p.id)} title="Delete"><Trash2 size={13} /></button>
              </div>
            ))}
          </div>
        )}
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
