# Week 5: Ask (RAG), PWA Polish & Wrap-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Ask/RAG feature with citation chips, polish the PWA (update banner, offline state, install hint, Lighthouse pass), and close out the prototype with a full evaluation run, demo script, and final results log.

**Architecture:** The backend gains a `rag/` module with four read-only tools (`get_observations`, `get_latest_observations`, `list_tests`, `search_documents`) and an orchestrator that makes up to 3 tool calls via native tool use (or a router-prompt fallback), then composes a cited answer. The Flutter Ask screen streams the answer text and renders `[obs:ID]` / `[doc:ID p:N]` citation markers as tappable chips. PWA polish targets the full Section 7.8 checklist.

**Tech Stack:** Python FastAPI, SQLAlchemy 2, pgvector, `pg_trgm`, `sentence-transformers`, `httpx`; Flutter Web (Wasm, Riverpod, go_router, dio), `fl_chart`; Lighthouse CLI; pytest / respx mocks.

**Spec:** `prototype-architecture.md` — Sections 11, 7.2, 7.8, 12, 13, 16, 17 (Week 5)

## Global Constraints

- `--wasm` is the primary Flutter Web build target; verify with `flutter build web --wasm --release`.
- No `dart:io`; use `XFile.readAsBytes()` / `dio` for all network calls.
- All routers require `X-API-Key` header via `verify_api_key` dependency.
- LLM extraction calls use structured output (no tools); Ask calls use tools (no structured output) — never combined (Groq restriction).
- Max 3 tool calls per Ask turn; tool arguments validated server-side.
- Answer LLM call carries **no** `response_format` constraint.
- `chunks.text` is redacted; OCR originals remain in `documents.ocr_text`.
- Tests: backend via `docker compose exec -T api pytest -v`; Flutter via `flutter test`.
- Commits follow `feat/fix/eval/test:` prefix convention.

## Review Focus

- **Unanswerable questions** (no relevant chunks/observations): orchestrator must return "I couldn't find that in your records." rather than hallucinating — test with a question about a test never extracted.
- **Router-prompt fallback correctness**: when `llm.supports_tools` is false the router returns `{tool, args}` JSON; the orchestrator must parse and execute it identically to native tool calls — test with `supports_tools=False` in settings.
- **Citation marker stripping in display**: if the LLM omits or malforms a citation marker the UI must render the bare text gracefully rather than showing `[obs:???]` — test with a mock answer containing no markers.
- **Offline → data screen behavior**: when the device has no network, the Ask screen must show a clear offline message rather than a spinner or crash — test by killing network in a browser dev-tools offline sim.
- **Service-worker stale-shell update**: after a new Wasm build is deployed, a browser with a cached shell must see the update banner within one page load — verify by bumping the build and reloading without force-refresh.

---

## Task 1: RAG tools layer

**Files:**
- Create: `api/app/rag/__init__.py`
- Create: `api/app/rag/tools.py`
- Test: `api/tests/test_rag_tools.py`

**Interfaces:**
- Consumes: `app.db.get_db` → `Session`; `app.models.{Observation, Chunk, Document}`; `app.pipeline.embed.EmbedEngine` (singleton getter `get_embed_engine()`); `app.pipeline.normalize._find_canonical_test_id(test_name, lab_dict) -> str | None`; `app.services.documents.get_lab_dictionary() -> dict`.
- Produces:
  - `get_observations(db, test: str, from_date: date | None, to_date: date | None) -> list[dict]` — confirmed observations for alias-resolved test, each dict has `{id, test_name, value_num, value_text, unit, flag, collected_at, document_id, page_no}`.
  - `get_latest_observations(db, tests: list[str]) -> list[dict]` — one most-recent confirmed observation per test.
  - `list_tests(db) -> list[dict]` — `{test_name, count, latest_date}` for each distinct canonical test with confirmed observations.
  - `search_documents(db, query: str, top_k: int = 5) -> list[dict]` — reciprocal-rank fusion of pgvector cosine and `pg_trgm` similarity on `chunks.text`; each result `{chunk_id, document_id, page, text, score}`.

- [ ] **Step 1: Write failing tests for all four tool functions**

```python
# api/tests/test_rag_tools.py
def test_list_tests_returns_confirmed_only(db_session):
    # seed one confirmed and one pending observation
    # assert list_tests returns only the confirmed one

def test_get_observations_alias_resolve(db_session):
    # seed observation with test_name="HB"; call get_observations(db, "Hemoglobin", ...)
    # assert result contains the HB observation (alias resolved)

def test_get_latest_observations(db_session):
    # seed two confirmed observations for same test at different dates
    # assert get_latest_observations returns only the more recent one

def test_search_documents_returns_ranked(db_session, monkeypatch):
    # monkeypatch EmbedEngine.embed to return a fixed vector
    # seed two chunks with known embeddings and text
    # assert search_documents returns them ranked by fused score
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec -T api pytest api/tests/test_rag_tools.py -v
```
Expected: 4 FAILs with `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 3: Implement `api/app/rag/tools.py`**

  Four functions. `search_documents` must:
  1. embed `query` with `get_embed_engine()`.
  2. run `SELECT id, document_id, page, text, (1 - (embedding <=> :q_vec)) AS cos_sim FROM chunks ORDER BY cos_sim DESC LIMIT :k` (SQLAlchemy text, cast the vector literal).
  3. run `SELECT id, document_id, page, text, similarity(text, :query) AS trgm_sim FROM chunks WHERE similarity(text, :query) > 0.1 ORDER BY trgm_sim DESC LIMIT :k`.
  4. merge both ranked lists with reciprocal-rank fusion: `score = 1/(60 + rank_cos) + 1/(60 + rank_trgm)`, deduplicate by `chunk_id`, return top `top_k`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose exec -T api pytest api/tests/test_rag_tools.py -v
```
Expected: 4 PASSes.

- [ ] **Step 5: Commit**

```bash
git add api/app/rag/ api/tests/test_rag_tools.py
git commit -m "feat(rag): add four read-only RAG tool functions with RRF search"
```

---

## Task 2: RAG orchestrator

**Files:**
- Create: `api/app/rag/prompts.py`
- Create: `api/app/rag/orchestrator.py`
- Test: `api/tests/test_rag_orchestrator.py`

**Interfaces:**
- Consumes: `api/app/rag/tools.py` (all four functions); `app.llm.client.OpenAICompatClient`; `app.services.settings.SettingsService`.
- Produces:
  - `ask(db, question: str) -> AskResult` where `AskResult` has `answer: str` and `citations: list[CitationRef]`.
  - `CitationRef`: `type: Literal["obs", "doc"]`, `id: int`, `page: int | None`.

**Schema definitions (add to `api/app/schemas.py`):**
```python
class CitationRef(BaseModel):
    type: Literal["obs", "doc"]
    id: int
    page: Optional[int] = None

class AskResponse(BaseModel):
    answer: str
    citations: list[CitationRef]
```

- [ ] **Step 1: Write failing tests**

```python
# api/tests/test_rag_orchestrator.py
def test_ask_native_tools_happy_path(db_session, respx_mock):
    # mock LLM: first call returns tool_calls=[{name:"list_tests", args:{}}]
    # second call (answer) returns "Your HbA1c is 7.2% [obs:42]"
    # assert result.answer contains the text, result.citations == [CitationRef(type="obs", id=42)]

def test_ask_router_fallback(db_session, respx_mock):
    # set supports_tools=False in settings
    # mock router call returns JSON '{"tool":"list_tests","args":{}}'
    # mock answer call returns "No tests found. I couldn't find that in your records."
    # assert result.answer == expected, citations == []

def test_ask_unanswerable(db_session, respx_mock):
    # seed no observations/chunks; mock LLM returns "I couldn't find that in your records."
    # assert answer starts with "I couldn't find"

def test_ask_max_tool_calls_enforced(db_session, respx_mock):
    # mock LLM to always return a tool_call; assert orchestrator stops after 3 rounds
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec -T api pytest api/tests/test_rag_orchestrator.py -v
```
Expected: 4 FAILs.

- [ ] **Step 3: Implement `api/app/rag/prompts.py`**

  Two prompt builders (return `list[dict]` message arrays):
  - `system_prompt() -> str` — instructs the LLM to use only tool results, cite with `[obs:ID]`/`[doc:ID p:N]`, forbid diagnosis/dosing, return "I couldn't find that in your records." when no evidence found.
  - `tool_specs() -> list[dict]` — four tool specs matching the OpenAI tool-calling schema for `get_observations`, `get_latest_observations`, `list_tests`, `search_documents`.
  - `router_prompt(question: str, tools: list[dict]) -> list[dict]` — fallback prompt asking LLM to return `{"tool": "<name>", "args": {...}}` JSON only.

- [ ] **Step 4: Implement `api/app/rag/orchestrator.py`**

  `ask(db, question) -> AskResult`:
  1. Load settings; determine `supports_tools`.
  2. If native tools: build messages with system prompt + user question; call `client.chat(..., purpose="route", tools=tool_specs())`. Up to 3 rounds: if response has `tool_calls`, execute each (validate name server-side), append results as `tool` messages, call again. Stop at 3 or when no tool calls.
  3. If router fallback: one `client.chat(..., purpose="route", json_schema=None)` with `router_prompt`; parse `{tool, args}` JSON; execute once; compose answer in a second `client.chat(..., purpose="answer")` with tool result in context.
  4. Final answer call: `client.chat(..., purpose="answer")` with accumulated context — **no** `json_schema` or `tools`.
  5. Parse `[obs:ID]` and `[doc:ID p:N]` markers from answer text into `CitationRef` list; retain markers in `answer` string (UI renders them as chips).
  6. Return `AskResult(answer=..., citations=[...])`.

- [ ] **Step 5: Run tests to verify they pass**

```bash
docker compose exec -T api pytest api/tests/test_rag_orchestrator.py -v
```
Expected: 4 PASSes.

- [ ] **Step 6: Commit**

```bash
git add api/app/rag/prompts.py api/app/rag/orchestrator.py api/app/schemas.py api/tests/test_rag_orchestrator.py
git commit -m "feat(rag): add RAG orchestrator with native tools and router-prompt fallback"
```

---

## Task 3: Ask API endpoint

**Files:**
- Create: `api/app/routers/ask.py`
- Modify: `api/app/main.py` (mount ask router)
- Test: `api/tests/test_ask_api.py`

**Interfaces:**
- Consumes: `app.rag.orchestrator.ask`; `app.db.get_db`; `app.security.auth.verify_api_key`.
- Produces:
  - `POST /api/v1/ask` body: `{"question": str}`, response: `AskResponse`.

- [ ] **Step 1: Write failing test**

```python
# api/tests/test_ask_api.py
def test_ask_endpoint_returns_answer(client, respx_mock, db_session):
    # POST /api/v1/ask {"question": "What was my last HbA1c?"}
    # mock orchestrator (or LLM calls via respx) to return answer + citation
    # assert 200, response json has "answer" and "citations" keys

def test_ask_endpoint_requires_api_key(client):
    # POST without X-API-Key header
    # assert 403
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec -T api pytest api/tests/test_ask_api.py -v
```
Expected: 2 FAILs.

- [ ] **Step 3: Implement `api/app/routers/ask.py`**

  Single `POST /api/v1/ask` endpoint: receive `{"question": str}` (Pydantic model), call `rag.orchestrator.ask(db, question)`, return `AskResponse`.

- [ ] **Step 4: Mount in `api/app/main.py`**

  Add `from app.routers import ask` and `app.include_router(ask.router)`.

- [ ] **Step 5: Run tests to verify they pass**

```bash
docker compose exec -T api pytest api/tests/test_ask_api.py -v
```
Expected: 2 PASSes.

- [ ] **Step 6: Run full backend suite**

```bash
docker compose exec -T api pytest -v
```
Expected: all previously passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add api/app/routers/ask.py api/app/main.py api/tests/test_ask_api.py
git commit -m "feat(api): add POST /ask endpoint wiring RAG orchestrator"
```

---

## Task 4: Flutter Ask screen

**Files:**
- Create: `app/lib/features/ask/ask_model.dart`
- Create: `app/lib/features/ask/ask_controller.dart`
- Create: `app/lib/features/ask/ask_screen.dart`
- Modify: `app/lib/features/navigation/app_router.dart` (wire `/ask` route and nav item)
- Test: `app/test/ask_screen_test.dart`

**Interfaces:**
- Consumes: `ApiClient` (from `app/lib/core/api_client.dart`); `POST /api/v1/ask` → `{answer: str, citations: [{type, id, page?}]}`.
- Produces:
  - `AskMessage`: `{role: "user"|"assistant", text: str, citations: List<CitationRef>}`.
  - `CitationRef`: `{type: String, id: int, page: int?}`.
  - `askControllerProvider`: `AsyncNotifier<List<AskMessage>>` with `ask(question)` method that appends user message, calls API, parses response, appends assistant message.
  - `AskScreen`: chat-style list of bubbles; `TextField` + send button at bottom. Assistant bubbles render `[obs:ID]`/`[doc:ID p:N]` markers as `InkWell` chips (tapping navigates to the relevant document review page or lab detail). User bubbles are plain text.

- [ ] **Step 1: Write failing widget test**

```dart
// app/test/ask_screen_test.dart
testWidgets('ask screen renders text field and send button', (tester) async {
  await tester.pumpWidget(ProviderScope(..., child: AskScreen()));
  expect(find.byType(TextField), findsOneWidget);
  expect(find.byIcon(Icons.send), findsOneWidget);
});

testWidgets('submitting question shows user message and mocked assistant reply', (tester) async {
  // override askControllerProvider with a mock that returns a fixed answer
  // enter 'What is my HbA1c?', tap send
  // assert user bubble appears, then assistant bubble appears with the mocked answer
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
flutter test test/ask_screen_test.dart
```
Expected: compile errors / test not found.

- [ ] **Step 3: Implement `ask_model.dart`**

  `CitationRef` (fromJson) and `AskMessage` data classes.

- [ ] **Step 4: Implement `ask_controller.dart`**

  `AsyncNotifier<List<AskMessage>>` — `build()` returns `[]`; `ask(question)` posts to `/ask`, parses `AskResponse`, updates state.

- [ ] **Step 5: Implement `ask_screen.dart`**

  Chat `ListView` with `UserBubble` and `AssistantBubble` widgets. `AssistantBubble` uses `_renderAnswer(text, citations)`: split text on `[obs:ID]`/`[doc:ID p:N]` with regex, render plain `TextSpan`s and `InkWell`-wrapped chip `TextSpan`s. `onTap` for obs chip → `context.push('/documents/$docId/review')`; for doc chip → same route with page query param (best-effort).

- [ ] **Step 6: Wire `/ask` route in `app_router.dart`**

  Add `/ask` route. Add Ask tab (icon: `Icons.chat_bubble_outline`) to `BottomNavigationBar` (index 2, pushing Documents=0, Labs=1, Ask=2, Settings=3).

- [ ] **Step 7: Run tests to verify they pass**

```bash
flutter test test/ask_screen_test.dart
```
Expected: 2 PASSes.

- [ ] **Step 8: Run full Flutter suite**

```bash
flutter test && flutter analyze
```
Expected: all tests pass, 0 analyzer issues.

- [ ] **Step 9: Commit**

```bash
git add app/lib/features/ask/ app/lib/features/navigation/app_router.dart app/test/ask_screen_test.dart
git commit -m "feat(flutter): add Ask screen with citation chip rendering and RAG controller"
```

---

## Task 5: PWA polish — update banner, offline state, install hint

**Files:**
- Modify: `app/lib/main.dart` (update banner listener)
- Modify: `app/lib/features/documents/documents_screen.dart` (offline message)
- Modify: `app/lib/features/ask/ask_screen.dart` (offline message)
- Modify: `app/web/index.html` (service worker update detection via JS)
- Test: `app/test/pwa_polish_test.dart`

**Interfaces:**
- Consumes: `connectivity_plus` package (add to `pubspec.yaml`); Flutter's service-worker JS messaging via `web_interop` or a thin `dart:js_interop` shim.
- Produces:
  - **Update banner:** when the service worker posts `{type: "UPDATE_AVAILABLE"}`, show a `SnackBar` "New version available — tap to reload" with a `Reload` action that calls `window.location.reload()`.
  - **Offline state:** on every data-fetching screen (Documents, Ask), if `Connectivity().checkConnectivity()` returns `none`, show a centered `Column` with an offline icon and "You're offline. Connect to load data." instead of the list/chat.
  - **Install hint:** a dismissible `Banner` widget shown once (persisted in `shared_preferences` key `install_hint_dismissed`) prompting "Install this app: tap ⋮ → Add to Home Screen".

- [ ] **Step 1: Write failing tests**

```dart
// app/test/pwa_polish_test.dart
testWidgets('documents screen shows offline message when connectivity is none', (tester) async {
  // override connectivityProvider to return ConnectivityResult.none
  // pump DocumentsScreen
  // expect find.text("You're offline") is visible
});

testWidgets('install hint is visible until dismissed', (tester) async {
  // override shared_preferences with install_hint_dismissed=false
  // pump main app shell
  // expect install hint banner visible
  // tap dismiss
  // expect banner gone
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
flutter test test/pwa_polish_test.dart
```
Expected: compile errors or 2 FAILs.

- [ ] **Step 3: Add `connectivity_plus` to `pubspec.yaml` and fetch**

```bash
cd app && flutter pub add connectivity_plus
```

- [ ] **Step 4: Implement connectivity check and offline widget in `documents_screen.dart` and `ask_screen.dart`**

  Create `connectivityProvider` (`StreamProvider` wrapping `Connectivity().onConnectivityChanged`). In each screen's `build`, if latest connectivity is `none`, return the offline `Column`.

- [ ] **Step 5: Implement install hint in `app_router.dart` or main shell widget**

  Read `shared_preferences` key `install_hint_dismissed`; if false, show a dismissible `MaterialBanner` at the top of the scaffold. On dismiss, write `true` to prefs.

- [ ] **Step 6: Implement service-worker update detection**

  In `app/web/index.html`, add JS listening to `navigator.serviceWorker` `controllerchange` event; when fired, post `{type: "UPDATE_AVAILABLE"}` to the Flutter `window.flutter_inappwebview` or use a `dart:js_interop` channel. In `main.dart`, listen for that message and show the `SnackBar` (use `web_interop` `EventTarget.addEventListener` for `message` events on `window`).

- [ ] **Step 7: Run tests to verify they pass**

```bash
flutter test test/pwa_polish_test.dart && flutter analyze
```
Expected: 2 PASSes, 0 analyzer issues.

- [ ] **Step 8: Commit**

```bash
git add app/lib/ app/web/index.html app/pubspec.yaml
git commit -m "feat(flutter): add offline state, update banner, and install hint for PWA polish"
```

---

## Task 6: PWA Section 7.8 checklist verification

**Files:**
- Read/verify: `app/web/manifest.json`, `app/web/index.html`, existing icons.
- Modify as needed: `app/web/manifest.json`, icon assets (192px/512px maskable), `app/web/index.html` (PWA meta), `app/lib/web.py` CSP headers.
- Create: `eval/RESULTS.md` entries for Lighthouse, first-load size, and 360px layout.

**No new test file** — verification is manual + Lighthouse CLI output recorded in `eval/RESULTS.md`.

- [ ] **Step 1: Build Wasm release**

```bash
cd app && flutter build web --wasm --release
```
Expected: succeeds.

- [ ] **Step 2: Verify `manifest.json` completeness**

  Check: `name`, `short_name`, `display: "standalone"`, `start_url`, `theme_color`, `background_color`, `icons` with both 192px and 512px entries including `"purpose": "maskable"`. Fix any gaps.

- [ ] **Step 3: Run Lighthouse on `http://localhost:8000`**

```bash
npx lighthouse http://localhost:8000 --only-categories=pwa,performance --output=json --output-path=eval/lighthouse-week5.json
```
  Record Installability pass/fail and Performance score in `eval/RESULTS.md`.

- [ ] **Step 4: Verify 360px layout in Chrome DevTools**

  Set device emulation to 360×800. Navigate through Documents → Labs → Ask → Settings. Note any overflow or unusable elements. Fix wrapping/overflow issues in Dart widget code if found.

- [ ] **Step 5: TalkBack / keyboard smoke test**

  On desktop Chrome: tab through Documents and Ask screens; every interactive element must receive focus and have a label. Log any issues in `eval/RESULTS.md`; fix critical ones.

- [ ] **Step 6: iOS Safari smoke test**

  Load the app in Safari (or iOS simulator). Attempt install (Add to Home Screen), navigate, upload one document. Log result in `eval/RESULTS.md`; issues are logged, not blocking.

- [ ] **Step 7: Commit PWA manifest/icon fixes + Lighthouse record**

```bash
git add app/web/ eval/RESULTS.md eval/lighthouse-week5.json
git commit -m "feat(pwa): complete Section 7.8 checklist — manifest, maskable icons, Lighthouse pass"
```

---

## Task 7: RAG bake-off and full evaluation

**Files:**
- Modify: `eval/run_eval.py` (add `ask_bakeoff` and `pwa_delivery` modes)
- Modify: `eval/RESULTS.md` (log Week 5 results)

**Interfaces:**
- Consumes: 40 QA pairs (from eval set described in spec Section 16); existing `eval/ground_truth/`; live backend at `http://localhost:8000`.
- Produces: `correct_answer_rate`, `valid_citation_rate`, `unanswerable_correctly_refused_rate` for native-tools vs router-fallback modes; logged in `eval/RESULTS.md`.

- [ ] **Step 1: Add `ask_bakeoff` mode to `eval/run_eval.py`**

  Read 40 QA pairs from `eval/ground_truth/ask_qa.json` (create if missing with ≥5 synthetic pairs covering: numeric retrieval, unanswerable, multi-test, medication text, cross-document). For each question:
  1. POST `/api/v1/ask` with `EVAL_API_KEY`.
  2. Compare `answer` to expected answer (keyword match or exact for "not found" cases).
  3. Check citations resolve to real DB IDs via `GET /api/v1/documents/{id}`.
  Log per-question results and aggregate metrics.

- [ ] **Step 2: Run `ask_bakeoff` evaluation with native tools**

```bash
python eval/run_eval.py ask_bakeoff
```
  Record `correct_answer_rate ≥ 85%` and `unanswerable_refused ≥ 95%` targets in `eval/RESULTS.md`.

- [ ] **Step 3: Run `ask_bakeoff` with router-fallback**

  Temporarily set `llm.supports_tools = false` in Settings, rerun, restore. Record results.

- [ ] **Step 4: Final full Section 16 evaluation sweep**

  Run all existing eval modes (OCR, extraction F1, embedding Recall@5) on full eval set and append final table to `eval/RESULTS.md`. Note any metrics that miss targets and document root cause.

- [ ] **Step 5: Provider portability smoke test**

  In Settings switch to a second provider (e.g. OpenRouter or Together AI). Run `POST /settings/test-llm`, upload one synthetic document, confirm extraction, ask one question. Record pass/fail in `eval/RESULTS.md`.

- [ ] **Step 6: Write demo script (`eval/demo_script.md`)**

  Step-by-step script for a 5-minute demo: install PWA, configure Groq key, upload one synthetic lab report, review, confirm, view chart, ask a question, show citation chip.

- [ ] **Step 7: Rotate provider key**

  Invalidate the prototype Groq key(s) used during development. Log "key rotated" in `eval/RESULTS.md`.

- [ ] **Step 8: Commit**

```bash
git add eval/run_eval.py eval/RESULTS.md eval/demo_script.md eval/ground_truth/
git commit -m "eval: add ask bake-off, full Week 5 eval results, demo script, key rotation note"
```

---

## Task 8: Final integration check

**Files:**
- No new files.

- [ ] **Step 1: Run full backend test suite**

```bash
docker compose exec -T api pytest -v
```
Expected: all tests pass (≥ 54 — prior 48 + 6 new RAG tests).

- [ ] **Step 2: Run Flutter test suite and analyzer**

```bash
flutter test && flutter analyze
```
Expected: all tests pass, 0 issues.

- [ ] **Step 3: Build Wasm release**

```bash
flutter build web --wasm --release
```
Expected: succeeds.

- [ ] **Step 4: Smoke test full flow on running stack**

  `docker compose up`, navigate to `http://localhost:8000`, ask "What is my latest hemoglobin?" and verify an answer with a citation chip appears.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: Week 5 complete — Ask/RAG, PWA polish, full evaluation"
```

---

## Week 5 Exit Criteria

| Check | Pass condition |
|---|---|
| Backend tests | All ≥ 54 tests pass |
| Flutter tests | All pass; 0 analyzer issues |
| Wasm build | `flutter build web --wasm --release` succeeds |
| Ask endpoint | `POST /api/v1/ask` returns `{answer, citations}` with valid IDs |
| Citation chips | Tapping an obs chip navigates to the correct document review |
| Router fallback | `supports_tools=false` path returns a valid cited answer |
| Offline state | Documents and Ask screens show offline message with no network |
| Update banner | Shown after a new build is deployed (verified manually) |
| Install hint | Appears once, dismissed state persists in `shared_preferences` |
| Lighthouse | PWA installability passes; first-load metrics recorded |
| 360px layout | No overflow on any navigation tab |
| Ask bake-off | Correct answer rate ≥ 85%; unanswerable refused ≥ 95% |
| Provider portability | Second provider passes probe ladder and produces extraction |
| Demo script | Exists at `eval/demo_script.md` |
| Key rotated | Prototype key invalidated; logged in `eval/RESULTS.md` |
