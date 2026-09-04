import { Compass, Database, Server, Code2, Palette, Terminal, MonitorPlay, CheckCircle2, Cpu } from "lucide-react";
import { useBuilder } from "./BuilderContext";

const ICONS = { Compass, Database, Server, Code2, Palette, Terminal, MonitorPlay, CheckCircle2 };

function AgentCard({ agent, live }) {
  const { modelsList, selected, setModel, building } = useBuilder();
  const Icon = ICONS[agent.icon] || Cpu;
  const status = live?.status || "queued";
  const contribution = live?.contribution || agent.desc;
  const modelId = selected[agent.id] || agent.default_model || live?.model;

  return (
    <div className={`bhai-agent ${status}`} data-testid={`agent-card-${agent.id}`}>
      <div style={{ display: "flex", alignItems: "center", gap: ".55rem" }}>
        <span style={{
          width: 32, height: 32, borderRadius: 9, flex: "none", display: "grid", placeItems: "center",
          background: "rgba(229,169,60,.1)", border: "1px solid var(--border)", color: "var(--gold)",
        }}><Icon size={16} /></span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: ".92rem", fontFamily: "'Outfit',sans-serif", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {agent.name}
          </div>
          <div className="jv-muted" style={{ fontSize: ".72rem" }}>{agent.role}</div>
        </div>
        <span className={`bhai-status ${status}`} data-testid={`agent-status-${agent.id}`}>{status}</span>
      </div>
      <div className="jv-muted jv-fade" key={contribution} style={{ fontSize: ".76rem", marginTop: ".5rem", lineHeight: 1.4 }}>
        {contribution}
      </div>
      <select
        className="bhai-model-select"
        data-testid={`per-agent-model-select-${agent.id}`}
        value={modelId}
        disabled={building}
        onChange={(e) => setModel(agent.id, e.target.value)}
      >
        {modelsList.map((m) => (
          <option key={m.id} value={m.id}>{m.name} · {m.badge}</option>
        ))}
      </select>
    </div>
  );
}

export default function AgentPanel({ variant = "grid" }) {
  const { agentsCfg, agents } = useBuilder();
  const liveMap = {};
  agents.forEach((a) => { liveMap[a.id] = a; });

  return (
    <div className={variant === "grid" ? "bhai-team-grid" : ""}
      style={variant === "panel" ? { display: "flex", flexDirection: "column", gap: ".6rem" } : undefined}
      data-testid={variant === "panel" ? "agent-activity-side-panel" : "agent-team-grid"}>
      {agentsCfg.map((a) => <AgentCard key={a.id} agent={a} live={liveMap[a.id]} />)}
    </div>
  );
}
