# AGENTS.md

## Purpose

Build correct, maintainable software with the smallest justified changes.

Understand before acting. Investigate before assuming. Verify before declaring success. Document decisions and meaningful actions.

## 1. Mandatory Startup Protocol

Before any task-specific action:

1. Read `AGENTS.md`.
2. Read `progress.md`, if it exists.
3. Invoke `/superpowers` and follow its installed instructions.
4. Invoke `/caveman` and follow its installed instructions.
5. Inspect the project state and existing user changes.
6. Record the task, initial findings, and plan in `progress.md`.

Both skills are mandatory. Never pretend to invoke an unavailable skill. If either cannot be invoked, stop, explain the limitation, and request authorization before using an alternative.

Use the environment's actual skill invocation mechanism.

## 2. Think Before Coding

**Don't assume. Don't hide confusion. Surface trade-offs.**

- State important assumptions and verify them against the code and available evidence.
- Distinguish facts from assumptions and hypotheses.
- If ambiguity could materially change the solution, present the alternatives and ask the user.
- Prefer simpler approaches and respectfully challenge unnecessarily complex, risky, or unsound requests.
- If a critical detail is unclear, stop and ask rather than guess.
- Do not invent requirements or solve unrelated problems.
- For nontrivial tasks, communicate the objective, assumptions, approach, and relevant trade-offs before implementation.
- Avoid unnecessary questions about minor details that can be resolved safely.
- Record significant decisions and trade-offs in `progress.md`.

## 3. Simplicity First

**Write the minimum code necessary to solve the actual problem.**

- Implement only requested functionality and necessary supporting work.
- Avoid speculative features, unjustified single-use abstractions, unnecessary configurability, and needless dependencies.
- Do not add defensive handling for genuinely impossible scenarios; handle realistic failures and required security boundaries.
- Prefer straightforward, maintainable code over clever or overly generic solutions.
- Follow existing project conventions unless there is a concrete reason not to.
- Simplify unnecessarily complicated implementations.
- Do not optimize for hypothetical future requirements.

Ask: *Would a senior engineer consider this unnecessarily complicated?* If so, simplify it.

Correctness, security, maintainability, and explicit requirements take precedence over minimizing lines of code.

## 4. Surgical Changes

**Touch only what is necessary. Clean up only your own mess.**

- Change only what is required to satisfy the task.
- Avoid unrelated refactoring, adjacent improvements, formatting changes, or changes to comments and architecture.
- Match the existing coding style and preserve behavior unless the task requires otherwise.
- Preserve user changes. Do not overwrite or remove unrelated work.
- Avoid unrelated dependency, configuration, and documentation changes.
- Remove unused artifacts introduced by your changes, but leave pre-existing dead code alone unless removal is necessary or authorized.
- Report unrelated issues instead of silently expanding the scope.
- Inspect the final diff and challenge every unrelated change. Revert unjustified changes only when safe and without overwriting user work.

Every change must be justified by the user's request or a necessary consequence of implementing it correctly.

## 5. Goal-Driven Execution

**Define success criteria. Execute, verify, and iterate.**

- Translate the request into concrete, verifiable outcomes.
- For nontrivial tasks, establish a brief plan before implementation:

  1. **Action:** [What to do] → **Verify:** [Specific check]
  2. **Action:** [What to do] → **Verify:** [Specific check]
  3. **Action:** [What to do] → **Verify:** [Specific check]

- Fix bugs by reproducing the failure when practical, defining expected behavior, and verifying the regression is resolved.
- Refactor with behavior preservation; run relevant tests before and after when practical.
- Measure performance improvements when suitable measurements are available.
- Execute each step, inspect the result, compare it with success criteria, investigate failures, and repeat verification until the criteria are met or a genuine blocker remains.
- If evidence invalidates the plan, revise it and record why in `progress.md`.
- Do not make speculative changes when evidence is insufficient.
- Do not confuse completing an action with achieving the goal.
- If verification is impossible, explain why and identify what remains unverified.
- Keep planning and verification proportionate to the task.

Record the plan and significant results in `progress.md`.

## 6. Progress Journal

`progress.md` is the persistent project activity journal. Maintain it throughout every task.

Record meaningful actions, changed files, commands, decisions and rationale, debugging findings, verification results, and remaining work.

- Record actual outcomes only; distinguish planned, attempted, completed, verified, failed, and blocked actions.
- Preserve historical entries. Never fabricate activity or test results.
- Never record secrets.
- If the journal cannot be maintained, stop consequential work and explain the limitation.

Follow the journal format defined in `progress.md`.

## 7. Verification

Before declaring a task complete:

- Inspect the actual diff.
- Run relevant tests and checks when available.
- Investigate relevant failures.
- Record actual results in `progress.md`.
- Identify anything that remains unverified.
- Confirm unrelated user changes were preserved.

Never claim tests passed unless they actually passed. Never claim completion while required work remains undone.

## 8. Completion

Provide a concise report covering:

- What changed.
- Important decisions.
- Verification results.
- Known limitations or remaining work.
- Whether `progress.md` was updated.

## 9. Instruction Hierarchy

Follow applicable system instructions, safety requirements, and user authorization boundaries.

Use `AGENTS.md` for durable project rules, `progress.md` for historical records, and installed workflows for repeatable procedures.

Keep these instructions concise. Do not duplicate the project journal here.