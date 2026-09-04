const THEMES = {
  bank: { accent: "#E5A93C", roof: "#8a3b22", sign: "BANK",
    stages: ["Zameen taiyaar", "Tijori-kamra", "Chhat dhalai", "Counter & Board", "Bank khul gaya!"] },
  shop: { accent: "#D95D39", roof: "#7a2f18", sign: "STORE",
    stages: ["Zameen taiyaar", "Dukaan ki deewar", "Shutter & Chhat", "Almari & Board", "Dukaan khul gayi!"] },
  food: { accent: "#E63946", roof: "#8a3b22", sign: "KITCHEN",
    stages: ["Zameen taiyaar", "Rasoi ki deewar", "Chimney & Chhat", "Chulha & Menu", "Dhaba khul gaya!"] },
  health: { accent: "#3E7B52", roof: "#245c3a", sign: "CLINIC",
    stages: ["Zameen taiyaar", "Ward ki deewar", "Chhat dhalai", "Reception & Board", "Clinic khul gaya!"] },
  school: { accent: "#5c74a8", roof: "#1B2A4A", sign: "SCHOOL",
    stages: ["Zameen taiyaar", "Class ki deewar", "Chhat dhalai", "Board & Gate", "School khul gaya!"] },
  app: { accent: "#E5A93C", roof: "#8a3b22", sign: "APP",
    stages: ["Buniyaad", "Deewar", "Chhat", "Sajaawat", "Taiyaar ho gaya!"] },
};

export function stageFor(progress, theme = "app") {
  const t = THEMES[theme] || THEMES.app;
  const idx = progress >= 100 ? 4 : progress >= 81 ? 3 : progress >= 51 ? 2 : progress >= 21 ? 1 : 0;
  return { name: t.stages[idx], idx };
}

const show = (on) => ({ opacity: on ? 1 : 0.06, transform: on ? "none" : "translateY(14px)" });

function Emblem({ theme, color }) {
  const c = color;
  if (theme === "bank")
    return <text x="161" y="150" textAnchor="middle" fontSize="26" fontWeight="900" fill={c} fontFamily="serif">₹</text>;
  if (theme === "health")
    return <g fill={c}><rect x="153" y="130" width="16" height="34" rx="2" /><rect x="144" y="139" width="34" height="16" rx="2" /></g>;
  if (theme === "school")
    return <g fill="none" stroke={c} strokeWidth="3"><path d="M148 138 h26 v20 h-26 z" /><path d="M161 138 v20" /></g>;
  if (theme === "shop")
    return <g fill="none" stroke={c} strokeWidth="3"><path d="M150 140 h22 l-3 20 h-16 z" /><path d="M154 140 a7 7 0 0 1 14 0" /></g>;
  if (theme === "food")
    return <g fill="none" stroke={c} strokeWidth="3"><ellipse cx="161" cy="152" rx="15" ry="8" /><path d="M154 140 v6 M161 138 v8 M168 140 v6" /></g>;
  return <text x="161" y="152" textAnchor="middle" fontSize="18" fontWeight="900" fill={c} fontFamily="monospace">{"</>"}</text>;
}

export default function BuildScene({ progress = 0, theme = "app" }) {
  const t = THEMES[theme] || THEMES.app;
  const st = stageFor(progress, theme);
  const foundation = progress > 2;
  const walls = progress >= 21;
  const roof = progress >= 51;
  const finish = progress >= 81;
  const ready = progress >= 100;

  return (
    <div className="bhai-house-wrap jv-fade" data-testid="build-scene">
      <div className="bhai-house-frame">
        <svg viewBox="0 0 320 260" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
          <g className="bhai-sun" transform="translate(268,44)">
            <circle r="16" fill={t.accent} opacity=".9" />
            {[...Array(8)].map((_, i) => (
              <rect key={i} x="-1.2" y="-26" width="2.4" height="8" rx="1" fill="#F2C56A" transform={`rotate(${i * 45})`} />
            ))}
          </g>

          <g className="bhai-crane" style={{ ...show(!ready), transition: "opacity .6s" }}>
            <rect x="40" y="40" width="6" height="150" fill="#3E7B52" />
            <rect x="40" y="40" width="120" height="6" fill="#3E7B52" />
            <line x1="150" y1="46" x2="150" y2="86" stroke="#A89B91" strokeWidth="1.5" />
            <rect x="144" y="86" width="12" height="9" fill={t.accent} />
          </g>

          <rect className="bhai-ground" x="0" y="210" width="320" height="50" />
          <rect x="0" y="208" width="320" height="4" fill="#3E7B52" opacity=".8" />

          <g className="bhai-part" style={show(foundation)}>
            <rect x="86" y="198" width="150" height="14" fill="#5a453a" />
            <rect x="86" y="198" width="150" height="4" fill="#7a5f50" />
          </g>

          <g className="bhai-part" style={show(walls)}>
            <rect x="94" y="118" width="134" height="82" fill={t.accent} opacity=".92" />
            {[...Array(4)].map((_, r) =>
              [...Array(7)].map((_, c) => (
                <rect key={`${r}-${c}`} x={96 + c * 19 + (r % 2 ? 9 : 0)} y={124 + r * 19}
                  width="16" height="14" fill="none" stroke="rgba(0,0,0,.18)" strokeWidth="1" />
              ))
            )}
          </g>

          <g className="bhai-part" style={show(roof)}>
            <polygon points="82,120 161,66 240,120" fill={t.roof} />
            <polygon points="82,120 161,66 240,120" fill="none" stroke={t.accent} strokeWidth="2" />
          </g>

          <g className="bhai-part" style={show(finish)}>
            {/* signboard */}
            <rect x="112" y="104" width="98" height="18" rx="3" fill="#1C1512" stroke={t.accent} strokeWidth="1.5" />
            <text x="161" y="117" textAnchor="middle" fontSize="11" fontWeight="800" fill={t.accent} fontFamily="'Outfit',sans-serif" letterSpacing="2">{t.sign}</text>
            {/* door + emblem */}
            <rect x="146" y="166" width="30" height="34" rx="2" fill="#3E7B52" />
            <Emblem theme={theme} color={ready ? "#F2C56A" : t.accent} />
            <rect x="104" y="150" width="24" height="22" rx="2" fill={ready ? "#F2C56A" : "#1B2A4A"} stroke={t.accent} strokeWidth="2" />
            <rect x="194" y="150" width="24" height="22" rx="2" fill={ready ? "#F2C56A" : "#1B2A4A"} stroke={t.accent} strokeWidth="2" />
          </g>

          <g className="bhai-garland" style={{ opacity: ready ? 1 : 0 }}>
            <path d="M82 120 Q161 150 240 120" stroke="#3E7B52" strokeWidth="2" fill="none" />
            {[...Array(9)].map((_, i) => (
              <circle key={i} cx={90 + i * 20} cy={120 + Math.sin((i / 8) * Math.PI) * 22}
                r="4" fill={i % 2 ? "#E63946" : "#E5A93C"} />
            ))}
          </g>
        </svg>
      </div>

      <div className="bhai-house-caption">
        <div style={{ minWidth: 0 }}>
          <div className="jv-mono" data-testid="scene-stage-label" style={{ fontSize: ".82rem", color: t.accent, fontWeight: 700 }}>{st.name}</div>
          <div className="jv-muted" style={{ fontSize: ".74rem" }}>Step {st.idx + 1} of 5</div>
        </div>
        <div className="bhai-progress-track" data-testid="scene-progress-bar">
          <div className="bhai-progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="jv-mono" style={{ fontSize: ".9rem", color: "var(--gold-2)", fontWeight: 700, width: 46, textAlign: "right" }}>{progress}%</div>
      </div>
    </div>
  );
}
