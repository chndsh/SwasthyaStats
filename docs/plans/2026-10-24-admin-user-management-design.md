# Admin User Management and Temporary Password Design

**Date:** 2026-10-24

## Goal

Complete the host onboarding workflow with an admin user-management screen and safe temporary-password handling for newly created and reset accounts.

## Decisions

- Add `users.must_change_password`, defaulting to `false`.
- Admin-created users receive a temporary password and `must_change_password = true`.
- Admin password resets also set `must_change_password = true`.
- A user with this flag can authenticate but cannot enter Documents, Labs, Ask, or Settings until changing the password.
- The user changes the password with the current temporary password plus a new password.
- A successful password change clears the flag.
- Password changes and admin resets invalidate existing refresh tokens for that user.
- Admins cannot delete their own account.
- Only admins can list, create, reset, or delete users.
- Temporary passwords are shown once in the admin UI and are not stored or returned after creation/reset.

## Backend

- Add an Alembic migration for `must_change_password`.
- Extend `/auth/me` user data with the flag.
- Set the flag in user creation and admin password-reset endpoints.
- Add `PUT /auth/me/password` for the authenticated user.
- Validate current password, new-password policy, and confirmation at the API boundary.
- Keep all medical data and settings scoped by `user_id`.

## Flutter

- Add `AdminUsersScreen` for listing, creating, resetting, and deleting users.
- Add `ChangePasswordScreen` for temporary-password onboarding.
- Add `/admin/users` and `/change-password` routes.
- Redirect temporary-password users before the authenticated shell.
- Show the admin route only when `is_admin` is true.
- Require confirmation before destructive actions.
- Display newly generated temporary passwords only in the immediate success dialog.

## Security and errors

- Use Argon2id for every stored password.
- Never log or persist plaintext passwords.
- Return generic login errors.
- Return explicit errors for wrong current password, weak new password, duplicate email, forbidden admin actions, and self-deletion.
- Invalidate refresh tokens after password changes and resets.

## Verification

- Backend tests cover migration state, admin CRUD, password-change success/failure, forced-change flags, token invalidation, and authorization.
- Flutter tests cover state parsing, route redirects, admin visibility, CRUD actions, temporary-password display, and change-password validation.
- Browser smoke covers admin creation, guest forced password change, normal access after change, logout/account switching, and admin reset.
