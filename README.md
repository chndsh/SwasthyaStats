<div align="center">

# 🩺 SwasthyaStats

*A self-hosted personal health records companion you actually own.*

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)]()
[![Flutter](https://img.shields.io/badge/Flutter-3.x-02569B.svg?logo=flutter&logoColor=white)]()
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%7C%20pgvector-336791.svg?logo=postgresql&logoColor=white)]()
[![Default Provider](https://img.shields.io/badge/LLM-Groq%20LPU-F55036.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)]()

<br />

**Swasthya** (*स्वास्थ्य*) means health and well-being.  
SwasthyaStats digitizes lab reports, prescriptions, and health scans into structured, searchable health data. It pairs local OCR and embeddings with fast LLM inference powered by **Groq** (or your own custom OpenAI-compatible endpoint), allowing you to track lab biomarkers over time and query your entire health timeline in plain language — with strict PII scrubbing and verified source citations.

</div>

---

## Why SwasthyaStats?

Your health history is often fragmented across physical printouts, hospital portal PDFs, and lab WhatsApp messages. Commercial health platforms monetize this data, lock records behind proprietary clouds, or train third-party models on sensitive diagnostics.

SwasthyaStats takes a patient-first approach:

- **Data Ownership:** Runs entirely on your own infrastructure (PostgreSQL with `pgvector`, local filesystem).
- **Fast, Affordable AI via Groq:** Uses Groq's high-throughput LPU inference by default for sub-second report extraction and conversational Q&A, while keeping local control over model parameters, key rotation, and failover.
- **Privacy-First (PII Redaction Before Cloud LLM):** Patient names, dates of birth, emails, phone numbers, and government IDs are scrubbed *locally on your server* before any text is transmitted to the LLM.
- **Zero Hallucination Tolerance:** AI extraction outputs are treated as drafts. The Flutter UI provides a side-by-side human-in-the-loop verification screen before any observation is confirmed into your permanent timeline.
- **Multilingual Health Literacy:** Ask questions in English, Nepali, Hindi, Spanish, or any other language, receiving answers cited against specific lab rows and report pages.
- **Offline Capable:** The responsive Flutter frontend caches document lists, verified lab observations, and chat history locally for offline access.

---

## Quick Start (Self-Hosting)

The entire application runs as a multi-container stack via Docker Compose.

### 1. Clone & Configure

```bash
git clone https://github.com/your-username/SwasthyaStats.git
cd SwasthyaStats
```

Create an `.env` file in the project root:

```env
# Database & Security
DATABASE_URL=postgresql+psycopg://postgres:dev@postgres:5432/health
SERVER_SECRET=dev-secret-key-32-chars-long-abc123!
STORAGE_PATH=/data/files

# Initial Admin Credentials
ADMIN_EMAIL=admin@localhost
ADMIN_PASSWORD=adminpass

# Default LLM Provider (Groq)
GROQ_API_KEY=gsk_your_groq_api_key_here
```

### 2. Build & Launch

```bash
docker compose up -d --build
```

- **Web App & API:** Available at `http://localhost:8000`
- **Database:** PostgreSQL with `pgvector` on port `5432`

> **Note:** On startup, the backend automatically runs database migrations (`alembic upgrade head`) and creates the initial admin user.

---

## Features

### 📄 Ingestion & Local OCR
- Upload multi-page PDFs or image files (JPEG, PNG).
- Pages are converted and preprocessed locally using **OpenCV** and **PIL**.
- On-premise text and line-level bounding box recognition using **EasyOCR** (no images are sent to any cloud provider).

### 🔒 Privacy Guard & PII Redaction
- Regex-based redaction engine executes locally on the server before sending text to the LLM.
- Masks patient names (`[PATIENT]`), birth dates (`[DOB]`), phone numbers (`[PHONE]`), emails (`[EMAIL]`), and national IDs (`[ID]`), while preserving clinical test names, values, units, reference intervals, doctor names, and laboratory banners.

### 🤖 Structured Extraction & Normalization
- Extracts raw tabular OCR lines into strict JSON schemas conforming to `LabReportRaw` and `LabObservationRaw`.
- Canonicalizes colloquial, misspelled, or regional test names (e.g., `SGOT/AST`, `Platelet Count`, `Leukocytes`) against a standardized dictionary.
- Computes observation confidence scores to prioritize ambiguous rows for user review.

### ✍️ Human-in-the-Loop Review
- Side-by-side review interface built in Flutter.
- Highlights low-confidence extractions first.
- Allows editing values, units, reference bounds, or adding missing rows directly with click-to-source bounding line highlights.
- Only confirmed observations are committed to long-term biomarker storage and embedded for retrieval.

### 💬 Grounded Health Companion (RAG Q&A)
- Conversational interface supporting multi-turn queries.
- Tool-calling agent capable of retrieving time-series observations, listing historical tests, or performing hybrid semantic document search.
- Inline clickable citations: `[obs:ID]` jumps to specific lab data points, and `[doc:ID p:N]` jumps to the exact source document page.

### 📈 Biomarker Analytics & Trends
- Interactive historical trend charts powered by `fl_chart`.
- Visual indicators for values outside reference intervals (High, Low, Normal).
- Favorite tests pinned for quick health monitoring.

---

## Architecture & How It Works

```
┌────────────────────────────────────────────────────────┐
│                   Flutter Client (Web/Mobile)          │
│       (Auth • Ingestion • Review UI • Charts • Ask)     │
└───────────────────────────┬────────────────────────────┘
                            │ REST / JSON
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Backend                     │
├────────────────────────────────────────────────────────┤
│  • EasyOCR Engine (Local)       • PII Redactor         │
│  • Groq LLM Client / KeyPool    • Hybrid RAG Engine    │
│  • SentenceTransformers (Local) • Settings Service     │
└─────────────┬────────────────────────────┬─────────────┘
              │                            │
              ▼                            ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│   PostgreSQL + pgvector  │  │    Local File Storage    │
│ (Users, Docs, Obs, Chunks│  │  (Original Scans & PDFs) │
└──────────────────────────┘  └──────────────────────────┘
```

### Where AI is Consumed Programmatically

SwasthyaStats does not merely pass text from an LLM into a chat box. The AI output is parsed into strict typed schemas, used in mathematical confidence ranking, and tied into agentic database tool loops.

The exact files and functions powering this pipeline are:

#### 1. Structured Document Extraction
- **File:** [`api/app/pipeline/extract.py`](file:///home/chandish/copilot-worktrees/SwasthyaStats/chndsh-supreme-meme/api/app/pipeline/extract.py)
- **Function:** `extract_page(page_text, ocr_line_ids, client, model, json_mode)`
- **Programmatic Consumption:** The LLM (Groq) is prompted with `EXTRACTION_SYSTEM_PROMPT` to return strict JSON matching `LabReportRaw`. The raw text response is sanitized via `_clean_json_markdown()`, parsed into a typed Pydantic object, and validated. If parsing fails, it retries with structured recovery; if the LLM output is empty, `recover_observations_from_ocr()` executes a deterministic fallback using line IDs.

#### 2. Test Normalization & Confidence Ranking
- **File:** [`api/app/pipeline/normalize.py`](file:///home/chandish/copilot-worktrees/SwasthyaStats/chndsh-supreme-meme/api/app/pipeline/normalize.py)
- **Functions:** `normalize_test_name()`, `_find_canonical_test_id()`, `score_observations()`
- **Programmatic Consumption:** Takes the `LabObservationRaw` list produced by the LLM and matches noisy OCR test names against canonical medical test IDs. It calculates a floating-point `confidence` score (0.0 to 1.0) based on string similarity, grounded OCR line IDs, and range sanity.
- **Frontend Integration:** In [`app/lib/features/review/review_controller.dart`](file:///home/chandish/copilot-worktrees/SwasthyaStats/chndsh-supreme-meme/app/lib/features/review/review_controller.dart), `ReviewController.build()` programmatically sorts observations ascending by confidence (`confA.compareTo(confB)`), ensuring doctors or patients review the most uncertain extractions first.

#### 3. Local Vector Embedding Pipeline
- **Files:** [`api/app/pipeline/embed.py`](file:///home/chandish/copilot-worktrees/SwasthyaStats/chndsh-supreme-meme/api/app/pipeline/embed.py) & [`api/app/pipeline/embed_worker.py`](file:///home/chandish/copilot-worktrees/SwasthyaStats/chndsh-supreme-meme/api/app/pipeline/embed_worker.py)
- **Functions:** `EmbedEngine.embed()`, `observation_summary()`, `embed_document()`
- **Programmatic Consumption:** Once a document is confirmed by the user, `embed_document()` formats each observation into a natural language summary and passes texts to a local `SentenceTransformer` model (`intfloat/multilingual-e5-small`). The resulting 384-dimensional normalized float vectors are inserted into PostgreSQL `chunks` via `pgvector`.

#### 4. Agentic RAG Orchestration & Citation Parser
- **File:** [`api/app/rag/orchestrator.py`](file:///home/chandish/copilot-worktrees/SwasthyaStats/chndsh-supreme-meme/api/app/rag/orchestrator.py)
- **Functions:** `ask()`, `execute_tool()`, `parse_citations()`
- **Programmatic Consumption:**
  - Evaluates user questions against database tool specs (`get_observations`, `get_latest_observations`, `list_tests`, `search_documents`) using Groq's tool-calling endpoint (or router fallback via `ROUTER_SYSTEM_PROMPT`).
  - Iteratively executes tool calls against PostgreSQL, injects tool outputs into the message stream, and synthesizes a grounded answer.
  - Passes the response to `parse_citations()`, which extracts regex matches for `[obs:<id>]` and `[doc:<id> p:<page>]` into structured `CitationRef` objects.
- **Frontend Integration:** Deserialized in [`app/lib/features/ask/ask_controller.dart`](file:///home/chandish/copilot-worktrees/SwasthyaStats/chndsh-supreme-meme/app/lib/features/ask/ask_controller.dart) and rendered by `ask_screen.dart` as clickable metadata chips linking directly to documents and lab charts.

#### 5. Groq LPU Client, Key Pool & Token Protection
- **Files:** [`api/app/llm/client.py`](file:///home/chandish/copilot-worktrees/SwasthyaStats/chndsh-supreme-meme/api/app/llm/client.py) & [`api/app/llm/keypool.py`](file:///home/chandish/copilot-worktrees/SwasthyaStats/chndsh-supreme-meme/api/app/llm/keypool.py)
- **Class / Methods:** `OpenAICompatClient.chat()`, `strip_think_tags()`, `KeyPool.select_key()`
- **Programmatic Consumption:**
  - Manages multiple decrypted Groq API keys with automated failover and round-robin strategies on HTTP 429 rate limits.
  - Strips reasoning `<think>` tags from models (e.g. DeepSeek-R1 / Qwen reasoning variants) before parsing.
  - Enforces Groq free-tier guardrails (capping max output tokens to 1,000 on Qwen models to prevent OTPM throttling).
  - Enforces a 5-second pacing delay between multi-page document extractions in [`api/app/services/documents.py`](file:///home/chandish/copilot-worktrees/SwasthyaStats/chndsh-supreme-meme/api/app/services/documents.py) to prevent ITPM exhaustion.

---

## Configuration & Providers

### Default Setup: Groq

By default, the backend initializes with:
- **Provider:** `groq`
- **Base URL:** `https://api.groq.com/openai/v1`
- **Supported Models:** `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `mixtral-8x7b-32768`, `qwen-2.5-32b`

Set your API key via the root `.env` (`GROQ_API_KEY=...`) or through the **Settings** screen in the application.

### Switching Providers

SwasthyaStats can be redirected to any OpenAI-compatible provider at runtime from **Settings**:

| Provider | Base URL | Tool Calling |
|---|---|---|
| **Groq (Default)** | `https://api.groq.com/openai/v1` | Yes |
| **Ollama (Self-Hosted)** | `http://localhost:11434/v1` | Yes (model dependent) |
| **vLLM / LocalAI** | `http://localhost:8000/v1` | Yes |
| **OpenAI** | `https://api.openai.com/v1` | Yes |

---

## Development & Testing

### Running the API Directly

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run test suite
pytest
```

### Running the Flutter Client

```bash
cd app
flutter pub get

# Run test suite
flutter test

# Run in Chrome (pointing to local API)
flutter run -d chrome --dart-define=API_BASE=http://localhost:8000/api/v1
```

---

## Medical Disclaimer

> [!WARNING]
> SwasthyaStats is a personal health literacy, record organization, and self-advocacy tool. It is **not** a certified medical device, does not formulate clinical diagnoses, and does not provide medical treatment plans. Always consult a qualified physician or healthcare professional before making clinical decisions.

---

## License

This project is licensed under the [MIT License](LICENSE).
