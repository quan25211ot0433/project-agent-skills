# Portable stage instructions

These stage contracts let hosts without Codex TOMLs use generic delegates.
The controller supplies the selected section, the absolute loaded SKILL.md path,
the owning skill path, and the execution contract. Read only the selected owner
and required references. This file specifies ownership, not model overrides:
model/effort, escalation, authority, and receipt validity belong to SKILL.md.

Load the current worktree's project guide as directed by SKILL.md; carry its
exact gates and opt-out semantics without importing another project's commands.
Every stage preserves user decisions and others' edits, follows repository rules,
and stays inside the supplied work-context, files, and publication boundary.
Return the mandatory final report from SKILL.md, including acceptance, evidence
validity, review, separate publication states, risks, next action owner/prerequisite,
and explicit No required follow-up when appropriate. Include revision/diff digest,
artifact paths, commands/results, limitations, and
runtime-exposed identity when available. End with `Status: DONE |
DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT`, Summary, and any Concerns/Blockers.
Do not recursively start the full lifecycle; return coordination to the controller.
For Codex CLI and Antigravity CLI, carry the supplied per-issue identity/repair
record through every stage. Report recurrence to the controller immediately;
no stage resets allowance or bypasses SKILL.md's automatic-advancement stop.

## min-brainstorm

Own outcome definition and assigned read-only technical or diagnostic advice.
Load the discovered `superpowers:brainstorming` owner when defining outcomes;
for read-only diagnostic advice use its applicable contract and evidence. Capture/reuse constraints, non-goals, and observable
acceptance. Inspect evidence before comparing options; diagnose bugs before
proposing repair. For advice, use the supplied attempts and alternatives and
recommend a discriminating next action without taking execution authority.
Write an assigned contract/report only when that artifact is authorized; a
strictly read-only advisory assignment returns its report through the host.
Do not edit application code, commit, or publish.

## min-plan

Own executable planning through `superpowers:writing-plans`. Reuse the accepted contract and flags;
inspect targeted docs, code, and tests. Follow project plan naming/lifecycle and
record dependencies, ownership, acceptance, validation, risks, and rollback.
Design meaningful unit/integration/E2E coverage and required live prerequisites.
Return plan-gate work to the controller for the prescribed independent reviewers
and model/effort. Initial Astra planning is not Sol High validation. Reconcile
supported findings only when assigned that stage with its required configuration.
Do not edit application code, commit, or publish.

## min-implement

Own assigned implementation files and changed-behavior tests. Load
`superpowers:executing-plans` or `superpowers:subagent-driven-development` for
known scope, `superpowers:systematic-debugging` for concrete bugs/failing checks,
and `superpowers:test-driven-development` for changed behavior. Skill maintenance
uses `skill-creator` and `superpowers:writing-skills` instead of application edits. Diagnose before repair;
run required repository impact analysis before edits. Implement real behavior
using local conventions, add meaningful tests, run focused checks, and return
revision-bound receipts. Coordination through a team is optional, not a replacement
for the owner. Send publication and GitHub writes to the shipping stage unless
explicitly assigned. Track and stop owned processes; do not weaken checks.

## min-test

Own verification through `superpowers:verification-before-completion` and
project-required domain owners/commands. Consume valid implementation receipts first. Run
missing focused checks, then required affected-contract and repository gates.
Record commands, environment, results, and justified non-applicability. Distinguish
mock evidence from required live database/browser/device/service evidence.
Missing prerequisites block required gates. Return defects to implementation;
do not edit application files, weaken tests, or publish without new ownership.
Check process ownership and stop processes started by this stage.

## min-review

Own independent read-only review through `superpowers:requesting-code-review`
and this review contract, or a discovered equivalent PR owner for existing PRs. Inspect the final tested revision and acceptance in fresh minimal
context. Review correctness, compatibility, security, and test gaps against actual
stored/protected/exposed data. Report severity, verified file/line, and source or
reproduction evidence. Bind findings to the revision/diff and test receipts;
changed inputs invalidate affected conclusions. Return fixes to implementation
and writes to shipping. Do not edit application files, commit/push, post replies,
or merge, even when the parent route permits those operations.

## min-ship

Own only authorized publication/release operations. Load the installed project
shipping owner, or `superpowers:finishing-a-development-branch` plus this ship
contract. For reply/merge use discovered owner modes only when supported. For
release discover an installed owner and platform references for the actual
destination; missing required capability blocks release. Read DevOps guidance only for
in-scope infrastructure. Consume valid final test/review receipts and run missing
or invalidated gates: lint before commit, tests before push, and required graph
change analysis. Stage only owned files, exclude sensitive data, use conventional
commits and normal push. Create PRs with `gh` and attach them when the host offers
an artifact tool. For merge explicitly authorized in the active task/session, verify current PR head, readiness, and
post-merge CI. For explicit deployment, resolve target/account/environment,
revision, CI, and rollback before executing; verify the running revision, health,
and critical flows afterward. Record URL/identifier and rollback evidence.
Reconcile plan state, update owning operational docs when contracts change, and
stop owned processes. Generic default delivery stops at PR. A guide or standing
policy cannot grant merge authority. Prior user authorization in the active
task/session remains valid; do not request it again. Deployment
requires separate authorization. Read-only review/audit never implies shipping.
