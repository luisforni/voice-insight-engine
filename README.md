# Voice Insight Engine — Monorepo

Pipeline de inteligencia de audio multi-proveedor. Transcribe voz con Whisper, resume y extrae insights con LLMs locales (Ollama) o APIs cloud.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js)](https://nextjs.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)](https://docker.com)

---

## Estructura del repositorio

Este es el **monorepo raíz**. Contiene dos submódulos git, cada uno con su propio repositorio:

```
voice-insight-engine/              ← este repo (orquestación)
├── backend/                       ← submódulo: vie-backend  (FastAPI + Whisper + LLMs)
├── frontend/                      ← submódulo: vie-frontend (Next.js)
├── docker-compose.yml             ← orquesta todos los servicios
├── docker-compose.override.yml    ← sobreescrituras para desarrollo (aplicado automáticamente)
├── Makefile                       ← atajos de desarrollo
└── .env.example                   ← plantilla de variables de entorno
```

| Repositorio | Descripción |
|---|---|
| `voice-insight-engine` | Monorepo raíz (este repo) |
| `vie-backend` | API FastAPI + Whisper + proveedores LLM |
| `vie-frontend` | Dashboard Next.js |

---

## Inicio rápido

### Clonar con submódulos

```bash
# Opción A: clonar + submódulos en un paso
git clone --recurse-submodules https://github.com/luisforni/voice-insight-engine.git
cd voice-insight-engine

# Opción B: ya clonado pero submódulos vacíos
git submodule update --init --recursive
```

### Configuración inicial

```bash
make setup
# → inicializa submódulos
# → copia .env.example a .env

# Edita tus claves API (todas opcionales — Ollama funciona sin claves)
nano .env
```

### Modo desarrollo (todo en Docker)

```bash
docker compose up --build
```

| Servicio | URL |
|---|---|
| Frontend | http://localhost:3004 |
| Backend API | http://localhost:8000 |
| Documentación Swagger | http://localhost:8000/docs |

### Modo producción

```bash
make up
```

---

## Comandos Makefile

```bash
make help               # mostrar todos los comandos

# Configuración
make setup              # primera vez: inicializar submódulos + .env
make submodules         # actualizar submódulos a la última versión

# Docker
make dev                # iniciar backend + ollama (modo dev, hot reload)
make up                 # iniciar todos los servicios (prod)
make down               # detener todo
make logs               # seguir todos los logs
make logs-backend       # seguir logs del backend únicamente

# Frontend (ejecución local sin Docker)
make frontend-install   # instalar dependencias npm
make frontend-dev       # servidor de desarrollo local

# Tests
make test               # ejecutar tests del backend
make test-cov           # tests con informe de cobertura HTML

# Modelos Ollama
make pull-model MODEL=mistral    # descargar un modelo Ollama
make list-models                 # listar modelos disponibles localmente
make status                      # comprobar estado de todos los proveedores

# Limpieza
make clean              # eliminar contenedores y volúmenes
make clean-all          # eliminar contenedores, volúmenes y caché de modelos
```

---

## Variables de entorno (`.env`)

Copia `.env.example` a `.env` y configura los proveedores que quieras usar. Solo Ollama es obligatorio para el funcionamiento sin claves externas.

```bash
# Transcripción
WHISPER_MODEL=base           # tiny | base | small | medium | large
WHISPER_DEVICE=cpu           # cpu | cuda

# Proveedores por defecto
DEFAULT_TRANSCRIPTION_PROVIDER=local    # local | openai
DEFAULT_LLM_PROVIDER=ollama             # ollama | openai | anthropic | groq

# Ollama (local, sin coste)
OLLAMA_MODEL=llama3.2

# OpenAI (opcional)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Anthropic (opcional)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-haiku-20241022

# Groq (opcional, capa gratuita disponible)
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.1-8b-instant
```

Todos los proveedores son opcionales. El sistema usa Ollama por defecto. Los proveedores se cambian **por petición**, sin necesidad de reiniciar.

---

## Arquitectura

```
┌──────────────────────────────────────────────────────────┐
│  vie-frontend (Next.js · :3004)                          │
│  AudioUpload → ProviderSelector → ResultsViewer          │
└───────────────────────┬──────────────────────────────────┘
                        │ 1. POST /api/v1/analyze  (multipart)
                        │ 2. ← HTTP 202 + job_id   (inmediato)
                        │ 3. GET /api/v1/jobs/{id} (polling cada 2s)
                        ▼
┌──────────────────────────────────────────────────────────┐
│  vie-backend (FastAPI · :8000)                           │
│                                                          │
│  POST /api/v1/analyze  → devuelve job_id (no bloquea)   │
│  GET  /api/v1/jobs/{id} → estado + resultado             │
│                                                          │
│  Background worker:                                      │
│    ├── TranscriptionService                              │
│    │     ├── LocalWhisperProvider  (openai-whisper)      │
│    │     └── OpenAIWhisperProvider (Whisper API)         │
│    └── LLMProviderFactory                                │
│          ├── OllamaProvider    → http://ollama:11434     │
│          ├── OpenAIProvider    → api.openai.com          │
│          ├── AnthropicProvider → api.anthropic.com       │
│          └── GroqProvider      → api.groq.com            │
└───────────────────────┬──────────────────────────────────┘
                        │
             ┌──────────┘
             ▼
┌──────────────────────┐
│  Ollama (:11434)     │
│  llama3.2 / mistral  │
└──────────────────────┘
```

### Flujo de procesamiento asíncrono

El backend procesa los audios de forma asíncrona para soportar archivos grandes sin timeouts:

```
Frontend                          Backend
   │                                 │
   │── POST /analyze (audio) ──────► │  guarda archivo en disco (streaming)
   │◄── 202 { job_id } ─────────────│  lanza worker en background
   │                                 │
   │── GET /jobs/{job_id} ─────────► │  status: "transcribing"
   │◄── { status: "processing" } ───│
   │                                 │  [Whisper procesando...]
   │── GET /jobs/{job_id} ─────────► │  status: "analyzing"
   │◄── { status: "processing" } ───│
   │                                 │  [LLM analizando...]
   │── GET /jobs/{job_id} ─────────► │
   │◄── { status: "completed",       │  resultado completo
   │      transcription: {...},      │
   │      analysis: {...} } ────────│
```

---

## Referencia de la API

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/v1/analyze` | POST | Envía audio para procesar. Devuelve `job_id` (HTTP 202) |
| `/api/v1/jobs/{job_id}` | GET | Consulta estado y resultado de un trabajo |
| `/api/v1/transcribe-only` | POST | Solo transcripción, sin análisis LLM |
| `/api/v1/status` | GET | Disponibilidad de todos los proveedores |
| `/api/v1/ollama/models` | GET | Lista modelos Ollama disponibles localmente |
| `/api/v1/ollama/pull` | POST | Descarga un modelo Ollama |
| `/health` | GET | Health check |
| `/docs` | GET | Swagger UI interactivo |

---

## Workflow con submódulos

### Trabajar en un submódulo

```bash
# Trabajar en el backend
cd backend
git checkout -b feat/mi-feature
# ... hacer cambios ...
git add . && git commit -m "feat: ..."
git push origin feat/mi-feature

# Volver al monorepo — actualizar el puntero del submódulo
cd ..
git add backend
git commit -m "chore: actualizar submódulo backend"
```

### Actualizar submódulos a la última versión

```bash
make submodules
# o manualmente:
git submodule update --remote --merge
```

### Ver estado de los submódulos

```bash
git submodule status
# muestra el hash de commit al que apunta cada submódulo
```

---

## Tests

```bash
make test        # tests unitarios e integración
make test-cov    # con informe de cobertura
```

---

## Licencia

MIT — [luisforni](https://github.com/luisforni)
