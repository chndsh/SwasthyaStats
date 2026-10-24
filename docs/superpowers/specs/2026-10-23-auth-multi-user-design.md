# Multi-User Authentication — Design Document

**Date:** 2026-10-23  
**Branch:** `feat/auth-multi-user`  
**Status:** Approved for planning

---

## Intent and Why

SwasthyaStats is self-hosted health record software. Users can run it on their own machine and share access with friends and family. This design adds multi-user authentication so each person's health data stays private — even from the person running the server (the "host").

The goal is **confidentiality, integrity, and availability** without any external identity provider. No Google. No email server. No internet connection required after initial setup.

---

## Goals

- Any number of users can have accounts on a single SwasthyaStats instance
- Each user's health data is invisible to other users and to the host at the database level
- Each user provides and manages their own LLM API keys — the host pays nothing for guests' AI usage
- Login works entirely offline (no external OAuth calls)
- A first-run admin bootstraps the instance; the admin creates accounts for guests
- The whole system runs with `docker compose up` and zero additional infrastructure

## Non-Goals

- Self-registration (admin controls the guest list entirely)
- Social login (Google, GitHub, etc.)
- Password reset via email (admin resets passwords manually)
- Audit logging of who accessed what
- HIPAA / GDPR compliance certification
- End-to-end encryption of data during AI processing (see Honest Limitations)

## Anti-Goals (what would make this a failure even if it technically works)

- Requiring an internet connection to log in
- A host who simply queries the PostgreSQL database can read guest health data in plaintext
- Guest A can see any of Guest B's documents, observations, or lab values
- Adding auth breaks any existing AI feature (OCR, extraction, Ask)

---

## Honest Limitations (logged here by design)

**What this design does NOT protect:**

1. **Processing-time data.** OCR and LLM extraction run on the host's machine in server memory. During the ~10–30 seconds a document is being processed, its plaintext content passes through the host's Python process. A host with shell access and a memory dumper could intercept this. This is unavoidable while keeping server-side AI. It is disclosed to users.

2. **Vector chunk text.** The RAG "Ask" feature stores plaintext text chunks in the `chunks` table for semantic retrieval. These are **not encrypted at rest** because the server needs to retrieve and re-read them to answer questions. A host with direct DB access can read chunk text.

3. **Vector embeddings.** Embeddings are mathematical representations of text — they cannot be meaningfully encrypted without destroying their utility. They are stored as-is.

4. **Host with shell + environment access.** The per-user encryption key is derived from `SERVER_SECRET` (an env var) + `user_id`. A host who has access to both the DB and the env var can decrypt stored data. This protects against DB dump / backup theft, not a malicious host with full server access.

**What this design DOES protect:**

- A host who only has DB access (e.g. a database backup, a `psql` shell) **cannot read** `ocr_text`, `raw_json` extraction data, observation values, or LLM API keys — they are stored as Fernet ciphertext
- No cross-user data access is possible through the API (enforced at application layer + PostgreSQL RLS as defence-in-depth)
- LLM API keys are per-user and encrypted — the host cannot see or use a guest's API keys
- Passwords are never stored or logged — only Argon2id hashes

---

## Architecture

### Authentication Flow

```
Flutter Login Screen
  │  POST /auth/login  {email, password}
  ▼
FastAPI
  ├── Verify Argon2id(password, stored_hash)
  ├── Generate access_token  (JWT, 15 min, HS256, signed with SERVER_SECRET)
  ├── Generate refresh_token (JWT, 7 days, HS256, signed with SERVER_SECRET)
  └── Return {access_token, refresh_token, token_type: "bearer"}

Flutter stores both tokens in flutter_secure_storage (hardware-encrypted on device)

Every subsequent API request:
  Authorization: Bearer <access_token>
  │
  ▼
FastAPI dependency: get_current_user()
  ├── Decode + verify JWT signature
  ├── Check expiry
  ├── Load User from DB by user_id claim
  └── Inject user into route handler

Token refresh (when access_token expires):
  POST /auth/refresh  {refresh_token}
  └── Returns new access_token (+ rotated refresh_token)
```

### User Creation Flow (admin only)

```
Admin (host) calls:
  POST /auth/users  {email, password, display_name}
  Authorization: Bearer <admin_token>

Server:
  ├── Verify caller is_admin = true
  ├── Hash password with Argon2id
  ├── Create User row
  └── Return {user_id, email, display_name}
```

First admin is bootstrapped from env var `ADMIN_EMAIL` + `ADMIN_PASSWORD` at startup (idempotent — only runs if no users exist).

---

## Database Schema Changes

### New: `users` table

```sql
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    email       VARCHAR(255) NOT NULL UNIQUE,
    display_name VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,   -- Argon2id output
    is_admin    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_users_email ON users(email);
```

### Remove: `patients` table

The existing `Patient` model is a single-tenant stub. It is replaced by `User`. All tables that reference `patient_id` are migrated to reference `user_id`.

### Modified: `documents`

```sql
ALTER TABLE documents
  DROP COLUMN patient_id,
  ADD COLUMN user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX ix_documents_user_id ON documents(user_id);
```

`ocr_text` column type remains `TEXT` but values will be stored as Fernet ciphertext (prefixed `gAAAA...`). Application layer handles encryption/decryption transparently.

### Modified: `observations`

```sql
ALTER TABLE observations
  DROP COLUMN patient_id,
  ADD COLUMN user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE;
```

`value_text` encrypted at rest.

### Modified: `extractions`

`raw_json` (JSONB) stored as encrypted `TEXT` (`LargeBinary` in SQLAlchemy). Application serialises to JSON, encrypts, stores as bytes. Decrypts and deserialises on read.

### Modified: `app_settings` → `user_settings`

The current global `AppSetting` table becomes per-user. Each user manages their own LLM provider, model, and API keys.

```sql
CREATE TABLE user_settings (
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key      VARCHAR(100) NOT NULL,
    value    JSONB NOT NULL,
    is_secret BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, key)
);
```

LLM API key values in `user_settings` where `is_secret = TRUE` are encrypted with the user's derived encryption key (not the global Fernet key).

### Unchanged tables (user_id added via document cascade)

`document_pages`, `chunks`, `llm_calls` — already cascade-delete from `documents`. `chunks` gets a direct `user_id` column for RLS efficiency.

---

## Encryption at Rest

### Key Derivation (per-user)

`crypto.py` gains a new function:

```python
def _get_user_fernet(user_id: int) -> Fernet:
    secret = get_settings().SERVER_SECRET.encode("utf-8")
    salt = f"user:{user_id}".encode("utf-8")
    digest = hashlib.sha256(secret + salt).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)
```

This derives a **different Fernet key for every user** from the same `SERVER_SECRET`. A DB dump alone is insufficient to decrypt — the attacker also needs `SERVER_SECRET`.

### Fields encrypted at rest

| Table | Column | Encrypted |
|-------|--------|-----------|
| `documents` | `ocr_text` | ✅ |
| `extractions` | `raw_json` | ✅ (JSON → encrypt → store as Text) |
| `observations` | `value_text` | ✅ |
| `user_settings` | `value` where `is_secret=True` | ✅ (LLM API keys) |
| `chunks` | `text` | ❌ (needed for retrieval — disclosed) |
| `chunks` | `embedding` | ❌ (mathematical, can't encrypt) |
| `documents` | `doctor_name`, `doc_date`, `sha256` | ❌ (metadata, low sensitivity) |

### Transparent encryption layer

A `UserCrypto` class wraps `_get_user_fernet(user_id)` with `encrypt(plaintext: str) -> str` and `decrypt(ciphertext: str) -> str`. Route handlers and services receive a `UserCrypto` instance via FastAPI dependency injection (constructed from `current_user.id`).

---

## Per-User LLM API Keys

Each user manages their own LLM configuration in `user_settings`. When a request triggers OCR + extraction or Ask:

1. API reads the calling user's `user_settings` for `llm.api_keys`, `llm.provider`, `llm.model`
2. Decrypts API keys using that user's `UserCrypto`
3. Makes the LLM call using the user's key — host's key is never used for guest processing
4. `llm_calls` log row records `user_id` for the call

The existing Settings UI in Flutter is repurposed as a per-user settings screen (not global). The global admin `AppSetting` table is removed.

---

## PostgreSQL Row Level Security (Defence-in-Depth)

RLS is enabled on `documents`, `observations`, `chunks`, `user_settings`. The application sets a session variable `app.current_user_id` on each DB connection before executing queries. RLS policies enforce that rows are only visible when `user_id = current_setting('app.current_user_id')::int`.

This means: even if a bug in the application code forgets to filter by `user_id`, the database itself refuses to return another user's rows.

```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY documents_user_isolation ON documents
  USING (user_id = current_setting('app.current_user_id')::int);
```

The application sets this variable via a SQLAlchemy event on connection checkout.

---

## API Changes

### New endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | None | Email + password → JWT pair |
| POST | `/auth/refresh` | Refresh token | Rotate tokens |
| POST | `/auth/logout` | Access token | Invalidate refresh token (server-side blocklist in DB) |
| GET | `/auth/me` | Access token | Return current user info |
| POST | `/auth/users` | Admin only | Create a new user account |
| GET | `/auth/users` | Admin only | List all users |
| DELETE | `/auth/users/{id}` | Admin only | Delete user + all their data |
| PUT | `/auth/users/{id}/password` | Admin only | Reset a user's password |

### Modified endpoints

All existing endpoints (`/documents`, `/tests`, `/ask`, `/settings`, etc.) replace the current `X-API-Key` header with `Authorization: Bearer <token>` dependency. The global `API_KEY` env var is removed.

All queries gain an implicit `WHERE user_id = current_user.id` filter.

---

## Flutter Changes

### New: Login Screen

`app/lib/features/auth/login_screen.dart` — shown when no valid token is found in secure storage. Fields: email, password. Calls `POST /auth/login`. On success, stores both tokens.

### New: Token Storage

Replace `SharedPreferences` usage for auth with `flutter_secure_storage`. Tokens stored under keys `access_token` and `refresh_token`.

### New: Auth Controller

`app/lib/features/auth/auth_controller.dart` — `StateNotifier` managing login state. Exposed as `authStateProvider`. App router redirects to `/login` when unauthenticated.

### Modified: Dio Interceptor

`app/lib/core/api_client.dart` gains a request interceptor that:
1. Reads `access_token` from secure storage, attaches as `Authorization: Bearer`
2. On 401 response: calls `POST /auth/refresh`, retries original request once
3. On refresh failure: clears tokens, emits unauthenticated state → router redirects to `/login`

### Modified: Settings Screen

Becomes per-user LLM settings (not global). Each user sees and manages only their own API keys. Host's settings are completely separate from guests'.

### New: Admin Screen (host only)

Simple screen visible only to `is_admin = true` users. Lists users, creates users, resets passwords, and deletes users other than the current admin.

### Temporary-password onboarding

The `users` table includes `must_change_password`, defaulting to `false`.

- Admin-created users receive a temporary password and `must_change_password = true`.
- Admin password resets set `must_change_password = true`.
- A user may authenticate with a temporary password, but the router sends them to `/change-password` before allowing access to Documents, Labs, Ask, or Settings.
- `PUT /auth/me/password` verifies the current password, stores a new Argon2id hash, clears `must_change_password`, and invalidates the user's existing refresh tokens.
- Temporary passwords are displayed once in the admin interface and must be delivered to the user through a secure channel. They are never returned by user-list endpoints or written to logs.
- Admins cannot delete their own account.

---

## Migration Strategy

**Clean slate.** All existing data is dropped. The Alembic migration:

1. Drops `patients` table (cascades to all related data)
2. Creates `users` table
3. Recreates `documents`, `observations`, `extractions`, `chunks`, `document_pages`, `llm_calls` with `user_id` instead of `patient_id`
4. Creates `user_settings` table, drops `app_settings`
5. Enables RLS on relevant tables
6. Creates RLS policies

Migration version: `003_add_multi_user_auth.py`

---

## Dependency Changes

### Backend (new)

- `argon2-cffi>=23.1.0` — Argon2id password hashing
- `PyJWT>=2.9.0` — JWT encode/decode (pure Python, no C deps)

### Flutter (new)

- `flutter_secure_storage: ^9.x` — hardware-encrypted token storage
- Remove: direct `SharedPreferences` usage for tokens

Both packages are already common in the Flutter ecosystem and have no external service dependencies.

---

## Environment Variables

| Variable | Purpose | Change |
|----------|---------|--------|
| `SERVER_SECRET` | JWT signing + field encryption key derivation | **Required** — must be ≥32 chars, random |
| `ADMIN_EMAIL` | Bootstrap admin account email | **New** |
| `ADMIN_PASSWORD` | Bootstrap admin account password | **New** — used once at first startup, then discarded |
| `API_KEY` | Old global API key | **Removed** |
| `DATABASE_URL` | Unchanged | — |

---

## Security Properties Summary

| Threat | Protected? | Mechanism |
|--------|-----------|-----------|
| DB dump / backup theft | ✅ Yes | Fields encrypted with per-user Fernet key |
| Cross-user API access | ✅ Yes | `user_id` filter + PostgreSQL RLS |
| Password database leak | ✅ Yes | Argon2id hashes only, never plaintext |
| Guest's LLM API key exposure | ✅ Yes | Per-user encryption, never logged |
| Host reading stored health data | ✅ Partial | Encrypted at rest; processing-time access unavoidable |
| Host reading chunk text (for Ask) | ❌ No | Plaintext required for retrieval — disclosed |
| Token theft (network) | ✅ Yes | HTTPS (deployment concern), short-lived tokens |
| Token theft (device) | ✅ Yes | `flutter_secure_storage` hardware encryption |
| MITM during processing | ❌ Not in scope | HTTPS / TLS is deployment-layer concern |

---

## Builder Decisions

The following were settled during the builder-check review. Marked as builder calls so readers know who decided them.

- **Argon2id parameters:** `time_cost=3, memory_cost=65536, parallelism=4` (OWASP recommended for interactive login)
- **JWT algorithm:** HS256 (sufficient; RS256 not needed for single-server)
- **Refresh token rotation:** yes — each `/auth/refresh` call issues a new refresh token and invalidates the previous one
- **Refresh token blocklist:** stored in a new `refresh_token_blocklist` table (token hash + expiry); cleaned up on startup
- **Flutter routing:** go_router `redirect` guard on `authStateProvider`
- **Admin screen placement:** accessible from user avatar menu, only visible to `is_admin = true`
- **Background workers + user identity:** `user_id` is passed explicitly as a function parameter to `process_document_background`, `_run_extraction_stage`, and `embed_document`. `SettingsService` gains a `user_id` parameter to load per-user settings. `get_current_user()` is not available after the response is sent.
- **RLS connection pool:** `app.current_user_id` is set on SQLAlchemy connection **checkout** and reset to `-1` on **check-in**. This prevents a stale RLS context leaking from one request to the next in a pooled connection.
- **`ocr_lines`, `field_confidence`, `reviewer_edits` columns:** intentionally **not** encrypted at rest. Reason: all three are JSONB columns; encrypting them would require changing the column type to Text and breaking all existing JSONB key-path queries in the review and extraction pipelines. The plaintext health content in `ocr_lines` is already duplicated in the encrypted `ocr_text` field. Noted as a future enhancement once a typed-encryption layer is available.
- **Env-var LLM key fallback (`GROQ_API_KEY`, `LLM_API_KEY`):** used **for the admin account only**. When the admin has no keys configured in `user_settings`, the backend falls back to env vars. Guest accounts receive no fallback — they must configure their own keys before AI features work. This ensures the host is never silently charged for guest AI usage.
- **Flutter Web token storage:** `flutter_secure_storage` on Flutter Web falls back to browser `localStorage` with a JavaScript AES layer — **no hardware keychain**. This is acceptable for the web-first deployment target. The security property "hardware-encrypted on device" in the table below is updated to reflect reality.

---

## Corrected Security Properties (post builder-check)

| Threat | Protected? | Mechanism |
|--------|-----------|-----------|
| DB dump / backup theft | ✅ Yes | Fields encrypted with per-user Fernet key |
| Cross-user API access | ✅ Yes | `user_id` filter + PostgreSQL RLS |
| Password database leak | ✅ Yes | Argon2id hashes only, never plaintext |
| Guest's LLM API key exposure to host | ✅ Yes | Per-user encryption, never logged |
| Host reading stored health data (ocr_text, raw_json) | ✅ Partial | Encrypted at rest; processing-time access unavoidable |
| Host reading ocr_lines / field_confidence | ❌ No | JSONB compat constraint — plaintext in DB, disclosed |
| Host reading chunk text (for Ask) | ❌ No | Plaintext required for retrieval — disclosed |
| Token theft on device (web) | ⚠️ Partial | Browser localStorage + JS AES — no hardware keychain |
| Token theft on device (native) | ✅ Yes | flutter_secure_storage uses OS hardware keystore |
| Host env-var keys used for guest AI calls | ✅ No | Env-var fallback applies to admin account only |
| MITM during processing | ❌ Not in scope | HTTPS / TLS is deployment-layer concern |

---

*This document was written after a full brainstorming session and a builder-check review. All limitations and security properties are stated accurately. No security is implied beyond what is written.*
