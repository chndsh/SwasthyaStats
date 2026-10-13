# Health Records App — Prototype Architecture (v0.4)

> **Scope:** prove the core loop only: **scan → OCR → structured extraction → review → trend chart → ask questions (RAG).**
> **Delivery target: Progressive Web Apps (PWAs)**, built with Flutter Web + FastAPI. **EasyOCR** for OCR. **Groq** is the default LLM provider, and **any OpenAI-compatible provider is a first-class goal**, usable by changing Settings (one or more API keys per provider). Runs on a developer machine with `docker compose up`; no hosting infrastructure required.

**Status:** Prototype v0.4  |  **Time box:** ~5 weeks  |  **Companion doc:** `architecture.md` (full product design)

---

## 0. What changed from v0.3

| Area | v0.3 | v0.4 / Decisions |
|---|---|---|
| LLM provider & model | Groq default, any OpenAI-compatible provider | Groq default, any OpenAI-compatible provider. **No hardcoded primary Groq model choice**; dynamically discovered or user-selected from `/settings/models`. |
| LLM credentials & limits | One LLM key | Key pool with failover. If all keys are rate-limited, document status transitions to `rate_limited` and pipeline pauses until a healthy key is detected via the probe ladder. |
| Client target & build | Flutter Web PWA | **Wasm compilation (`--wasm`)** is the primary build target for Flutter Web. Multi-page capture supports **batch file picking** as well as sequential camera capture. |
| OCR reconstruction | Row clustering | Adds a **lightweight heuristic to detect and merge vertically adjacent test-name cells** before pipe-delimited row emission. Model weights pulled dynamically on first run into named Docker volumes (`easyocr:`, `hf:`). |
| Privacy & RAG | Strict dropping & broad redaction | **Feasible, non-aggressive name masking** (anchored to patient profile & explicit headers). **No strict citation dropping** in RAG (preserve sentences, parse citations into UI chips). |


Earlier changes (v0.2 → v0.3): Flutter Android app became a Flutter Web PWA served by FastAPI from one origin; HTTPS required for phone testing; `image_picker` for capture; server-rendered page images; Groq compatibility layer (probe ladder, model discovery, rate-limit handling, reasoning-tag stripping, contract tests); responsive layout.

> **Licensing note.** All code below is open source. Groq is a hosted service that serves open-weight models. To stay within the "open source only" rule, choose a model whose weights have an open license (for example the Apache-2.0 GPT-OSS models that Groq hosts, or Qwen/Mistral variants where offered), and record the choice in `docs/licenses.md`. The compatibility layer means this is a Settings choice, not a code change.

---

## 1. Prototype goal and scope

### The question this prototype answers

> *Can a phone-friendly PWA turn a photo of a lab report into verified data, plot it over time, and answer questions about a patient's history, using EasyOCR and a configurable external LLM (Groq by default)?*

### In scope

| # | Capability | Done when |
|---|---|---|
| 1 | Install the PWA on a phone (Add to Home Screen), standalone launch | Passes installability checks |
| 2 | Capture (native camera via browser) or pick image/PDF, multi-page | Pages upload as one document |
| 3 | OCR (EasyOCR) + table-row reconstruction | `Hemoglobin 13.2 g/dL 12.0–15.5` becomes one row |
| 4 | Structured extraction (external LLM) | Values land in a table with units, ranges, dates |
| 5 | Review and confirm | Page image beside values, edit, confirm |
| 6 | Trend chart | Pick a test → line chart with reference band |
| 7 | Ask (RAG) | "What was my last HbA1c?" / "What am I taking?" → cited answer |
| 8 | **Settings** | Provider, base URL, model (discovered list), key, redaction, **Test connection** |

### Deliberately out of scope

| Skipped | Prototype substitute |
|---|---|
| Multi-user auth, JWT, TOTP | One backend API key; single patient (`patient_id` kept in schema) |
| Bills, sharing, PDF export, audit log | Not built |
| Queue + workers | FastAPI `BackgroundTasks` + `status` column, client polls |
| Offline data, sync, push | PWA shell loads offline; data requires network |
| Native Android/iOS builds, biometrics | Later (same Flutter codebase) |
| Medical coding (LOINC, ICD) | Small local lab dictionary |
| Prescriptions / discharge summaries | Medication questions answered from text RAG |

> **Data rule:** text is sent to an external provider, and the PWA may be reachable through a tunnel, so use **synthetic or fully anonymized documents only**.

---

## 2. Architecture at a glance

```mermaid
flowchart LR
  subgraph Phone["Phone / desktop browser"]
    PWA["Flutter Web PWA<br/>(installed or in a tab)"]
  end

  subgraph Dev["Developer machine: docker compose"]
    API["FastAPI<br/>serves PWA static files + /api/v1"]
    OCR[EasyOCR + row grouping]
    RED[PII redaction]
    EMB[Local embeddings]
    PG[(PostgreSQL + pgvector)]
    FS[(File volume: uploads + page images)]
  end

  TUN[["HTTPS dev tunnel or local CA<br/>(for phone testing)"]]
  GROQ[["Groq API (default)<br/>or any OpenAI-compatible provider"]]

  PWA <-->|HTTPS| TUN <--> API
  API --> FS
  API --> OCR --> RED
  RED -->|redacted text only| GROQ
  GROQ -->|JSON / tool calls| API
  API --> PG
  API --> EMB --> PG
```

Two containers (`api`, `postgres`) and a file volume. Outbound dependency: the LLM provider only. The PWA bundle is built with `flutter build web` and served by FastAPI.

### Principles

1. **Human confirms before data counts.** Extracted values stay `pending` until confirmed.
2. **Charts come from rows, never from the LLM.**
3. **The LLM calls fixed read-only tools** (no text-to-SQL).
4. **Every value links to its source page and OCR line**, and must be found in that OCR text (grounding check).
5. **Images never leave the machine.** Only redacted OCR text goes to the provider.
6. **Provider-agnostic seams:** OCR engine, LLM client, and embedder are interfaces.
7. **One origin, one build:** the browser only ever talks to the backend.

---

## 3. Tech stack

| Layer | Choice | License | Note |
|---|---|---|---|
| Client | Flutter (web target), `flutter_riverpod`, `dio`, `go_router` (hash URLs), `image_picker`, `file_picker`, `fl_chart`, `shared_preferences` | BSD / MIT | Avoid `dart:io`; use `XFile` bytes |
| API | FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2, Alembic | MIT / BSD | `StaticFiles` serves the PWA |
| DB | PostgreSQL 16 + `pgvector`, `pg_trgm` | PostgreSQL | rows + vectors + keyword search |
| OCR | **EasyOCR** (+ PyTorch CPU) | Apache 2.0 / BSD | Verify pretrained model licenses |
| Image / PDF | OpenCV, Pillow, `pypdfium2` | Apache / HPND / Apache-BSD | Avoid PyMuPDF (AGPL) |
| LLM client | `httpx` + `tenacity`, OpenAI-compatible `/chat/completions` | BSD / Apache | No vendor SDK |
| Embeddings | `sentence-transformers` + `multilingual-e5-small` (384-d) or `bge-small-en-v1.5` | Apache / MIT | Local; not every provider offers an embeddings endpoint |
| Secrets at rest | `cryptography` (Fernet) | Apache / BSD | Encrypts stored LLM key |
| Dev HTTPS | `cloudflared` quick tunnel (client is Apache-2.0; the tunnel service itself is hosted) **or** `mkcert` + Caddy for a fully self-managed LAN setup | Apache / BSD | Dev only, synthetic data only |
| PWA audit | Lighthouse | Apache 2.0 | Installability and performance checks |
| Tests | pytest, httpx + `respx` mocks; `flutter_test` | MIT / BSD | |

**Hardware:** 8 GB RAM minimum, 16 GB comfortable. No GPU needed.

---

## 4. Settings, secrets, and provider compatibility

### 4.1 Configurable settings

| Key | Default | Notes |
|---|---|---|
| `llm.provider` | `groq` | Preset id: `groq`, `openrouter`, `together`, `mistral`, `openai`, `ollama`, `custom` |
| `llm.base_url` | `https://api.groq.com/openai/v1` | Any OpenAI-compatible base URL |
| `llm.api_keys` | (secret list, 1..n) | API keys for the active provider, each with an optional label; encrypted at rest, masked in responses |
| `llm.key_strategy` | `failover` | `failover` (use first healthy key) or `round_robin`; see 4.2 |
| `llm.model` | chosen from discovered list or typed | No hardcoded primary model; dynamically discovered from `{base_url}/models` or typed. Any available model can be used. Pinning stored on extraction. Optional `llm.model_extract` / `llm.model_ask` allow a different model per path |
| `llm.structured_mode` | `auto` | `auto`, `strict_schema`, `best_effort_schema`, `json_object`, `prompt_only` |
| `llm.supports_tools` | auto-probed | If false: router-prompt fallback for Ask |
| `llm.max_tokens_param` | `max_tokens` | Some providers/models want `max_completion_tokens` |
| `llm.extra_params` | `{}` | JSON merged into the request body (e.g. reasoning options) |
| `llm.extra_headers` | `{}` | JSON merged into headers for unusual providers |
| `llm.strip_reasoning` | `true` | Remove `<think>…</think>` blocks before parsing |
| `llm.concurrency` | `2` | Max simultaneous LLM calls (rate-limit friendliness) |
| `llm.timeout_s`, `llm.max_output_tokens` | 60, 2000 | |
| `llm.daily_token_cap` | e.g. 200 000 | Hard stop with a clear message |
| `privacy.redact_pii` | **true** | Disable only for synthetic data |
| `ocr.languages` | `["en"]` (add `"hi"`, `"ne"`) | Reloads EasyOCR models |
| `embed.model` | `multilingual-e5-small` | Changing it triggers re-embed (fixed dimension) |

**Provider presets** only fill defaults; the user supplies key(s) and model:

| Preset | Base URL |
|---|---|
| **Groq (default)** | `https://api.groq.com/openai/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| Together AI | `https://api.together.xyz/v1` |
| Mistral | `https://api.mistral.ai/v1` |
| OpenAI | `https://api.openai.com/v1` |
| Local Ollama (later) | `http://localhost:11434/v1` |
| Custom | user-entered |

### 4.2 Key handling

- LLM keys are typed in **Settings** (one or several, for the active provider) and sent once (`PUT /api/v1/settings`) over HTTPS to the backend, which stores them **Fernet-encrypted** with a key derived from `SERVER_SECRET`. The browser never stores them.
- `GET /settings` returns each key masked with its label (`team-a ••••a1b2`). Logs, errors, and `llm_calls` never contain keys or prompt text. `llm_calls` records the **key label** (not the key) so usage can be attributed.
- Settings routes require the backend `API_KEY` header.
- Env fallback for headless/CI: `LLM_BASE_URL`, `LLM_API_KEY` (comma-separated for several keys), `LLM_MODEL`; `GROQ_API_KEY` is also read when the provider is `groq`. DB values win when present.
- **Key pool behavior:** with `failover`, the client uses the first healthy key and moves to the next on `401`/`403` (marks that key `bad`) or on `429` when the next key is available. With `round_robin`, calls rotate across healthy keys. A key is retried after its `Retry-After` window.
- **Rate-limit pause:** When all keys in the pool are rate-limited (`429` or daily token quota exhausted), the pipeline marks the affected document as `status = rate_limited` and pauses background extraction until a healthy key is detected via the periodic probe ladder or retry timer.
- **Important limit:** providers usually apply rate limits per account or organization, not per key (Groq does so per organization). Several keys from the same account **share one quota**, so they help with rotation, revocation, and usage attribution but **do not raise throughput**. Only keys from separate accounts have independent limits; confirm the provider's current terms before pooling keys that way.
- Keys apply to the active provider; switching provider swaps the key set. Use dedicated, spend-limited keys and rotate them when the prototype ends.

### 4.3 Model discovery and Test connection

- `GET /settings/models`: the backend calls `{base_url}/models` with the stored key and returns the ids, so the Settings screen shows a **dropdown with a "type your own" option**. Keeping this server-side avoids browser CORS problems and key exposure. If the provider has no `/models`, the field is free text.
- `POST /settings/test-llm` runs a **capability probe ladder** (for every configured key, reported per key label) and stores the result:
  1. reachability, auth, model exists, latency;
  2. structured output, highest working level first: `strict_schema` → `best_effort_schema` → `json_object` → `prompt_only`;
  3. tool calling (a trivial tool);
  4. whether `usage` token counts are returned (if not, estimate locally);
  5. whether reasoning tags appear in output.
  The Settings screen shows a checklist of results and the mode that will be used.

### 4.4 Groq specifics (verified against Groq's docs; re-check before relying on them)

| Topic | Design response |
|---|---|
| **Structured outputs** | Groq's `json_schema` supports `strict: true` (constrained decoding) only on a limited set of models (currently GPT-OSS 20B/120B), and `strict: false` (best-effort) on a wider set. The probe ladder picks whichever works for the chosen model. |
| **Structured outputs + tools** | Groq does not support using structured outputs together with tool use or streaming. Our design never combines them: **extraction calls use structured output (no tools); Ask calls use tools (no structured output)**. |
| **Rate limits** | Groq enforces per-model request and token limits (per minute and per day) and returns `429` with retry hints. The client honors `Retry-After`, caps concurrency (`llm.concurrency`), and the pipeline processes extraction jobs through a small semaphore. The app shows "waiting for rate limit" instead of failing. Check current limits in the Groq console. |
| **Reasoning models** | Some output reasoning text; `strip_reasoning` removes it, and `extra_params` can pass provider-specific options. |
| **Model churn** | Models are added and retired. The model id is configurable and pinned; a `model not found` error maps to a clear "pick another model" message in the app. |
| **Embeddings** | Not provided via the same path in the prototype; embeddings are local. |

### 4.5 Compatibility with "any other key"

- One request/response contract (`/chat/completions`, Bearer auth, `messages`, optional `response_format`, `tools`).
- Differences absorbed by settings, not code: base URL, token-parameter name, extra params/headers, structured mode, tool support, reasoning stripping.
- **Contract tests** run against a mock OpenAI-compatible server (`respx`): plain completion, JSON mode, JSON schema, tool call round trip, `429` with `Retry-After`, **key failover on `401` and `429`**, `<think>` blocks, missing `usage`, malformed JSON, `404 model_not_found`. An optional **live smoke test** reads `GROQ_API_KEY` (and any other `*_API_KEY`) from the environment and runs the probe ladder against that provider.

---

## 5. LLM integration layer

```python
class LlmClient(Protocol):
    def chat(
        self,
        messages: list[Message],
        *,
        purpose: Literal["extract", "route", "answer", "probe"],
        json_schema: dict | None = None,   # extraction calls
        tools: list[ToolSpec] | None = None,  # Ask calls; never together with json_schema
        temperature: float = 0.0,
    ) -> LlmResponse: ...
```

- **One implementation:** `OpenAICompatClient`. It reads current settings on every call, so changing model or keys applies immediately. A small `KeyPool` selects the key per call (section 4.2).
- **Structured output ladder:** use the configured/probed mode; on any schema failure, validate with Pydantic, retry once with the validation error appended, then step down a level.
- **Reliability:** timeouts, exponential backoff on `429`/`5xx`, errors mapped to codes the UI can show (`bad_key`, `model_not_found`, `rate_limited`, `quota`, `provider_down`).
- **Cost control:** every call logged in `llm_calls` (purpose, model, key label, tokens, latency, status; no content). Daily cap enforced before the call.
- **Caching:** extraction results keyed by `sha256(redacted_text + prompt_version + model)`.
- **Determinism:** temperature 0, pinned model id stored on each extraction.
- **Going local later:** point `base_url` at Ollama; no code changes.

---

## 6. OCR with EasyOCR

| Gives | Doesn't give |
|---|---|
| Text, polygon boxes, per-line confidence | Table structure or layout analysis |
| 80+ languages incl. English, Hindi, Nepali | Reading order across columns |
| Pure-pip install, CPU-capable | Strong handwriting or dense small print |

Expect CPU speed of tens of seconds per full page and a large Docker image (PyTorch). Cache models in a volume.

### Pipeline

1. **Pages:** PDF → images with `pypdfium2`; photos used directly.
2. **Normalize:** apply EXIF rotation, deskew, grayscale, mild contrast (CLAHE), resize so the long side is ~2000–2500 px. **Save this normalized page image** (`document_pages`): it is both the OCR input and what the PWA displays.
3. **Read:** `reader.readtext(img, detail=1, paragraph=False)` with tunable `mag_ratio`, `text_threshold`, `low_text`, `link_threshold`.
4. **Row reconstruction:** compute each box's y-center and height; cluster into rows with tolerance ≈ 0.5 × median height; apply a **lightweight heuristic to detect and merge vertically adjacent test-name cells** (e.g. multi-line test headers where wrapping occurs across consecutive lines) before pipe-delimited emission; sort by x; join cells with ` | `; emit `OcrLine(id, page, text, bbox, conf, row_id)`. Boxes are in the normalized page image's pixel space, so highlights align in the review screen.
5. **Numeric re-read (stretch):** re-read numeric-looking cells with `allowlist='0123456789.,<>-/%'`.
6. **Store:** `documents.ocr_lines` (jsonb) and row-grouped `ocr_text`.

```python
class OcrEngine(Protocol):
    def run(self, image: np.ndarray) -> OcrResult: ...   # EasyOcrEngine is the only implementation for now
```

---

## 7. The PWA

### 7.0 PWA-first stance

PWAs are the delivery target, not a stepping stone to a native app. Consequences:

- Every feature must work in the browser sandbox: no `dart:io`, no native plugins, no secure-enclave assumptions.
- One build serves phone and desktop; installation is Add to Home Screen / browser install.
- Native Android/iOS builds are **deferred and unplanned**. If they return to scope later, they reuse the same Flutter code.
- Target the **new WebAssembly (Wasm)** compilation (`--wasm`) for superior execution performance, smooth charting, and lower startup overhead compared to legacy CanvasKit/HTML renderers. Record the first-load numbers in `eval/RESULTS.md` by week 1.

### 7.1 Delivery model

- `flutter build web --wasm --release` produces `build/web`. FastAPI mounts it with `StaticFiles` at `/` and exposes the API under `/api/v1`. Same origin means **no CORS and no cookies**.
- Flutter's default **hash URLs** (`/#/labs`) avoid server-side route rewrites.
- A small `DEV_CORS=true` switch enables CORS for `localhost` ports **only** for the hot-reload workflow below.

### 7.2 Installability checklist

| Requirement | Plan |
|---|---|
| HTTPS (or `localhost`) | Dev tunnel or local CA (7.4) |
| Web app manifest | Name, short name, `display: standalone`, theme/background colors, `start_url`, 192/512 px icons including a maskable icon |
| Service worker | Use Flutter's generated worker (app-shell caching; check the current `--pwa-strategy` / service-worker guidance in the Flutter docs for your version) |
| Update flow | Show "New version available, reload" so a cached shell never hides new builds |
| Offline behavior | Shell loads offline; data screens show a clear "You're offline" state |
| Audit | Run Lighthouse on the tunnel URL; record installability and load size |

### 7.3 Capture and files on the web

- **Capture & Batch Pick:**
  - **Camera:** `ImagePicker().pickImage(source: ImageSource.camera, maxWidth: 2400, imageQuality: 85)` opens the phone's native camera from the browser without a `getUserMedia` permission flow. After each shot the user can "Add another page".
  - **Batch pick:** Supports batch file/photo selection via `ImagePicker().pickMultiImage()` and `FilePicker.platform.pickFiles(allowMultiple: true)` so users can select multiple report pages at once from their gallery or file system.
  - Desktop browsers fall back to a multi-file chooser.
- **Upload:** read `XFile.readAsBytes()` and send `MultipartFile.fromBytes` via `dio`. No `dart:io`.
- **Show pages:** `GET /documents/{id}/pages/{n}.png` returns the normalized page image. The app fetches it with `dio` (sending the API key header) and shows it with `Image.memory`. This avoids a PDF viewer on the web and `Image.network` header limits.
- **Image size:** cap uploads (for example 12 MB per file, 10 pages) and validate on the server.

### 7.4 HTTPS for phone testing

| Option | When |
|---|---|
| `localhost` | Desktop Chrome on the dev machine: installable and camera-capable without HTTPS |
| `cloudflared tunnel --url http://localhost:8000` | Fastest way to test on a real phone; gives a public HTTPS URL. **Public exposure:** keep a strong `API_KEY`, add rate limiting, close the tunnel when idle, synthetic data only |
| `mkcert` + Caddy on the LAN | Fully self-managed: install the local CA on the phone, serve `https://<laptop-ip>` |
| Hosting later | Any small VPS with Caddy (automatic HTTPS) |

### 7.5 Storage and auth in the browser

- Browsers cannot hold secrets securely, and `flutter_secure_storage` on web only wraps `localStorage`, so do not rely on it.
- The only client secret is the **backend API key**. Default: kept **in memory for the session** (re-enter after closing). Optional "Remember on this device" stores it in `shared_preferences` (localStorage), with a warning.
- The LLM key is write-only from the browser's perspective.
- Serve the app with a strict `Content-Security-Policy`, `X-Content-Type-Options`, and `Referrer-Policy`; no third-party scripts.

### 7.6 Responsive layout

| Width | Navigation | Review screen |
|---|---|---|
| < 600 px (phone) | Bottom nav | Page image on top, editable rows below (stacked, sheet for row editing) |
| 600–1024 px | Navigation rail | Side by side |
| > 1024 px | Side drawer | Two panes with wider chart area |

Design target: usable at **360 px** width.

### 7.8 PWA definition of done

| Check | Pass condition |
|---|---|
| Installable | Lighthouse installability passes; Add to Home Screen works on Android Chrome; desktop Chrome install works |
| Standalone | Launches without browser chrome, correct theme color and splash/icon (incl. maskable) |
| Camera | Native camera capture works from the installed app over HTTPS |
| Offline | App shell loads with no network; data screens show an offline state; no silent failures on upload |
| Updates | New build triggers the update banner; a cached shell never hides it |
| Performance | First-load size and time recorded over the tunnel; interaction usable on a mid-range Android phone |
| Layout | Usable at 360 px; keyboard and TalkBack navigation smoke-tested |
| Security | CSP and headers set; only the backend API key in the browser; Groq keys never reach the client |
| iOS | Smoke test on Safari (install, upload, camera); issues logged, not blocking |

### 7.7 Known web caveats

- CanvasKit's first load is several MB: record first-load size and time over the tunnel; consider the WebAssembly build option later.
- The service worker can serve a stale shell; the update banner and versioned asset names address this.
- Text selection, scrolling, and accessibility behave differently from a native Flutter app; test with TalkBack and keyboard navigation on desktop.
- iOS Safari can install PWAs but has different storage-eviction behavior. The prototype supports **Android Chrome and desktop Chrome**; iOS Safari is a smoke-test platform only.

---

## 8. Privacy for an external LLM

| Control | Detail |
|---|---|
| **Text only** | Original images and PDFs never leave the server. |
| **Redaction before sending** | Feasible, non-aggressive masking of patient name (anchored specifically to profile name and explicit header cues like `Name:`, `Patient Name:`), DOB, phone, email, address, and ID patterns with placeholders like `[PATIENT]`. Kept pragmatic to prevent accidentally stripping medical terminology, clinical notes, or lab remarks. Test names, collection dates, values, units, ranges are preserved. |
| **Local mismatch check** | "Report name differs from profile" is computed locally on unredacted text. |
| **Redacted chunks** | `chunks.text` (RAG context) is redacted; originals stay only in `documents.ocr_text`. |
| **What still goes out** | Lab values and medication text. Redaction is best-effort, so the synthetic-data rule stays binding. |
| **Provider hygiene** | Review the provider's current data-retention and training terms; use a dedicated, spend-limited key; rotate it when the prototype ends. |
| **Transport** | HTTPS browser → backend (tunnel/CA) and backend → provider. |
| **Observability** | `llm_calls` stores metadata only. |

---

## 9. Data model

```
patients        id, name                              # one row for the prototype
app_settings    key (pk), value jsonb, is_secret bool, updated_at
documents       id, patient_id, filename, sha256, status, doc_type, doc_date,
                ocr_text, ocr_lines jsonb, page_count, created_at
                status: queued | normalizing | ocr | extracting | needs_review | confirmed | failed | rate_limited
document_pages  id, document_id, page_no, width, height, image_path, original_path
extractions     id, document_id, model, prompt_version, structured_mode, input_hash,
                raw_json, field_confidence jsonb, reviewer_edits jsonb, created_at
observations    id, patient_id, document_id, test_name, canonical_test_id,
                value_num, value_text, unit, ref_low, ref_high, flag,
                collected_at, page_no, source_line_ids int[], status (pending|confirmed)
chunks          id, document_id, text (redacted), embed_model,
                embedding vector(384), page
llm_calls       id, purpose, model, prompt_tokens, completion_tokens,
                latency_ms, status, created_at       # metadata only
```

Notes:
- Pending observations are created at extraction time so the review screen edits real rows.
- Chunks hold redacted OCR text plus a one-line summary per observation (e.g. `HbA1c 7.2 % on 2026-03-14 (ref 4.0–5.6)`), which improves semantic search on tables.
- Embeddings are created only for confirmed documents; the vector size is tied to `embed_model`.
- `lab_dictionary.json` (40–60 common tests: aliases, standard unit, plausible range, conversions) drives alias matching, unit handling, and plausibility checks.

---

## 10. Core flows

### 10.1 Upload → reviewable data

```mermaid
sequenceDiagram
  participant PWA
  participant API
  participant BG as Background task
  participant LLM as LLM provider (Groq default)
  participant DB as Postgres

  PWA->>API: POST /api/v1/documents (1..n pages or a PDF)
  API->>DB: document(status=queued)
  API-->>PWA: 202 {document_id}
  API->>BG: process(document_id)
  BG->>BG: normalize pages, save page images, EasyOCR, row grouping
  BG->>DB: ocr_text + lines, status=extracting
  BG->>BG: redact PII, check cache
  BG->>LLM: extract (structured output, no tools)
  LLM-->>BG: JSON (or 429 -> wait/retry, status=rate_limited)
  BG->>BG: validate, ground values in OCR lines, normalize, score
  BG->>DB: extraction + pending observations, status=needs_review
  PWA->>API: poll GET /documents/{id}
  PWA->>API: GET /documents/{id}/extraction and /pages/{n}.png
  PWA->>API: PATCH /observations/{id} (edits)
  PWA->>API: POST /documents/{id}/confirm
  API->>DB: observations -> confirmed
  API->>BG: embed(document_id)
```

### 10.2 Extraction details

- Input: redacted, row-grouped text, one call per page (or ~40 rows).
- Schema:

```python
class LabObservation(BaseModel):
    test_name: str
    value: float | None
    value_text: str | None            # "Negative", "<0.5"
    unit: str | None
    ref_low: float | None
    ref_high: float | None
    flag: Literal["low", "normal", "high", "critical"] | None
    line_ids: list[int]               # OCR lines this came from

class LabReport(BaseModel):
    lab_name: str | None
    report_date: date | None
    observations: list[LabObservation]
```

- **Grounding check:** reject or flag any observation whose numeric string is not present in the referenced OCR lines.
- **Normalization and confidence:** combine OCR line confidence, dictionary match, unit validity, plausible range, flag-vs-range agreement, and date ambiguity. Confidence only drives review highlighting; nothing is auto-accepted.
- **Fallbacks:** invalid JSON → retry → step down structured mode → regex row parser → `failed` with a manual-entry option.

### 10.3 Trend chart

`GET /api/v1/charts/lab?test=hba1c&from=&to=` → `{ points: [{date, value, flag, document_id, page_no}], ref_low, ref_high, unit }`. Rendered with `fl_chart` (line + reference band); tapping a point opens the source page.

---

## 11. Ask (RAG)

```mermaid
flowchart TB
  Q[Question] --> R{LLM picks tool}
  R -->|numbers, trends| T1[get_observations / get_latest / list_tests]
  R -->|meds, history, notes| T2[search_documents: pgvector + keyword]
  T1 --> C[Results with record ids]
  T2 --> C
  C --> A[LLM composes answer from results only]
  A --> V[Citation check]
  V --> O[Answer + citation chips]
```

| Tool | Signature | Source |
|---|---|---|
| `get_observations` | `(test, from?, to?)` | confirmed `observations`, alias-resolved |
| `get_latest_observations` | `(tests[])` | same |
| `list_tests` | `()` | distinct tests with counts and date ranges |
| `search_documents` | `(query, top_k=5)` | pgvector cosine + `pg_trgm`, merged with reciprocal-rank fusion |

Rules:
- The LLM sees only tool results with record IDs. Max 3 tool calls per question; arguments validated server-side.
- Answers are prompted to include `[obs:ID]` or `[doc:ID p:N]` markers. **No strict citation dropping:** Uncited sentences (such as conversational framing or transitions) are retained rather than dropped, while parsed citation markers are surfaced as interactive citation chips linked to source records. If no relevant evidence was found at all, the answer is "I couldn't find that in your records."
- The system prompt forbids diagnosis, dosing advice, and interpretation beyond restating records.
- **Native tool calling** by default (`llm.supports_tools`); otherwise the router fallback (router prompt returns `{tool, args}` → server executes → answer prompt). Same tools either way.
- The final-answer call carries **no structured-output constraint**, which avoids the tools-plus-structured-output restriction on Groq.

---

## 12. PWA screens

1. **Documents:** list with status chips (`processing`, `waiting for rate limit`, `needs review`, `confirmed`, `failed`); "Add" opens camera or file picker, with "add another page".
2. **Review:** page image (pinch/scroll zoom, highlight of the selected row) with editable rows (test, value, unit, range, flag), low-confidence first, "Confirm all".
3. **Labs:** tests with latest value and direction; tap → trend chart with reference band and table toggle.
4. **Ask:** chat with citation chips that open the page.
5. **Settings:**
   - Backend API key, "Remember on this device" toggle
   - Provider preset, base URL, **model dropdown (discovered) or custom id**, LLM key (write-only, masked), advanced (token parameter name, extra params/headers, structured mode, concurrency)
   - **Test connection** with the probe checklist
   - Daily token cap, "Redact personal info" toggle (warning when off)
   - OCR languages
   - Usage panel: tokens today, calls, last error, rate-limit status
6. **Install prompt:** a small in-app hint to Add to Home Screen where the browser supports it.

State: Riverpod `AsyncNotifier`s, status polling, one `ApiClient` (dio, base `/api/v1`).

---

## 13. API surface (`/api/v1`, all routes need the `API_KEY` header)

| Method | Path | Purpose |
|---|---|---|
| POST | `/documents` | Upload 1..n page images or one PDF → `{id}` |
| GET | `/documents`, `/documents/{id}` | List, status |
| GET | `/documents/{id}/pages/{n}.png` | Normalized page image used for OCR |
| GET | `/documents/{id}/extraction` | Pending observations + OCR lines + confidence |
| PATCH | `/observations/{id}` | Edit during review |
| POST | `/documents/{id}/confirm` | Confirm, trigger embeddings |
| DELETE | `/documents/{id}` | Remove document, pages, observations, chunks |
| GET | `/tests` | Tests available for charting |
| GET | `/charts/lab` | Series for one test |
| POST | `/ask` | `{question}` → `{answer, citations[]}` |
| GET / PUT | `/settings` | Read (masked) / update |
| GET | `/settings/models` | Provider's model ids via `{base_url}/models` |
| POST | `/settings/test-llm` | Probe ladder |
| GET | `/usage` | Token and call counts for today |

---

## 14. Repository layout, Compose, and dev workflow

```
health-proto/
├── api/app/
│   ├── main.py  config.py  db.py  models.py  schemas.py
│   ├── web.py                         # StaticFiles mount, security headers, DEV_CORS
│   ├── security/crypto.py             # Fernet for stored secrets
│   ├── services/settings.py           # read/write/mask, env fallback, presets
│   ├── llm/                           # client.py, keypool.py, probe.py, ladder.py, usage.py, cache.py
│   ├── pipeline/
│   │   ├── normalize_pages.py         # EXIF, deskew, resize, PDF -> PNG
│   │   ├── ocr/                       # base.py, easyocr_engine.py, rows.py
│   │   ├── redact.py  extract.py  normalize.py  embed.py
│   ├── rag/                           # tools.py, orchestrator.py, prompts.py
│   ├── routers/                       # documents.py charts.py ask.py settings.py
│   ├── data/lab_dictionary.json
│   └── tests/                         # contract tests with mock provider
├── app/                               # Flutter (web target)
│   ├── web/                           # manifest.json, icons, index.html
│   └── lib/                           # core/, features/{documents,labs,ask,settings}
├── eval/                              # samples/, ground_truth/, run_eval.py, RESULTS.md
└── docker-compose.yml
```

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment: { POSTGRES_PASSWORD: dev, POSTGRES_DB: health }
    volumes: [pgdata:/var/lib/postgresql/data]
  api:
    build: ./api                        # torch (CPU wheels), easyocr, sentence-transformers
    environment:
      DATABASE_URL: postgresql+psycopg://postgres:dev@postgres/health
      API_KEY: change-me                # backend key entered in the PWA
      SERVER_SECRET: change-me-too      # derives the Fernet key for stored secrets
      DEV_CORS: "false"
      # optional env fallback: LLM_BASE_URL / LLM_API_KEY (comma-separated for several) / LLM_MODEL
      # (GROQ_API_KEY also read when provider is groq)
    volumes:
      - files:/data/files
      - easyocr:/root/.EasyOCR
      - hf:/root/.cache/huggingface
      - ./app/build/web:/app/static:ro  # the PWA bundle
    ports: ["8000:8000"]
    depends_on: [postgres]
volumes: { pgdata: {}, files: {}, easyocr: {}, hf: {} }
```

```bash
# 1. Backend
docker compose up

# 2a. UI development with hot reload (needs DEV_CORS=true)
cd app && flutter run -d chrome --web-port 5000 --wasm --dart-define=API_BASE=http://localhost:8000/api/v1

# 2b. Release PWA served by FastAPI at http://localhost:8000
cd app && flutter build web --wasm --release --dart-define=API_BASE=/api/v1

# 3. Test on a real phone over HTTPS (synthetic data only)
cloudflared tunnel --url http://localhost:8000
```

Models (EasyOCR and sentence-transformers) are pulled dynamically on first container start and cached in persistent named volumes (`easyocr:`, `hf:`), keeping the base Docker image leaner and build times fast.

---

## 15. Bake-offs (each ≤ 1 day)

| Decision | Method | Choose by |
|---|---|---|
| **EasyOCR settings** | Compare preprocessing variants and `mag_ratio` / thresholds, with and without numeric re-read, on 15–20 documents (include phone photos) | Numeric/unit accuracy, row reconstruction, seconds per page |
| **Groq model** | 2–3 hosted models (include an Apache-licensed open-weight model with strict structured output) on the extraction eval and 40 QA pairs | Field F1, valid-JSON rate, tool-call success, tokens per document, latency, rate-limit friction |
| **Provider portability** | Run the probe ladder and extraction eval against one second provider (e.g. OpenRouter) | Works with settings changes only |
| **Key pool behavior** | Force `429`/`401` on one key and confirm failover and recovery; check whether keys from one account share limits | Failover works; documented quota behavior |
| **Embedding model** | `multilingual-e5-small` vs `bge-small-en-v1.5` on 30 retrieval queries | Recall@5 |
| **Native tools vs router** | 40 questions each way | Correct tool + args rate |
| **PWA delivery** | Lighthouse on the tunnel URL, real Android Chrome install, camera capture of 5 documents | Install success, first-load size/time, upload success rate |

Log outcomes in `eval/RESULTS.md`.

---

## 16. Evaluation and acceptance

**Eval set (week 1):** 20–30 synthetic or anonymized documents (about 15 lab reports across at least 3 layouts, plus skewed, dim, and phone-photographed copies), hand-verified ground truth, and 40 QA pairs including unanswerable ones.

| Stage | Metric | Prototype target |
|---|---|---|
| OCR | Accuracy on numeric tokens and units | ≥ 93 % clean, ≥ 80 % photographed |
| Row reconstruction | Rows correctly grouped | ≥ 90 % |
| Extraction | Field F1 before review | ≥ 85 % on clean docs |
| Grounding | Hallucinated values passing the check | 0 on the eval set |
| Review | Median time to confirm one report on a phone | ≤ 90 s |
| Charts | Series equals ground truth after review | 100 % |
| RAG | Correct answer with valid citation | ≥ 85 % |
| RAG safety | Unanswerable questions answered "not found" | ≥ 95 % |
| Latency | Upload → needs_review (CPU EasyOCR + hosted LLM) | ≤ 90 s per page (record actual) |
| Cost / limits | Median tokens per document; rate-limit waits | Recorded |
| **PWA** | Every check in section 7.8 | All pass (iOS: logged only) |
| **Portability** | Switch provider/model and add/remove/fail over keys through Settings only | Works for Groq (two models, two keys) plus one other provider |

---

## 17. Five-week build plan

**Week 1: Skeleton, settings, PWA shell**
- [ ] Repo, Compose, Alembic baseline, FastAPI serving a Flutter web build
- [ ] Flutter web shell: hash routing, responsive navigation, API client, manifest and icons
- [ ] `app_settings` + Fernet, `/settings`, `/settings/models`, `/settings/test-llm` (probe ladder), `llm_calls`
- [ ] `OpenAICompatClient` with Groq default preset, `KeyPool` (failover/round-robin), retries/`Retry-After`, structured-mode ladder, daily cap
- [ ] Contract tests with a mock provider; first live Groq smoke test
- [ ] Settings screen; HTTPS tunnel working; install the PWA on a phone
- [ ] Build the eval set and ground truth; draft `lab_dictionary.json`
- **Exit:** enter LLM key(s) (Groq by default) in the installed PWA → Test connection shows per-key status, detected mode, and capabilities. Lighthouse baseline recorded.

**Week 2: Capture and OCR**
- [ ] Capture/pick/upload (multi-page), page normalization and page-image endpoint
- [ ] `EasyOcrEngine`, row reconstruction, stored lines; background processing + status polling
- [ ] *Bake-off: EasyOCR settings*; OCR scoring in `run_eval.py`
- **Exit:** phone photo → row-grouped text and viewable page image; OCR targets met on clean docs.

**Week 3: Extraction and review**
- [ ] Redaction, extraction prompt/schema, grounding check, normalization, confidence
- [ ] Rate-limit handling and `rate_limited` status in the UI; result cache; usage panel
- [ ] Review screen (responsive, highlights, edit, confirm)
- [ ] *Bake-offs: Groq model, provider portability, key pool behavior*
- **Exit:** scan → confirmed observations on a phone; F1 and cost per document measured.

**Week 4: Charts and embeddings**
- [ ] `/tests`, `/charts/lab`, Labs screen with `fl_chart` band and point → source page
- [ ] Local embeddings, per-observation summary chunks, hybrid search
- [ ] *Bake-off: embedding model*
- **Exit:** charts match ground truth; Recall@5 recorded.

**Week 5: Ask, PWA polish, wrap-up**
- [ ] Tools, orchestrator (native tools, router fallback), citation enforcement
- [ ] Ask screen with citation chips; update banner, offline state, install hint
- [ ] Section 7.8 PWA checklist pass (Lighthouse, 360 px layout, TalkBack, iOS smoke test)
- [ ] Full evaluation, fix top failure categories, `eval/RESULTS.md`, demo script, rotate provider key
- **Exit:** section 16 targets met, or gaps documented with causes.

---

## 18. Risks specific to this setup

| Risk | Impact | Mitigation |
|---|---|---|
| EasyOCR has no table structure | Misaligned values | Row clustering, row-level eval, plausibility checks, review screen; swappable engine |
| EasyOCR slow on CPU | Slow demo | Cap image size, status UI, page-level parallelism |
| Digit errors (0/O, 1/l, lost decimals) | Wrong values | Numeric re-read, grounding check, dictionary ranges, mandatory review |
| Health data sent to an external provider | Privacy exposure | Synthetic data only, redaction, text only, provider terms, dedicated spend-limited key |
| Public dev tunnel exposes the API | Unauthorized access | Strong `API_KEY`, rate limiting, close tunnel when idle, no real data |
| API key in browser storage | Theft via XSS or shared device | Session-only default, CSP, no third-party scripts, LLM key never in the browser |
| Groq rate limits or model retirement | Stalled pipeline | `Retry-After`, concurrency cap, `rate_limited` status, key pool failover, pinned and configurable model, clear errors |
| Multiple keys in one account share one quota | Pool gives false sense of capacity | Document it (4.2), measure in the key-pool bake-off, attribute usage per key label |
| Provider quirks vary beyond Groq | Breakage with other keys | Settings overrides, probe ladder, contract tests, portability bake-off |
| Structured outputs strict only on some models; not combinable with tools | Parse failures | Probe ladder, validation + retry, separate extraction and Ask call paths |
| Provider quirks (token param, reasoning tags, missing usage) | Breakage with other keys | Settings overrides, tag stripping, local token estimates, contract tests |
| HTTPS needed for PWA features | Blocked camera/install on phone | Tunnel or mkcert from week 1 |
| Flutter web size and stale service worker | Slow first load, old UI | Measure in week 1, update banner, versioned assets; revisit client framework if size is unacceptable (7.0) |
| iOS Safari differences | Unexpected behavior | Android Chrome and desktop Chrome supported; iOS smoke-tested and logged |
| Hosted model not open-weight | Conflicts with policy | Prefer Apache/MIT-weight models; record the decision |
| Scope creep | Missed deadline | Section 1 "out of scope" is binding until week 5 |

---

## 19. Path from prototype to full system

- **PWA hardening:** the PWA remains the product client. Next steps are push notifications where supported, background upload retry, richer offline reads, and a Web Share Target for receiving photos/PDFs from other apps.
- **Native apps (deferred, not planned):** the same Flutter codebase can target Android/iOS later if the PWA hits a hard limit.
- **Self-hosted LLM:** change `base_url` and model in Settings; schemas and evals stay.
- **Real hosting:** put the same Compose stack behind Caddy on a small server; replace the single API key with real auth, encryption at rest, and workers as in `architecture.md`.
- **Multi-patient and caregiver profiles:** `patient_id` is already everywhere.
- **Next features in order:** auth + encrypted storage → prescriptions → bills → clinician sharing → hardening.
