# Repository delivery guide

This guide applies to the active `project-agent-skills` checkout. Resolve its
root with `git rev-parse --show-toplevel` and read any applicable repository
instructions before changing files. The installed min-delivery skill owns
workflow routing, model policy, independent review and publication boundaries.
This guide supplies project checks; it grants no commit, push, merge, deployment
or resource-removal authority.

## Requirements and local verification

Use Git and Python 3 standard library on macOS or Linux. The installer uses
POSIX `flock`; CI deliberately tests Python 3.13 on both platforms. No dependency
installation, application server or browser is needed for the repository gate.
From the active checkout root, run:

```bash
python3 -B scripts/check.py
```

The [runner](../scripts/check.py) parses repository Python syntax in memory, then
executes its explicit required unittest inventory in separate processes. Every
required suite must succeed and execute at least one test (`total - skipped >
0`); a missing, empty, failing or all-skipped suite fails the gate. It reports
per-suite and aggregate total, skipped and executed counts and writes no Python
bytecode. Run a touched suite directly first, then the complete gate before
publication. Add new required suites to the runner inventory and its coverage
test. Preserve the installer API and receipt compatibility covered by these tests.

Skill instructions also require native behavioral evaluation appropriate to the
changed guidance. Record actual runtime/tool choices and protected-state proof;
ordinary structural tests and CI do not emulate or certify agent behavior.
Follow the loaded owning skill's validation requirements. Keep filesystem
installation integrity, fresh-session runtime discovery and behavioral
qualification as separate evidence; unknown runtime capability is not a pass.

Review the full change inventory, including committed changes since the review
base, staged/unstaged changes, new files and task-owned ignored payloads. Check
links and bundled resources after documentation/skill edits. Refresh owning
bundle manifests and source provenance when covered payloads change, preserving
origin evidence. Run `git diff --check` before commit. No Inailso package,
GitNexus, custody or plan-closure command is a gate in this repository merely
because another project's guide uses it.

## CI and revision proof

[CI](../.github/workflows/ci.yml) runs for pull requests targeting `main`, pushes
to `main` and manual dispatch, without path filters. The `check (ubuntu-24.04)`
and `check (macos-15)` matrix jobs run the same local gate with Python 3.13,
full Git history and environment/HEAD evidence. They use read-only contents
permission and no persisted checkout credentials, secrets, dependency installs,
caches or deployment steps. Each job has a 15-minute timeout; matrix failures do
not cancel the other platform.

Before an authorized merge, inspect actual workflow applicability and both
completed successful jobs for the current PR head and base. If the forge tests a
synthetic merge commit, bind that commit to the exact head/base pair. Zero jobs,
queued/skipped/cancelled/failed jobs and stale revisions do not satisfy the gate.
A workflow absent from the default branch first needs a PR update/push trigger;
manual dispatch alone cannot bootstrap it. Missing hosted capacity blocks this
gate and does not authorize runner administration or alternate credentials.

Recheck head/base and merge readiness immediately before an authorized merge,
using the forge's exact-head guard. After merge, fetch `main`, prove integration
of the reviewed result (or exact forge squash proof), and require successful
checks on the actual integrated `main` SHA. PR-only checks do not replace
post-merge evidence. Use a separately owned verification checkout when required
by the shipping owner; preserve any pre-existing checkout. Deployment is a
separate authorized operation and is not part of this repository CI.

## Worktree custody and closure

Use an isolated named branch/worktree for implementation unless the authorized
workflow already supplies one or explicitly permits in-place work. Before
creating a checkout, record its intended absent path, source/base SHA and task
ownership. Reuse a recorded existing worktree rather than replacing it. There is
no project-specific custody utility here; record ownership and process evidence
in the task's existing execution contract/ledger using real Git state.

Before removing any resource, follow the loaded cleanup owner and applicable
project rules. Prove ownership, integration and exact current ref identity;
inspect tracked, staged, untracked, ignored and hidden-index state with the
bundled preservation preflight. Its success alone grants no deletion authority.
Keep unknown or changed state and stop processes only when their task ownership
is established. Never force worktree removal, erase preserved edits or delete a
pre-existing checkout as routine teardown. Retain branches unless their deletion
is independently authorized and proven safe.

Close a task only after acceptance, tests, independent review where required and
the authorized publication endpoint have matching receipts. Record exact tested
revision/diff, commands/counts, CI identities, integration proof, retained or
removed owned resources, and unresolved limits in the existing task record.
This repository has no required close-plan script. Use ordinary project records
rather than borrowing another project's utility. On uncertain ownership, failed
checks or missing authority, preserve the work and state the concrete resume
prerequisite. After merge, corrections use reviewed fix/revert PRs rather than
rewriting the integrated branch.
