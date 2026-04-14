# Arquitectura — Voice Insight Engine

Este documento describe el flujo completo del sistema desde que el usuario carga un archivo de audio y pulsa "Analyze Audio" hasta que ve los resultados en pantalla. Se explica qué hace cada fichero, cada clase y cada función.

---

## Índice

1. [Visión general](#visión-general)
2. [Flujo completo paso a paso](#flujo-completo-paso-a-paso)
3. [Frontend — fichero por fichero](#frontend--fichero-por-fichero)
4. [Backend — fichero por fichero](#backend--fichero-por-fichero)
5. [Diagrama de dependencias](#diagrama-de-dependencias)

---

## Visión general

```
Usuario
  │
  │  1. Selecciona archivo + configura opciones
  │  2. Pulsa "ANALYZE AUDIO"
  ▼
Frontend (Next.js · localhost:3004)
  │
  │  3. POST /api/v1/analyze  →  recibe job_id en < 1s
  │  4. Polling GET /api/v1/jobs/{job_id}  cada 2 segundos
  ▼
Backend (FastAPI · localhost:8000)
  │
  │  5. Guarda el archivo en disco (streaming por chunks)
  │  6. Lanza worker en background
  │     ├── Transcripción con Whisper (puede tardar minutos)
  │     └── Análisis con LLM (Ollama / OpenAI / Anthropic / Groq)
  │  7. Guarda resultado en memoria
  ▼
Frontend
  │
  │  8. Polling detecta status="completed"
  │  9. Renderiza transcripción + resumen + insights
```

El procesamiento es **asíncrono**: el servidor responde de inmediato con un `job_id` y el cliente hace polling hasta que el trabajo termina. Esto evita timeouts con archivos grandes.

---

## Flujo completo paso a paso

### Paso 1 — El usuario selecciona un archivo

En `src/app/page.tsx`, el componente `Home` renderiza una zona de drop. El usuario puede:

- **Arrastrar y soltar** un archivo (evento `onDrop` → `handleDrop`)
- **Hacer clic** en la zona para abrir el explorador de archivos (evento `onChange` → `handleFile`)

En ambos casos el archivo queda almacenado en el estado local `file` (un `File` de la Web API).

---

### Paso 2 — El usuario configura opciones

El panel de la derecha de `page.tsx` actualiza el estado `options` (tipo `AnalysisOptions`):

- **Proveedor de transcripción**: `local` (Whisper en CPU/GPU) u `openai` (API de OpenAI)
- **Proveedor LLM**: `ollama`, `openai`, `anthropic` o `groq`
- **Profundidad**: `quick`, `standard` o `deep`
- **Idioma**: código ISO o vacío para autodetección

---

### Paso 3 — El usuario pulsa "ANALYZE AUDIO"

`handleAnalyze` en `page.tsx` llama a `analyze(file, options)` del hook `useAnalysis`.

---

### Paso 4 — El hook inicia el proceso (frontend)

`useAnalysis.analyze()` en `src/hooks/useAnalysis.ts`:

1. Cambia `stage` a `"uploading"` → la UI muestra la barra de progreso
2. Llama a `submitAnalysis(file, options)` de `src/lib/api.ts`
3. Recibe `{ job_id }` del servidor (respuesta HTTP 202 en menos de 1 segundo)
4. Cambia `stage` a `"transcribing"`
5. Llama a `pollJob(job_id, callback)` que hace GET cada 2 segundos
6. Cuando el backend cambia el `stage` a `"analyzing"`, el hook cambia su propio `stage` a `"analyzing"`
7. Cuando recibe `status: "completed"`, guarda el resultado en `result` y cambia `stage` a `"done"`

---

### Paso 5 — El archivo llega al backend

`POST /api/v1/analyze` en `backend/app/api/routes/analysis.py`:

1. Valida la extensión del archivo
2. **Escribe el archivo a disco en chunks de 1 MB** (nunca carga el archivo entero en RAM)
3. Comprueba que no supera `MAX_FILE_SIZE_MB`
4. Crea un registro `Job` en el diccionario `_jobs` con `status="processing"`
5. Registra `_process_job` como tarea en background con `BackgroundTasks`
6. **Responde HTTP 202 inmediatamente** con `{ job_id, status: "processing" }`

---

### Paso 6 — El worker de background transcribe el audio

`_process_job()` en `analysis.py` ejecuta en segundo plano:

1. Llama a `get_transcription_provider(provider)` para obtener el transcriptor
2. Llama a `transcriber.transcribe(tmp_path, language)`:
   - Si es `local`: carga el modelo Whisper y transcribe con CPU/GPU
   - Si es `openai`: envía el archivo a la API de OpenAI Whisper
3. Recibe un `TranscriptionResult` con el texto, idioma, duración y segmentos
4. Actualiza `job.stage = "analyzing"`

---

### Paso 7 — El worker analiza la transcripción con un LLM

Continuando en `_process_job()`:

1. Llama a `get_llm_provider(provider)` para obtener el proveedor LLM
2. Llama a `llm.analyze(transcription, depth)`:
   - Construye un prompt estructurado con `build_analysis_prompt()`
   - Llama a la API del LLM seleccionado
   - Parsea la respuesta JSON en un `SummaryResult`
3. Guarda `transcription` y `analysis` en el objeto `Job`
4. Marca `job.status = "completed"`
5. Elimina el archivo temporal de disco

---

### Paso 8 — El frontend detecta el resultado

El polling en `pollJob()` hace `GET /api/v1/jobs/{job_id}` cada 2 segundos. Cuando recibe `status: "completed"`, retorna el objeto completo al hook `useAnalysis`, que:

1. Guarda el resultado en el estado `result`
2. Cambia `stage` a `"done"`

---

### Paso 9 — La UI renderiza los resultados

El componente `Home` en `page.tsx` detecta `stage === "done"` y renderiza:

- **Resumen corto** y **topics** (etiquetas)
- **Tres pestañas**:
  - `Summary`: puntos clave, elementos de acción y resumen detallado
  - `Insights`: lista de insights con categoría y nivel de confianza
  - `Raw`: texto completo de la transcripción con metadatos
- **Barra de estadísticas**: tiempo de procesamiento, palabras, insights, proveedor y modelo usados

---

## Frontend — fichero por fichero

---

### `src/app/layout.tsx`

Layout raíz de Next.js. Se ejecuta en el servidor.

**`RootLayout({ children })`**
Envuelve toda la aplicación con las etiquetas `<html>` y `<body>`. Define los metadatos de la página (título y descripción).

---

### `src/app/globals.css`

Estilos globales. Define las variables CSS de tema (colores, bordes), las clases de utilidad personalizadas (`card`, `badge`, `provider-btn`, `glow-green`) y la animación `waveform` de las barras de sonido.

---

### `src/app/page.tsx`

Página principal de la aplicación. Componente cliente (`"use client"`). Es la única página de la app.

#### Constantes

**`Icon`**
Objeto con componentes SVG inline para cada icono de la UI (`Mic`, `Upload`, `Zap`, `Check`, `X`, `Brain`, `Server`, `Cloud`, `ChevronDown`, `Refresh`, `FileAudio`). Se usan SVG inline para no depender de ninguna librería externa de iconos.

**`LLM_PROVIDERS`**
Array con los cuatro proveedores LLM disponibles para mostrar en el panel de configuración.

**`TRANSCRIPTION_PROVIDERS`**
Array con los dos proveedores de transcripción disponibles.

**`DEPTH_OPTIONS`**
Array con las tres opciones de profundidad de análisis (`quick`, `standard`, `deep`).

#### Componentes

**`Waveform({ active })`**
Animación visual de barras de sonido. Cuando `active=true` anima 16 barras con alturas aleatorias usando la animación CSS `waveform`. Cuando `active=false` muestra las barras estáticas con opacidad reducida.

**`SentimentBadge({ sentiment })`**
Badge de color que muestra el sentimiento del análisis (`positive`, `negative`, `neutral`, `mixed`). El color y texto cambian según el valor.

**`ConfidenceDot({ level })`**
Punto de color pequeño que indica el nivel de confianza de un insight (`high`=verde, `medium`=amarillo, `low`=rojo).

#### Componente principal

**`Home()`**
Componente raíz de la página. Gestiona el estado global de la UI.

Estado interno:
- `file` — archivo seleccionado por el usuario
- `dragging` — si el usuario está arrastrando un archivo sobre la zona de drop
- `status` — estado de los proveedores (recibido del backend al cargar)
- `ollamaModels` — lista de modelos Ollama disponibles localmente
- `activeTab` — pestaña activa en la sección de resultados (`summary`, `insights`, `raw`)
- `options` — opciones de análisis seleccionadas por el usuario

Funciones:
- **`handleDrop(e)`** — gestiona el evento de soltar un archivo en la zona de drop. Extrae el `File` del evento y lo guarda en `file`.
- **`handleFile(e)`** — gestiona el cambio del `<input type="file">`. Extrae el `File` del evento y lo guarda en `file`.
- **`handleAnalyze()`** — llamada al pulsar el botón "ANALYZE AUDIO". Llama a `analyze(file, options)` del hook `useAnalysis`.
- **`providerStatus(pid)`** — busca en el array `status.llm_providers` el estado de disponibilidad de un proveedor por su id. Usado para mostrar el punto verde/rojo en el selector de proveedores.

`useEffect` inicial: al montar el componente llama a `getSystemStatus()` y `getOllamaModels()` para obtener el estado de los proveedores y la lista de modelos Ollama. Estos datos no son críticos; si fallan, simplemente no se muestran.

---

### `src/hooks/useAnalysis.ts`

Hook React que encapsula todo el ciclo de vida de un análisis: upload → polling → resultado.

**`useAnalysis()`**

Estado interno:
- `stage` — estado de la máquina de estados (`idle | uploading | transcribing | analyzing | done | error`)
- `result` — objeto `AnalysisResponse` completo cuando el análisis termina
- `error` — mensaje de error si algo falla
- `stageLabel` — texto descriptivo para mostrar al usuario en cada etapa

Retorna:
- `stage`, `stageLabel`, `result`, `error` — estado de solo lectura para la UI
- `analyze(file, options)` — inicia el análisis. Llama primero a `submitAnalysis` para subir el archivo y obtener el `job_id`, luego llama a `pollJob` que hace polling hasta recibir `status: "completed"` o `"failed"`. Actualiza `stage` y `stageLabel` conforme avanzan las etapas del backend.
- `reset()` — vuelve al estado inicial `idle` limpiando resultado y error.

**`STAGE_LABELS`**
Diccionario que mapea los nombres de etapa del backend (`queued`, `transcribing`, `analyzing`, `done`) al texto que se muestra al usuario en español.

---

### `src/lib/api.ts`

Cliente HTTP del backend. Todas las llamadas a la API están centralizadas aquí.

#### Interfaces (tipos)

- **`AnalysisOptions`** — opciones que el usuario selecciona: proveedor de transcripción, proveedor LLM, idioma y profundidad.
- **`TranscriptionResult`** — resultado de la transcripción: texto, idioma, duración, proveedor y segmentos.
- **`Insight`** — un insight individual: categoría, contenido y nivel de confianza.
- **`SummaryResult`** — resultado completo del análisis LLM: resumen corto, resumen detallado, puntos clave, insights, elementos de acción, sentimiento, temas, contador de palabras, proveedor y modelo.
- **`AnalysisResponse`** — respuesta del endpoint de jobs: `job_id`, `status`, `stage`, y opcionalmente `transcription`, `analysis`, `error` y `processing_time_ms`.
- **`ProviderStatus`** — disponibilidad de un proveedor: nombre, si está disponible y modelo configurado.
- **`SystemStatus`** — estado global del sistema: lista de proveedores de transcripción y LLM disponibles, y proveedores por defecto.

#### Funciones

**`submitAnalysis(file, options)`**
Construye un `FormData` con el archivo y las opciones y hace `POST /api/v1/analyze`. Devuelve `{ job_id }` nada más recibir la respuesta HTTP 202. No espera a que el procesamiento termine.

**`pollJob(jobId, onStageChange?, intervalMs?)`**
Bucle asíncrono que llama a `GET /api/v1/jobs/{jobId}` cada `intervalMs` milisegundos (por defecto 2000ms). En cada iteración:
- Si el campo `stage` del backend ha cambiado, llama al callback `onStageChange` con el nuevo valor.
- Si `status` es `"completed"` o `"failed"`, termina el bucle y retorna el objeto completo.
- En caso contrario espera `intervalMs` y repite.

**`getSystemStatus()`**
Llama a `GET /api/v1/status`. Retorna el estado de disponibilidad de todos los proveedores de transcripción y LLM.

**`getOllamaModels()`**
Llama a `GET /api/v1/ollama/models`. Retorna la lista de modelos instalados localmente en Ollama.

**`pullOllamaModel(model)`**
Llama a `POST /api/v1/ollama/pull?model={model}`. Dispara la descarga de un modelo en Ollama.

---

## Backend — fichero por fichero

---

### `app/main.py`

Punto de entrada de la aplicación FastAPI.

**Instancia `app`**
Crea la aplicación FastAPI con título, versión y URLs de documentación (`/docs` Swagger, `/redoc`).

**Middleware CORS**
Permite peticiones desde cualquier origen (`allow_origins=["*"]`). Necesario para que el frontend en otro puerto pueda llamar al backend.

**Routers**
Registra los dos routers de la aplicación: `analysis.router` y `system.router`, ambos con prefijo `/api/v1`.

**`health()`**
Endpoint `GET /health`. Retorna `{ status: "ok", version }`. Lo usa el healthcheck de Docker para saber si el contenedor está listo.

---

### `app/core/config.py`

Configuración de la aplicación mediante variables de entorno.

**`class Settings(BaseSettings)`**
Clase Pydantic que lee la configuración del fichero `.env` y las variables de entorno del sistema. Contiene todos los parámetros de la aplicación: modelos, claves API, URLs, límites de archivo. Si una variable no está definida, usa el valor por defecto.

**`get_settings()`**
Función decorada con `@lru_cache()`. Retorna siempre la misma instancia de `Settings` (singleton). El caché evita leer el fichero `.env` en cada petición.

---

### `app/models/schemas.py`

Modelos de datos Pydantic. Define la forma de todos los objetos que entran y salen de la API.

**`class TranscriptionProvider(str, Enum)`**
Enumeración de proveedores de transcripción válidos: `local` y `openai`.

**`class LLMProvider(str, Enum)`**
Enumeración de proveedores LLM válidos: `ollama`, `openai`, `anthropic`, `groq`.

**`class AnalysisRequest(BaseModel)`**
Modelo de los parámetros de una petición de análisis. No se usa directamente como body JSON (el endpoint usa `Form`), pero define los valores válidos y por defecto.

**`class TranscriptionResult(BaseModel)`**
Resultado de una transcripción: texto completo, idioma detectado, duración en segundos, nombre del proveedor y lista de segmentos con timestamps.

**`class Insight(BaseModel)`**
Un insight individual extraído por el LLM: categoría temática, contenido descriptivo y nivel de confianza (`high`, `medium`, `low`).

**`class SummaryResult(BaseModel)`**
Resultado completo del análisis LLM. Contiene: resumen corto (1-2 frases), resumen detallado (párrafo), lista de puntos clave, lista de insights, lista de elementos de acción, sentimiento global, temas detectados, contador de palabras, y nombre del proveedor y modelo usados.

**`class AnalysisResponse(BaseModel)`**
Respuesta de los endpoints de análisis y polling. Contiene el `job_id`, el `status` (`processing`, `completed`, `failed`), y opcionalmente `transcription`, `analysis`, `error` y `processing_time_ms`.

**`class ProviderStatus(BaseModel)`**
Estado de disponibilidad de un proveedor: nombre, booleano `available`, modelo configurado y detalles opcionales.

**`class SystemStatus(BaseModel)`**
Estado global del sistema: listas de `ProviderStatus` para transcripción y LLM, y nombres de los proveedores por defecto.

---

### `app/api/routes/analysis.py`

Router principal del análisis. Gestiona el ciclo completo: recepción del archivo, procesamiento en background y consulta de resultados.

#### Job store (almacén de trabajos)

**`@dataclass class Job`**
Estructura de datos de un trabajo de análisis. Campos:
- `job_id` — identificador único del trabajo
- `status` — estado global: `processing`, `completed` o `failed`
- `stage` — etapa detallada: `queued`, `transcribing`, `analyzing`, `done`
- `transcription` — resultado de la transcripción (dict) cuando está disponible
- `analysis` — resultado del análisis LLM (dict) cuando está disponible
- `error` — mensaje de error si el trabajo falla
- `processing_time_ms` — tiempo total de procesamiento en milisegundos
- `created_at` — timestamp de creación (para limpieza automática)

**`_jobs: dict[str, Job]`**
Diccionario en memoria que almacena todos los trabajos activos. La clave es el `job_id`. Los trabajos se eliminan automáticamente después de 1 hora.

**`_cleanup_old_jobs()`**
Elimina del diccionario `_jobs` todos los trabajos con más de `MAX_JOB_AGE_SECONDS` segundos de antigüedad. Se llama al inicio de cada nueva petición de análisis.

#### Worker de background

**`_process_job(job_id, tmp_path, transcription_provider, llm_provider, language, analysis_depth)`**
Función `async` que ejecuta el pipeline completo en background:

1. Actualiza `job.stage = "transcribing"`
2. Obtiene el proveedor de transcripción con `get_transcription_provider()`
3. Llama a `transcriber.transcribe(tmp_path, language)` y espera el resultado
4. Actualiza `job.stage = "analyzing"`
5. Obtiene el proveedor LLM con `get_llm_provider()`
6. Llama a `llm.analyze(transcription, depth)` y espera el resultado
7. Guarda `transcription` y `analysis` en el objeto `Job`
8. Marca `job.status = "completed"` y `job.stage = "done"`
9. En el bloque `finally`, elimina siempre el archivo temporal de disco

Si ocurre cualquier excepción en los pasos 2-8, marca `job.status = "failed"` y guarda el mensaje de error.

#### Endpoints

**`analyze_audio(background_tasks, file, transcription_provider, llm_provider, language, analysis_depth)`**
`POST /api/v1/analyze` — Recibe el audio y lo encola para procesamiento.

1. Llama a `_cleanup_old_jobs()`
2. Valida la extensión del archivo contra `SUPPORTED_FORMATS`
3. Escribe el archivo en `/tmp/{job_id}{extension}` en chunks de 1 MB con `aiofiles`. Si durante la escritura se supera `MAX_FILE_SIZE_MB`, lanza HTTP 413 y limpia el archivo parcial.
4. Crea un objeto `Job` y lo guarda en `_jobs`
5. Registra `_process_job` en `background_tasks` (FastAPI lo ejecutará al terminar esta función)
6. Retorna HTTP 202 con `{ job_id, status: "processing", stage: "queued" }`

**`get_job(job_id)`**
`GET /api/v1/jobs/{job_id}` — Consulta el estado de un trabajo.

Busca el `job_id` en `_jobs`. Si no existe, lanza HTTP 404. Si existe, retorna un `AnalysisResponse` con todos los campos disponibles en ese momento.

**`transcribe_only(background_tasks, file, provider, language)`**
`POST /api/v1/transcribe-only` — Solo transcripción, sin análisis LLM. Mismo patrón asíncrono que `analyze_audio` pero ejecuta solo el paso de transcripción.

---

### `app/api/routes/system.py`

Router para información del sistema y gestión de modelos Ollama.

**`get_status()`**
`GET /api/v1/status` — Comprueba la disponibilidad de todos los proveedores.

Itera sobre todos los proveedores LLM (via `all_providers()`) y los dos de transcripción, llamando a `is_available()` en cada uno. Retorna un `SystemStatus` con el estado real en ese momento.

**`list_ollama_models()`**
`GET /api/v1/ollama/models` — Lista los modelos instalados en Ollama.

Instancia `OllamaProvider` y llama a `provider.list_models()`, que consulta la API `GET /api/tags` de Ollama.

**`pull_ollama_model(model)`**
`POST /api/v1/ollama/pull?model={model}` — Dispara la descarga de un modelo.

Instancia `OllamaProvider` y llama a `provider.pull_model(model)`, que hace `POST /api/pull` al servicio Ollama con `stream: false`.

---

### `app/services/transcription/__init__.py`

Servicio de transcripción. Contiene los dos proveedores y la función factory.

**`class TranscriptionProvider(ABC)`**
Clase base abstracta que define la interfaz que deben implementar todos los transcriptores.
- `transcribe(audio_path, language)` — método abstracto: transcribe el audio del path indicado
- `is_available()` — método abstracto: comprueba si el proveedor está operativo

**`class LocalWhisperProvider(TranscriptionProvider)`**
Transcripción local usando el modelo Whisper de OpenAI ejecutado en CPU o GPU.

- `_model_cache: dict` — caché de clase compartido entre instancias. Evita cargar el modelo de Whisper en cada petición (cargar el modelo puede tardar varios segundos).
- **`is_available()`** — intenta importar el módulo `whisper`. Retorna `True` si está instalado.
- **`_load_model()`** — carga el modelo Whisper con el tamaño y dispositivo configurados en `Settings`. Usa `_model_cache` para reutilizar el modelo ya cargado en memoria.
- **`transcribe(audio_path, language)`** — ejecuta la transcripción. Como Whisper es una operación bloqueante de CPU, usa `loop.run_in_executor(None, _run)` para ejecutarla en un thread pool sin bloquear el event loop de asyncio. Retorna un `TranscriptionResult` con el texto, idioma, duración (extraída del último segmento) y los segmentos con timestamps.

**`class OpenAIWhisperProvider(TranscriptionProvider)`**
Transcripción usando la API de OpenAI Whisper (cloud).

- **`is_available()`** — comprueba que `OPENAI_API_KEY` no está vacía.
- **`transcribe(audio_path, language)`** — abre el archivo de audio y lo envía a `client.audio.transcriptions.create` con formato `verbose_json` para obtener también duración e idioma. Retorna un `TranscriptionResult`.

**`get_transcription_provider(provider)`**
Función factory. Recibe el nombre del proveedor (`"local"` u `"openai"`), busca la clase correspondiente en el diccionario `registry` y retorna una nueva instancia. Lanza `ValueError` si el nombre no existe.

---

### `app/services/llm/__init__.py`

Registro y factory de proveedores LLM.

**`_REGISTRY: dict[str, type[LLMProvider]]`**
Diccionario que mapea cada nombre de proveedor a su clase. Permite añadir nuevos proveedores simplemente agregando una entrada.

**`get_llm_provider(provider)`**
Función factory. Recibe el nombre del proveedor, busca su clase en `_REGISTRY` y retorna una nueva instancia. Lanza `ValueError` si el proveedor no está registrado, incluyendo en el mensaje los proveedores disponibles.

**`all_providers()`**
Retorna una instancia de cada proveedor registrado. Usado por `GET /api/v1/status` para comprobar la disponibilidad de todos.

---

### `app/services/llm/base.py`

Clase base abstracta para LLM y construcción de prompts.

**`SUMMARY_SYSTEM_PROMPT`**
Prompt de sistema que se envía a todos los LLMs. Le indica al modelo que es un analista experto y que debe responder **únicamente con JSON válido**, sin texto adicional ni markdown.

**`build_analysis_prompt(transcription, depth)`**
Construye el prompt de usuario para el análisis. Incluye:
- El schema JSON exacto que debe devolver el LLM (con todos los campos requeridos)
- La instrucción de profundidad según el nivel seleccionado (`quick`, `standard`, `deep`), que ajusta la cantidad de puntos clave e insights esperados
- El texto transcrito completo con su idioma y duración como contexto

**`class LLMProvider(ABC)`**
Clase base abstracta que define la interfaz de todos los proveedores LLM.

Propiedades abstractas:
- `provider_name` — nombre identificador del proveedor (ej. `"ollama"`)
- `model_name` — nombre del modelo configurado (ej. `"llama3.2"`)

Métodos abstractos:
- `is_available()` — comprueba si el proveedor está operativo (clave API presente, servicio accesible)
- `analyze(transcription, depth)` — envía la transcripción al LLM y retorna un `SummaryResult`

**`_parse_analysis_json(raw, provider, model)`**
Método de instancia compartido por todos los proveedores. Recibe la respuesta en texto crudo del LLM y la parsea a un `SummaryResult`:
1. Elimina bloques de código markdown si el LLM los incluyó (` ```json ``` `)
2. Parsea el JSON con `json.loads()`
3. Construye y retorna un `SummaryResult` con los campos extraídos

---

### `app/services/llm/ollama_provider.py`

Proveedor LLM para Ollama (modelos locales).

**`class OllamaProvider(LLMProvider)`**

- **`is_available()`** — hace `GET /api/tags` al servicio Ollama con timeout de 3 segundos. Retorna `True` si responde con HTTP 200.
- **`list_models()`** — hace `GET /api/tags` y extrae los nombres de los modelos del campo `models[].name`.
- **`pull_model(model)`** — hace `POST /api/pull` con `stream: false` para descargar un modelo. Timeout de 5 minutos.
- **`analyze(transcription, depth)`** — hace `POST /api/chat` con el modelo configurado, el system prompt y el prompt de análisis. Usa `format: "json"` para forzar respuesta JSON y `temperature: 0.3` para respuestas consistentes. Extrae el texto de `data["message"]["content"]` y lo parsea con `_parse_analysis_json()`.

---

### `app/services/llm/openai_provider.py`

Proveedor LLM para OpenAI (GPT-4o, etc.).

**`class OpenAIProvider(LLMProvider)`**

- **`is_available()`** — comprueba que `OPENAI_API_KEY` no está vacía.
- **`analyze(transcription, depth)`** — usa el SDK `AsyncOpenAI` para llamar a `chat.completions.create`. Especifica `response_format={"type": "json_object"}` para forzar JSON. Extrae el texto de `response.choices[0].message.content` y lo parsea.

---

### `app/services/llm/anthropic_provider.py`

Proveedor LLM para Anthropic (Claude).

**`class AnthropicProvider(LLMProvider)`**

- **`is_available()`** — comprueba que `ANTHROPIC_API_KEY` no está vacía.
- **`analyze(transcription, depth)`** — usa el SDK `AsyncAnthropic` para llamar a `messages.create`. El system prompt se pasa como parámetro `system` separado (así funciona la API de Anthropic). Extrae el texto de `response.content[0].text` y lo parsea.

---

### `app/services/llm/groq_provider.py`

Proveedor LLM para Groq (modelos open source con inferencia ultrarrápida).

**`class GroqProvider(LLMProvider)`**

- **`is_available()`** — comprueba que `GROQ_API_KEY` no está vacía.
- **`analyze(transcription, depth)`** — usa el SDK `AsyncGroq` para llamar a `chat.completions.create`. Usa `response_format={"type": "json_object"}` igual que OpenAI. Extrae el texto de `response.choices[0].message.content` y lo parsea.

---

## Diagrama de dependencias

```
page.tsx
  ├── useAnalysis.ts
  │     └── api.ts
  │           └── Backend API (HTTP)
  └── api.ts  (getSystemStatus, getOllamaModels)

main.py
  ├── analysis.router  (analysis.py)
  │     ├── get_transcription_provider()
  │     │     ├── LocalWhisperProvider   → openai-whisper
  │     │     └── OpenAIWhisperProvider  → openai SDK
  │     └── get_llm_provider()
  │           ├── OllamaProvider         → httpx → Ollama API
  │           ├── OpenAIProvider         → openai SDK → api.openai.com
  │           ├── AnthropicProvider      → anthropic SDK → api.anthropic.com
  │           └── GroqProvider           → groq SDK → api.groq.com
  └── system.router   (system.py)
        ├── all_providers()
        └── OllamaProvider.list_models() / pull_model()

config.py  ←  todos los servicios lo usan vía get_settings()
schemas.py ←  todos los servicios lo usan como tipos de datos
```

---

## Ficheros de infraestructura

### `docker-compose.yml`

Define tres servicios:
- **`backend`** — construye la imagen desde `backend/Dockerfile`, expone el puerto 8000, monta `backend/` como volumen para hot reload en desarrollo, depende de que `ollama` esté iniciado.
- **`frontend`** — construye la imagen desde `frontend/Dockerfile`, expone el puerto 3004 (host) → 3000 (contenedor), espera a que el backend esté healthy.
- **`ollama`** — imagen oficial `ollama/ollama`. No expone puertos al host (el backend lo alcanza por la red interna Docker `http://ollama:11434`).
- **`ollama-init`** — contenedor de un solo uso que espera 8 segundos y lanza la descarga del modelo configurado en `OLLAMA_MODEL`.

### `docker-compose.override.yml`

Sobreescrituras automáticas para desarrollo. Activa `--reload` en uvicorn y monta el código del backend como volumen para que los cambios se reflejen sin rebuild.

### `backend/Dockerfile`

Build multi-stage:
1. Instala dependencias del sistema (`ffmpeg`, `git`)
2. Instala `setuptools<71` antes de instalar `openai-whisper` (necesario porque `openai-whisper` usa un `setup.py` legacy que requiere `pkg_resources`, eliminado en setuptools≥71)
3. Descarga el modelo Whisper `base` en tiempo de build para que no haya espera en el primer uso

### `frontend/Dockerfile`

Build multi-stage:
1. **`deps`** — instala todas las dependencias npm (incluyendo devDependencies necesarias para el build)
2. **`builder`** — ejecuta `next build` con `output: "standalone"` activado en `next.config.js`
3. **`runner`** — imagen final mínima que solo contiene el output compilado, sin `node_modules`
