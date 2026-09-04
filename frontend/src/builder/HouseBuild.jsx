const STAGES = [
  { min: 0, max: 20, name: "Buniyaad", en: "Foundation & Layout" },
  { min: 21, max: 50, name: "Deewar", en: "Walls & Scaffold" },
  { min: 51, max: 80, name: "Chhat", en: "Roof & Framework" },
  { min: 81, max: 99, name: "Sajaawat", en: "Finishing & Painting" },
  { min: 100, max: 100, name: "Griha Pravesh", en: "House Ready — App Live!" },
];

export function stageFor(progress) {
  return STAGES.find((s) => progress >= s.min && progress <= s.max) || STAGES[0];
}

const show = (on) => ({ opacity: on ? 1 : 0.06, transform: on ? "none" : "translateY(14px)" });

export default function HouseBuild({ progress = 0 }) {
  const st = stageFor(progress);
  const foundation = progress > 2;
  const walls = progress >= 21;
  const roof = progress >= 51;
  const finish = progress >= 81;
  const ready = progress >= 100;

  return (
    <div className="bhai-house-wrap jv-fade" data-testid="house-construction">
      <div className="bhai-house-frame">
        <svg viewBox="0 0 320 260" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
          {/* sun */}
          <g className="bhai-sun" transform="translate(268,44)">
            <circle r="16" fill="#E5A93C" opacity=".9" />
            {[...Array(8)].map((_, i) => (
              <rect key={i} x="-1.2" y="-26" width="2.4" height="8" rx="1" fill="#F2C56A"
                transform={`rotate(${i * 45})`} />
            ))}
          </g>

          {/* crane */}
          <g className="bhai-crane" style={{ ...show(!ready), transition: "opacity .6s" }}>
            <rect x="40" y="40" width="6" height="150" fill="#3E7B52" />
            <rect x="40" y="40" width="120" height="6" fill="#3E7B52" />
            <line x1="150" y1="46" x2="150" y2="86" stroke="#A89B91" strokeWidth="1.5" />
            <rect x="144" y="86" width="12" height="9" fill="#E5A93C" />
          </g>

          {/* ground */}
          <rect className="bhai-ground" x="0" y="210" width="320" height="50" />
          <rect x="0" y="208" width="320" height="4" fill="#3E7B52" opacity=".8" />

          {/* foundation */}
          <g className="bhai-part" style={show(foundation)}>
            <rect x="86" y="198" width="150" height="14" fill="#5a453a" />
            <rect x="86" y="198" width="150" height="4" fill="#7a5f50" />
          </g>

          {/* walls (brick) */}
          <g className="bhai-part" style={show(walls)}>
            <rect x="94" y="118" width="134" height="82" fill="#D95D39" />
            {[...Array(4)].map((_, r) =>
              [...Array(7)].map((_, c) => (
                <rect key={`${r}-${c}`} x={96 + c * 19 + (r % 2 ? 9 : 0)} y={124 + r * 19}
                  width="16" height="14" fill="#c24e2b" stroke="#a53f22" strokeWidth="1" />
              ))
            )}
          </g>

          {/* roof */}
          <g className="bhai-part" style={show(roof)}>
            <polygon points="82,120 161,66 240,120" fill="#8a3b22" />
            <polygon points="82,120 161,66 240,120" fill="none" stroke="#E5A93C" strokeWidth="2" />
            <rect x="150" y="78" width="20" height="26" fill="#5a453a" />
          </g>

          {/* finishing: door, windows, mithila motif, lights */}
          <g className="bhai-part" style={show(finish)}>
            <rect x="146" y="150" width="30" height="50" rx="2" fill="#3E7B52" />
            <circle cx="170" cy="176" r="2" fill="#F2C56A" />
            <rect x="104" y="134" width="26" height="24" rx="2" fill={ready ? "#F2C56A" : "#1B2A4A"} stroke="#E5A93C" strokeWidth="2" />
            <rect x="192" y="134" width="26" height="24" rx="2" fill={ready ? "#F2C56A" : "#1B2A4A"} stroke="#E5A93C" strokeWidth="2" />
            {/* mithila motif band */}
            <g stroke="#E5A93C" strokeWidth="1.6" fill="none" opacity=".9">
              <path d="M100 190 q6 -8 12 0 q6 -8 12 0 q6 -8 12 0" />
              <path d="M188 190 q6 -8 12 0 q6 -8 12 0 q6 -8 12 0" />
            </g>
          </g>

          {/* ready: garland + glow */}
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
          <div className="jv-mono" data-testid="house-stage-label"
            style={{ fontSize: ".82rem", color: "var(--gold)", fontWeight: 700 }}>
            {st.name}
          </div>
          <div className="jv-muted" style={{ fontSize: ".74rem" }}>{st.en}</div>
        </div>
        <div className="bhai-progress-track" data-testid="house-progress-bar">
          <div className="bhai-progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="jv-mono" style={{ fontSize: ".9rem", color: "var(--gold-2)", fontWeight: 700, width: 46, textAlign: "right" }}>
          {progress}%
        </div>
      </div>
    </div>
  );
}
