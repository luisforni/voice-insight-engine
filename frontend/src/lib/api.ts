const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface AnalysisOptions {
  transcriptionProvider: "local" | "openai";
  llmProvider: "ollama" | "openai" | "anthropic" | "groq";
  language: string;
  analysisDepth: "quick" | "standard" | "deep";
}

export interface TranscriptionResult {
  text: string;
  language: string;
  duration_seconds: number;
  provider: string;
  segments: any[];
}

export interface Insight {
  category: string;
  content: string;
  confidence: "high" | "medium" | "low";
}

export interface SummaryResult {
  short_summary: string;
  detailed_summary: string;
  key_points: string[];
  insights: Insight[];
  action_items: string[];
  sentiment: "positive" | "negative" | "neutral" | "mixed";
  topics: string[];
  word_count: number;
  provider: string;
  model: string;
}

export interface AnalysisResponse {
  job_id: string;
  status: "processing" | "completed" | "failed";
  stage?: string;
  transcription?: TranscriptionResult;
  analysis?: SummaryResult;
  error?: string;
  processing_time_ms?: number;
}

export interface ProviderStatus {
  provider: string;
  available: boolean;
  model: string;
}

export interface SystemStatus {
  transcription_providers: ProviderStatus[];
  llm_providers: ProviderStatus[];
  default_transcription: string;
  default_llm: string;
}

// Submit audio for background processing — returns job_id immediately
export async function submitAnalysis(
  file: File,
  options: AnalysisOptions,
): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("transcription_provider", options.transcriptionProvider);
  form.append("llm_provider", options.llmProvider);
  form.append("language", options.language);
  form.append("analysis_depth", options.analysisDepth);

  const res = await fetch(`${API_BASE}/api/v1/analyze`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

// Poll job status until completed or failed
export async function pollJob(
  jobId: string,
  onStageChange?: (stage: string) => void,
  intervalMs = 2000,
): Promise<AnalysisResponse> {
  let lastStage = "";

  while (true) {
    const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data: AnalysisResponse = await res.json();

    if (data.stage && data.stage !== lastStage) {
      lastStage = data.stage;
      onStageChange?.(data.stage);
    }

    if (data.status === "completed" || data.status === "failed") {
      return data;
    }

    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

export async function getSystemStatus(): Promise<SystemStatus> {
  const res = await fetch(`${API_BASE}/api/v1/status`);
  return res.json();
}

export async function getOllamaModels(): Promise<{ models: string[] }> {
  const res = await fetch(`${API_BASE}/api/v1/ollama/models`);
  return res.json();
}

export async function pullOllamaModel(model: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/ollama/pull?model=${model}`, {
    method: "POST",
  });
  return res.json();
}
