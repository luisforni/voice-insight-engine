import os
import uuid
import time
import aiofiles
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.models.schemas import (
    AnalysisResponse, AnalysisRequest,
    LLMProvider as LLMProviderEnum,
    TranscriptionProvider as TranscriptionProviderEnum,
)
from app.services.transcription import get_transcription_provider
from app.services.llm import get_llm_provider

router = APIRouter(prefix="/api/v1", tags=["analysis"])

SUPPORTED_FORMATS = {".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".flac", ".webm"}

@dataclass
class Job:
    job_id: str
    status: str = "processing"          # processing | completed | failed
    stage: str = "queued"               # queued | transcribing | analyzing | done
    transcription: Optional[dict] = None
    analysis: Optional[dict] = None
    error: Optional[str] = None
    processing_time_ms: Optional[int] = None
    created_at: float = field(default_factory=time.time)

_jobs: dict[str, Job] = {}

MAX_JOB_AGE_SECONDS = 3600  # auto-clean jobs older than 1h


def _cleanup_old_jobs():
    cutoff = time.time() - MAX_JOB_AGE_SECONDS
    stale = [jid for jid, j in _jobs.items() if j.created_at < cutoff]
    for jid in stale:
        del _jobs[jid]


async def _process_job(
    job_id: str,
    tmp_path: str,
    transcription_provider: str,
    llm_provider: str,
    language: str,
    analysis_depth: str,
):
    job = _jobs[job_id]
    start_time = time.time()
    try:
        job.stage = "transcribing"
        transcriber = get_transcription_provider(transcription_provider)
        transcription = await transcriber.transcribe(tmp_path, language=language or None)

        job.stage = "analyzing"
        llm = get_llm_provider(llm_provider)
        analysis = await llm.analyze(transcription, depth=analysis_depth)

        job.transcription = transcription.model_dump()
        job.analysis = analysis.model_dump() if hasattr(analysis, "model_dump") else analysis
        job.processing_time_ms = int((time.time() - start_time) * 1000)
        job.status = "completed"
        job.stage = "done"
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/analyze", status_code=202)
async def analyze_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Audio file to analyze"),
    transcription_provider: str = Form(default="local"),
    llm_provider: str = Form(default="ollama"),
    language: str = Form(default=""),
    analysis_depth: str = Form(default="standard"),
):
    """
    Submit audio for analysis. Returns job_id immediately (HTTP 202).
    Poll GET /api/v1/jobs/{job_id} for status and results.
    """
    settings = get_settings()
    _cleanup_old_jobs()

    suffix = Path(file.filename or "audio").suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {suffix}. Supported: {SUPPORTED_FORMATS}",
        )

    job_id = str(uuid.uuid4())[:8]
    tmp_path = f"/tmp/{job_id}{suffix}"

    # Stream file to disk in chunks — never loads the entire file into RAM
    size = 0
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    try:
        async with aiofiles.open(tmp_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):  # 1 MB chunks
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {settings.MAX_FILE_SIZE_MB} MB limit",
                    )
                await out.write(chunk)
    except HTTPException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    # Register job and kick off background processing
    _jobs[job_id] = Job(job_id=job_id)
    background_tasks.add_task(
        _process_job,
        job_id, tmp_path,
        transcription_provider, llm_provider,
        language, analysis_depth,
    )

    return {"job_id": job_id, "status": "processing", "stage": "queued"}


@router.get("/jobs/{job_id}", response_model=AnalysisResponse)
async def get_job(job_id: str):
    """Poll this endpoint to get job status and results."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return AnalysisResponse(
        job_id=job.job_id,
        status=job.status,
        transcription=job.transcription,
        analysis=job.analysis,
        error=job.error,
        processing_time_ms=job.processing_time_ms,
    )


@router.post("/transcribe-only", response_model=AnalysisResponse)
async def transcribe_only(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    provider: str = Form(default="local"),
    language: str = Form(default=""),
):
    """Transcription only, no LLM analysis. Returns job_id immediately."""
    job_id = str(uuid.uuid4())[:8]
    suffix = Path(file.filename or "audio").suffix.lower()
    tmp_path = f"/tmp/{job_id}{suffix}"

    async with aiofiles.open(tmp_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            await out.write(chunk)

    async def _transcribe_only():
        job = _jobs[job_id]
        try:
            job.stage = "transcribing"
            transcriber = get_transcription_provider(provider)
            transcription = await transcriber.transcribe(tmp_path, language=language or None)
            job.transcription = transcription.model_dump()
            job.status = "completed"
            job.stage = "done"
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    _jobs[job_id] = Job(job_id=job_id)
    background_tasks.add_task(_transcribe_only)

    return AnalysisResponse(job_id=job_id, status="processing")
