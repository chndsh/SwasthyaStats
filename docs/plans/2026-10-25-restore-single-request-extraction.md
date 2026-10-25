# Restore Single-Request Extraction and Align with Main Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore single-request full-page OCR extraction and align token limits with the main branch, eliminating high rate-limit thrashing and incomplete test extraction caused by artificial 6-line chunking.

**Architecture:** Revert `api/app/pipeline/extract.py` to send the complete page text in a single LLM request with full table context, keeping the OCR recovery fallback only for empty LLM responses. Remove artificial 1000-token clamping in `api/app/llm/client.py` and restore default output tokens to 2000 in schemas and settings.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, pytest, Groq API

## Global Constraints
- Match `main` branch behavior where 1 page = 1 LLM request.
- Retain Admin Users UI enhancements (`admin_users_screen.dart` back navigation).
- Retain conservative OCR recovery (`recover_observations_from_ocr`) as a page-level safety net when LLM observations are empty.

---

### Task 1: Update Tests for Single-Request Extraction and Unclamped Tokens

**Files:**
- Modify: `api/tests/test_extract.py`
- Modify: `api/tests/test_llm_client.py`

- [ ] Write a test in `api/tests/test_extract.py` asserting that multi-row pages are extracted in a single LLM call and all observations are captured.
- [ ] Remove `test_groq_output_tokens_are_clamped_to_provider_limit` from `api/tests/test_llm_client.py` or update it to verify that configured `llm_max_output_tokens` (e.g. 2000) is honored.
- [ ] Run tests to verify failure against current chunking/clamping code.

### Task 2: Restore Full-Page Extraction and Remove Output Token Clamping

**Files:**
- Modify: `api/app/pipeline/extract.py`
- Modify: `api/app/llm/client.py`
- Modify: `api/app/schemas.py`
- Modify: `api/app/services/settings.py`

- [ ] In `api/app/pipeline/extract.py`: Remove `MAX_EXTRACTION_LINES = 6` and `_extract_chunk`. Restore `extract_page` to send full `redacted_text` in a single `client.chat()` invocation. Keep `recover_observations_from_ocr` as a fallback when `not report.observations`.
- [ ] In `api/app/llm/client.py`: Remove `GROQ_MAX_OUTPUT_TOKENS` and the `payload[token_param] = min(...)` clamp.
- [ ] In `api/app/schemas.py` and `api/app/services/settings.py`: Restore default `llm_max_output_tokens` to 2000.

### Task 3: Verification & Container Live Check

- [ ] Run full backend test suite in Docker container.
- [ ] Verify live API container picks up changes and verify with live extraction smoke test.
- [ ] Log changes in `progress.md`.
