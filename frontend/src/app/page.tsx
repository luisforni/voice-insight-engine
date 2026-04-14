"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { useAnalysis } from "@/hooks/useAnalysis";
import { getSystemStatus, getOllamaModels, SystemStatus } from "@/lib/api";
import type { AnalysisOptions } from "@/lib/api";

const Icon = {
  Mic: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5">
      <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3M9 22h6"/>
    </svg>
  ),
  Upload: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="17,8 12,3 7,8"/>
      <line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  ),
  Zap: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <polygon points="13,2 3,14 12,14 11,22 21,10 12,10 13,2"/>
    </svg>
  ),
  Check: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
      <polyline points="20,6 9,17 4,12"/>
    </svg>
  ),
  X: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  ),
  Brain: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5">
      <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.84A2.5 2.5 0 0 1 9.5 2"/>
      <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.84A2.5 2.5 0 0 0 14.5 2"/>
    </svg>
  ),
  Server: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/>
      <line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/>
    </svg>
  ),
  Cloud: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>
    </svg>
  ),
  ChevronDown: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
      <polyline points="6,9 12,15 18,9"/>
    </svg>
  ),
  Refresh: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <polyline points="23,4 23,10 17,10"/>
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
    </svg>
  ),
  FileAudio: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
      <polyline points="14,2 14,8 20,8"/>
      <path d="M9 13v4"/><path d="M12 11v6"/><path d="M15 13v4"/>
    </svg>
  ),
};

function Waveform({ active }: { active: boolean }) {
  return (
    <div className="flex items-center gap-[3px] h-8">
      {Array.from({ length: 16 }).map((_, i) => (
        <div
          key={i}
          className="wave-bar"
          style={{
            height: active ? `${20 + Math.random() * 60}%` : "20%",
            animationName: active ? "waveform" : "none",
            animationDuration: `${0.8 + (i % 4) * 0.15}s`,
            animationDelay: `${i * 0.05}s`,
            animationTimingFunction: "ease-in-out",
            animationIterationCount: "infinite",
            opacity: active ? 1 : 0.3,
            transition: "opacity 0.3s",
          }}
        />
      ))}
    </div>
  );
}

const LLM_PROVIDERS = [
  { id: "ollama", label: "Ollama", sublabel: "local", icon: "🦙", type: "local" },
  { id: "openai", label: "OpenAI", sublabel: "GPT-4o", icon: "⬡", type: "cloud" },
  { id: "anthropic", label: "Anthropic", sublabel: "Claude", icon: "◈", type: "cloud" },
  { id: "groq", label: "Groq", sublabel: "fast", icon: "⚡", type: "cloud" },
] as const;

const TRANSCRIPTION_PROVIDERS = [
  { id: "local", label: "Whisper Local", sublabel: "CPU/GPU", icon: "💻" },
  { id: "openai", label: "Whisper API", sublabel: "OpenAI", icon: "☁" },
] as const;

const DEPTH_OPTIONS = [
  { id: "quick", label: "Quick", desc: "~5s" },
  { id: "standard", label: "Standard", desc: "~15s" },
  { id: "deep", label: "Deep", desc: "~30s" },
] as const;

function SentimentBadge({ sentiment }: { sentiment: string }) {
  const map = {
    positive: { color: "#4ade80", bg: "rgba(74,222,128,0.1)", label: "▲ POSITIVE" },
    negative: { color: "#f87171", bg: "rgba(248,113,113,0.1)", label: "▼ NEGATIVE" },
    neutral: { color: "#94a3b8", bg: "rgba(148,163,184,0.1)", label: "◆ NEUTRAL" },
    mixed: { color: "#fbbf24", bg: "rgba(251,191,36,0.1)", label: "◇ MIXED" },
  };
  const s = map[sentiment as keyof typeof map] || map.neutral;
  return (
    <span style={{ color: s.color, background: s.bg, border: `1px solid ${s.color}40` }}
      className="text-xs font-mono px-2 py-1 rounded">
      {s.label}
    </span>
  );
}

function ConfidenceDot({ level }: { level: string }) {
  const colors = { high: "#4ade80", medium: "#fbbf24", low: "#f87171" };
  return <span style={{ background: colors[level as keyof typeof colors] || "#94a3b8" }}
    className="inline-block w-1.5 h-1.5 rounded-full mr-1.5 relative top-[-1px]" />;
}

export default function Home() {
  const { stage, stageLabel, result, error, analyze, reset } = useAnalysis();
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const [activeTab, setActiveTab] = useState<"summary" | "insights" | "raw">("summary");

  const [options, setOptions] = useState<AnalysisOptions>({
    transcriptionProvider: "local",
    llmProvider: "ollama",
    language: "",
    analysisDepth: "standard",
  });

  // Load system status
  useEffect(() => {
    getSystemStatus()
      .then(setStatus)
      .catch(() => null);
    getOllamaModels()
      .then(d => setOllamaModels(d.models || []))
      .catch(() => null);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  }, []);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) setFile(f);
  };

  const handleAnalyze = () => {
    if (!file) return;
    analyze(file, options);
  };

  const isProcessing = ["uploading", "transcribing", "analyzing"].includes(stage);
  const providerStatus = (pid: string) =>
    status?.llm_providers.find(p => p.provider === pid);

  return (
    <div className="relative z-10 min-h-screen">
      {/* Header */}
      <header className="border-b border-[var(--border)] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded border border-[var(--border-active)] flex items-center justify-center glow-green">
            <span className="text-[var(--accent)] text-sm">▶</span>
          </div>
          <div>
            <div className="text-[var(--accent)] font-display text-sm font-bold tracking-widest uppercase glow-text">
              Voice Insight Engine
            </div>
            <div className="text-[var(--text-muted)] text-xs">multi-provider audio intelligence</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {status?.llm_providers.map(p => (
            <div key={p.provider} className="flex items-center gap-1.5">
              <div className={`w-1.5 h-1.5 rounded-full ${p.available ? "bg-[var(--accent)]" : "bg-red-500"}`}
                style={p.available ? { boxShadow: "0 0 6px #4ade80" } : {}} />
              <span className="text-[var(--text-muted)] text-xs">{p.provider}</span>
            </div>
          ))}
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">

        {/* LEFT: Upload + Results */}
        <div className="space-y-6">

          {/* Upload zone */}
          {stage === "idle" || stage === "error" ? (
            <div>
              <div
                onDrop={handleDrop}
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onClick={() => fileRef.current?.click()}
                className={`card p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-300 min-h-[220px]
                  ${dragging ? "card-active scale-[1.01]" : "hover:border-[var(--border-active)]"}`}
                style={dragging ? { boxShadow: "0 0 30px rgba(74,222,128,0.2)" } : {}}
              >
                <input ref={fileRef} type="file"
                  accept=".mp3,.mp4,.wav,.m4a,.ogg,.flac,.webm"
                  className="hidden" onChange={handleFile} />

                {file ? (
                  <div className="space-y-3">
                    <div className="text-[var(--accent)] flex justify-center"><Icon.FileAudio /></div>
                    <div className="text-[var(--text-primary)] font-mono text-sm">{file.name}</div>
                    <div className="text-[var(--text-muted)] text-xs">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </div>
                    <Waveform active={false} />
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="text-[var(--text-muted)] flex justify-center opacity-40"><Icon.Upload /></div>
                    <div className="text-[var(--text-primary)] text-sm">DROP AUDIO FILE HERE</div>
                    <div className="text-[var(--text-muted)] text-xs">mp3 · wav · m4a · ogg · flac · webm</div>
                    <div className="badge">max 50 mb</div>
                  </div>
                )}
              </div>

              {error && (
                <div className="mt-3 card p-3 border-red-500/30 bg-red-500/5 flex items-center gap-2">
                  <span className="text-red-400"><Icon.X /></span>
                  <span className="text-red-300 text-xs font-mono">{error}</span>
                </div>
              )}

              {file && (
                <button onClick={handleAnalyze}
                  className="mt-4 w-full py-3 px-6 font-display font-bold text-sm tracking-widest uppercase
                    bg-[var(--accent)] text-[var(--bg-primary)] rounded
                    hover:bg-green-300 transition-all duration-200
                    flex items-center justify-center gap-2">
                  <Icon.Zap />
                  ANALYZE AUDIO
                </button>
              )}
            </div>
          ) : null}

          {/* Processing state */}
          {isProcessing && (
            <div className="card card-active p-8 space-y-6">
              <div className="flex items-center justify-between">
                <div className="text-[var(--accent)] text-xs uppercase tracking-widest">Processing</div>
                <div className="badge">
                  {stage === "uploading" ? "01/03" : stage === "transcribing" ? "02/03" : "03/03"}
                </div>
              </div>

              <div className="flex justify-center">
                <Waveform active={true} />
              </div>

              <div className="space-y-2">
                {["Uploading audio file", "Transcribing audio", "Analyzing with AI"].map((s, i) => {
                  const stageIndex = stage === "uploading" ? 0 : stage === "transcribing" ? 1 : 2;
                  return (
                    <div key={s} className="flex items-center gap-3">
                      <div className={`w-4 h-4 rounded-full border flex items-center justify-center text-xs
                        ${i < stageIndex ? "border-[var(--accent)] bg-[var(--accent)] text-black"
                          : i === stageIndex ? "border-[var(--accent)] animate-pulse"
                          : "border-[var(--border)] text-[var(--text-muted)]"}`}>
                        {i < stageIndex ? <Icon.Check /> : <span>{i + 1}</span>}
                      </div>
                      <span className={`text-xs font-mono
                        ${i === stageIndex ? "text-[var(--accent)]" : i < stageIndex ? "text-[var(--text-muted)] line-through" : "text-[var(--text-muted)]"}`}>
                        {s}
                        {i === stageIndex && <span className="cursor-blink" />}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Results */}
          {stage === "done" && result && (
            <div className="space-y-4 animate-fade-up">
              {/* Header bar */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-[var(--accent)] text-xs">✓ ANALYSIS COMPLETE</span>
                  <span className="text-[var(--text-muted)] text-xs">
                    {result.processing_time_ms ? `${(result.processing_time_ms / 1000).toFixed(1)}s` : ""}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {result.analysis && <SentimentBadge sentiment={result.analysis.sentiment} />}
                  <button onClick={reset}
                    className="text-[var(--text-muted)] hover:text-[var(--accent)] text-xs flex items-center gap-1 transition-colors">
                    <Icon.Refresh /> NEW
                  </button>
                </div>
              </div>

              {/* Short summary */}
              {result.analysis && (
                <div className="card p-5 border-[var(--border-active)]"
                  style={{ boxShadow: "0 0 20px rgba(74,222,128,0.08)" }}>
                  <div className="text-[var(--text-muted)] text-xs mb-2 uppercase tracking-widest">Summary</div>
                  <p className="text-[var(--text-primary)] text-sm leading-relaxed">
                    {result.analysis.short_summary}
                  </p>
                  <div className="flex flex-wrap gap-2 mt-3">
                    {result.analysis.topics.map(t => (
                      <span key={t} className="badge">{t}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Tabs */}
              <div className="flex gap-0 border-b border-[var(--border)]">
                {(["summary", "insights", "raw"] as const).map(tab => (
                  <button key={tab} onClick={() => setActiveTab(tab)}
                    className={`px-4 py-2 text-xs uppercase tracking-widest font-mono transition-colors
                      ${activeTab === tab
                        ? "text-[var(--accent)] border-b-2 border-[var(--accent)]"
                        : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"}`}>
                    {tab}
                  </button>
                ))}
              </div>

              {/* Tab: Summary */}
              {activeTab === "summary" && result.analysis && (
                <div className="space-y-4">
                  <div className="card p-5">
                    <div className="text-[var(--text-muted)] text-xs mb-3 uppercase tracking-widest">Key Points</div>
                    <ul className="space-y-2">
                      {result.analysis.key_points.map((p, i) => (
                        <li key={i} className="flex gap-3 text-sm">
                          <span className="text-[var(--accent)] mt-0.5 shrink-0">▸</span>
                          <span className="text-[var(--text-primary)] leading-relaxed">{p}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {result.analysis.action_items.length > 0 && (
                    <div className="card p-5">
                      <div className="text-[var(--text-muted)] text-xs mb-3 uppercase tracking-widest">Action Items</div>
                      <ul className="space-y-2">
                        {result.analysis.action_items.map((a, i) => (
                          <li key={i} className="flex gap-3 text-sm">
                            <span className="text-yellow-400 mt-0.5 shrink-0">□</span>
                            <span className="text-[var(--text-primary)]">{a}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="card p-5">
                    <div className="text-[var(--text-muted)] text-xs mb-3 uppercase tracking-widest">Full Summary</div>
                    <p className="text-sm text-[var(--text-primary)] leading-relaxed">
                      {result.analysis.detailed_summary}
                    </p>
                  </div>
                </div>
              )}

              {/* Tab: Insights */}
              {activeTab === "insights" && result.analysis && (
                <div className="grid gap-3">
                  {result.analysis.insights.map((ins, i) => (
                    <div key={i} className="card p-4 hover:border-[var(--border-active)] transition-colors">
                      <div className="flex items-center justify-between mb-2">
                        <span className="badge">{ins.category}</span>
                        <span className="text-xs text-[var(--text-muted)] flex items-center">
                          <ConfidenceDot level={ins.confidence} />{ins.confidence}
                        </span>
                      </div>
                      <p className="text-sm text-[var(--text-primary)] leading-relaxed">{ins.content}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Tab: Raw transcription */}
              {activeTab === "raw" && result.transcription && (
                <div className="card p-5">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[var(--text-muted)] text-xs uppercase tracking-widest">Transcription</span>
                    <div className="flex gap-3 text-xs text-[var(--text-muted)]">
                      <span>lang: {result.transcription.language}</span>
                      <span>{result.transcription.duration_seconds.toFixed(1)}s</span>
                      <span>via {result.transcription.provider}</span>
                    </div>
                  </div>
                  <p className="text-sm text-[var(--text-primary)] leading-relaxed font-mono whitespace-pre-wrap">
                    {result.transcription.text}
                  </p>
                </div>
              )}

              {/* Model info bar */}
              {result.analysis && (
                <div className="flex items-center gap-4 text-xs text-[var(--text-muted)] font-mono">
                  <span>LLM: {result.analysis.provider}/{result.analysis.model}</span>
                  <span>·</span>
                  <span>ASR: {result.transcription?.provider}</span>
                  <span>·</span>
                  <span>{result.analysis.word_count} words</span>
                  <span>·</span>
                  <span>job {result.job_id}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* RIGHT: Config panel */}
        <div className="space-y-4">
          {/* Transcription provider */}
          <div className="card p-4">
            <div className="flex items-center gap-2 mb-3">
              <Icon.Mic />
              <span className="text-xs uppercase tracking-widest text-[var(--text-muted)]">Transcription</span>
            </div>
            <div className="space-y-2">
              {TRANSCRIPTION_PROVIDERS.map(p => (
                <button key={p.id}
                  onClick={() => setOptions(o => ({ ...o, transcriptionProvider: p.id as any }))}
                  className={`provider-btn w-full card p-3 text-left flex items-center justify-between
                    ${options.transcriptionProvider === p.id ? "active" : ""}`}>
                  <div className="flex items-center gap-2">
                    <span className="text-base">{p.icon}</span>
                    <div>
                      <div className="text-xs font-mono text-[var(--text-primary)]">{p.label}</div>
                      <div className="text-xs text-[var(--text-muted)]">{p.sublabel}</div>
                    </div>
                  </div>
                  {options.transcriptionProvider === p.id && (
                    <span className="text-[var(--accent)]"><Icon.Check /></span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* LLM provider */}
          <div className="card p-4">
            <div className="flex items-center gap-2 mb-3">
              <Icon.Brain />
              <span className="text-xs uppercase tracking-widest text-[var(--text-muted)]">LLM Provider</span>
            </div>
            <div className="space-y-2">
              {LLM_PROVIDERS.map(p => {
                const ps = providerStatus(p.id);
                return (
                  <button key={p.id}
                    onClick={() => setOptions(o => ({ ...o, llmProvider: p.id as any }))}
                    className={`provider-btn w-full card p-3 text-left flex items-center justify-between
                      ${options.llmProvider === p.id ? "active" : ""}`}>
                    <div className="flex items-center gap-2">
                      <span className="text-base">{p.icon}</span>
                      <div>
                        <div className="text-xs font-mono text-[var(--text-primary)] flex items-center gap-2">
                          {p.label}
                          {p.type === "local"
                            ? <span className="text-[10px] text-[var(--text-muted)] flex items-center gap-1"><Icon.Server />local</span>
                            : <span className="text-[10px] text-[var(--text-muted)] flex items-center gap-1"><Icon.Cloud />cloud</span>
                          }
                        </div>
                        <div className="text-xs text-[var(--text-muted)]">
                          {ps ? ps.model : p.sublabel}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      {ps && (
                        <div className={`w-1.5 h-1.5 rounded-full ${ps.available ? "bg-[var(--accent)]" : "bg-red-500"}`} />
                      )}
                      {options.llmProvider === p.id && (
                        <span className="text-[var(--accent)]"><Icon.Check /></span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Ollama models */}
          {options.llmProvider === "ollama" && ollamaModels.length > 0 && (
            <div className="card p-4">
              <div className="text-xs uppercase tracking-widest text-[var(--text-muted)] mb-2">Local Models</div>
              <div className="flex flex-wrap gap-1.5">
                {ollamaModels.map(m => (
                  <span key={m} className="badge text-[10px]">{m}</span>
                ))}
              </div>
            </div>
          )}

          {/* Analysis depth */}
          <div className="card p-4">
            <div className="text-xs uppercase tracking-widest text-[var(--text-muted)] mb-3">Analysis Depth</div>
            <div className="grid grid-cols-3 gap-2">
              {DEPTH_OPTIONS.map(d => (
                <button key={d.id}
                  onClick={() => setOptions(o => ({ ...o, analysisDepth: d.id }))}
                  className={`provider-btn card p-2 text-center ${options.analysisDepth === d.id ? "active" : ""}`}>
                  <div className="text-xs font-mono text-[var(--text-primary)]">{d.label}</div>
                  <div className="text-[10px] text-[var(--text-muted)]">{d.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Language */}
          <div className="card p-4">
            <div className="text-xs uppercase tracking-widest text-[var(--text-muted)] mb-2">Language</div>
            <input
              type="text"
              value={options.language}
              onChange={e => setOptions(o => ({ ...o, language: e.target.value }))}
              placeholder="auto-detect"
              className="w-full bg-transparent border border-[var(--border)] rounded px-3 py-2 text-xs
                text-[var(--text-primary)] placeholder-[var(--text-muted)]
                focus:outline-none focus:border-[var(--border-active)] transition-colors"
            />
            <div className="text-[10px] text-[var(--text-muted)] mt-1">e.g. en, es, fr, de, pt</div>
          </div>

          {/* Stats */}
          {result?.analysis && (
            <div className="card p-4 space-y-2 animate-fade-up">
              <div className="text-xs uppercase tracking-widest text-[var(--text-muted)] mb-2">Run Stats</div>
              {[
                ["Processing", `${(result.processing_time_ms! / 1000).toFixed(2)}s`],
                ["Words", result.analysis.word_count],
                ["Audio", `${result.transcription?.duration_seconds.toFixed(1)}s`],
                ["Key Points", result.analysis.key_points.length],
                ["Insights", result.analysis.insights.length],
                ["Action Items", result.analysis.action_items.length],
              ].map(([k, v]) => (
                <div key={String(k)} className="flex justify-between text-xs font-mono">
                  <span className="text-[var(--text-muted)]">{k}</span>
                  <span className="text-[var(--accent)]">{v}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
