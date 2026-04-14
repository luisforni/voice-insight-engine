"use client";
import { useState, useCallback } from "react";
import { submitAnalysis, pollJob, AnalysisOptions, AnalysisResponse } from "@/lib/api";

type Stage = "idle" | "uploading" | "transcribing" | "analyzing" | "done" | "error";

const STAGE_LABELS: Record<string, string> = {
  queued:       "Queued, waiting to start...",
  transcribing: "Transcribing audio...",
  analyzing:    "Analysing with AI...",
  done:         "Complete",
};

export function useAnalysis() {
  const [stage, setStage] = useState<Stage>("idle");
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stageLabel, setStageLabel] = useState("");

  const analyze = useCallback(async (file: File, options: AnalysisOptions) => {
    setStage("uploading");
    setError(null);
    setResult(null);
    setStageLabel("Uploading audio file...");

    try {
      // 1. Upload file — returns immediately with job_id
      const { job_id } = await submitAnalysis(file, options);

      setStage("transcribing");
      setStageLabel("Transcribing audio...");

      // 2. Poll until done — backend runs Whisper + LLM in background
      const response = await pollJob(job_id, (backendStage) => {
        if (backendStage === "analyzing") {
          setStage("analyzing");
        }
        setStageLabel(STAGE_LABELS[backendStage] ?? backendStage);
      });

      if (response.status === "failed") {
        throw new Error(response.error || "Analysis failed");
      }

      setResult(response);
      setStage("done");
      setStageLabel("Complete");
    } catch (err: any) {
      setError(err.message || "Unknown error");
      setStage("error");
      setStageLabel("Failed");
    }
  }, []);

  const reset = useCallback(() => {
    setStage("idle");
    setResult(null);
    setError(null);
    setStageLabel("");
  }, []);

  return { stage, stageLabel, result, error, analyze, reset };
}
