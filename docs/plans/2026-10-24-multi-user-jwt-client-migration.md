# Multi-User JWT Client Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete the end-to-end JWT authentication migration so Flutter can log in, persist and refresh sessions, access documents/labs with bearer tokens, and route expired sessions back to login.

**Architecture:** Keep authentication authoritative in the existing FastAPI `/auth` endpoints. Add a Flutter auth state controller backed by secure token storage, make `ApiClient` attach bearer tokens and perform one guarded refresh/retry on `401`, and make `go_router` react to auth state. Migrate the settings router from the legacy API-key dependency to the current user dependency and scope settings data to that user.

**Tech Stack:** FastAPI, SQLAlchemy, PyJWT, Flutter, Riverpod, Dio, go_router, flutter_secure_storage, pytest, Flutter widget/unit tests.

---

## Scope and acceptance criteria

- A user can log in from Flutter with email and password.
- Access and refresh tokens are stored outside `SharedPreferences`.
- Documents, labs, ask, review, and settings requests send `Authorization: Bearer <access_token>`.
- A single expired access token triggers refresh-token rotation and one retry of the original request.
- Failed refresh clears local credentials and redirects to `/login`.
- Unauthenticated navigation cannot reach the application shell.
- Authenticated navigation cannot remain on `/login`.
- `/api/v1/settings`, `/api/v1/settings/models`, `/api/v1/settings/test-llm`, and `/api/v1/usage` accept the current user JWT and use that user’s settings/data.
- No production request depends on `X-API-Key`.
- Backend and Flutter tests cover login, refresh, logout, route guards, bearer headers, retry behavior, and the documents/labs regression.

## Task 1: Add secure Flutter token storage

**Files:**
- Modify: `app/pubspec.yaml`
- Create: `app/lib/features/auth/token_storage.dart`
- Test: `app/test/token_storage_test.dart`

**Step 1: Add the dependency**

Add `flutter_secure_storage` to `dependencies`. Do not use `SharedPreferences` for access or refresh tokens; retain `SharedPreferences` only for non-secret UI preferences and caches.

**Step 2: Write storage tests**

Use an injectable storage abstraction so tests can use an in-memory fake. Cover:

- Writing and reading access/refresh tokens.
- Replacing rotated tokens.
- Clearing both tokens.
- Reporting whether a complete session exists.

**Step 3: Implement the storage abstraction**

Expose constants for `access_token` and `refresh_token`, plus `readAccessToken`, `readRefreshToken`, `writeTokens`, and `clear`. Keep platform-specific secure-storage construction inside this class.

**Step 4: Run focused tests**

Run:

```bash
cd app
flutter test test/token_storage_test.dart
```

Expected: all token-storage tests pass.

**Step 5: Commit**

```bash
git add app/pubspec.yaml app/lib/features/auth/token_storage.dart app/test/token_storage_test.dart
git commit -m "feat(app): add secure JWT token storage"
```

## Task 2: Add auth state and login/logout behavior

**Files:**
- Create: `app/lib/features/auth/auth_model.dart`
- Create: `app/lib/features/auth/auth_controller.dart`
- Create: `app/lib/features/auth/login_screen.dart`
- Modify: `app/lib/main.dart`
- Test: `app/test/auth_controller_test.dart`
- Test: `app/test/login_screen_test.dart`

**Step 1: Define auth state**

Represent loading, unauthenticated, authenticated, and error states. The authenticated state should retain the `/auth/me` user payload (`id`, `email`, `display_name`, `is_admin`, `created_at`) so route/UI code does not decode JWT claims.

**Step 2: Write controller tests**

Cover:

- Startup with no stored tokens produces unauthenticated state.
- Startup with stored tokens calls `/auth/me` and produces authenticated state.
- Successful login stores both tokens and loads the current user.
- Invalid credentials remain unauthenticated and expose a user-safe error.
- Logout calls `/auth/logout` when possible and always clears local tokens.

Use a fake API/auth service rather than real network calls.

**Step 3: Implement the controller**

Create `authStateProvider` as a Riverpod notifier. Inject token storage and an auth API service. Keep login/logout orchestration out of widgets. Ensure logout clears tokens even if the network request fails.

**Step 4: Implement the login screen**

Provide email and password fields, submit/loading state, validation, and a visible authentication error. On success, let router refresh from auth state rather than manually pushing the main route.

**Step 5: Wire startup**

Initialize auth state in `main.dart` before rendering protected application routes. Preserve existing `SharedPreferences` provider overrides for cache/UI behavior.

**Step 6: Run focused tests**

```bash
cd app
flutter test test/auth_controller_test.dart test/login_screen_test.dart
```

Expected: all auth controller and login widget tests pass.

**Step 7: Commit**

```bash
git add app/lib/features/auth app/lib/main.dart app/test/auth_controller_test.dart app/test/login_screen_test.dart
git commit -m "feat(app): add JWT login and session state"
```

## Task 3: Replace API-key injection with bearer authentication and refresh

**Files:**
- Modify: `app/lib/core/api_client.dart`
- Modify: `app/lib/features/auth/auth_controller.dart`
- Test: `app/test/api_client_auth_test.dart`

**Step 1: Write interceptor tests**

Cover:

- Requests include `Authorization: Bearer <access_token>`.
- Requests do not include `X-API-Key`.
- A `401` invokes refresh exactly once.
- A successful refresh stores the rotated pair and retries the original request once.
- A failed refresh clears tokens and reports session expiration.
- A retried request cannot recursively trigger another refresh.
- Login and refresh calls themselves bypass the protected-request interceptor.

**Step 2: Implement bearer injection**

Make `ApiClient` depend on token storage and an auth-session callback. Read the current access token for each protected request and attach the bearer header. Keep the API base URL behavior unchanged.

**Step 3: Implement guarded refresh**

Use a separate Dio instance or an explicit bypass flag for `POST /auth/refresh`. Serialize concurrent refreshes so multiple simultaneous `401`s share one refresh operation. Retry each original request at most once.

**Step 4: Remove legacy client API-key state**

Delete `_apiKey`, `setApiKey`, and `apiKey` from `ApiClient` after updating all callers. Do not silently retain the old header as a fallback.

**Step 5: Run focused tests**

```bash
cd app
flutter test test/api_client_auth_test.dart
```

Expected: all header, refresh, retry, and failure-path tests pass.

**Step 6: Commit**

```bash
git add app/lib/core/api_client.dart app/lib/features/auth/auth_controller.dart app/test/api_client_auth_test.dart
git commit -m "feat(app): authenticate API requests with refreshable JWTs"
```

## Task 4: Add router guards and authenticated shell logout

**Files:**
- Modify: `app/lib/features/navigation/app_router.dart`
- Modify: `app/lib/main.dart`
- Modify: the authenticated shell widget in `app/lib/features/navigation/app_router.dart`
- Test: `app/test/app_router_auth_test.dart`

**Step 1: Write route tests**

Cover:

- Unauthenticated `/documents`, `/labs`, `/ask`, and `/settings` redirect to `/login`.
- Unauthenticated users can open `/login`.
- Authenticated users opening `/login` redirect to the application default route.
- The original requested location is preserved as a redirect target where practical.

**Step 2: Make router refresh from auth state**

Provide a `Listenable`/router refresh bridge from the auth notifier. Avoid a static router that captures the initial auth state forever.

**Step 3: Add redirects**

Use `/login` as the public route and preserve the existing authenticated shell/routes. Change the default authenticated landing route from the current settings route to `/documents`.

**Step 4: Add logout action**

Expose logout from the authenticated shell/app navigation UI. After logout, clear state and let the guard redirect to `/login`.

**Step 5: Run focused tests**

```bash
cd app
flutter test test/app_router_auth_test.dart
```

Expected: all guarded-route and logout navigation tests pass.

**Step 6: Commit**

```bash
git add app/lib/features/navigation/app_router.dart app/lib/main.dart app/test/app_router_auth_test.dart
git commit -m "feat(app): guard routes with auth state"
```

## Task 5: Migrate the backend settings endpoints to JWT and user scope

**Files:**
- Modify: `api/app/routers/settings.py`
- Modify: `api/app/services/settings.py`
- Modify: any settings-related model/schema files required by the existing user-settings migration
- Test: `api/tests/test_settings_auth.py`

**Step 1: Write backend regression tests**

Cover:

- JWT-authenticated `GET /api/v1/settings` returns `200`.
- JWT-authenticated settings models/test/usage endpoints do not require `X-API-Key`.
- Missing bearer token returns `401`.
- A guest cannot read or update another user’s settings.
- Existing API-key-only access is rejected or removed according to the final migration contract.

**Step 2: Replace the router dependency**

Remove `dependencies=[Depends(verify_api_key)]` and inject `current_user: User = Depends(get_current_user)` into each settings endpoint. Call `set_rls_user_id(db, current_user.id)` before querying or mutating data.

**Step 3: Scope the settings service**

Update `SettingsService` methods to accept a user ID and query the user’s settings row. Ensure encrypted LLM keys are derived/decrypted for that user only. Usage statistics must filter by `user_id` where the model supports it.

**Step 4: Remove stale API-key assumptions**

Remove settings API-key wording and any backend dependency that is no longer used by production routes. Keep `verify_api_key` only if another explicitly supported compatibility/admin path still requires it; otherwise delete it and its tests.

**Step 5: Run backend tests**

```bash
docker compose exec -T api pytest tests/test_settings_auth.py tests/test_auth_api.py tests/test_user_isolation.py -v
```

Expected: all settings JWT, auth, and isolation tests pass.

**Step 6: Commit**

```bash
git add api/app/routers/settings.py api/app/services/settings.py api/app/models.py api/app/schemas.py api/tests/test_settings_auth.py
git commit -m "fix(api): migrate settings endpoints to user JWT auth"
```

## Task 6: Remove the obsolete Flutter server-key settings UI

**Files:**
- Modify: `app/lib/features/settings/settings_screen.dart`
- Modify: `app/lib/features/settings/settings_controller.dart` only if request/error handling needs adjustment
- Modify: `app/lib/features/settings/settings_model.dart` only if response shape changes
- Test: existing settings/widget tests plus `app/test/settings_auth_test.dart`

**Step 1: Update tests**

Assert that the settings screen does not display “X-API-Key”, “Server Key”, or instructions to reset `change-me`. Add coverage for a `401` session-expired state being handled by the shared auth interceptor rather than rendered as an API-key troubleshooting message.

**Step 2: Remove legacy controls**

Delete the server-key text field, reset button, and `setApiKey` calls. Keep per-user LLM provider/key configuration and usage UI.

**Step 3: Update error presentation**

Use a generic backend/session error message. Do not expose token values or instruct users to enter LLM keys as backend credentials.

**Step 4: Run focused tests**

```bash
cd app
flutter test test/settings_auth_test.dart test/widget_test.dart
```

Expected: settings UI tests pass without legacy API-key text.

**Step 5: Commit**

```bash
git add app/lib/features/settings app/test/settings_auth_test.dart app/test/widget_test.dart
git commit -m "fix(app): remove legacy server-key settings UI"
```

## Task 7: Verify documents and labs regression end to end

**Files:**
- Modify: `app/test/documents_screen_test.dart` only if auth-aware providers are needed
- Modify: `app/test/labs_screen_test.dart` only if auth-aware providers are needed
- Create or modify: `api/tests/test_settings_auth.py` and client integration tests as needed

**Step 1: Run Flutter tests**

```bash
cd app
flutter test
flutter analyze
```

Expected: all widget/unit tests pass and analysis reports zero issues.

**Step 2: Run the backend suite in Docker**

```bash
docker compose up -d --build
docker compose exec -T api pytest -q
```

Expected: the complete backend suite passes.

**Step 3: Run an HTTP smoke flow**

Authenticate as the bootstrap admin, call `/auth/me`, then call:

- `GET /api/v1/documents`
- `GET /api/v1/tests`
- `GET /api/v1/settings`
- `GET /api/v1/usage`

Verify all return `200` with the bearer token, while the same protected calls without a token return `401`.

**Step 4: Verify refresh behavior**

Use a deliberately expired access token with a valid refresh token. Verify the client refreshes, retries the documents/labs requests once, and succeeds. Then revoke/logout the refresh token and verify the client clears credentials and navigates to `/login`.

**Step 5: Build the web client**

```bash
cd app
flutter build web --wasm
```

Expected: the web build completes and the generated app can be served by the API without API-key configuration.

**Step 6: Update verification documentation**

Append the final command results and any remaining limitations to `progress.md`. Update the auth design/spec only if implementation decisions differ from it.

**Step 7: Commit**

```bash
git add app api progress.md
git commit -m "test: verify end-to-end JWT authentication flow"
```

## Final review checklist

- Search for production references to `X-API-Key`, `setApiKey`, `change-me`, `flutter_secure_storage`, `access_token`, and `refresh_token`.
- Confirm no protected Flutter API call bypasses `ApiClient`.
- Confirm all protected backend routers use `get_current_user`.
- Confirm settings data and usage counts are user-scoped.
- Run `git diff --check`.
- Run the complete backend and Flutter verification commands again after the final edits.
