# Admin User Management and Temporary Passwords Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an admin user-management screen and force newly created or reset users to replace temporary passwords before accessing health data.

**Architecture:** Extend the existing FastAPI JWT auth model with a `must_change_password` flag and a self-service password-change endpoint. Extend the existing Riverpod auth state and go_router guards with temporary-password routing, then add admin CRUD and password-change screens using the shared bearer-authenticated API client.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Argon2id, PyJWT, Flutter, Riverpod, Dio, go_router, Flutter widget tests, Docker Compose.

---

## Acceptance criteria

- Admin can list users, create users, reset passwords, and delete non-self users.
- New and reset passwords are temporary and force a password change.
- Temporary-password users cannot access Documents, Labs, Ask, or Settings.
- Users can change passwords with current-password verification.
- Password changes and resets invalidate refresh tokens for that user.
- Non-admin users cannot call admin APIs or see admin navigation.
- Old passwords fail after password change or reset.
- User data remains isolated.
- Auth, Flutter, Docker, browser smoke, and documentation checks pass.

## Task 1: Add the password-change flag and migration

**Files:**
- Modify: `api/app/models.py`
- Create: `api/alembic/versions/004_password_change_required.py`
- Test: `api/tests/test_password_change_migration.py`

**Steps:**

1. Write a migration test that checks `users.must_change_password` exists, is non-null, and defaults to false.
2. Run the test against the current schema and verify it fails.
3. Add the SQLAlchemy Boolean column with `default=False` and `nullable=False`.
4. Add an Alembic migration that adds the column with a server default, then removes the temporary server default if consistent with repository migration style.
5. Add downgrade support that removes the column.
6. Run the migration test in Docker.
7. Commit:

```bash
git add api/app/models.py api/alembic/versions/004_password_change_required.py api/tests/test_password_change_migration.py
git commit -m "feat(api): track temporary-password accounts"
```

## Task 2: Extend auth API for temporary passwords

**Files:**
- Modify: `api/app/routers/auth.py`
- Modify: `api/app/schemas.py` if shared user schemas are used
- Test: `api/tests/test_auth_api.py`
- Create: `api/tests/test_password_change_api.py`

**Steps:**

1. Add failing tests for:
   - User creation returns `must_change_password = true`.
   - Admin reset sets the flag.
   - Wrong current password returns `401`.
   - Weak new password returns `422` or repository-standard validation status.
   - Successful password change clears the flag.
   - Old password fails after change.
   - Refresh tokens issued before password change are rejected.
   - Non-admin user cannot list/create/reset/delete users.
   - Admin cannot delete self.
2. Run focused tests and verify failure.
3. Add `must_change_password` to `UserRead`.
4. Set the flag on admin-created users and reset passwords.
5. Add `PUT /auth/me/password` accepting `current_password` and `new_password`.
6. Verify the current Argon2id hash, enforce the minimum password policy, replace the hash, clear the flag, and invalidate the user’s refresh-token blocklist entries or introduce a user-session invalidation mechanism consistent with the existing model.
7. Keep login response generic for unknown email and wrong password.
8. Run:

```bash
docker compose exec -T api pytest tests/test_password_change_api.py tests/test_auth_api.py -v
```

9. Commit:

```bash
git add api/app/routers/auth.py api/app/schemas.py api/tests/test_password_change_api.py api/tests/test_auth_api.py
git commit -m "feat(api): enforce temporary password changes"
```

## Task 3: Extend Flutter auth state and route guards

**Files:**
- Modify: `app/lib/features/auth/auth_model.dart`
- Modify: `app/lib/features/auth/auth_controller.dart`
- Modify: `app/lib/features/navigation/app_router.dart`
- Test: `app/test/auth_controller_test.dart`
- Test: `app/test/app_router_auth_test.dart`

**Steps:**

1. Add failing tests for parsing `must_change_password`, redirecting temporary users to `/change-password`, allowing `/change-password`, and redirecting authenticated normal users away from `/login`.
2. Run focused tests and verify failure.
3. Add the field to the auth user model and authenticated state.
4. Add a controller method for changing the current password and refreshing `/auth/me`.
5. Add `/change-password` route.
6. Update redirects so temporary users cannot enter the main shell.
7. Preserve the original requested location and use it after successful password change where practical.
8. Run focused Flutter tests.
9. Commit:

```bash
git add app/lib/features/auth app/lib/features/navigation/app_router.dart app/test/auth_controller_test.dart app/test/app_router_auth_test.dart
git commit -m "feat(app): guard temporary-password sessions"
```

## Task 4: Add change-password screen

**Files:**
- Create: `app/lib/features/auth/change_password_screen.dart`
- Test: `app/test/change_password_screen_test.dart`

**Steps:**

1. Write widget tests for required fields, password confirmation mismatch, weak password validation, loading state, API error display, and successful submission.
2. Run tests and verify failure.
3. Implement current-password, new-password, and confirmation fields.
4. Call the auth controller, show safe errors, and navigate through router state after success.
5. Do not display or log password values.
6. Run:

```bash
cd app
flutter test test/change_password_screen_test.dart
```

7. Commit:

```bash
git add app/lib/features/auth/change_password_screen.dart app/test/change_password_screen_test.dart
git commit -m "feat(app): add forced password change screen"
```

## Task 5: Add admin API client and user-management controller

**Files:**
- Create: `app/lib/features/admin/admin_users_model.dart`
- Create: `app/lib/features/admin/admin_users_controller.dart`
- Test: `app/test/admin_users_controller_test.dart`

**Steps:**

1. Write tests for list, create, reset, delete, duplicate-email errors, and self-delete protection in the UI/controller layer.
2. Run tests and verify failure.
3. Add typed user response and temporary-password response models.
4. Add controller methods for:
   - `GET /auth/users`
   - `POST /auth/users`
   - `PUT /auth/users/{id}/password`
   - `DELETE /auth/users/{id}`
5. Keep temporary passwords in transient state only.
6. Run focused tests.
7. Commit:

```bash
git add app/lib/features/admin app/test/admin_users_controller_test.dart
git commit -m "feat(app): add admin user-management controller"
```

## Task 6: Build admin user-management screen

**Files:**
- Create: `app/lib/features/admin/admin_users_screen.dart`
- Modify: `app/lib/features/navigation/app_router.dart`
- Modify: authenticated shell navigation in `app/lib/features/navigation/app_router.dart`
- Test: `app/test/admin_users_screen_test.dart`

**Steps:**

1. Write widget tests for admin-only visibility, user list rendering, create dialog, temporary-password success dialog, reset confirmation, delete confirmation, and blocked self-delete.
2. Run tests and verify failure.
3. Implement responsive admin screen matching existing app styling.
4. Add create-user form with email, display name, and temporary password.
5. Add reset-password action that displays the generated temporary password once.
6. Add delete confirmation and disable/delete-block the current admin account.
7. Add admin navigation entry only for authenticated users with `is_admin`.
8. Add loading, empty, success, and error states.
9. Run focused tests and analyzer.
10. Commit:

```bash
git add app/lib/features/admin app/lib/features/navigation/app_router.dart app/test/admin_users_screen_test.dart
git commit -m "feat(app): add admin user-management screen"
```

## Task 7: Add backend and Flutter integration coverage

**Files:**
- Modify: `api/tests/test_user_isolation.py`
- Create: `api/tests/test_admin_user_management.py`
- Modify: `app/test/auth_controller_test.dart`
- Create: `app/test/admin_onboarding_flow_test.dart`

**Steps:**

1. Add the complete flow tests:
   - Admin creates guest.
   - Guest logs in with temporary password.
   - Guest is forced to change password.
   - Guest changes password.
   - Old password fails.
   - Guest accesses documents and labs.
   - Admin resets guest password.
   - Guest is forced to change password again.
2. Run focused backend and Flutter tests.
3. Fix only failures caused by this feature.
4. Commit:

```bash
git add api/tests app/test
git commit -m "test: cover admin onboarding and password lifecycle"
```

## Task 8: Update documentation and verification log

**Files:**
- Modify: `docs/superpowers/specs/2026-10-23-auth-multi-user-design.md`
- Modify: `progress.md`
- Modify: `app/README.md` or deployment documentation if setup instructions live elsewhere
- Add: `docs/plans/2026-10-24-admin-user-management-design.md`

**Steps:**

1. Document admin bootstrap from `ADMIN_EMAIL` and `ADMIN_PASSWORD`.
2. Document admin user creation and temporary-password onboarding.
3. Document forced password changes after creation and reset.
4. Document admin-only operations and self-delete protection.
5. Document browser smoke steps and the security limitation that temporary passwords must be delivered securely.
6. Record test results in `progress.md`.
7. Run `git diff --check`.
8. Commit:

```bash
git add docs progress.md app/README.md
git commit -m "docs: document admin onboarding and password lifecycle"
```

## Task 9: Full verification

**Commands:**

```bash
docker compose up -d --build
docker compose exec -T api pytest -q

cd app
flutter test
flutter analyze
flutter build web --wasm
```

Run browser smoke:

1. Log in as admin.
2. Open Admin Users.
3. Create guest and copy temporary password securely.
4. Log out.
5. Log in as guest.
6. Confirm redirect to Change Password.
7. Change password.
8. Confirm Documents and Labs load.
9. Confirm guest cannot open Admin Users.
10. Log in as admin and reset guest password.
11. Confirm guest must change password again.
12. Confirm old guest password fails.
13. Confirm deleting another user works and deleting self is blocked.

Expected:

- Backend tests pass.
- Flutter tests pass.
- Analyzer reports zero issues.
- Web build succeeds.
- Browser flow has no `401` caused by missing bearer authentication.

## Final review

- Search production code for stale `X-API-Key`, `setApiKey`, and server-key UI.
- Confirm plaintext passwords never enter logs, persistent storage, or analytics.
- Confirm temporary passwords are not returned by list endpoints.
- Confirm reset invalidates existing refresh tokens.
- Confirm user medical data remains user-scoped.
- Run `git status --short` and `git diff --check`.
