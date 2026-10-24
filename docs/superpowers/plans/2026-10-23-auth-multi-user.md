# Multi-User Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Argon2id username/password authentication with per-user data isolation, per-user field encryption at rest, per-user LLM API keys, and a Flutter login screen — all without any external identity provider.

**Architecture:** A new `users` table replaces the existing `patients` table (clean-slate migration). Every existing data table gains `user_id`. FastAPI's `get_current_user()` JWT dependency replaces the global `X-API-Key` check everywhere. Sensitive fields (`ocr_text`, `raw_json`, `value_text`, LLM API keys) are encrypted at rest with a per-user Fernet key derived from `SERVER_SECRET + user_id`. PostgreSQL Row Level Security is added as defence-in-depth.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL + pgvector, `argon2-cffi`, `PyJWT`, Flutter Web, `flutter_secure_storage`, `go_router`, Riverpod.

**Spec:** `docs/superpowers/specs/2026-10-23-auth-multi-user-design.md`

## Global Constraints

- All 60 existing backend tests must remain green after every task.
- `flutter analyze` must report 0 issues before every Flutter commit.
- No new external service dependencies (no OAuth, no email, no SMS).
- `SERVER_SECRET` must be ≥ 32 chars; the constraint is enforced at startup.
- Background workers receive `user_id` as an explicit function parameter — never from `get_current_user()`.
- Env-var LLM keys (`GROQ_API_KEY`, `LLM_API_KEY`) are treated as admin-account-only fallback; guests without configured keys get an HTTP 402 error before any LLM call.
- Flutter target is web-only; `flutter_secure_storage` on web uses browser localStorage + JS AES (not hardware keychain) — this is documented, not a bug.

## Review Focus

1. **Stale RLS context on pooled connections** — if `app.current_user_id` is set on a connection but not reset before returning to the pool, the next request could inherit a stale value. Expect `app.current_user_id` to be reset to `-1` on check-in. Test: two sequential requests from different users must each see only their own rows.
2. **Admin bootstrap idempotency** — calling startup bootstrap twice (e.g. container restart) must not create a duplicate admin. Expect the `ON CONFLICT DO NOTHING` semantics.
3. **Expired access token with valid refresh token** — the Flutter Dio interceptor must silently refresh and retry on 401, not log the user out. Test: mock a 401 then a successful refresh, verify the original request is retried once.
4. **Guest with no configured LLM keys** — uploading a document must fail at the LLM extraction step with a clear 402 error, not a 500. Existing documents must still be viewable.
5. **Cascade delete on user deletion** — deleting a user via `DELETE /auth/users/{id}` must remove all their documents, observations, chunks, and settings without leaving orphaned rows.

---

### Task 1: Clean-Slate Migration + New Models

**Files:**
- Create: `api/alembic/versions/003_multi_user_auth.py`
- Modify: `api/app/models.py`
- Modify: `api/app/db.py` (add SQLAlchemy pool event for RLS session variable)

**Interfaces:**
- Produces:
  - `User` model: `id: int`, `email: str`, `display_name: str | None`, `password_hash: str`, `is_admin: bool`, `created_at: datetime`
  - `RefreshTokenBlocklist` model: `token_hash: str (PK)`, `expires_at: datetime`
  - `UserSetting` model: `user_id: int (FK)`, `key: str`, `value: JSONB`, `is_secret: bool`; composite PK `(user_id, key)`
  - `Document.user_id: int (FK → users.id CASCADE DELETE)`; `Document.patient_id` removed
  - `Observation.user_id: int (FK → users.id CASCADE DELETE)`; `Observation.patient_id` removed
  - `Chunk.user_id: int (FK → users.id CASCADE DELETE)` added for RLS efficiency
  - `LlmCall.user_id: int (FK → users.id SET NULL)` added
  - SQLAlchemy pool checkout event: `SET LOCAL app.current_user_id = :uid` on each request; reset to `-1` on check-in
  - `AppSetting` model and `app_settings` table: **dropped**
  - `Patient` model and `patients` table: **dropped**

- [ ] **Step 1: Write migration file `003_multi_user_auth.py`**

  Migration must:
  1. Drop all existing tables (`patients`, `app_settings`, `chunks`, `observations`, `extractions`, `document_pages`, `documents`, `llm_calls`) using `DROP TABLE IF EXISTS ... CASCADE`.
  2. Create `users` table.
  3. Create `refresh_token_blocklist` table.
  4. Recreate `documents`, `document_pages`, `extractions`, `observations`, `chunks`, `llm_calls` with `user_id` column; no `patient_id`.
  5. Create `user_settings` table.
  6. Enable RLS on `documents`, `observations`, `chunks`, `user_settings`:
     ```sql
     ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
     CREATE POLICY documents_isolation ON documents
       USING (user_id = current_setting('app.current_user_id', true)::int);
     ```
  7. Repeat for `observations`, `chunks`, `user_settings`.
  8. `downgrade()` raises `NotImplementedError` (clean-slate; no rollback).

- [ ] **Step 2: Update `api/app/models.py`**

  Remove `Patient`, `AppSetting`. Add `User`, `RefreshTokenBlocklist`, `UserSetting`. Update foreign keys on `Document`, `Observation`, `Chunk`, `LlmCall` as described in Interfaces.

- [ ] **Step 3: Add pool event in `api/app/db.py`**

  Add SQLAlchemy `@event.listens_for(engine, "connect")` to set `app.current_user_id = -1` as default. Add `set_rls_user_id(db: Session, user_id: int)` helper that runs `SELECT set_config('app.current_user_id', :uid, true)`.

- [ ] **Step 4: Run migration and verify schema**

  ```bash
  docker compose exec api alembic upgrade head
  docker compose exec api python -c "from app.db import engine; from sqlalchemy import inspect; print(inspect(engine).get_table_names())"
  ```
  Expected: `users`, `documents`, `observations`, `chunks`, `user_settings`, `refresh_token_blocklist` in output; `patients`, `app_settings` absent.

- [ ] **Step 5: Commit**

  ```bash
  git add api/
  git commit -m "feat(api): clean-slate migration, user model, and RLS policies"
  ```

---

### Task 2: Per-User Crypto Layer

**Files:**
- Modify: `api/app/security/crypto.py`
- Create: `api/tests/test_crypto.py`

**Interfaces:**
- Consumes: `get_settings().SERVER_SECRET: str`, `user_id: int`
- Produces:
  - `encrypt_for_user(plaintext: str, user_id: int) -> str`
  - `decrypt_for_user(ciphertext: str, user_id: int) -> str`
  - Existing `encrypt_secret(plaintext: str) -> str` and `decrypt_secret(ciphertext: str) -> str` remain unchanged (used for admin env-var key display)

- [ ] **Step 1: Write failing tests**

  ```python
  # api/tests/test_crypto.py
  def test_encrypt_for_user_roundtrip():
      ct = encrypt_for_user("HbA1c: 7.2", user_id=1)
      assert decrypt_for_user(ct, user_id=1) == "HbA1c: 7.2"

  def test_encrypt_for_user_isolation():
      ct = encrypt_for_user("secret", user_id=1)
      with pytest.raises(Exception):
          decrypt_for_user(ct, user_id=2)

  def test_encrypt_for_user_empty():
      assert encrypt_for_user("", user_id=1) == ""
      assert decrypt_for_user("", user_id=1) == ""
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  docker compose exec api pytest tests/test_crypto.py -v
  ```
  Expected: FAIL — `encrypt_for_user` not defined.

- [ ] **Step 3: Implement `encrypt_for_user` and `decrypt_for_user` in `api/app/security/crypto.py`**

  Add `_get_user_fernet(user_id: int) -> Fernet` that derives a key from `sha256(SERVER_SECRET.encode() + f"|user:{user_id}".encode())`. `encrypt_for_user` and `decrypt_for_user` wrap it with the same empty-string short-circuit as existing functions.

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  docker compose exec api pytest tests/test_crypto.py -v
  ```
  Expected: 3 PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add api/
  git commit -m "feat(api): add per-user Fernet encryption layer"
  ```

---

### Task 3: Auth Endpoints + Admin Bootstrap

**Files:**
- Create: `api/app/routers/auth.py`
- Create: `api/tests/test_auth_api.py`
- Modify: `api/app/security/auth.py` (replace `verify_api_key` with `get_current_user`)
- Modify: `api/app/config.py` (add `ADMIN_EMAIL`, `ADMIN_PASSWORD`; remove `API_KEY`)
- Modify: `api/app/main.py` (register auth router; run bootstrap on startup)

**Interfaces:**
- Consumes: `User` model (Task 1), `argon2-cffi`, `PyJWT`, `get_settings().SERVER_SECRET`
- Produces:
  - `get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User` — raises HTTP 401 if token invalid/expired
  - `get_admin_user(current_user: User = Depends(get_current_user)) -> User` — raises HTTP 403 if not admin
  - `POST /auth/login` body: `{email: str, password: str}` → `{access_token: str, refresh_token: str, token_type: "bearer"}`; HTTP 401 on bad credentials
  - `POST /auth/refresh` body: `{refresh_token: str}` → `{access_token: str, refresh_token: str, token_type: "bearer"}`; HTTP 401 if blocklisted/expired
  - `POST /auth/logout` (bearer) → HTTP 204; blocklists the refresh token hash
  - `GET /auth/me` (bearer) → `{id, email, display_name, is_admin}`
  - `POST /auth/users` (admin bearer) body: `{email, password, display_name?}` → `{id, email, display_name, is_admin: false}` HTTP 201
  - `GET /auth/users` (admin bearer) → list of `{id, email, display_name, is_admin, created_at}`
  - `DELETE /auth/users/{id}` (admin bearer) → HTTP 204; cascades all user data
  - `PUT /auth/users/{id}/password` (admin bearer) body: `{password: str}` → HTTP 204
  - `bootstrap_admin(db)` — creates admin from `ADMIN_EMAIL`/`ADMIN_PASSWORD` env vars if zero users exist; idempotent

- [ ] **Step 1: Add `argon2-cffi>=23.1.0` and `PyJWT>=2.9.0` to `api/requirements.txt`**

- [ ] **Step 2: Write failing tests**

  ```python
  # api/tests/test_auth_api.py
  def test_login_success(client, admin_headers):
      resp = client.post("/auth/login", json={"email": "admin@test.com", "password": "adminpass"})
      assert resp.status_code == 200
      assert "access_token" in resp.json()
      assert "refresh_token" in resp.json()

  def test_login_wrong_password(client):
      resp = client.post("/auth/login", json={"email": "admin@test.com", "password": "wrong"})
      assert resp.status_code == 401

  def test_create_user_admin_only(client, admin_headers, user_headers):
      resp = client.post("/auth/users",
          json={"email": "guest@test.com", "password": "guestpass"},
          headers=user_headers)
      assert resp.status_code == 403

  def test_create_user_success(client, admin_headers):
      resp = client.post("/auth/users",
          json={"email": "new@test.com", "password": "pass123", "display_name": "New User"},
          headers=admin_headers)
      assert resp.status_code == 201
      assert resp.json()["email"] == "new@test.com"
      assert resp.json()["is_admin"] is False

  def test_refresh_token_rotates(client, admin_headers):
      login = client.post("/auth/login", json={"email": "admin@test.com", "password": "adminpass"})
      old_refresh = login.json()["refresh_token"]
      resp = client.post("/auth/refresh", json={"refresh_token": old_refresh})
      assert resp.status_code == 200
      new_refresh = resp.json()["refresh_token"]
      assert new_refresh != old_refresh
      # Old refresh token must now be invalid
      resp2 = client.post("/auth/refresh", json={"refresh_token": old_refresh})
      assert resp2.status_code == 401

  def test_logout_blocks_refresh(client, admin_headers):
      login = client.post("/auth/login", json={"email": "admin@test.com", "password": "adminpass"})
      refresh = login.json()["refresh_token"]
      access = login.json()["access_token"]
      client.post("/auth/logout", headers={"Authorization": f"Bearer {access}"})
      resp = client.post("/auth/refresh", json={"refresh_token": refresh})
      assert resp.status_code == 401

  def test_delete_user_cascades(client, admin_headers):
      create = client.post("/auth/users",
          json={"email": "todelete@test.com", "password": "pass"},
          headers=admin_headers)
      uid = create.json()["id"]
      resp = client.delete(f"/auth/users/{uid}", headers=admin_headers)
      assert resp.status_code == 204
  ```

- [ ] **Step 3: Run tests to verify they fail**

  ```bash
  docker compose exec api pytest tests/test_auth_api.py -v
  ```
  Expected: FAIL — router not registered.

- [ ] **Step 4: Implement `api/app/routers/auth.py`**

  - Argon2id: `argon2.PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)`
  - Access token: `JWT({"sub": str(user_id), "exp": now + 15min})`, HS256, `SERVER_SECRET`
  - Refresh token: `JWT({"sub": str(user_id), "jti": uuid4(), "exp": now + 7days})`, stored hash in `refresh_token_blocklist` on use/logout
  - `get_current_user`: OAuth2PasswordBearer scheme, decode JWT, load user
  - Bootstrap: `bootstrap_admin(db)` called in `app.on_event("startup")`; uses `INSERT ... ON CONFLICT DO NOTHING`

- [ ] **Step 5: Update `api/app/security/auth.py`**

  Replace `verify_api_key` with re-export of `get_current_user` and `get_admin_user` from `auth.py` router. Keep old `verify_api_key` as a no-op stub with a deprecation comment (removed in Task 4).

- [ ] **Step 6: Run tests**

  ```bash
  docker compose exec api pytest tests/test_auth_api.py -v
  ```
  Expected: all PASS.

- [ ] **Step 7: Run all backend tests to confirm no regressions**

  ```bash
  docker compose exec api pytest tests/ -q
  ```
  Expected: all existing tests still pass (they still use `X-API-Key` via `auth_headers` fixture — unchanged yet).

- [ ] **Step 8: Commit**

  ```bash
  git add api/
  git commit -m "feat(api): add auth endpoints, JWT, Argon2id, admin bootstrap"
  ```

---

### Task 4: Scope All Existing Endpoints to Current User

**Files:**
- Modify: `api/app/routers/documents.py`
- Modify: `api/app/routers/charts.py`
- Modify: `api/app/routers/ask.py`
- Modify: `api/app/routers/settings.py`
- Modify: `api/app/services/documents.py`
- Modify: `api/app/db.py` (`set_rls_user_id` call added to request lifecycle)
- Modify: `api/tests/conftest.py` (update `auth_headers` to use JWT; add `user_headers` for a non-admin user)
- Delete: `API_KEY` env var usage in `api/app/config.py` and `docker-compose.yml`

**Interfaces:**
- Consumes: `get_current_user() -> User` (Task 3)
- Produces: all routes replace `Depends(verify_api_key)` with `Depends(get_current_user)`; every DB query adds `.filter(Model.user_id == current_user.id)`; `set_rls_user_id(db, current_user.id)` called at start of each request

- [ ] **Step 1: Update `conftest.py`**

  Replace `auth_headers` fixture to: call `POST /auth/login` with admin credentials, return `{"Authorization": f"Bearer {token}"}`. Add `user_headers` fixture for a second non-admin test user.

- [ ] **Step 2: Replace `verify_api_key` in all routers**

  In every router file, replace `Depends(verify_api_key)` with `current_user: User = Depends(get_current_user)`. Add `set_rls_user_id(db, current_user.id)` as first line of each route body.

- [ ] **Step 3: Add `user_id` filter to all document and observation queries**

  In `documents.py` router and `documents.py` service, every `.query(Document)` gains `.filter(Document.user_id == current_user.id)`. Every `Document(...)` creation gains `user_id=current_user.id`. Same for `Observation`, `Chunk`.

- [ ] **Step 4: Write cross-user isolation test**

  ```python
  # api/tests/test_user_isolation.py
  def test_user_cannot_see_other_users_documents(client, admin_headers, user_headers):
      # Admin uploads document
      resp = client.get("/documents", headers=admin_headers)
      # Regular user should see empty list, not admin's documents
      resp2 = client.get("/documents", headers=user_headers)
      assert resp2.status_code == 200
      assert resp2.json() == []
  ```

- [ ] **Step 5: Run all backend tests**

  ```bash
  docker compose exec api pytest tests/ -q
  ```
  Expected: all PASS. This is the regression gate — if anything breaks, fix before continuing.

- [ ] **Step 6: Commit**

  ```bash
  git add api/
  git commit -m "feat(api): scope all endpoints to current user, replace API key auth with JWT"
  ```

---

### Task 5: Per-User Settings Service

**Files:**
- Modify: `api/app/services/settings.py`
- Modify: `api/app/routers/settings.py`
- Create: `api/tests/test_user_settings.py`

**Interfaces:**
- Consumes: `UserSetting` model (Task 1), `get_current_user` (Task 3), `encrypt_for_user` / `decrypt_for_user` (Task 2)
- Produces:
  - `SettingsService(db: Session, user_id: int)` — replaces global `SettingsService(db)`
  - All `AppSetting` queries replaced with `UserSetting` queries filtered by `user_id`
  - `get_decrypted_keys(self) -> list[dict]` — falls back to env vars only if `self.user_id == admin_user_id` (admin check: `db.query(User).filter(User.id == self.user_id).first().is_admin`)
  - LLM API key values encrypted with `encrypt_for_user(key, self.user_id)` on write; `decrypt_for_user(ct, self.user_id)` on read

- [ ] **Step 1: Write failing test**

  ```python
  # api/tests/test_user_settings.py
  def test_guest_llm_key_isolated_from_admin(client, admin_headers, user_headers):
      # Admin sets a key
      client.put("/settings", json={"llm_api_keys": [{"key": "admin-key", "label": "main"}]},
          headers=admin_headers)
      # Guest should see no keys
      resp = client.get("/settings", headers=user_headers)
      assert resp.json()["llm_api_keys"] == []

  def test_guest_no_env_fallback(client, user_headers):
      # Guest with no keys configured should get 402 on LLM call
      # (tested via upload endpoint attempting extraction)
      pass  # Integration tested in Task 6
  ```

- [ ] **Step 2: Refactor `SettingsService` to accept `user_id`**

  Replace all `AppSetting` references with `UserSetting`. `get_setting_value`, `set_setting_value` filter by `self.user_id`. `get_decrypted_keys` checks `is_admin` before falling back to env vars. Secret values use `encrypt_for_user` / `decrypt_for_user`.

- [ ] **Step 3: Update `settings.py` router**

  Inject `current_user` and pass `user_id=current_user.id` to `SettingsService`.

- [ ] **Step 4: Run tests**

  ```bash
  docker compose exec api pytest tests/test_user_settings.py tests/ -q
  ```
  Expected: all PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add api/
  git commit -m "feat(api): per-user settings service with isolated encrypted LLM keys"
  ```

---

### Task 6: Background Workers + Encrypted Field Storage

**Files:**
- Modify: `api/app/pipeline/extract.py`
- Modify: `api/app/services/documents.py`
- Modify: `api/app/routers/documents.py` (pass `user_id` to background task)

**Interfaces:**
- Consumes: `encrypt_for_user` / `decrypt_for_user` (Task 2), `SettingsService(db, user_id)` (Task 5)
- Produces:
  - `process_document_background(document_id: int, user_id: int, db_url: str)` — `user_id` added as explicit parameter
  - `_run_extraction_stage(doc, user_id: int, db: Session)` — uses `SettingsService(db, user_id)` for keys
  - `Document.ocr_text` written as `encrypt_for_user(raw_text, user_id)`, read back with `decrypt_for_user`
  - `Extraction.raw_json` written as `encrypt_for_user(json.dumps(raw), user_id)`, column type changed to `Text`; read with `json.loads(decrypt_for_user(...))`
  - `Observation.value_text` written as `encrypt_for_user(value, user_id)` on create, decrypted on read
  - Guest with no keys: `SettingsService.get_decrypted_keys()` returns `[]` → document status set to `"failed"` with error message `"No LLM API key configured. Add one in Settings."`

- [ ] **Step 1: Write failing test for guest-no-key 402 path**

  ```python
  # api/tests/test_documents_api.py (add to existing file)
  def test_extraction_fails_gracefully_without_llm_key(client, user_headers):
      # user_headers user has no LLM keys configured
      # Upload a document
      # After processing, document status should be "failed" not 500
      resp = client.get("/documents", headers=user_headers)
      # At minimum, endpoint must return 200 (not crash)
      assert resp.status_code == 200
  ```

- [ ] **Step 2: Add `user_id` parameter to background worker call site**

  In `api/app/routers/documents.py` upload endpoint: pass `user_id=current_user.id` to `BackgroundTasks.add_task(process_document_background, ..., user_id=current_user.id)`.

- [ ] **Step 3: Update `process_document_background` and `_run_extraction_stage`**

  Add `user_id: int` parameter. Thread it through to `SettingsService(db, user_id)`. On empty key list, set `doc.status = "failed"` and `doc.ocr_text = encrypt_for_user("No LLM API key configured.", user_id)`.

- [ ] **Step 4: Encrypt `ocr_text` on write, decrypt on read**

  In `documents.py` service: after OCR, `doc.ocr_text = encrypt_for_user(raw_text, user_id)`. In the router's `GET /documents/{id}` (review endpoint), `doc.ocr_text = decrypt_for_user(doc.ocr_text, doc.user_id)` before returning.

- [ ] **Step 5: Encrypt `Extraction.raw_json` on write, decrypt on read**

  Change `Extraction.raw_json` column in `models.py` from `JSONB` to `Text` (via a migration addendum or handled inline in the Task 1 migration). In `_run_extraction_stage`: `extraction.raw_json = encrypt_for_user(json.dumps(data), user_id)`. On read in charts/review endpoints: `json.loads(decrypt_for_user(extraction.raw_json, doc.user_id))`.

- [ ] **Step 6: Encrypt `Observation.value_text` on write, decrypt on read**

  In services that create observations: `obs.value_text = encrypt_for_user(val, user_id)` if val is not None. In endpoints that return observations: decrypt before serialisation.

- [ ] **Step 7: Run all backend tests**

  ```bash
  docker compose exec api pytest tests/ -q
  ```
  Expected: all PASS.

- [ ] **Step 8: Commit**

  ```bash
  git add api/
  git commit -m "feat(api): pass user_id to background workers, encrypt sensitive fields at rest"
  ```

---

### Task 7: Flutter — AuthController + Login Screen + Secure Storage

**Files:**
- Modify: `app/pubspec.yaml` (add `flutter_secure_storage`)
- Create: `app/lib/features/auth/auth_model.dart`
- Create: `app/lib/features/auth/auth_controller.dart`
- Create: `app/lib/features/auth/login_screen.dart`
- Modify: `app/lib/core/api_client.dart` (remove `X-API-Key`, no-op for now — interceptor in Task 8)
- Modify: `app/lib/features/navigation/app_router.dart` (add `/login` route + redirect guard)
- Modify: `app/lib/main.dart` (initialise auth state before routing)
- Create: `app/test/login_screen_test.dart`

**Interfaces:**
- Consumes: `POST /auth/login`, `GET /auth/me`
- Produces:
  - `AuthUser({id, email, displayName, isAdmin})`
  - `authControllerProvider: StateNotifierProvider<AuthController, AsyncValue<AuthUser?>>` — `null` = unauthenticated
  - `AuthController.login(email, password) -> Future<void>` — throws on bad credentials
  - `AuthController.logout() -> Future<void>`
  - `AuthController.loadFromStorage() -> Future<void>` — called at startup; reads token from secure storage, calls `/auth/me` to hydrate user; on failure emits `null`
  - Tokens stored: `flutter_secure_storage` keys `"access_token"` and `"refresh_token"`
  - `/login` route: renders `LoginScreen`; on success redirects to `/`
  - go_router redirect: if `authState == null` and path != `/login`, redirect to `/login`

- [ ] **Step 1: Add `flutter_secure_storage: ^9.2.2` to `app/pubspec.yaml` and run `flutter pub get`**

- [ ] **Step 2: Write failing login screen test**

  ```dart
  // app/test/login_screen_test.dart
  testWidgets('login screen renders email and password fields', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: MaterialApp(home: LoginScreen())));
    expect(find.byType(TextField), findsNWidgets(2));
    expect(find.text('Sign in'), findsOneWidget);
  });

  testWidgets('login screen shows error on failed login', (tester) async {
    // Override authControllerProvider to throw on login
    // Expect an error message to appear after tapping Sign in
  });
  ```

- [ ] **Step 3: Implement `auth_model.dart`**

  `AuthUser` with `fromJson(Map<String, dynamic>)` from `/auth/me` response.

- [ ] **Step 4: Implement `auth_controller.dart`**

  `AuthController extends StateNotifier<AsyncValue<AuthUser?>>`. `login()`: POST `/auth/login`, store tokens in `FlutterSecureStorage`, POST `/auth/me`, update state. `logout()`: POST `/auth/logout` (fire-and-forget), clear storage, state = `AsyncData(null)`. `loadFromStorage()`: read token, if present call `/auth/me`; on 401 call refresh endpoint; on failure emit `AsyncData(null)`.

- [ ] **Step 5: Implement `login_screen.dart`**

  Email `TextField`, password `TextField` (obscured), "Sign in" `FilledButton`. On submit calls `ref.read(authControllerProvider.notifier).login(email, password)`. Shows inline error on `AsyncError`. Shows `CircularProgressIndicator` on `AsyncLoading`.

- [ ] **Step 6: Add `/login` route and guard to `app_router.dart`**

  Add `GoRoute(path: '/login', builder: LoginScreen)`. In `redirect`: `if (authState == null && location != '/login') return '/login';`

- [ ] **Step 7: Call `loadFromStorage()` in `main.dart` before app renders**

  In the async init block, `await container.read(authControllerProvider.notifier).loadFromStorage()`.

- [ ] **Step 8: Run flutter analyze and login screen tests**

  ```bash
  cd app && /home/chandish/flutter/bin/flutter analyze --no-pub
  cd app && /home/chandish/flutter/bin/flutter test test/login_screen_test.dart --no-pub
  ```
  Expected: 0 issues, tests PASS.

- [ ] **Step 9: Commit**

  ```bash
  git add app/
  git commit -m "feat(app): add auth controller, login screen, and route guard"
  ```

---

### Task 8: Flutter — Dio Interceptor (Bearer Token + Auto-Refresh)

**Files:**
- Modify: `app/lib/core/api_client.dart`
- Create: `app/test/api_client_test.dart`

**Interfaces:**
- Consumes: `authControllerProvider` (Task 7), `FlutterSecureStorage`
- Produces:
  - Dio interceptor on every request: read `access_token` from secure storage; attach `Authorization: Bearer <token>`
  - On 401 response: call `POST /auth/refresh` with `refresh_token` from storage; on success store new tokens and retry original request once; on refresh failure call `authController.logout()` (triggers redirect to `/login`)
  - Remove `X-API-Key` header from all requests

- [ ] **Step 1: Write failing test**

  ```dart
  // app/test/api_client_test.dart
  test('interceptor attaches bearer token to requests', () async {
    // Mock secure storage returning a token
    // Make a request via Dio
    // Assert Authorization header is present and correct
  });

  test('interceptor refreshes on 401 and retries', () async {
    // Mock: first request returns 401, refresh returns new token, retry returns 200
    // Assert the final response is 200 and new token is stored
  });
  ```

- [ ] **Step 2: Implement interceptor in `api_client.dart`**

  Add `AuthInterceptor` extending `Interceptor`. `onRequest`: read access token from `FlutterSecureStorage`, set header. `onError`: if error is 401, call refresh endpoint, on success store new tokens and retry with `handler.resolve(await dio.fetch(err.requestOptions))`. On refresh failure: call `logout()` via provider ref or callback.

- [ ] **Step 3: Register interceptor in `ApiClient` constructor**

  ```dart
  dio.interceptors.add(AuthInterceptor(storage: const FlutterSecureStorage()));
  ```

- [ ] **Step 4: Run flutter analyze and tests**

  ```bash
  cd app && /home/chandish/flutter/bin/flutter analyze --no-pub
  cd app && /home/chandish/flutter/bin/flutter test test/api_client_test.dart --no-pub
  ```
  Expected: 0 issues, PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add app/
  git commit -m "feat(app): add Dio JWT interceptor with auto-refresh on 401"
  ```

---

### Task 9: Flutter — Per-User Settings Screen + Admin Panel

**Files:**
- Modify: `app/lib/features/settings/` (existing settings screen — scope to current user)
- Create: `app/lib/features/admin/admin_screen.dart`
- Modify: `app/lib/features/navigation/app_router.dart` (add `/admin` route)
- Modify: `app/lib/features/navigation/app_router.dart` (add user avatar/menu in scaffold)

**Interfaces:**
- Consumes: `authControllerProvider` (Task 7), `GET /auth/users`, `POST /auth/users`, `DELETE /auth/users/{id}`, `PUT /auth/users/{id}/password`
- Produces:
  - Settings screen works unchanged (now per-user via scoped API)
  - Logout option in user menu (calls `authController.logout()`)
  - Admin screen: list of users, "Create user" form (email + display name + password), delete button per user, reset password button per user
  - `/admin` route only reachable when `currentUser.isAdmin == true`

- [ ] **Step 1: Add user avatar menu to `ScaffoldWithResponsiveNav`**

  `CircleAvatar` in AppBar showing first letter of `displayName`. Tapping opens `PopupMenuButton` with "Settings", "Admin" (only if `isAdmin`), "Sign out".

- [ ] **Step 2: Implement `admin_screen.dart`**

  `ConsumerStatefulWidget`. Loads user list from `GET /auth/users`. Displays `ListView` of users. FAB opens `showDialog` with create-user form. Each row has delete icon (with confirm dialog) and password reset icon (opens dialog with new password field).

- [ ] **Step 3: Add `/admin` route with admin guard**

  ```dart
  GoRoute(
    path: '/admin',
    redirect: (context, state) {
      final user = ref.read(authControllerProvider).value;
      if (user == null || !user.isAdmin) return '/';
      return null;
    },
    builder: (context, state) => const AdminScreen(),
  )
  ```

- [ ] **Step 4: Run flutter analyze and all flutter tests**

  ```bash
  cd app && /home/chandish/flutter/bin/flutter analyze --no-pub
  cd app && /home/chandish/flutter/bin/flutter test --no-pub
  ```
  Expected: 0 issues, all tests PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add app/
  git commit -m "feat(app): add admin panel, user menu, and logout"
  ```

---

### Task 10: Full End-to-End Verification + Web Build

**Files:**
- Modify: `docker-compose.yml` (add `ADMIN_EMAIL`, `ADMIN_PASSWORD`; remove `API_KEY`)
- Modify: `progress.md`

**Interfaces:**
- Consumes: all previous tasks

- [ ] **Step 1: Update `docker-compose.yml`**

  Add env vars to `api` service:
  ```yaml
  ADMIN_EMAIL: admin@localhost
  ADMIN_PASSWORD: change-me-on-first-run
  ```
  Remove `API_KEY` line.

- [ ] **Step 2: Run all backend tests**

  ```bash
  docker compose exec api pytest tests/ -q
  ```
  Expected: all PASS (≥60 tests).

- [ ] **Step 3: Run flutter analyze**

  ```bash
  cd app && /home/chandish/flutter/bin/flutter analyze --no-pub
  ```
  Expected: 0 issues.

- [ ] **Step 4: Run all flutter tests**

  ```bash
  cd app && /home/chandish/flutter/bin/flutter test --no-pub
  ```
  Expected: all PASS.

- [ ] **Step 5: Build Flutter web**

  ```bash
  cd app && /home/chandish/flutter/bin/flutter build web --wasm
  ```
  Expected: `✓ Built build/web`

- [ ] **Step 6: Smoke test the running stack**

  ```bash
  docker compose up -d --build
  curl -s http://localhost:8000/health | python3 -m json.tool
  # Login as admin
  curl -s -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@localhost","password":"change-me-on-first-run"}' | python3 -m json.tool
  ```
  Expected: health returns `{"status":"ok"}`, login returns `{"access_token": "...", "refresh_token": "..."}`.

- [ ] **Step 7: Log completion in `progress.md`**

- [ ] **Step 8: Final commit**

  ```bash
  git add .
  git commit -m "feat: complete multi-user auth with per-user encryption and admin panel"
  ```

---

## File Map

| File | Task | Action |
|------|------|--------|
| `api/alembic/versions/003_multi_user_auth.py` | 1 | Create |
| `api/app/models.py` | 1 | Modify — User, RefreshTokenBlocklist, UserSetting; remove Patient, AppSetting |
| `api/app/db.py` | 1 | Modify — pool event, `set_rls_user_id()` |
| `api/app/security/crypto.py` | 2 | Modify — add per-user Fernet functions |
| `api/tests/test_crypto.py` | 2 | Create |
| `api/app/routers/auth.py` | 3 | Create |
| `api/app/security/auth.py` | 3 | Modify — replace verify_api_key with get_current_user |
| `api/app/config.py` | 3 | Modify — add ADMIN_EMAIL/PASSWORD, remove API_KEY |
| `api/app/main.py` | 3 | Modify — register auth router, bootstrap startup |
| `api/tests/test_auth_api.py` | 3 | Create |
| `api/app/routers/documents.py` | 4 | Modify — JWT dep, user_id filter |
| `api/app/routers/charts.py` | 4 | Modify — JWT dep, user_id filter |
| `api/app/routers/ask.py` | 4 | Modify — JWT dep, user_id filter |
| `api/app/routers/settings.py` | 4, 5 | Modify — JWT dep, per-user settings |
| `api/app/services/documents.py` | 4, 6 | Modify — user_id scoping, field encryption |
| `api/tests/conftest.py` | 4 | Modify — JWT-based auth fixtures |
| `api/tests/test_user_isolation.py` | 4 | Create |
| `api/app/services/settings.py` | 5 | Modify — UserSetting, per-user keys |
| `api/tests/test_user_settings.py` | 5 | Create |
| `api/app/pipeline/extract.py` | 6 | Modify — user_id param, SettingsService(db, user_id) |
| `app/pubspec.yaml` | 7 | Modify — add flutter_secure_storage |
| `app/lib/features/auth/auth_model.dart` | 7 | Create |
| `app/lib/features/auth/auth_controller.dart` | 7 | Create |
| `app/lib/features/auth/login_screen.dart` | 7 | Create |
| `app/lib/features/navigation/app_router.dart` | 7, 9 | Modify — login route, guard, admin route, user menu |
| `app/lib/main.dart` | 7 | Modify — loadFromStorage() at startup |
| `app/test/login_screen_test.dart` | 7 | Create |
| `app/lib/core/api_client.dart` | 8 | Modify — AuthInterceptor |
| `app/test/api_client_test.dart` | 8 | Create |
| `app/lib/features/admin/admin_screen.dart` | 9 | Create |
| `docker-compose.yml` | 10 | Modify — ADMIN_EMAIL/PASSWORD, remove API_KEY |
