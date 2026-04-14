# vie-frontend

Dashboard web para el Voice Insight Engine. Permite subir audios, seleccionar proveedores de IA y visualizar los resultados de transcripción y análisis.

[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js)](https://nextjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-blue?logo=typescript)](https://typescriptlang.org)
[![Tailwind](https://img.shields.io/badge/Tailwind-3-38bdf8?logo=tailwindcss)](https://tailwindcss.com)

---

## Descripción

`vie-frontend` es la interfaz de usuario del Voice Insight Engine. Comunica con el backend de forma **asíncrona**: sube el audio, recibe un `job_id` inmediatamente y hace polling hasta que el procesamiento termina, sin bloquear la interfaz.

---

## Tecnologías

| Librería | Versión | Uso |
|---|---|---|
| Next.js | 14.2.5 | Framework React con App Router |
| React | 18 | UI |
| TypeScript | 5 | Tipado estático |
| Tailwind CSS | 3.4 | Estilos |
| Lucide React | 0.441 | Iconos |

---

## Estructura del proyecto

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Layout raíz (fuentes, metadatos)
│   │   ├── page.tsx            # Página principal (UI completa)
│   │   └── globals.css         # Estilos globales Tailwind
│   ├── hooks/
│   │   └── useAnalysis.ts      # Hook: upload → polling → resultado
│   └── lib/
│       └── api.ts              # Cliente HTTP del backend
├── Dockerfile                  # Build multi-stage para producción
├── next.config.js              # Configuración Next.js (standalone output)
├── tailwind.config.ts          # Configuración Tailwind
├── tsconfig.json               # Configuración TypeScript
└── package.json
```

---

## Flujo de la aplicación

```
Usuario sube audio
       │
       ▼
useAnalysis.analyze(file, options)
       │
       ├─► submitAnalysis()  →  POST /api/v1/analyze
       │                        ← { job_id }  (inmediato)
       │
       └─► pollJob(job_id)   →  GET /api/v1/jobs/{job_id}  (cada 2s)
                                ← { status: "processing", stage: "transcribing" }
                                ← { status: "processing", stage: "analyzing" }
                                ← { status: "completed", transcription, analysis }
                                       │
                                       ▼
                               Renderiza resultados
```

---

## Módulos principales

### `src/lib/api.ts`

Cliente HTTP del backend. Exporta:

| Función | Descripción |
|---|---|
| `submitAnalysis(file, options)` | Sube el audio al backend. Devuelve `{ job_id }` |
| `pollJob(jobId, onStageChange?, intervalMs?)` | Hace polling hasta `completed` o `failed` |
| `getSystemStatus()` | Estado de disponibilidad de todos los proveedores |
| `getOllamaModels()` | Lista de modelos Ollama disponibles localmente |
| `pullOllamaModel(model)` | Descarga un modelo Ollama |

### `src/hooks/useAnalysis.ts`

Hook React que gestiona el ciclo de vida completo del análisis:

```ts
const { stage, stageLabel, result, error, analyze, reset } = useAnalysis();
```

| Campo | Tipo | Descripción |
|---|---|---|
| `stage` | `idle \| uploading \| transcribing \| analyzing \| done \| error` | Estado actual |
| `stageLabel` | `string` | Texto descriptivo para mostrar al usuario |
| `result` | `AnalysisResponse \| null` | Resultado completo cuando `stage === "done"` |
| `error` | `string \| null` | Mensaje de error cuando `stage === "error"` |
| `analyze(file, options)` | función | Inicia el análisis |
| `reset()` | función | Vuelve al estado inicial |

---

## Variables de entorno

| Variable | Por defecto | Descripción |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | URL base del backend |

En Docker, esta variable se pasa desde `docker-compose.yml`.

---

## Desarrollo local

### Requisitos

- Node.js 20+
- npm 10+
- Backend corriendo en `http://localhost:8000`

### Instalar dependencias

```bash
cd frontend
npm install
```

### Iniciar servidor de desarrollo

```bash
npm run dev
# → http://localhost:3004
```

### Build de producción

```bash
npm run build
npm start
```

---

## Docker

El `Dockerfile` usa un **build multi-stage** para producir una imagen mínima:

| Stage | Descripción |
|---|---|
| `deps` | Instala todas las dependencias (incluyendo devDependencies para el build) |
| `builder` | Compila la aplicación con `next build` (genera output standalone) |
| `runner` | Imagen final mínima: solo el output compilado |

La imagen final **no incluye** `node_modules` gracias al modo `standalone` de Next.js.

```bash
# Desde la raíz del monorepo
docker compose up --build frontend
```

Puerto: `3004` (host) → `3000` (contenedor)

---

## Opciones de análisis disponibles

### Proveedor de transcripción

| Valor | Descripción |
|---|---|
| `local` | Whisper ejecutándose en CPU/GPU dentro del backend |
| `openai` | Whisper API de OpenAI (requiere `OPENAI_API_KEY`) |

### Proveedor LLM

| Valor | Descripción |
|---|---|
| `ollama` | Modelo local (sin coste, requiere Ollama corriendo) |
| `openai` | GPT-4o mini u otros (requiere `OPENAI_API_KEY`) |
| `anthropic` | Claude (requiere `ANTHROPIC_API_KEY`) |
| `groq` | Llama vía Groq (capa gratuita disponible, requiere `GROQ_API_KEY`) |

### Profundidad de análisis

| Valor | Descripción |
|---|---|
| `quick` | Resumen breve, 3 puntos clave, 2 insights |
| `standard` | Análisis equilibrado, 5 puntos clave, 3-4 insights |
| `deep` | Análisis exhaustivo, 8+ puntos clave, 5+ insights, temas implícitos |

---

## Licencia

MIT — [luisforni](https://github.com/luisforni)
