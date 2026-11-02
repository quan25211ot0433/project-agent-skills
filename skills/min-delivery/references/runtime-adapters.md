# Runtime adapters

Resolve the current worktree root and optional/required project guide using
SKILL.md before setup or delegation. The guide documents existing project gates
and standing publication policy; user instructions prevail. Never import a
sibling worktree guide or synthesize absent owner capabilities.
When isolating implementation in a worktree, the host's native worktree tool is
preferred, falling back to git worktrees otherwise as directed by
`superpowers:using-git-worktrees`.
During teardown, runtime adapters must support worktree directory switching:
the shell/controller working directory (CWD) must be restored to the primary
repository root (`cd "$MAIN_REPO_ROOT"` or pass `-C "$MAIN_REPO_ROOT"`) before
running `git worktree remove` to prevent directory-locking errors (`EBUSY`).
All owned background processes, watchers, or dev servers spawned inside the
worktree must be terminated. If the host platform provides a native workspace
exit tool (such as `ExitWorktree`), prefer it over manual `git worktree remove`.

Use the adapter for the active host. Installation grants no extra tool, model,
publication, or delegation authority. Host and project restrictions take precedence.
Keep the model/effort policy in the parent SKILL.md; resolve exact provider IDs
from the live registry instead of guessing aliases or changing global defaults.

For either CLI, keep four evidence states separate: requested model/effort,
requested inheritance, runtime-confirmed inheritance, and exposed effective
model/effort. A supported inheritance request and a completed delegate output
can be reported even when effective identity is unknown. Confirm inheritance
only when runtime evidence establishes it; `Model: inherit` alone describes
inheritance, not a named effective model. Conversation IDs, workspace/log paths,
receipt filenames, and child self-reports do not establish effective identity.
Record the limitation alongside usable output rather than treating missing
identity metadata alone as an execution failure. Required configuration still
needs the supported selection/inheritance evidence described below.

## Codex App and CLI

Invoke `$min-delivery`. Keep the canonical installation at
`~/.codex/skills/min-delivery`; for CLI discovery expose the complete directory
at `~/.agents/skills/min-delivery` (a symlink to the canonical copy is supported).
Do not create another project-local copy when a project prohibits it. Inspect a
fresh skill catalog; filesystem installation alone does not prove activation.

Inspect the active session's tool schema and callable roles. CLI and App versions
can expose different delegation schemas; a `codex agents` terminal command opens
session browsing, not a model-visible dispatch API. `codex --help`,
`codex features list`, and, when listed by `codex debug --help`,
`codex debug models` provide read-only inventories, not execution receipts.

Use a callable matching named role with bundled [stage instructions](stage-roles.md)
and the loaded SKILL.md absolute path. Inspect `~/.codex/agents/min-*.toml`
and the active role catalog separately. Role files use `model` and
`model_reasoning_effort`; inspect effective configuration and precedence before
relying on a role. A role file on disk is not proof it is callable or executable.

When the live schema exposes `model`, `reasoning_effort`, and `fork_turns`, use a
callable generic `default`/`worker` with explicit requested settings and
`fork_turns: "none"` when that isolated mode supports overrides. If those fields
are absent, use the actual supported schema with an existing matching role or
verified matching inheritance. Never invent parameter names. A prompt asking a
child to use a model does not configure that model. If a required setting cannot
be selected through the callable API or an existing matching role, block that
stage. Do not edit global settings, create outer CLI sessions, or use `codex exec`
as an orchestration bypass.

Establish whether the active host is Codex CLI or Codex App from session/runtime
evidence. Only CLI uses SKILL.md's phase loop and recurrence stop; App retains
the existing workflow. Do not infer CLI solely from the installation path. Codex
delegates execute inside the isolated worktree path; during worktree teardown,
ensure the shell CWD is restored to the primary repository root (`cd "$MAIN_REPO_ROOT"`
or pass `-C "$MAIN_REPO_ROOT"`) before running `git worktree remove`.

## Antigravity (IDE and `agy` CLI)

Expose the complete canonical directory via user-level symlinks at both
`~/.gemini/antigravity-cli/skills/min-delivery` (for `agy` CLI) and
`~/.gemini/config/skills/min-delivery` (for Antigravity IDE / App), maintained
by `scripts/sync-installations.py`; invoke `/min-delivery check` or
`/min-delivery` inside the interactive `agy` CLI, or load the `min-delivery`
skill directly in Antigravity IDE. Preserve any existing target before
installation. User-level symlink aliases keep one canonical policy source at
`~/.codex/skills/min-delivery`; verify their resolved files with
`python3 scripts/sync-installations.py --check --expect-version 1.5.0`, then
inspect a fresh skill/slash-command catalog before claiming activation. Never
infer a successful reload from a directory listing.

In `agy` CLI, run `agy --help`, `agy models`, and `agy agents` for supported CLI
options, current model IDs, and custom-agent inventory. An empty custom-agent list
does not establish absence of built-in delegates. In both Antigravity IDE and
`agy` CLI, inspect the live model-visible `invoke_subagent` schema and built-in
types. When exposed, use `TypeName: "self"` for stage work with the caller's
capabilities; use `research` for independent read-only work only when its exposed
model and tools satisfy the assignment. An independent `self` delegate may perform
read-only review under an explicit no-edits brief. Do not treat `--agent` or
`--model` session-start flags as child dispatch fields, or pass Codex fields to
`invoke_subagent`.

Antigravity uses the user's selected session model and effort under the explicit
host exception in SKILL.md. Prefer inherited `self` delegates; inspect the live
schema's inheritance contract and returned metadata. If the schema supports
caller inheritance and the request uses it, record that supported request;
report runtime confirmation and effective identity only to the extent exposed.
For example, a selected Gemini session plus `Model: inherit` does not by itself
confirm the child's effective Gemini model/effort. Do not silently select
`flash`, `pro`, a research preset, or another model tier. If required inheritance
or an explicit user override cannot be established, block the affected delegate
stage rather than substitute. Keep the same review lenses, advisory triggers,
independence, tests, receipts, and publication boundaries. Advice uses a separate
read-only selected-model delegate; model escalation requires a further user
choice. Use native async completion and supported follow-up by returned agent ID;
inspect the schema rather than inventing lifecycle calls. No shell-launched
alternate CLI fallback. `check` never launches a delegate or changes settings.
Antigravity native subagents (`invoke_subagent`) must be passed the worktree root
in their contract. Background processes started via Antigravity tools (e.g. dev
servers or background watchers) must be terminated before directory deletion. If
the host provides a native workspace exit tool (such as `ExitWorktree`), prefer
it over manual `git worktree remove`.

Sources: [Codex skills](https://developers.openai.com/codex/skills),
[Codex subagents](https://developers.openai.com/codex/multi-agent),
[Antigravity skills](https://antigravity.google/docs/skills/),
[Antigravity CLI skills](https://antigravity.google/docs/skills/#cli-skill-locations),
[Antigravity subagents](https://antigravity.google/docs/subagents/), and installed
CLI help. Live schemas and account model inventories resolve version differences.

Apply SKILL.md's CLI phase loop and recurrence stop in Antigravity CLI, including
intermediate reports, prerequisite checks, and durable per-issue repair records;
Antigravity IDE retains the interactive App/IDE workflow and two-attempt advisory
policy. The selected-session-model exception does not alter that stop.

## Install and verify global aliases

Keep the canonical bundle at `~/.codex/skills/min-delivery`, including references,
scripts, and eval cases. Check for any existing directory or conflicting link at
`~/.agents/skills/min-delivery`, `~/.gemini/antigravity-cli/skills/min-delivery`,
or `~/.gemini/config/skills/min-delivery` and back up user modifications outside
auto-discovered skill directories before replacement. Do not copy credentials,
host settings, session logs, or project-local `min-delivery` shadows into skill
discovery trees.

Run `python3 scripts/sync-installations.py --apply --expect-version 1.5.0` (and
`--check` for read-only verification) to confirm bundle hashes and all three
global symlink aliases. Start a fresh Codex or Antigravity session when needed,
inspect skill diagnostics, and resolve name collisions before claiming
activation. `$min-delivery check` / `/min-delivery check` verifies setup only;
it does not prove application delivery, model execution, or deployment.
