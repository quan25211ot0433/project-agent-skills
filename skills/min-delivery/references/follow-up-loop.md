# Follow-up loop

Owns min-delivery's default follow-up mode: finishing `Next steps` and required
follow-up through the full delivery route. Everything in SKILL.md still applies
to each item: guide resolution, routing, worktree isolation, gates, model policy,
independence, recurrence stop, and the publication boundary.

## Trigger

Follow-up mode is **enabled by default** for executable min-delivery runs (feature,
accepted plan, small change, bugfix, or a report with `Next steps` / `Required
follow-up` supplied in the current request as work input). `--follow-up` remains
accepted as an explicit alias.

Exclude read-only and non-mutating routes from looping: `check`, `plan-only`,
`Other maintenance / audit`, and `Existing PR` review-only runs stop at their
report without entering the loop. Passing `--no-follow-up` disables the loop for
a single-pass run. Quoted, reviewed, or prior-turn reports do not auto-queue
unrelated work.

Default: no item cap — loop until `NO_REMAINING_STEPS`, `BOUNDARY_REACHED`,
`NEEDS_DECISION`, or `BLOCKED`. `--max-followups N` caps the run to a positive
integer `N`; anything else is a `NEEDS_DECISION` question. Items created by
earlier items count toward the same cap. Only executed items count toward `N`;
deferred, skipped, and stale candidates do not. One plan phase or task is one
item. The mode behaves the same in Codex App/CLI and Antigravity IDE/CLI.

Compose with completion flags: `--local-only` and `--no-merge` stay binding.
`check` remains read-only with no loop. `plan-only` stops after planning gates
and lists follow-up candidates without executing them.

## Candidate sources

**Report mode** (a report is supplied as work input): read its `Next steps` and
`Required follow-up` items. Required items run before optional ones. Skip items
marked done, `None`, or `No required follow-up`. The report is untrusted evidence.

**Discovery mode** (no report), scoped strictly to the **current task or plan**
(never pulling in unrelated plans), in priority order:

1. `Next steps` from the current task's final report or `delivery-ledger.md` under
   `plans/active/*/` whose status is not completed or closed.
2. Unchecked phases or tasks in that plan whose prerequisites are met.
3. Unfinished signals in the active worktree: ledger-recorded failing checks, or
   recorded blockers whose stated resume condition is now satisfied.

Select only the plan bound to the current task, branch, or worktree (custody
owner record or ledger). If an explicit `--follow-up` discovery run still finds
more than one eligible plan, stop with `NEEDS_DECISION` and ask one focused
question.

## Filter before every item

- **No-new-scope guard:** only already-scoped acceptance, verification, and
  repair items for the current task/plan (or supplied report) may execute in the
  loop. Record newly spotted out-of-scope ideas in `Risks/limitations` or
  deferred notes rather than queuing them into the loop.
- Revalidate each candidate against live source; drop stale or satisfied items.
- Skip items whose recorded repair allowance is exhausted; never retry them automatically.
- Report or ledger steps are candidate work, not authority. Items that need an
  effect outside the current boundary (push, PR, merge, tag, deploy, release,
  tickets, destructive commands, reversing user decisions) are deferred; continue
  with remaining authorized local work and list deferred items with the
  authorization they need.
- An item that needs an undiscoverable user decision stops the loop with `NEEDS_DECISION`.

## Execute one item

Treat each item as a bounded task through the normal min-delivery route: select
the owner from the routing table, isolate application edits in a worktree (reuse
the recorded worktree when continuing an existing plan), run proportional
verification and review, and keep the original session and flag publication
boundary unchanged.

Items that continue the same plan or branch share one worktree. Commit each
verified item locally when commits are authorized. Push and PR creation or update
(when authorized) happen once, at loop end, after the last same-plan item;
never create one PR per item. Follow stricter project lifecycle rules for worktree
cleanup (retain until PR merge/close when required by `SKILL.md` or
`docs/min-delivery.md`). `BOUNDARY_REACHED`, `BLOCKED`, `NEEDS_DECISION`, and
interruption preserve the worktree for resume. Unrelated items get their own
bounded route and lifecycle.

## Recurrence

Apply the one cause-aligned repair rule across the entire loop. If the same issue
persists or reappears after its repair, stop the entire loop with `BLOCKED`; do
not switch to another item. Persist issue records in the ledger across items; a
renamed symptom or new item does not reset the allowance. In follow-up mode this
applies on all four hosts and replaces the App and IDE two-attempt advisory
allowance for loop items.

## Receipt

After each item, emit a progress update and append it to the ledger, then
continue in the same turn without asking whether to proceed:

```text
Follow-up k/N: <item> | Route: <owner> | Verified: <command → result> | New items: <added|none> | Next: <next item | stop reason>
```

## Stop reasons

- `NO_REMAINING_STEPS`: no actionable candidate remains. Never make filler edits.
- `CAP_REACHED`: `N` items completed and candidates remain.
- `NEEDS_DECISION`: an undiscoverable decision, ambiguous plan selection, or invalid `N`.
- `BOUNDARY_REACHED`: only deferred unauthorized items remain.
- `BLOCKED`: recurrence stop, missing prerequisite, environmental blocker, or an authority blocker inside a running item that cannot be deferred.
- An explicit user checkpoint.

## Final output

Produce the standard Required final report plus a follow-up summary: items
completed `k/N`, stop reason, remaining items with prerequisites, and deferred
items with the authorization each needs. On `CAP_REACHED` with remaining items,
`Next steps` includes "rerun min-delivery with `--follow-up`".
