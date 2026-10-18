# SwasthyaStats — Week 5 Demo Script (5 Minutes)

> **Goal:** Show the end-to-end flow: install PWA → configure key → upload lab report → review → view chart → ask a question → see citation chip.

---

## Prerequisites (done before demo)

- [ ] Docker stack running: `docker compose up -d`
- [ ] Flutter Wasm build served: `http://localhost:8000`
- [ ] Groq API key ready (fresh session — allow ≥1 min before first question)
- [ ] Sample lab report image ready: `eval/fixtures/sample_lab_report.png`

---

## Step 1 — Install the PWA (≈30s)

1. Open Chrome/Edge at `http://localhost:8000`.
2. Click the **install banner** at the top ("Add SwasthyaStats to home screen") or use the browser's install button in the address bar.
3. Launch from the installed icon. It opens in standalone mode (no browser chrome).

**What to show:** App launches without browser UI, title "SwasthyaStats", teal theme.

---

## Step 2 — Configure Groq API Key (≈30s)

1. Tap the **Settings** (gear icon) tab.
2. Under "LLM Provider", set:
   - **Base URL:** `https://api.groq.com/openai/v1`
   - **Model:** `qwen/qwen3.8-27b`
   - **API Key:** `<paste Groq key>`
3. Tap **Save**.

**What to show:** Settings saved, no error toast.

---

## Step 3 — Upload a Lab Report (≈45s)

1. Tap the **Documents** tab.
2. Tap **+** (upload FAB).
3. Choose `sample_lab_report.png`.
4. Wait for status to change from `processing` → `review`.

**What to show:** Progress indicator during OCR, then row-by-row extracted observations appear in the review panel.

---

## Step 4 — Review & Confirm (≈30s)

1. In the review panel, inspect the extracted rows (hemoglobin, RBC, WBC, platelets).
2. Adjust any confidence-flagged rows if needed (amber/red rows).
3. Tap **Confirm**.
4. Status changes to `complete`.

**What to show:** Human-in-the-loop confirmation step; grounding prevents hallucinated values from being stored.

---

## Step 5 — View the Chart (≈30s)

1. Tap the **Charts** tab.
2. Select "Hemoglobin" from the metric dropdown.
3. The line chart shows the single data point at 13.8 gm/dL.

**What to show:** Data is stored, queryable, and visualised.

---

## Step 6 — Ask a Question with RAG (≈90s)

1. Tap the **Ask** tab.
2. Type: `What was my hemoglobin on my lab report?`
3. Tap **Send** (or press Enter).
4. Wait ~5–10s for the answer.

**Expected response:** "Your most recent hemoglobin result was **13.8 gm/dl**..."

5. Tap the **citation chip** (document name shown below the answer).
6. The document detail screen opens, showing the source record.

**What to show:** Grounded, citation-backed answer. No hallucinations — the answer comes directly from confirmed records.

---

## Step 7 — Show Offline Behaviour (≈30s, optional)

1. Disable network (Chrome DevTools → Network → Offline).
2. Reload the app.
3. Navigate to Documents — an **offline banner** appears; data screens gracefully degrade.
4. Re-enable network — banner disappears.

---

## Closing Notes

- All data stays on-device (Docker local stack). Nothing sent to external servers except LLM prompts to Groq.
- After the demo, invalidate the Groq key via Groq console or run:
  ```bash
  docker compose exec db psql -U postgres -d swasthya \
    -c "DELETE FROM settings WHERE key='api_keys';"
  ```
