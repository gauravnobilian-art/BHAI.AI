import { useState, useRef, useEffect } from "react";
import "@/App.css";
import axios from "axios";
import {
  MessageSquare, Mail, Search, Image as ImageIcon, Rocket,
  Send, Download, Copy, Check, Sparkles, Wand2,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TABS = [
  { id: "chat", label: "AI Chat", icon: MessageSquare },
  { id: "email", label: "Email", icon: Mail },
  { id: "research", label: "Research", icon: Search },
  { id: "image", label: "Images", icon: ImageIcon },
  { id: "build", label: "App Builder", icon: Rocket },
];

function Spinner() {
  return <span className="jv-spin" />;
}

/* ------------------------------- Chat ------------------------------- */
function ChatTab() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [style, setStyle] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const next = [...messages, { role: "user", content: input.trim() }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const { data } = await axios.post(`${API}/chat`, { messages: next, style });
      setMessages([...next, { role: "assistant", content: data.reply }]);
      setStyle("");
    } catch (e) {
      setMessages([...next, { role: "assistant", content: "⚠️ Failed to reach the AI." }]);
    } finally { setLoading(false); }
  };

  const presets = [
    { k: "professional", label: "✍️ Make Professional" },
    { k: "summarize", label: "📝 Summarize" },
    { k: "tone", label: "🎭 Change Tone" },
  ];

  return (
    <div data-testid="chat-tab">
      <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap", marginBottom: "1rem" }}>
        {presets.map((p) => (
          <button key={p.k}
            data-testid={`chat-preset-${p.k}`}
            className={`jv-preset ${style === p.k ? "active" : ""}`}
            onClick={() => setStyle(style === p.k ? "" : p.k)}>
            {p.label}
          </button>
        ))}
      </div>
      <div className="jv-card" style={{ padding: "1rem", minHeight: 360, maxHeight: 460, overflowY: "auto", marginBottom: "1rem" }}>
        {messages.length === 0 && (
          <p className="jv-muted">Ask Jarvis anything, or pick a rewrite style and paste your text.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start", marginBottom: ".7rem" }}>
            <div className={`jv-bubble ${m.role}`} style={{ maxWidth: "85%", whiteSpace: "pre-wrap" }}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && <div className="jv-muted" style={{ display: "flex", gap: ".5rem", alignItems: "center" }}><Spinner /> Jarvis is thinking…</div>}
        <div ref={endRef} />
      </div>
      <div style={{ display: "flex", gap: ".6rem" }}>
        <input
          data-testid="chat-input"
          className="jv-input"
          placeholder="Message Jarvis…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button data-testid="chat-send" className="jv-btn" onClick={send} disabled={loading}>
          <Send size={16} /> Send
        </button>
      </div>
    </div>
  );
}

/* ------------------------------- Email ------------------------------- */
function CopyBtn({ text }) {
  const [state, setState] = useState("idle");
  const copy = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
        document.body.appendChild(ta); ta.focus(); ta.select();
        document.execCommand("copy"); document.body.removeChild(ta);
      }
      setState("done");
    } catch {
      setState("fail");
    }
    setTimeout(() => setState("idle"), 1800);
  };
  return (
    <button data-testid="copy-btn" className="jv-btn jv-btn-ghost" onClick={copy}>
      {state === "done" ? <Check size={16} /> : <Copy size={16} />}{" "}
      {state === "done" ? "Copied" : state === "fail" ? "Press Ctrl+C" : "Copy"}
    </button>
  );
}

function EmailTab() {
  const [recipient, setRecipient] = useState("");
  const [tone, setTone] = useState("Polite");
  const [context, setContext] = useState("");
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);

  const gen = async () => {
    if (!context.trim() || loading) return;
    setLoading(true); setDraft("");
    try {
      const { data } = await axios.post(`${API}/email`, { recipient, tone, context });
      setDraft(data.draft);
    } catch { setDraft("⚠️ Failed to generate email."); }
    finally { setLoading(false); }
  };

  return (
    <div data-testid="email-tab">
      <div className="jv-grid-2" style={{ marginBottom: ".8rem" }}>
        <input data-testid="email-recipient" className="jv-input" placeholder="Recipient (e.g. Hiring Manager)"
          value={recipient} onChange={(e) => setRecipient(e.target.value)} />
        <select data-testid="email-tone" className="jv-select" value={tone} onChange={(e) => setTone(e.target.value)}>
          {["Polite", "Urgent", "Casual", "Formal", "Persuasive"].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      <textarea data-testid="email-context" className="jv-textarea" placeholder="What is this email about? What's your goal?"
        value={context} onChange={(e) => setContext(e.target.value)} />
      <div style={{ marginTop: ".8rem" }}>
        <button data-testid="email-generate" className="jv-btn" onClick={gen} disabled={loading}>
          {loading ? <Spinner /> : <Sparkles size={16} />} Generate Email
        </button>
      </div>
      {draft && (
        <div className="jv-card" style={{ padding: "1rem", marginTop: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: ".6rem" }}>
            <strong>📋 Draft</strong><CopyBtn text={draft} />
          </div>
          <pre className="jv-mono" data-testid="email-draft" style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: ".9rem" }}>{draft}</pre>
        </div>
      )}
    </div>
  );
}

/* ------------------------------- Research ------------------------------- */
function ResearchTab() {
  const [query, setQuery] = useState("");
  const [summary, setSummary] = useState("");
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);

  const go = async () => {
    if (!query.trim() || loading) return;
    setLoading(true); setSummary(""); setSources([]);
    try {
      const { data } = await axios.post(`${API}/research`, { query });
      setSummary(data.summary); setSources(data.sources || []);
    } catch { setSummary("⚠️ Research failed."); }
    finally { setLoading(false); }
  };

  return (
    <div data-testid="research-tab">
      <div style={{ display: "flex", gap: ".6rem" }}>
        <input data-testid="research-query" className="jv-input" placeholder="Ask anything — Jarvis searches the live web…"
          value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && go()} />
        <button data-testid="research-go" className="jv-btn" onClick={go} disabled={loading}>
          {loading ? <Spinner /> : <Search size={16} />} Search
        </button>
      </div>
      {summary && (
        <div className="jv-card" data-testid="research-summary" style={{ padding: "1.1rem", marginTop: "1rem", whiteSpace: "pre-wrap" }}>
          {summary}
        </div>
      )}
      {sources.length > 0 && (
        <div className="jv-card" style={{ padding: "1rem", marginTop: ".8rem" }}>
          <strong>🔗 Sources</strong>
          <ol style={{ margin: ".5rem 0 0", paddingLeft: "1.2rem" }}>
            {sources.map((s, i) => (
              <li key={i} style={{ marginBottom: ".3rem" }}>
                <a href={s.href} target="_blank" rel="noreferrer" style={{ color: "var(--neon)" }}>{s.title || s.href}</a>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

/* ------------------------------- Image ------------------------------- */
function ImageTab() {
  const [prompt, setPrompt] = useState("");
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [w, setW] = useState(1024);
  const [h, setH] = useState(1024);
  const [err, setErr] = useState(false);

  const gen = () => {
    if (!prompt.trim()) return;
    setLoading(true); setErr(false);
    const seed = Math.floor(Math.random() * 1e6);
    const u = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt.trim())}?width=${w}&height=${h}&nologo=true&seed=${seed}`;
    setUrl(u);
  };

  return (
    <div data-testid="image-tab">
      <textarea data-testid="image-prompt" className="jv-textarea" style={{ minHeight: 90 }}
        placeholder="Describe your image — e.g. a neon cyberpunk city in the rain, cinematic, 8k"
        value={prompt} onChange={(e) => setPrompt(e.target.value)} />
      <div style={{ display: "flex", gap: ".8rem", alignItems: "center", marginTop: ".8rem", flexWrap: "wrap" }}>
        <select data-testid="image-width" className="jv-select" style={{ width: 130 }} value={w} onChange={(e) => setW(+e.target.value)}>
          {[512, 768, 1024].map((n) => <option key={n} value={n}>W {n}</option>)}
        </select>
        <select data-testid="image-height" className="jv-select" style={{ width: 130 }} value={h} onChange={(e) => setH(+e.target.value)}>
          {[512, 768, 1024].map((n) => <option key={n} value={n}>H {n}</option>)}
        </select>
        <button data-testid="image-generate" className="jv-btn" onClick={gen}>
          <Wand2 size={16} /> Generate
        </button>
      </div>
      {url && (
        <div className="jv-card" style={{ padding: "1rem", marginTop: "1rem", textAlign: "center" }}>
          {loading && <div className="jv-muted" style={{ marginBottom: ".5rem", display: "flex", gap: ".5rem", justifyContent: "center" }}><Spinner /> Painting…</div>}
          {err && <div style={{ color: "#ff6b81" }} data-testid="image-error">⚠️ Image failed to load. Try again.</div>}
          {!err && (
            <img data-testid="image-result" src={url} alt={prompt}
              onLoad={() => setLoading(false)}
              onError={() => { setLoading(false); setErr(true); }}
              style={{ maxWidth: "100%", borderRadius: 14, border: "1px solid var(--border)" }} />
          )}
          {!err && !loading && (
            <div style={{ marginTop: ".8rem" }}>
              <a data-testid="image-download" className="jv-btn" href={url} target="_blank" rel="noreferrer" download="jarvis-image.png">
                <Download size={16} /> Open / Download
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------------- Build ------------------------------- */
function BuildTab() {
  const [idea, setIdea] = useState("");
  const [refine, setRefine] = useState("");
  const [html, setHtml] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const build = async () => {
    if (!idea.trim() || loading) return;
    setLoading(true); setErr("");
    try {
      const { data } = await axios.post(`${API}/build`, { idea });
      setHtml(data.html);
    } catch { setErr("⚠️ Build failed — please try again."); }
    finally { setLoading(false); }
  };

  const applyRefine = async () => {
    if (!refine.trim() || loading) return;
    setLoading(true); setErr("");
    try {
      const { data } = await axios.post(`${API}/build`, { idea, refine, current_html: html });
      setHtml(data.html); setRefine("");
    } catch { setErr("⚠️ Update failed — please try again."); }
    finally { setLoading(false); }
  };

  const download = () => {
    const blob = new Blob([html], { type: "text/html" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "index.html"; a.click();
  };

  return (
    <div data-testid="build-tab">
      <textarea data-testid="build-idea" className="jv-textarea" style={{ minHeight: 80 }}
        placeholder="Describe an app — e.g. a habit tracker with streaks, charts and dark mode"
        value={idea} onChange={(e) => setIdea(e.target.value)} />
      <div style={{ marginTop: ".8rem" }}>
        <button data-testid="build-run" className="jv-btn" onClick={build} disabled={loading}>
          {loading ? <Spinner /> : <Rocket size={16} />} Build it live
        </button>
      </div>
      {err && <div data-testid="build-error" style={{ color: "#ff6b81", marginTop: ".8rem" }}>{err}</div>}
      {html && (
        <>
          <div className="jv-card" style={{ marginTop: "1rem", overflow: "hidden" }}>
            <div style={{ padding: ".6rem 1rem", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong>🟢 Live Preview</strong>
              <button className="jv-btn jv-btn-ghost" onClick={download}><Download size={16} /> index.html</button>
            </div>
            <iframe data-testid="build-preview" title="preview" srcDoc={html}
              sandbox="allow-scripts allow-same-origin allow-popups allow-forms allow-modals"
              style={{ width: "100%", height: 520, border: "none", background: "#fff" }} />
          </div>
          <div style={{ display: "flex", gap: ".6rem", marginTop: ".8rem" }}>
            <input data-testid="build-refine" className="jv-input" placeholder="Refine — e.g. add a dark mode toggle and a chart"
              value={refine} onChange={(e) => setRefine(e.target.value)} onKeyDown={(e) => e.key === "Enter" && applyRefine()} />
            <button data-testid="build-refine-btn" className="jv-btn" onClick={applyRefine} disabled={loading}>
              {loading ? <Spinner /> : <Wand2 size={16} />} Apply
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/* ------------------------------- App ------------------------------- */
function App() {
  const [tab, setTab] = useState("chat");

  return (
    <div className="jv-app">
      <div style={{ maxWidth: 980, margin: "0 auto", padding: "2rem 1.2rem 4rem" }}>
        <div style={{ marginBottom: "1.4rem" }}>
          <div className="jv-hero" style={{ fontSize: "2.6rem" }}>🤖 Jarvis Personal OS</div>
          <p className="jv-muted" style={{ marginTop: ".2rem" }}>
            Your private command center — chat, email, live web research, images and instant apps.
          </p>
          <div style={{ marginTop: ".4rem" }}>
            {["AI Chat", "Web Research", "Email", "Images", "App Builder"].map((c) => (
              <span key={c} className="jv-chip">{c}</span>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", gap: ".35rem", background: "var(--panel)", border: "1px solid var(--border)",
          borderRadius: 14, padding: ".35rem", marginBottom: "1.4rem", overflowX: "auto" }}>
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button key={t.id} data-testid={`tab-${t.id}`}
                className={`jv-tab ${tab === t.id ? "active" : ""}`}
                onClick={() => setTab(t.id)}
                style={{ display: "flex", alignItems: "center", gap: ".4rem" }}>
                <Icon size={16} /> {t.label}
              </button>
            );
          })}
        </div>

        {tab === "chat" && <ChatTab />}
        {tab === "email" && <EmailTab />}
        {tab === "research" && <ResearchTab />}
        {tab === "image" && <ImageTab />}
        {tab === "build" && <BuildTab />}

        <div className="jv-footer" data-testid="footer">
          Jarvis Personal OS · built with ❤️ on Emergent
        </div>
      </div>
    </div>
  );
}

export default App;
