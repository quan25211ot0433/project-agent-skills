---
name: clean-worktree
description: "Use when retiring, consolidating, or cleaning up secondary Git worktrees and branches in the Inailso monorepo (cleanWorkTree / clean-worktree), or when active feature, bugfix, or detached worktrees have accumulated and workspace checkouts need to be landed and reclaimed safely."
user-invocable: true
argument-hint: "[<worktree-path | branch-name> ... | --all] [--dry-run] [--no-merge | --local-only] [--quarantine --reason \"<text>\"] [--superseded-by=<#PR>]"
---

# Merge Secondary Worktrees to `main` & Delete Them (`clean-worktree` / `cleanWorkTree`)

This bundle is adapted for Inailso only. Before activation in another project,
adapt its commands, CI, custody and merge-proof contracts. Resolve
`docs/min-delivery.md` from the active Git root (`git rev-parse --show-toplevel`)
and require that guide plus every referenced project script before execution.
The [original Inailso guide](https://github.com/quan25211ot0433/monorepoInailsokit/blob/main/docs/min-delivery.md)
is reference only and does not supply the active project's authority.
Read the [active project contract](../ship-to-main/references/project-contract.md) first.

Before any checkout removal, run from the active Git root:
`python3 .agents/skills/min-delivery/scripts/worktree-preflight.py --worktree "<wt-path>"`.
Nonzero means preserve the target, including ignored state. Success is only a
read-only state check: separately require custody, exact task ownership, idle
processes, branch/merge proof and removal authority. Unknown ignored files block
removal. Classify owned disposable artifacts individually before any authorized
handling; broad ignore patterns and retained branches do not preserve file bytes.


Retire secondary Git worktrees without losing a single commit or dirty edit by classifying every worktree against `origin/main`, shipping unmerged or dirty worktrees sequentially through **`ship-to-main`**, and removing a worktree and its branch **only** when programmatic `--require-merged` verification proves containment in `origin/main` (or when an operator explicitly authorizes target-scoped `--superseded-by=<#PR>` or `--quarantine --reason "<text>"` archival).

**Core principle:** `pnpm worktree:clean` without `--require-merged` is a local backup-and-prune utility, **never** a substitute for landing work on `origin/main`. Every unmerged commit or non-scratch edit in a target secondary worktree must complete **`ship-to-main` Phase 1 (Stages 1–5) AND Phase 2 (Stage 6)** before deletion, while the primary root checkout (`<primary-checkout>`) and protected branches (`main`, `master`, `HEAD`, `release/*`) remain untouched. Time urgency, disk pressure, or WIP backup refs never permit deleting an unmerged worktree directory. **Violating the letter of these rules is violating the spirit of these rules.**

## Authority & Completion Flags (`docs/min-delivery.md`)

All operations adhere to the monotonic authority ladder defined in `docs/min-delivery.md`:
`local-edit < commit < push+PR < merge < deploy`. Lower tiers cannot authorize higher tiers.

- **`--dry-run`:** Run **Phase 1** read-only classification (`git fetch origin main` + `pnpm worktree:clean --classify --json`) and open-handle checks, print the per-worktree disposition plan, and stop with zero mutations.
- **`--local-only`:** Execute `ship-to-main` `--local-only` (Stages 1–2 locally; no remote fetch, push, PR, merge, or Stage 6). **Never delete** any worktree or directory under `--local-only` (not even via raw `git worktree remove`).
- **`--no-merge` (or merge unauthorized):** Execute `ship-to-main` `--no-merge` (Stages 1–4 open PR with green PR CI on `HEAD_SHA`) for unmerged targets, stop after Stage 4, and **preserve `<wt-path>` on disk** for PR review/iteration — **never** run directory-only `git worktree remove` on an open-PR or unmerged worktree even if asked to clean up the directory once PR CI turns green; report the `--no-merge` preservation boundary explicitly. Only targets already classified `ALREADY_MERGED_CLEAN` against `origin/main` may be deleted via `--require-merged`.
- **Authorized merge (default `/clean-worktree` when asked to merge worktrees to `main` and delete them):** Execute **Phases 1 → 4** sequentially. Never bypass `pnpm worktree:clean --classify --json` -> `ship-to-main` Stages 1–6 -> `--require-merged` under time or disk-full pressure.

```dot
digraph clean_worktree {
    rankdir=TB;
    "Phase 1: git fetch origin main + pnpm worktree:clean --classify --json" [shape=box];
    "Open handles / live foreign custody or SKIP_VERIFY_WORKTREE?" [shape=diamond];
    "Preserve worktree & report owner/skip" [shape=octagon];
    "--dry-run?" [shape=diamond];
    "Emit classification table & stop (0 mutations)" [shape=doublecircle];
    "Batch-Reclaim All ALREADY_MERGED_CLEAN Worktrees First (--local-only skips)" [shape=box];
    "Any NEEDS_SHIP_TO_MAIN / MERGED_HEAD_DIRTY_WORKTREE targets left?" [shape=diamond];
    "--local-only or --no-merge?" [shape=diamond];
    "Stop at authorized ship-to-main stage; preserve <wt> on disk" [shape=doublecircle];
    "Detached HEAD with unmerged work?" [shape=diamond];
    "Attach branch: git -C <wt> checkout -b <type>/worktree-<slug>" [shape=box];
    "Phase 2: Sequential ship-to-main (Stages 1-5 Squash Merge + Stage 6 Clean Sibling origin/main CI)" [shape=box];
    "Stage 6 origin/main clean?" [shape=diamond];
    "Phase 3: git fetch origin main + pnpm worktree:clean --require-merged --target=<wt> --delete-remote-branch --json" [shape=box];
    "More NEEDS_SHIP_TO_MAIN targets in queue?" [shape=diamond];
    "Phase 4: Verify git worktree list + manage.sh status & emit Receipt Table" [shape=doublecircle];

    "Phase 1: git fetch origin main + pnpm worktree:clean --classify --json" -> "Open handles / live foreign custody or SKIP_VERIFY_WORKTREE?";
    "Open handles / live foreign custody or SKIP_VERIFY_WORKTREE?" -> "Preserve worktree & report owner/skip" [label="yes (exclude from active batch)"];
    "Open handles / live foreign custody or SKIP_VERIFY_WORKTREE?" -> "--dry-run?" [label="eligible targets"];
    "--dry-run?" -> "Emit classification table & stop (0 mutations)" [label="yes"];
    "--dry-run?" -> "Batch-Reclaim All ALREADY_MERGED_CLEAN Worktrees First (--local-only skips)" [label="no"];
    "Batch-Reclaim All ALREADY_MERGED_CLEAN Worktrees First (--local-only skips)" -> "Any NEEDS_SHIP_TO_MAIN / MERGED_HEAD_DIRTY_WORKTREE targets left?";
    "Any NEEDS_SHIP_TO_MAIN / MERGED_HEAD_DIRTY_WORKTREE targets left?" -> "Phase 4: Verify git worktree list + manage.sh status & emit Receipt Table" [label="no"];
    "Any NEEDS_SHIP_TO_MAIN / MERGED_HEAD_DIRTY_WORKTREE targets left?" -> "Detached HEAD with unmerged work?" [label="yes"];
    "Detached HEAD with unmerged work?" -> "Attach branch: git -C <wt> checkout -b <type>/worktree-<slug>" [label="yes"];
    "Detached HEAD with unmerged work?" -> "--local-only or --no-merge?" [label="no"];
    "Attach branch: git -C <wt> checkout -b <type>/worktree-<slug>" -> "--local-only or --no-merge?";
    "--local-only or --no-merge?" -> "Stop at authorized ship-to-main stage; preserve <wt> on disk" [label="yes (Stages 1-2 or 1-4)"];
    "--local-only or --no-merge?" -> "Phase 2: Sequential ship-to-main (Stages 1-5 Squash Merge + Stage 6 Clean Sibling origin/main CI)" [label="no (merge authorized)"];
    "Phase 2: Sequential ship-to-main (Stages 1-5 Squash Merge + Stage 6 Clean Sibling origin/main CI)" -> "Stage 6 origin/main clean?";
    "Stage 6 origin/main clean?" -> "Preserve worktree & report owner/skip" [label="no / disk-or-CI blocked"];
    "Stage 6 origin/main clean?" -> "Phase 3: git fetch origin main + pnpm worktree:clean --require-merged --target=<wt> --delete-remote-branch --json" [label="yes"];
    "Phase 3: git fetch origin main + pnpm worktree:clean --require-merged --target=<wt> --delete-remote-branch --json" -> "More NEEDS_SHIP_TO_MAIN targets in queue?";
    "More NEEDS_SHIP_TO_MAIN targets in queue?" -> "Detached HEAD with unmerged work?" [label="yes (next unmerged target)"];
    "More NEEDS_SHIP_TO_MAIN targets in queue?" -> "Phase 4: Verify git worktree list + manage.sh status & emit Receipt Table" [label="no"];
}
```

## Phase 1: Preflight, Process Check & Worktree Classification

1. **Environment & Primary Root Protection:**
   - Use the active project `.nvmrc` Node version and `package.json` package manager; verify both before running gates.
   - **Never** run `git checkout`, `git pull`, `git reset`, or `git clean` in the primary root checkout (`<primary-checkout>`).
2. **Refresh `origin/main` & Classify Targets:**
   - Unless `--local-only` is active, run `git fetch origin main`.
   - Always run `pnpm worktree:clean --classify --json` (add `--target="<wt>"` when cleaning specific worktrees).
   - Inspect each target's returned `disposition`:
     - `SKIP_VERIFY_WORKTREE`: Active `ship-to-main` Stage 6 sibling worktree (`--role stage6-verify` or `<owned-sibling-verification-path>`) — skip while Stage 6 owns it.
     - `ACTIVE_FOREIGN_CUSTODY` / `MALFORMED_CUSTODY`: Live foreign Codex/Antigravity/Orca session or malformed `.worktree-owner.json` (`canDeleteNow: false`) — preserve `<wt-path>` and coordinate handoff.
     - `ALREADY_MERGED_CLEAN`: Working tree is clean (aside from allowlisted ephemeral caches/verification outputs) and `HEAD` is `MERGED_ANCESTOR` or `MERGED_SQUASH` in `origin/main` — retire upfront in Step 4 (**Phase 3**).
     - `MERGED_HEAD_DIRTY_WORKTREE`: `HEAD` is already merged, but uncommitted/untracked or non-allowlisted ignored files exist — inventory every path, preserve unknown or foreign state, and re-run `pnpm worktree:clean --classify --target="<wt>" --json`. If real edits remain, ship via `NEEDS_SHIP_TO_MAIN` (or use operator-authorized `--quarantine --reason "<text>"`).
     - `NEEDS_SHIP_TO_MAIN`: Contains unmerged commits (`UNMERGED` or `SUPERSEDED_UNVERIFIED`) and/or real uncommitted changes.
3. **Open-Handle & Live-Process Check:**
   - Before mutating or removing `<wt-path>`, check `lsof +D "<wt-path>" 2>/dev/null || true` and running command lines (`ps aux | grep -F "<wt-path>"`).
   - Stop only clearly owned stale dev/test watchers via `SIGTERM`; if another active agent, IDE, or user terminal owns `<wt-path>`, **preserve `<wt-path>` and ask the user**.
4. **Batch-Reclaim All `ALREADY_MERGED_CLEAN` Worktrees First:**
   - Unless `--dry-run` or `--local-only` is active, immediately retire **every** eligible `ALREADY_MERGED_CLEAN` target through **Phase 3** (`worktree-preflight.py` + `pnpm worktree:clean --require-merged --target="<wt-path>" --delete-remote-branch --json`) **before** starting **Phase 2** on any `NEEDS_SHIP_TO_MAIN` target. Reclaiming already-merged checkouts upfront frees disk space before Stage 6 `$VERIFY_WT` `pnpm install --frozen-lockfile` runs and avoids stranding clean merged worktrees behind a long `ship-to-main` queue.

## Phase 2: Sequential Merge to `main` via `ship-to-main`

For each `NEEDS_SHIP_TO_MAIN` worktree, execute **strictly sequentially** (complete Target `N` through Stage 6 and Phase 3 deletion before starting Target `N+1`):

1. **Attach a Branch When Detached `HEAD` Holds Unmerged Work:**
   - If `isDetached === true`, create a descriptive branch inside the worktree before shipping:
     ```bash
     git -C "<wt-path>" checkout -b "chore/worktree-<slug>"
     ```
2. **Execute Full Two-Phase Shipping (**REQUIRED SUB-SKILL:** `ship-to-main`):**
   - Run `ship-to-main` **Phase 1 (Stages 1–5):** Diff Audit & `origin/main` reconciliation (including committing real uncommitted edits cleanly with cause-aligned tests) → Whole-Diff Review → `pr-body-contract.cjs` PR → Persistent Self-Hosted Runner CI (`scripts/ci/self-hosted-runner/manage.sh status` showing `inailso-ci-linux` and `inailso-ci-mac` `online`) → Squash Merge (`gh pr merge --squash`), keeping `<wt-path>` intact across Stage 5.
   - Run `ship-to-main` **Phase 2 (Stage 6):** Fetch `origin/main` into the recorded fresh owned sibling verification path (`--role stage6-verify`), run `pnpm -C "$VERIFY_WT" install --frozen-lockfile`, execute touched local contract/workspace gates + integrated `main` GitHub CI across `$BASE_MAIN_SHA..$MAIN_SHA`, and ship any required `fix/post-merge-...` PR within the recurrence cap.
   - **Blocker & Disk-Pressure Rule:** If `ship-to-main` stops on a conflict, runner-authority prerequisite, insufficient disk space during Stage 6 `pnpm -C "$VERIFY_WT" install --frozen-lockfile`, Stage 6 recurrence cap, or `--no-merge`/`--local-only` stop boundary, **stop and preserve `<wt-path>` and its branch intact on disk** and record the blocker receipt — never pin WIP branches/backup refs and run raw `git worktree remove` on unmerged checkouts.

## Phase 3: Merge-Verified Non-Force Retirement & Quarantine/Superseded Escape Hatches

Only after `<wt-path>` is `ALREADY_MERGED_CLEAN` (in Phase 1 Step 4 upfront batch reclamation or following Phase 2 Stage 6 completion), always delete via `--require-merged` and `--delete-remote-branch` (never omit `--require-merged`, never run raw `git worktree remove --force` / `git branch -D`, and never run unleased `git push origin --delete <branch>`):

```bash
python3 .agents/skills/min-delivery/scripts/worktree-preflight.py --worktree "<wt-path>"
# Stop and preserve on nonzero; separately verify ownership, idle processes and merge authority.
git fetch origin main
pnpm worktree:clean --require-merged --target="<wt-path>" --delete-remote-branch --json
```

- `--require-merged` fails closed with exit code `5` (`UNMERGED_WORKTREE`) if `<wt-path>` is dirty, `UNMERGED`, or `SUPERSEDED_UNVERIFIED` (PR title mention without merge proof).
- On exit `0`, it records a zero-OID CAS `refs/cleanworktree-backups/<branch>-<timestamp>` safety ref, purges only allowlisted disposable caches/outputs (`node_modules`, `.turbo`, `.gitnexus`, `.next`, `.next-build`, `.next-dev`, `dist`, `build`, `.build`, `test-results`, `playwright-report`, `blob-report`, `*.tsbuildinfo`, `apps/*/src/generated/prisma`, `.pnpm-store`, root `.worktree-owner.json`), removes `<wt-path>` **without `--force`**, re-verifies `git worktree list --porcelain`, deletes local `<branch>` via CAS `git update-ref -d`, and deletes `origin/<branch>` under SHA `--force-with-lease`.
- **Target-Scoped Escape Hatches (`scripts/delivery/worktree-quarantine.mjs` — explicit `--target` required; still blocked on `SKIP_VERIFY_WORKTREE`, `ACTIVE_FOREIGN_CUSTODY`, `MALFORMED_CUSTODY`, and locked worktrees):**
  - **Verified superseding PR (`--superseded-by=<#PR>`):** Confirms replacement PR `#N` is `MERGED` and an ancestor of `origin/main`, archives any remaining commit delta to `${HOME}/.local/share/inailso/worktree-quarantine/<ts>-<slug>-<pid>-<seq>/` (mode `0700`/`0600`, SHA-256-verified `manifest.json`; combine with `--quarantine --reason "<text>"` if dirty/untracked files exist), and retires `<wt-path>`: `pnpm worktree:clean --target="<wt-path>" --superseded-by=<#PR> --delete-remote-branch --json`.
  - **Operator-authorized quarantine (`--quarantine --reason "<text>"`):** Exports a SHA-256-verified `0700`/`0600` bundle (`manifest.json`, optional `commits.bundle`, `--binary` `tracked.patch` & `staged.patch`, non-dereferencing `untracked-and-ignored.tar.gz`) before non-force retirement (refusing `--delete-remote-branch` on unmerged branches without `--superseded-by`): `pnpm worktree:clean --target="<wt-path>" --quarantine --reason "<operator-reason>" --json`.

## Phase 4: Post-Cleanup Verification & Receipt Table

1. Run `git worktree list` to confirm `<primary-checkout>` remains intact and all deleted targets are absent (while any `--no-merge` / `--local-only` / blocked targets remain preserved).
2. Confirm `scripts/ci/self-hosted-runner/manage.sh status` still shows `inailso-ci-linux` (plus any provisioned `inailso-ci-linux-2..4` workers) and `inailso-ci-mac` `online` (never tear down persistent runners after cleanup).
3. Emit the mandatory receipt table:

| Worktree Path | Branch / Initial HEAD | Initial Disposition | PR `#` & Merge SHA (or Prior Proof) | Stage 6 `main` CI Run ID | Deleted (WT / Local / Remote) | Backup Ref |
|---|---|---|---|---|---|---|
| `<path>` | `<branch>@<sha>` | `<ALREADY_MERGED_CLEAN \| NEEDS_SHIP_TO_MAIN \| BLOCKED>` | `<#PR -> MERGE_SHA or ancestor>` | `<MAIN_RUN_ID or prior-merged>` | `<yes/yes/yes or preserved (reason)>` | `<refs/cleanworktree-backups/...>` |

## Rationalization Prevention

| Excuse | Reality |
|---|---|
| "`pnpm worktree:clean` creates `refs/cleanworktree-backups/...` and commits WIP automatically, so I can run it directly without `--require-merged` or `ship-to-main`" | Unshipped commits buried in local `refs/cleanworktree-backups/*` are **not** on `origin/main`. Never delete an unmerged worktree; ship via `ship-to-main` first and always pass `--require-merged`. |
| "We only have 10 minutes and disk is almost full, so I'll pin WIP branches / backup refs and run raw `git worktree remove` to reclaim disk without `ship-to-main`" | Time or disk pressure never permits deleting unmerged worktree checkouts. Always run `pnpm worktree:clean --classify --json` -> batch-reclaim `ALREADY_MERGED_CLEAN` -> sequential `ship-to-main` Stages 1–6 -> `--require-merged`; if disk space blocks Stage 6 `pnpm` install, stop and preserve unmerged worktrees intact. |
| "`gh pr merge --squash` succeeded and `gh run list --commit $MERGE_SHA --event push` returned `[]` (or started a `push-scope` run), so I can delete the worktree now" | `[]` means post-merge `main` is **unrun**, and even an auto-triggered `ci-release.yml` `push-scope` run never replaces `ship-to-main` **Stage 6** (`verify-origin-main` clean sibling local gates + full `$BASE_MAIN_SHA..$MAIN_SHA` CI proof) before Phase 3 deletion. |
| "Stage 6 passed, so I'll run `pnpm worktree:clean --in-flight=error --target=<wt>` and `git push origin --delete <branch>`" | Omitting `--require-merged` runs `git branch -D` without programmatic `origin/main` ancestry/squash-PR proof, and `git push origin --delete` lacks `--force-with-lease` SHA protection. Always run `pnpm worktree:clean --require-merged --target="<wt-path>" --delete-remote-branch --json`. |
| "The operator passed `--no-merge` AND asked to clean up the workspace directory tonight once PR CI is green, so I'll run `git worktree remove` while keeping the branch and open PR" | Under `--no-merge` (or `--local-only`), **never** remove an unmerged or open-PR worktree directory — not even via directory-only `git worktree remove`. Stop after `ship-to-main` Stage 4, preserve `<wt-path>` on disk for PR review/iteration, and report the `--no-merge` preservation boundary. |
| "A closed PR was mentioned in another merged PR's title (`SUPERSEDED_UNVERIFIED`), so I'll force-delete its worktree" | Title references do not prove commit/tree integration (`docs/ai-delivery-workflow.md`). Diff against `origin/main`; ship real remaining deltas, pass `--superseded-by=<#PR>` against a verified merged replacement PR, or obtain explicit operator authorization for `--quarantine --reason "<text>"`. |
| "I'll ship and delete multiple worktrees in parallel to finish faster" | Persistent runners (`inailso-ci-linux`, `inailso-ci-mac`) and `origin/main` rebase/Stage 6 state serialize. Process one worktree completely through Stage 6 + Phase 3 deletion before starting the next. |

## Red Flags — STOP

- Pinning WIP branches/backup refs and running raw `git worktree remove` on unmerged worktrees under time or disk-full urgency instead of `pnpm worktree:clean --classify --json` -> sequential `ship-to-main` Stages 1–6 -> `--require-merged`
- Running `pnpm worktree:clean` / `node scripts/clean-worktree.mjs` **without** `--require-merged` (including `--in-flight=error` or `--in-flight=discard`), raw `git branch -D`, or unleased `git push origin --delete <branch>` instead of `--require-merged ... --delete-remote-branch`
- Deleting a worktree after Stage 5 squash-merge before `ship-to-main` **Stage 6** clean sibling `origin/main` verification and integrated `main` CI succeed
- Removing an open-PR or unmerged worktree directory (even via directory-only `git worktree remove` while keeping the branch) when `--no-merge` or `--local-only` is active
- Mutating, pulling, resetting, or cleaning the primary root checkout (`<primary-checkout>`) or tearing down `inailso-ci-linux` / `inailso-ci-mac`
- Deleting a worktree with active unowned `lsof` handles or live editor/agent processes without operator confirmation

## Installation compatibility check

`pnpm worktree:clean --install-skill` is check-only: it validates the canonical
`.agents/skills/clean-worktree` bundle against `.agents/project-skills.json`.
It must fail on missing, drifted, symlinked or pending installation state without
copying a catalog or creating `.claude` wrappers. Use the pinned source checkout's
`python3 scripts/project-install.py --source SOURCE --project PROJECT --revision SHA --check`
for diagnosis; reviewed adoption/update uses that installer's explicit `--apply`
with its required backup and preimage inputs. This interface grants no cleanup
or publication authority.
