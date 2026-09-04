import { Compass, Database, Server, Code2, Palette, Terminal, MonitorPlay, CheckCircle2, Cpu } from "lucide-react";
import { useBuilder } from "./BuilderContext";

const ICONS = { Compass, Database, Server, Code2, Palette, Terminal, MonitorPlay, CheckCircle2 };

function ModelSelect({ agentId, fallback }) {
  const { modelsList, selected, setModel, building } = useBuilder();
  return (
    <select className="bhai-model-select" data-testid={`per-agent-model-select-${agentId}`}
      value={selected[agentId] || fallback} disabled={building}
      onChange={(e) => setModel(agentId, e.target.value)}>
      {modelsList.map((m) => <option key={m.id} value={m.id}>{`${m.name} · ${m.badge}`}</option>)}
    </select>
  );
}

function AgentCard({ agent, live, variant }) {
  const Icon = ICONS[agent.icon] || Cpu;
  const status = live?.status || "queued";
  const name = live?.name || agent.name;
  const title = live?.title || agent.role;
  const quip = live?.quip;
  const contribution = live?.contribution;
  const fallback = agent.default_model || live?.model;

  if (variant === "row") {
    return (
      <div className={`bhai-agent row ${status}`} data-testid={`agent-card-${agent.id}`}>
        <div style={{ display: "flex", alignItems: "center", gap: ".4rem", marginBottom: ".35rem" }}>
          <span className="bhai-agent-ic"><Icon size={14} /></span>
          <span className={`bhai-status ${status}`} data-testid={`agent-status-${agent.id}`} style={{ marginLeft: "auto" }}>{status}</span>
        </div>
        <div style={{ fontWeight: 800, fontSize: ".84rem", fontFamily: "'Outfit',sans-serif", lineHeight: 1.15 }}>{name}</div>
        <div className="jv-muted" style={{ fontSize: ".68rem", marginBottom: ".3rem" }}>{title}</div>
        {quip && <div className="jv-fade" key={quip} style={{ fontSize: ".68rem", color: "var(--gold-2)", fontStyle: "italic", lineHeight: 1.3, minHeight: 26 }}>“{quip}”</div>}
        <ModelSelect agentId={agent.id} fallback={fallback} />
      </div>
    );
  }

  return (
    <div className={`bhai-agent ${status}`} data-testid={`agent-card-${agent.id}`}>
      <div style={{ display: "flex", alignItems: "center", gap: ".55rem" }}>
        <span className="bhai-agent-ic"><Icon size={16} /></span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: ".92rem", fontFamily: "'Outfit',sans-serif", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{name}</div>
          <div className="jv-muted" style={{ fontSize: ".72rem" }}>{title}</div>
        </div>
        <span className={`bhai-status ${status}`} data-testid={`agent-status-${agent.id}`}>{status}</span>
      </div>
      <div className="jv-muted jv-fade" key={quip || contribution} style={{ fontSize: ".76rem", marginTop: ".5rem", lineHeight: 1.4 }}>
        {quip ? `“${quip}”` : contribution || agent.desc}
      </div>
      <ModelSelect agentId={agent.id} fallback={fallback} />
    </div>
  );
}

export default function AgentPanel({ variant = "grid" }) {
  const { agentsCfg, agents } = useBuilder();
  const liveMap = {};
  agents.forEach((a) => { liveMap[a.id] = a; });
  const cls = variant === "grid" ? "bhai-team-grid" : variant === "row" ? "bhai-agent-row" : "";
  const testid = variant === "row" ? "agent-activity-row" : variant === "panel" ? "agent-activity-side-panel" : "agent-team-grid";
  return (
    <div className={cls} data-testid={testid}
      style={variant === "panel" ? { display: "flex", flexDirection: "column", gap: ".6rem" } : undefined}>
      {agentsCfg.map((a) => <AgentCard key={a.id} agent={a} live={liveMap[a.id]} variant={variant} />)}
    </div>
  );
}
