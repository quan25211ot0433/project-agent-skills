---
name: next-step
description: "Use when invoking /next-step, $next-step, or nextStep, or to execute pending next steps and required follow-ups from session context."
metadata:
  version: "1.0.0"
---

# Next Step (`next-step`)

Advance pending session work across a bounded **2-pass sequential loop** (`MAX_PASSES = 2` default), re-evaluating live state after Pass 1 so Pass 2 executes newly unlocked follow-ups without mid-loop pauses.

## 1. Loop Budget and Focus

- **Budget:** `MAX_PASSES = 2` default; override if positive integer `N` supplied (e.g. `/next-step 3`).
- **Focus:** Restrict candidate selection to matching keywords if supplied (e.g. `/next-step tests`).

## 2. Per-Pass Loop (`k = 1 .. MAX_PASSES`)

Derive ready work from fresh session state at pass start:

1. **Extract candidates (priority order):**
   - Explicit `Next steps`, `Required follow-up`, or audit items from latest output (required before optional; exclude completed).
   - Unchecked ready items in active checklist/plan phase with met prerequisites.
   - Immediate unfinished signals (failing test/lint or partial edits).
2. **Early-exit checks before mutating:**
   - `NO_REMAINING_STEPS`: No actionable items remain -> stop cleanly. **Zero filler edits or cosmetic churn to consume passes.**
   - `NEEDS_DECISION`: Items depend on an undiscoverable decision -> stop and ask one focused question.
   - `BOUNDARY_REACHED`: Only unapproved external actions remain (Section 3) -> stop and report required authorization. If authorized local work coexists with unapproved external actions, run local work and defer external ones.
3. **Execute one coherent unit:**
   - Run highest-priority ready step following repository instructions (`AGENTS.md`, delivery guide, TDD).
4. **Mandatory verification barrier:**
   - Run narrowest proving check(s) for pass changes.
   - **Recurrence stop:** On failure, attempt **at most ONE cause-aligned repair** in Pass `k` and re-verify. If failure persists, halt loop immediately (`BLOCKED`). Never burn Pass `k+1` retrying broken state.
5. **Emit receipt and auto-continue:**
   - Output inline receipt:
     `Pass k/MAX_PASSES: <executed> | Verified: <command -> result> | Next: <continuing to Pass k+1 | stop reason>`
   - When `k < MAX_PASSES` and ready work remains, **continue immediately to Pass k+1 in same turn**. Do not pause after Pass 1 to ask.

## 3. Authorization Boundaries

- **Autonomous:** Read-only inspection, local edits in task scope, local builds/tests/linters, checklist updates.
- **Requires explicit session authorization:** `git push`, `gh pr create/merge`, releases, tickets, local `git commit` (unless pre-authorized), destructive commands, or reversing user choices. A report's Next steps list is candidate work, not publication authority.

## 4. Final Loop Summary

After completion or early exit, emit:
- **Passes completed:** `<ran>/<MAX_PASSES>` (`COMPLETED_BUDGET` | `NO_REMAINING_STEPS` | `BOUNDARY_REACHED` | `BLOCKED` | `NEEDS_DECISION`)
- **Pass receipts:** Bullet per executed pass with modified paths and verification result.
- **Remaining next steps:** Remaining items with authorization prerequisites, or `None`.

## Red Flags

- *Pausing after Pass 1:* Run Pass 2 in same turn when budget and work remain.
- *Pushing from report list:* Stop at `BOUNDARY_REACHED`.
- *Inventing filler edits:* Exit early with `NO_REMAINING_STEPS`.
- *Retrying broken tests on Pass 2:* Max 1 repair; halt with `BLOCKED` on recurrence.
