---
name: start-task
description: Start a coding task using the project's mandatory startup protocol, required skills, progress journal, goal-driven plan, and verification loop. Use before beginning any new coding task.
---

# Start Task

Prepare and execute the user's task according to the project's `AGENTS.md`.

## Phase 1: Mandatory startup

Before any task-specific action:

1. Read the project's `AGENTS.md`.
2. Read `progress.md` if it exists.
3. Invoke `/superpowers` and follow its actual installed instructions.
4. Invoke `/caveman` and follow its actual installed instructions.

Both skills are mandatory. Do not pretend to invoke them, simulate their execution, or silently skip them.

If either skill is unavailable or cannot be invoked:
- Stop before performing task-specific work.
- Explain which skill is unavailable and why.
- Ask the user for authorization before substituting an alternative.

Use the actual skill invocation mechanism supported by Antigravity.

## Phase 2: Inspect and record

After both skills have been invoked successfully:

1. Inspect the repository structure and relevant files.
2. Inspect Git status and existing user changes, if Git is available.
3. Understand the requested outcome and identify important assumptions.
4. Check `progress.md` for unfinished work or relevant history.
5. If `progress.md` does not exist, create it.
6. Record the task, initial findings, assumptions, and plan.

Never overwrite historical journal entries or unrelated user changes.

## Phase 3: Define success

Translate the request into concrete, verifiable acceptance criteria.

For nontrivial tasks, create a concise plan using:

1. Action → verify: specific check.
2. Action → verify: specific check.
3. Action → verify: specific check.

Identify relevant tests and checks before implementation when practical.

If critical requirements are ambiguous, ask the user before proceeding.

## Phase 4: Implement

Follow `AGENTS.md` and the instructions of both required skills.

- Prefer the simplest correct solution.
- Make only changes necessary for the task.
- Preserve existing user work.
- Avoid speculative features and unrelated refactoring.
- Record meaningful actions, decisions, commands, and findings in `progress.md`.

For each planned step:

1. Perform the action.
2. Inspect the result.
3. Compare it with the acceptance criteria.
4. Investigate failures or unexpected behavior.
5. Correct problems and repeat verification as needed.

## Phase 5: Verify and finish

Before declaring completion:

1. Inspect the final diff.
2. Run relevant tests and checks when available.
3. Investigate failures and unexpected results.
4. Confirm unrelated user changes were preserved.
5. Update `progress.md` with actual outcomes, verification results, and remaining work.

Never claim a test passed unless it actually passed.

If verification is blocked or incomplete, state that explicitly.

Finish with a concise report covering:
- Changes made.
- Important decisions.
- Verification performed and actual results.
- Known limitations or remaining work.
- Whether `progress.md` was updated.

For trivial tasks, keep planning and verification proportionate.
