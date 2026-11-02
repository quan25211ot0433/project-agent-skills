# Min Delivery for Codex and Antigravity

Current bundle version: **1.5.0**. [SKILL.md metadata](SKILL.md) is the version
source; the local release tag and manifest are checked separately. Edited
working-tree content remains distinct from the existing tagged release, even
when its metadata still says 1.5.0 and its regenerated manifest passes.

Min Delivery routes work in the current project through required verification
and authorized publication. Discover installed owning skills from the live catalog
using the current [routing policy](SKILL.md#route-the-task-by-available-capability);
the mappings below are skill names, not CLI commands or flags.

| Runtime | User installation | Invocation |
| --- | --- | --- |
| Codex App / CLI | canonical `~/.codex/skills/min-delivery`; CLI discovery alias `~/.agents/skills/min-delivery` → canonical directory | `$min-delivery` |
| Antigravity CLI (`agy`) | `~/.gemini/antigravity-cli/skills/min-delivery` → canonical directory | `/min-delivery` |
| Antigravity IDE / App | `~/.gemini/config/skills/min-delivery` → canonical directory | `min-delivery` skill / `/min-delivery` |

Examples below use Codex syntax; in Antigravity replace `$min-delivery`
with `/min-delivery` (or invoke the `min-delivery` skill directly in Antigravity
IDE). Expose the complete directory, not just SKILL.md. Antigravity uses
callable native subagents (`invoke_subagent`) with bundled
[stage instructions](references/stage-roles.md), not Codex TOMLs. Read
[runtime setup](references/runtime-adapters.md) for exact model/effort mapping
and discovery checks.

Antigravity (IDE and CLI) uses the user's selected session model and effort for
all stages and supported inherited delegates, including advice and plan review.
The fixed Sol/Astra defaults below remain for Codex. Independent review,
all gates, and publication limits remain required. Inspect `agy models`,
`agy agents`, and the live `invoke_subagent` schema; never pass Codex spawn
fields or session CLI flags as child parameters. Discovery installation is
verified separately from a fresh-session catalog and actual model execution.

| Work | Owner | Default model / effort |
| --- | --- | --- |
| Brainstorm and initial plan | `superpowers:brainstorming` → `superpowers:writing-plans` | `gpt-6-astra` / medium |
| Plan review, finding reconciliation and validation | Independent reviewers with the bundled plan-gate contract | `gpt-6.1-sol` / high |
| Known implementation | Worktree isolation via `superpowers:using-git-worktrees` → `superpowers:subagent-driven-development` or `superpowers:executing-plans`, plus `superpowers:test-driven-development` → worktree cleanup on verified completion | `gpt-6.1-sol` / medium |
| Bug or failing CI | `superpowers:systematic-debugging` before repair → worktree isolation via `superpowers:using-git-worktrees` → `superpowers:test-driven-development` → worktree cleanup on verified completion | `gpt-6.1-sol` / medium |
| Tests and final review | `superpowers:verification-before-completion`; `superpowers:requesting-code-review` and `superpowers:receiving-code-review` | `gpt-6.1-sol` / medium |
| Existing PR | Callable independent read-only reviewer with the bundled review contract; discovered PR owners only in authorized modes | `gpt-6.1-sol` / medium |
| PR shipping / authorized release | Installed project shipping owner, otherwise `superpowers:finishing-a-development-branch` plus bundled ship contract → worktree cleanup on PR creation; discover actual deployment owner separately | `gpt-6.1-sol` / medium |
| Skill maintenance | `skill-creator` plus `superpowers:writing-skills` and behavioral validation | `gpt-6.1-sol` / medium |

Team coordinates independent work with disjoint ownership only when useful.
Sequential delivery needs no team. Codex's six optional role profiles live at
`~/.codex/agents/min-{brainstorm,plan,implement,review,test,ship}.toml`.
Antigravity uses the equivalent bundled stage contracts with `invoke_subagent`.
Review stays read-only; implementation owns fixes and shipping owns authorized
GitHub writes and releases.

Select GPT-6.1 Sol / Medium for the controller when available. Matching
configuration allows proportional inline work; other stages use matching
delegates. Security, data, public-contract, or cross-module risk requires
independent review of the final tested revision. Tests are designed in planning
and added with code. Valid implementation, test, and review receipts are reused rather
than duplicated across later stages.

Explicit user model/effort choices win. Astra high handles unresolved
architectural tradeoffs; Sol 6.1 high handles complex logic, concurrency, test
diagnosis, and security/data/contract review. Outside the Codex CLI and
Antigravity CLI phase loop, after two distinct repair attempts without progress,
Astra medium provides diagnostic advice. Escalations are
announced and recorded. Astra medium also advises on consequential unresolved
technical decisions during coordination, shipping, deployment, or auxiliary work.
Explicitly requested advice checkpoints are honored; composed skill defaults
do not change the shared model or repair-escalation policy.
Environmental failures require their missing
prerequisite. Read [the shared policy](SKILL.md) for exact rules.

Codex CLI and Antigravity CLI run each accepted authorized phase through
implementation, required verification and review, then report result, evidence,
status, the exact next phase and prerequisites as a progress update and continue
automatically. Explicit checkpoints, required prerequisites and publication
limits still stop advancement; `check` and `plan-only` retain their boundaries.
A new issue permits one cause-aligned automatic repair. If it persists or recurs,
the whole automatic phase loop stops with reproduction, expected/actual behavior,
sanitized evidence, repair/check history, impact, proven versus suspected cause,
owner and exact resume condition. Issue identity and allowance survive phases,
delegates and chats; generic resume or advice cannot grant another repair.
Another repair requires explicit user authorization. Codex App and Antigravity
IDE retain their existing workflow and advisory policy.

Plan checks are automatic before implementation:

| Plan | Checks |
| --- | --- |
| Straightforward and low risk | Validate facts, ownership, acceptance, and executable checks |
| Complex, uncertain, or high risk | Independent red-team review, resolve findings, then validate the final plan |

Risk includes coupled contracts, concurrency, permissions/payments, data
migrations, and difficult rollback. A one-phase risky change still gets red-team
review. Hard/deep/parallel planning retains its required red-team gate. Ordinary
small changes do not need a formal plan just to pass a gate.

Before code edits begin, implementation isolates changes in a dedicated worktree
using `superpowers:using-git-worktrees` (preferring native worktree tools, with a git
worktree fallback). Worktree setup is skipped for `plan-only`, `check`, review, and
audit routes, when already inside a dedicated feature worktree, when `implement-only`/`resume`
reuses a recorded worktree, or when the user explicitly directs working in place.
Inside the new worktree, the delivery guide and instructions are re-read from the new
root, and `BASE=HEAD` is recorded. If worktree creation fails, report an evidenced
blocker rather than silently falling back to in-place edits.

When implementation finishes, min-delivery automatically cleans up the isolated
worktree directory as a routine teardown action without interactive confirmation prompts.
Teardown triggers upon PR creation in publishing routes, or upon verified local completion
under `--local-only` and `implement-only`. Before deletion, pre-removal safety checks verify
that the working tree is clean (`git status --porcelain -uall` is empty), a named branch is
attached, commits are pushed (for remote PR routes) or committed locally (for `--local-only`),
background processes are stopped, and CWD is restored to the primary repository root.
Worktree removal deletes only the checkout directory (`git worktree remove` and `git worktree prune`);
the git branch is always retained intact for review iteration or local work. `plan-only` and `check`
create no worktree and skip cleanup; pre-existing worktrees are never deleted.

Sol 6.1 High owns plan review, finding reconciliation and validation. When new
agents cannot be created, reuse existing Sol 6.1 High agents for the remaining
lenses and validation without a new approval pause. Keep separate lens receipts
and independence from the work being reviewed; an implementer cannot provide the
final independent code review. Re-read current inputs after reassignment.
Unresolved architectural tradeoffs can escalate to Astra High. Initial planning
keeps its Astra Medium default. Explicit model choices still take precedence.
Facts are checked against source; questions are reserved for material unresolved decisions.

Accepted plans and resume reuse matching evidence. Changed assumptions or code
invalidate affected checks. Plan-only runs the applicable plan checks but does
not implement; check mode only inspects setup. These checks do not replace
application tests or final code review. To request extra scrutiny, use prose:

```text
$min-delivery plan-only
Plan the payment retry change. Red-team the plan, resolve supported findings,
and validate it before finishing. Preserve the accepted payment behavior.
```

Start with a read-only setup check:

```text
$min-delivery check
```

A role file on disk does not make the role callable. When necessary, use a
generic delegate with exact model/effort and role instructions. Missing required
models/capabilities are reported without silent substitution. Effective identity
is reported only from exposed runtime metadata. Start a fresh chat if the
installed skill is absent from the catalog.

These examples illustrate intent. Supply the real project plan path or PR
reference when relevant.

For a new feature through a PR:

```text
$min-delivery
Add status filtering to the admin list. Preserve pagination and permissions.
Acceptance: the filter survives refresh; clearing it restores the full list.
Design tests with the plan, implement, verify, review, and open a PR.
```

For a local bug repair:

```text
$min-delivery
Fix the admin filter losing its selected status after refresh.
Reproduce it, prove the cause, and add a regression check. Keep edits local.
```

For an accepted plan, place its actual path after `implement-only`, or identify
an accessible accepted plan in the prompt:

```text
$min-delivery implement-only
Use the accepted plan attached to this chat. Implement, test, and review locally.
```

For an existing PR, supply its real number/URL or accessible attachment:

```text
$min-delivery
Review the PR attached to this chat for regressions and test gaps.
```

Review alone is read-only. Explicitly request fix, reply, or merge to authorize
the corresponding operations through a supported owner. Requesting fixes and a reply authorizes repair,
commit/push, re-review, and posting the final review. Merge needs explicit
authorization in the active task/session and readiness/post-merge CI verification.
Prior user authorization persists; do not request it again. A project guide or
standing policy cannot grant merge authority.

For deployment:

```text
$min-delivery
Deploy the approved release to the configured staging environment.
Resolve target, exact revision, required CI, and rollback first.
Verify the deployed revision, health, and critical user flows.
```

The target and environment must be discoverable or selected. Questions about a
provider do not authorize deployment. Verify what actually runs, not merely
an upload response.

Legacy boundaries remain available:

```text
$min-delivery plan-only
Design status filtering and its tests. Stop after a reviewable plan.
```

Use `implement-only` with an accepted plan for local implementation, checks,
and review. Use `resume` with an existing plan path to continue its incomplete
stage after revalidating evidence. Resume preserves the original publication
boundary; publishing local work needs an explicit request. Both full delivery and
local-only routes automatically clean up the isolated worktree directory upon their
respective completion trigger while preserving the branch.

Default implementation delivery includes commit, push, and PR creation.
Narrower instructions override that default. Merge and deploy never follow
implicitly. Maintenance is on demand; recurring monitoring requires a user
request and its notification policy.

Composed skill defaults do not add issue creation, version changes, or social/wiki
publication. Project-required docs and journal work still apply.

Follow current repository plans, docs, quality gates, and process rules.
Report final revision, artifacts, checks, worktree disposition, remaining gaps,
and publication state. Missing services, credentials, runners, or required checks block a gate.
A setup check does not prove application stages ran.

Validate with the installed skill creator's `quick_validate.py` and discover any
additional validators from its current instructions; parse the six TOMLs when using Codex profiles, and
inspect a fresh skill catalog. For Antigravity, verify `sync-installations.py --check`
across global symlink aliases and live `invoke_subagent` discovery; do not treat
Codex profiles as callable Antigravity subagents.
[Evaluation cases](evals/evals.json) cover routes and boundaries. Verify CLI
model availability for that client/account; do not infer it from desktop roles.

## Local version checks and synchronization

The canonical directory can be a local Git repository with an original `v1.4.0`
baseline and a verified `v1.5.0` release. A manifest or metadata version alone
does not establish that a tag exists. No remote or automatic update is performed
by the utility. A missing remote does not block
local verification or update-policy design; fetch, push and remote integration
checks need a known destination and applicable authorization. Inspect existing
configuration before asking for remote information needed by those operations.

Run from the canonical directory with Python 3:

```bash
python3 scripts/sync-installations.py --check --expect-version 1.5.0
python3 scripts/sync-installations.py --check --expect-version 1.5.0 \
  --project ~/dev/inailsoClaude --project ~/dev/hqPosAppV2 \
  --project ~/dev/deliverytaxi --project ~/dev/kyc
```

`--check` is the default and never writes. `--project` is repeatable and limits
inspection to supplied projects and their ancestors through the nearest Git
root; outside Git it inspects the supplied directory. No other project tree is
searched. It checks `.agents/skills`, `.codex/skills`, `.gemini/skills`,
`.gemini/antigravity-cli/skills`, `.agent/skills` and `.claude/skills` for a
`min-delivery` shadow. Guide presence is informational here; a project requiring
`docs/min-delivery.md` still enforces that requirement when delivery begins.

The release manifest records sorted SHA-256 hashes of every bundled file except
itself, `.git`, `__pycache__` and `.DS_Store`. Checks reject extra, missing or
modified content, version/schema mismatches and bundled symlinks. This detects
accidental drift; it does not authenticate a deliberately rewritten manifest.
Tag/version/manifest agreement establishes consistency separately from release
provenance and commit ancestry. An automatic updater is optional additional
scope: if requested, settle its release-selection, trust/provenance, ancestry
and rollback policy before implementation. A remote URL alone supplies no trust
policy, and updater design does not require creating or contacting a remote.
All three global aliases (`~/.agents/skills/min-delivery`,
`~/.gemini/antigravity-cli/skills/min-delivery`, and
`~/.gemini/config/skills/min-delivery`) must be symlinks resolving to this
canonical directory.
Ordinary copies, wrong or dangling symlinks, conflicting parent paths and
project-local shadows are preserved and reported as failures.

For a new workstation, copy the complete verified bundle or clone its repository
from a remote you choose and configure separately into
`~/.codex/skills/min-delivery`. After inspecting its version and contents, create
only missing global aliases deliberately:

```bash
python3 scripts/sync-installations.py --apply --expect-version 1.5.0
```

All bundle, version, project and alias-conflict checks precede alias creation.
Repeated valid apply is idempotent. `--home PATH` scopes global aliases to another
home for isolated tests; it does not change the source, which is the script's
resolved parent skill directory. The utility never replaces conflicts. Resolve
them explicitly while preserving user content, then check again. Filesystem
equality does not prove a live runtime reloaded its catalog or executed a model.

For authorized local preparation, run the subprocess tests and owning skill
validator, then regenerate the manifest only after all bundle edits are complete.
These commands preserve the current 1.5.0 metadata; they create no Git release,
alias activation or provenance claim:

```bash
python3 scripts/test-sync-installations.py
python3 scripts/sync-installations.py --write-manifest --expect-version 1.5.0
python3 scripts/sync-installations.py --check --expect-version 1.5.0
git diff --check
git diff
git status --short
```

Commit, tag and remote publication require their applicable task/session
authorization and required review. Reuse existing authorization for the concrete
destination and exact branch/tag changes; if absent, request it for those changes.
Stage only owned files and never recreate or force-move an existing tag. Choose
a new version only when that release change is in scope. For an already verified
and authorized branch plus tag publication, use explicit refspecs, for example
`git push <remote> refs/heads/releases:refs/heads/releases refs/tags/v1.5.0:refs/tags/v1.5.0`
when those are exactly the authorized refs. This publishes the existing tag's
commit, not pending working-tree edits. Inspect the destination and refs first;
avoid `--tags`, which also publishes unrelated local tags. No remote creation or
push follows from local preparation alone.

For rollback, first preserve uncommitted modifications outside discovered skill
directories, inspect the prior verified tag and its file
list, then restore only the intended owned files. `v1.4.0` predates the utility;
restoring it also requires deliberately removing only newly introduced owned
release files after preserving them. Revalidate version, complete alias contents
and applicable skill checks for the restored version. Do not hard-reset user
work or retain a newer manifest as evidence for older content.
