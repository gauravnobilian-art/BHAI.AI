import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { http } from "../http";

const BuilderContext = createContext(null);
export const useBuilder = () => useContext(BuilderContext);

export function BuilderProvider({ children }) {
  const [modelsList, setModelsList] = useState([]);
  const [agentsCfg, setAgentsCfg] = useState([]);
  const [selected, setSelected] = useState({});
  const [idea, setIdea] = useState("");
  const [extra, setExtra] = useState("");
  const [refine, setRefine] = useState("");
  const [building, setBuilding] = useState(false);
  const [progress, setProgress] = useState(0);
  const [agents, setAgents] = useState([]);
  const [theme, setTheme] = useState("app");
  const [themeLabel, setThemeLabel] = useState("");
  const [banter, setBanter] = useState([]);
  const [result, setResult] = useState(null); // {appId, plan, files, preview_html}
  const [error, setError] = useState("");
  const [apps, setApps] = useState([]);
  const [presets, setPresets] = useState([]);
  const stopRef = useRef(false);

  const loadApps = useCallback(
    () => http.get("/history/apps").then(({ data }) => setApps(data.apps || [])).catch(() => {}),
    []
  );
  const loadPresets = useCallback(
    () => http.get("/crew-presets").then(({ data }) => setPresets(data.presets || [])).catch(() => {}),
    []
  );

  useEffect(() => {
    http.get("/models").then(({ data }) => {
      setModelsList(data.models || []);
      setAgentsCfg(data.agents || []);
      setAgents((data.agents || []).map((a) => ({ ...a, status: "queued", contribution: "" })));
      const init = {};
      (data.agents || []).forEach((a) => { init[a.id] = a.default_model; });
      setSelected(init);
    }).catch(() => {});
    loadApps();
    loadPresets();
    return () => { stopRef.current = true; };
  }, [loadApps, loadPresets]);

  const setModel = (agentId, modelId) => setSelected((s) => ({ ...s, [agentId]: modelId }));

  const savePreset = async (name) => {
    await http.post("/crew-presets", { name: name || "My Crew", models: selected }).catch(() => {});
    loadPresets();
  };
  const applyPreset = (p) => setSelected((s) => ({ ...s, ...(p.models || {}) }));
  const deletePreset = async (id) => {
    await http.delete(`/crew-presets/${id}`).catch(() => {});
    loadPresets();
  };
  const deployApp = async (appId, token) => {
    const { data } = await http.post(`/apps/${appId}/deploy`, { netlify_token: token });
    return data.url;
  };

  const build = async () => {
    if (!idea.trim() || building) return;
    setBuilding(true); setError(""); setResult(null); setProgress(0);
    setBanter([]); setTheme("app"); setThemeLabel("");
    stopRef.current = false;
    const fullIdea = extra.trim() ? `${idea}\n\nAdditional instructions:\n${extra.trim()}` : idea;
    try {
      const { data } = await http.post("/build", { idea: fullIdea, models: selected });
      const id = data.id;
      if (data.agents?.length) setAgents(data.agents);
      for (let i = 0; i < 200 && !stopRef.current; i++) {
        await new Promise((r) => setTimeout(r, 2500));
        try {
          const { data: st } = await http.get(`/apps/${id}`);
          setProgress(st.progress || 0);
          if (st.agents?.length) setAgents(st.agents);
          if (st.theme) setTheme(st.theme);
          if (st.theme_label) setThemeLabel(st.theme_label);
          if (st.banter?.length) setBanter(st.banter);
          if (st.status === "done") {
            setProgress(100);
            setResult({ appId: id, plan: st.plan || "", files: st.files || [], preview_html: st.preview_html || "" });
            loadApps();
            break;
          }
          if (st.status === "error") {
            setError("⚠️ Build failed — " + (st.error || "please try again."));
            break;
          }
        } catch { /* keep polling on transient errors */ }
      }
    } catch {
      setError("⚠️ Build failed — please try again.");
    } finally {
      setBuilding(false);
    }
  };

  const applyRefine = async () => {
    if (!refine.trim() || building || !result) return;
    setBuilding(true); setError("");
    try {
      const { data } = await http.post("/build", { idea, refine, current_html: result.preview_html });
      setResult((r) => ({ ...r, preview_html: data.preview_html }));
      setRefine("");
    } catch {
      setError("⚠️ Update failed — please try again.");
    } finally {
      setBuilding(false);
    }
  };

  const value = {
    modelsList, agentsCfg, selected, setModel,
    idea, setIdea, extra, setExtra, refine, setRefine,
    building, progress, agents, theme, themeLabel, banter, result, error,
    apps, loadApps, build, applyRefine,
    presets, savePreset, applyPreset, deletePreset, deployApp,
  };
  return <BuilderContext.Provider value={value}>{children}</BuilderContext.Provider>;
}
