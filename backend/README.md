# vie-backend

API REST para transcripción de audio e inteligencia con LLMs. Construida con FastAPI, Whisper y soporte para múltiples proveedores de IA.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Whisper](https://img.shields.io/badge/Whisper-20240930-orange)](https://github.com/openai/whisper)

---

## Descripción

`vie-backend` es el núcleo del Voice Insight Engine. Recibe un archivo de audio, lo transcribe con Whisper y lo analiza con un LLM para extraer resumen, puntos clave, insights y elementos de acción.

El procesamiento es **asíncrono**: el endpoint de análisis devuelve un `job_id` inmediatamente (HTTP 202) y el trabajo se ejecuta en background, permitiendo procesar audios largos sin timeouts.

---

## Tecnologías

| Librería | Versión | Uso |
|---|---|---|
| FastAPI | 0.115.0 | Framework API REST |
| Uvicorn | 0.30.6 | Servidor ASGI |
| openai-whisper | 20240930 | Transcripción local (CPU/GPU) |
| Pydantic | 2.9.0 | Validación de datos y schemas |
| pydantic-settings | 2.5.2 | Configuración por variables de entorno |
| openai | 1.51.0 | Proveedor OpenAI (Whisper API + GPT) |
| anthropic | 0.34.2 | Proveedor Anthropic (Claude) |
| groq | 0.11.0 | Proveedor Groq |
| httpx | 0.27.2 | Cliente HTTP async (Ollama) |
| aiofiles | 24.1.0 | Escritura de ficheros asíncrona |
| pydub / ffmpeg-python | — | Procesamiento de audio |
| structlog | 24.4.0 | Logging estructurado |

---

## Estructura del proyecto

```
backend/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── analysis.py     # POST /analyze, GET /jobs/{id}, POST /transcribe-only
│   │       └── system.py       # GET /status, GET /ollama/models, POST /ollama/pull
│   ├── core/
│   │   └── config.py           # Settings con pydantic-settings (variables de entorno)
│   ├── models/
│   │   └── schemas.py          # Modelos Pydantic (request/response)
│   ├── services/
│   │   ├── transcription/
│   │   │   └── __init__.py     # LocalWhisperProvider, OpenAIWhisperProvider
│   │   └── llm/
│   │       ├── base.py         # Clase base LLMProvider + prompts
│   │       ├── ollama_provider.py
│   │       ├── openai_provider.py
│   │       ├── anthropic_provider.py
│   │       └── groq_provider.py
│   └── main.py                 # App FastAPI, CORS, routers
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   └── test_llm_providers.py
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

---

## Referencia de la API

### Análisis completo (asíncrono)

**`POST /api/v1/analyze`** — Envía un audio para transcripción + análisis LLM.

Devuelve `job_id` de forma **inmediata** (HTTP 202). El procesamiento ocurre en background.

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "file=@mi_audio.mp3" \
  -F "transcription_provider=local" \
  -F "llm_provider=ollama" \
  -F "language=es" \
  -F "analysis_depth=standard"
```

Respuesta:
```json
{
  "job_id": "a1b2c3d4",
  "status": "processing",
  "stage": "queued"
}
```

Parámetros del formulario:

| Campo | Tipo | Opciones | Por defecto |
|---|---|---|---|
| `file` | archivo | `.mp3`, `.mp4`, `.wav`, `.m4a`, `.ogg`, `.flac`, `.webm` | — |
| `transcription_provider` | string | `local`, `openai` | `local` |
| `llm_provider` | string | `ollama`, `openai`, `anthropic`, `groq` | `ollama` |
| `language` | string | código ISO (ej. `es`, `en`) o vacío para autodetección | `""` |
| `analysis_depth` | string | `quick`, `standard`, `deep` | `standard` |

---

**`GET /api/v1/jobs/{job_id}`** — Consulta el estado y resultado de un trabajo.

```bash
curl http://localhost:8000/api/v1/jobs/a1b2c3d4
```

Respuesta mientras procesa:
```json
{
  "job_id": "a1b2c3d4",
  "status": "processing"
}
```

Respuesta al completar:
```json
{
  "job_id": "a1b2c3d4",
  "status": "completed",
  "processing_time_ms": 12450,
  "transcription": {
    "text": "Texto transcrito...",
    "language": "es",
    "duration_seconds": 187.4,
    "provider": "local-whisper",
    "segments": [...]
  },
  "analysis": {
    "short_summary": "Resumen en 1-2 frases.",
    "detailed_summary": "Párrafo detallado...",
    "key_points": ["Punto 1", "Punto 2"],
    "insights": [
      { "category": "Tema principal", "content": "...", "confidence": "high" }
    ],
    "action_items": ["Acción 1"],
    "sentiment": "positive",
    "topics": ["tecnología", "producto"],
    "word_count": 1420,
    "provider": "ollama",
    "model": "llama3.2"
  }
}
```

Estados posibles del campo `status`: `processing` → `completed` / `failed`

---

**`POST /api/v1/transcribe-only`** — Solo transcripción, sin análisis LLM.

```bash
curl -X POST http://localhost:8000/api/v1/transcribe-only \
  -F "file=@mi_audio.wav" \
  -F "provider=local" \
  -F "language=es"
```

---

### Sistema

**`GET /api/v1/status`** — Estado de disponibilidad de todos los proveedores.

```bash
curl http://localhost:8000/api/v1/status | python3 -m json.tool
```

**`GET /api/v1/ollama/models`** — Lista los modelos Ollama instalados localmente.

**`POST /api/v1/ollama/pull?model=mistral`** — Descarga un modelo desde el registro de Ollama.

**`GET /health`** — Health check del servicio.

**`GET /docs`** — Swagger UI interactivo.

---

## Proveedores

### Transcripción

| Proveedor | Clave | Descripción |
|---|---|---|
| `local` | — | Whisper ejecutándose en CPU/GPU local |
| `openai` | `OPENAI_API_KEY` | Whisper API de OpenAI (nube, límite 25 MB) |

#### Modelos Whisper locales

| Modelo | VRAM aprox. | Velocidad | Precisión |
|---|---|---|---|
| `tiny` | ~1 GB | Muy rápido | Básica |
| `base` | ~1 GB | Rápido | Buena |
| `small` | ~2 GB | Moderado | Muy buena |
| `medium` | ~5 GB | Lento | Excelente |
| `large` | ~10 GB | Muy lento | Máxima |

### LLM

| Proveedor | Clave | Modelos de ejemplo |
|---|---|---|
| `ollama` | — (local) | `llama3.2`, `mistral`, `gemma2` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini`, `gpt-4o` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-3-5-haiku-20241022` |
| `groq` | `GROQ_API_KEY` | `llama-3.1-8b-instant` |

---

## Configuración

Todas las variables se configuran mediante el fichero `.env` en la raíz del monorepo o como variables de entorno:

| Variable | Por defecto | Descripción |
|---|---|---|
| `WHISPER_MODEL` | `base` | Modelo Whisper local |
| `WHISPER_DEVICE` | `cpu` | Dispositivo de inferencia (`cpu` o `cuda`) |
| `DEFAULT_TRANSCRIPTION_PROVIDER` | `local` | Proveedor de transcripción por defecto |
| `DEFAULT_LLM_PROVIDER` | `ollama` | Proveedor LLM por defecto |
| `MAX_FILE_SIZE_MB` | `50` | Tamaño máximo de archivo en MB |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | URL del servicio Ollama |
| `OLLAMA_MODEL` | `llama3.2` | Modelo Ollama a usar |
| `OPENAI_API_KEY` | — | Clave API de OpenAI |
| `OPENAI_MODEL` | `gpt-4o-mini` | Modelo OpenAI |
| `ANTHROPIC_API_KEY` | — | Clave API de Anthropic |
| `ANTHROPIC_MODEL` | `claude-3-5-haiku-20241022` | Modelo Anthropic |
| `GROQ_API_KEY` | — | Clave API de Groq |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Modelo Groq |

---

## Desarrollo local

### Requisitos

- Python 3.11+
- ffmpeg instalado en el sistema
- Docker (para Ollama)

### Configuración del entorno

```bash
cd backend

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate        # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### Ejecutar en desarrollo

```bash
# Arrancar Ollama por separado (o usar el de Docker)
docker run -d -p 11434:11434 ollama/ollama

# Iniciar el servidor con hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker

```bash
# Desde la raíz del monorepo
docker compose up --build backend
```

---

## Tests

```bash
# Con entorno virtual activado
pytest -v

# Con cobertura
pytest --cov=app --cov-report=term-missing

# Test específico
pytest tests/test_api.py -v
```

---

## Formatos de audio soportados

`.mp3` · `.mp4` · `.wav` · `.m4a` · `.ogg` · `.flac` · `.webm`

Tamaño máximo por defecto: **50 MB** (configurable con `MAX_FILE_SIZE_MB`).

---

## Licencia

MIT — [luisforni](https://github.com/luisforni)
