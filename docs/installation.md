# Install existing agent skills in another project

This guide explains how to reuse the existing skill folders. You do not need
to recreate their instructions. For the generic skills, install a complete
folder, then check that your agent loads it and that its required tools exist in the target project. The two
Inailso workflows below are reference-only and must remain outside discovery.

The examples use macOS/Linux, Git, and `rsync`, with an agent already installed
and signed in. Each project receives its own copy, so updating one project
does not update another.

## Choose the skills

| Skill | Purpose | Before using it elsewhere |
| --- | --- | --- |
| `next-step` | Continue ready follow-up work from the session | Read the target project's instructions and authorization limits |
| `min-delivery` | Coordinate planning, implementation, verification, and review | Check its owning-skill dependencies, runtime adapter, and model/delegation requirements |
| `ship-to-main` | Verify and ship branches or PRs | **REFERENCE-ONLY**; review and adapt destructive worktree handling before any activation, including Inailso |
| `clean-worktree` | Retire worktrees with merge proof | **REFERENCE-ONLY**; depends on the unreviewed shipping recipe; review and adapt before any activation, including Inailso |

Start with `next-step`, then add `min-delivery` after checking prerequisites.
The last two skills are archived Inailso workflows. Keep both outside all skill
discovery directories until review and adaptation are complete, including in
the original Inailso project.

Canonical folder names are `next-step` and `clean-worktree`. The current text
recognizes `nextStep` and `cleanWorkTree`, but these are not guaranteed native
commands in every agent. `clearWorkTree` is a requested future alias; use the
canonical name today.

## Reference-only Inailso workflows

`ship-to-main` and its dependent `clean-worktree` are preserved for source
reference only. Do not activate either unchanged, even in the original project.
The inherited shipping recipe reuses an existing `VERIFY_WT` by running
`checkout --detach`, `reset --hard`, and `clean -fd` before an explicit dirty-work
and ownership preflight. Its later cleanup uses forced worktree removal. These
steps can discard tracked/untracked edits or disrupt processes owned by another
user or agent session. The source snapshot retains this behavior for review.

Before activation, separately review and test an adaptation that preserves all
local work before destructive actions, verifies the exact worktree and its
ownership, checks tracked/untracked and relevant ignored state before reuse or
removal, identifies open handles and running processes, and stops only processes
owned by that workflow. Preserve the worktree and report the unresolved condition
when ownership, clean state, merge/commit preservation, or process safety cannot
be proven. Repository/CI/path substitutions alone do not address this hazard.
The copy commands below are for `next-step` and `min-delivery` only.

## Get the complete source folder

Clone the public source snapshot into a location outside your target project's
skill discovery directories:

```bash
git clone https://github.com/quan25211ot0433/project-agent-skills.git
cd project-agent-skills
export SKILLS_REPO="$(pwd)"
```

The complete bundles are in `skills/min-delivery`, `skills/next-step`,
`skills/ship-to-main`, and `skills/clean-worktree`. Review their contents and
[source provenance](../source-provenance.json) before installing. Preserve
`SKILL.md`, scripts, references, evaluations, assets, and `agents/` metadata
when present. Do not copy credentials or machine settings.

This is an initial source snapshot, not a tagged release or an automatic
installer. The original Inailso documentation links in the two project-specific
skills require access to that private project. Those documents are not included.

## Choose the project location

All paths below are relative to the target repository root.

| Agent | Project skill directory | Explicit invocation |
| --- | --- | --- |
| Codex App / CLI | `.agents/skills` | `$next-step` or `$min-delivery` |
| Antigravity App / CLI / IDE | `.agents/skills` | Mention the skill by name; App/CLI also expose slash commands |
| Claude Code | `.claude/skills` | `/next-step` or `/min-delivery` |
| Pi | `.agents/skills` or `.pi/skills` | `/skill:next-step` or `/skill:min-delivery` |

These locations come from the current [Codex](https://developers.openai.com/codex/skills/),
[Antigravity](https://antigravity.google/docs/skills/),
[Claude Code](https://code.claude.com/docs/en/skills), and
[Pi](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md)
documentation. Discovery support does not prove that every workflow in these
particular skills can execute on that runtime.

Codex, Antigravity, and Pi can share one `.agents/skills` copy. For Claude Code,
use its separate project directory and keep that copy in sync when updating.
Do not also copy the same skill into `.pi/skills` when Pi already discovers it
through `.agents/skills`.

## Install one skill

First read the target project's `AGENTS.md` and any local installation rules.
This Inailso checkout requires user-level `min-delivery` and prohibits a local
shadow; the example is for another project whose rules permit project copies.

Set the three variables below. Replace the project path with your real target.
For Claude Code, change `SKILLS_DIR` to `.claude/skills`. For a standalone Pi
installation, `.pi/skills` is also supported.

```bash
export PROJECT="/absolute/path/to/your-project"
export SKILL_SOURCE="$SKILLS_REPO/skills/next-step"
export SKILLS_DIR=".agents/skills"
```

Run this in Bash or Zsh. It refuses existing destinations and symlinked
discovery directories; it does not overwrite an existing installation.

```bash
(
  set -eu
  case "$SKILLS_DIR" in
    .agents/skills|.claude/skills|.pi/skills) ;;
    *) echo "Choose a project skill directory from the table." >&2; exit 1 ;;
  esac
  project_root="$(git -C "$PROJECT" rev-parse --show-toplevel)"
  skill_name="$(basename "$SKILL_SOURCE")"
  test -f "$SKILL_SOURCE/SKILL.md"
  destination="$project_root/$SKILLS_DIR/$skill_name"
  for candidate_path in "$project_root/${SKILLS_DIR%%/*}" "$project_root/$SKILLS_DIR" "$destination"; do
    if [ -L "$candidate_path" ]; then echo "Refusing symlink: $candidate_path" >&2; exit 1; fi
  done
  if [ -e "$destination" ]; then
    echo "Already exists; review it before updating: $destination" >&2
    exit 1
  fi
  mkdir -p "$destination"
  rsync -a --exclude='.git' --exclude='__pycache__' "$SKILL_SOURCE/" "$destination/"
  echo "Copied skill to $destination; verify it in a fresh agent session."
)
```

To install `min-delivery`, set `SKILL_SOURCE="$SKILLS_REPO/skills/min-delivery"`
and repeat.
Do not run its bundled `sync-installations.py --apply` for a project install:
that helper maintains user-level aliases on the original machine.
If copying fails, inspect the partial destination before retrying; preserve
it outside discovery rather than merging another copy into it blindly.

## Prepare the target project

For `min-delivery`, inspect its `references/runtime-adapters.md`. Install or
make available the owning skills it actually needs for your chosen task,
including the referenced Superpowers workflows. Follow the
[upstream Superpowers installation instructions](https://github.com/obra/superpowers)
for your runtime; copying `min-delivery` does not install these dependencies.

Put repository-specific build/test commands, architecture requirements, and
publication limits in the target project's `docs/min-delivery.md`, and link
it from that project's `AGENTS.md`. Use that project's real commands. Do not
copy Inailso's guide into an unrelated repository.

The current `min-delivery` requires particular model/delegation capabilities
on Codex and inherits the selected session configuration on Antigravity.
Its runtime-adapter reference documents those hosts; Claude/Pi discovery
alone does not establish a working delivery adapter. If a required capability
is missing, stop that workflow and report the prerequisite.

Only after the reference-only worktree review above, and before installing an
adapted `ship-to-main` or `clean-worktree` into discovery,
review a working copy outside discovery and replace all project-specific
assumptions: GitHub repository, default branch, absolute paths, CI workflow
names, runner names, verification commands, PR-body validator, and cleanup
utility/flags. Preserve the existing authorization, merge-proof, dirty-work,
process-ownership, and recurrence safeguards. Verify supporting document links
from the final installed path. Adaptation is a separate behavior change that
needs tests and review; this guide does not perform it.

## Verify before doing delivery work

1. Open the target repository in a fresh agent session and complete its normal
   project trust step after reviewing the files.
2. Ask: “List the available skills and report the full path of `next-step`.”
   Confirm the path points into this project. An agent's answer is a useful
   check; confirm it against available skill diagnostics or selectors too.
3. Invoke `next-step` with no pending work. It should report no remaining
   actionable steps rather than create work.
4. Invoke `min-delivery check` using the runtime's syntax from the table.
   Confirm required skills, models, tools, and the project guide resolve.
   This is a setup check, not a successful feature-delivery test.

If a personal, plugin, or enterprise skill has the same name, inspect which
provider loads before continuing. Codex can show both; Claude Code gives
enterprise/personal copies precedence over project copies. Do not assume a
project copy overrides another provider, or delete global settings to force it.

This snapshot has no seven-surface runtime qualification. Copying bundles and
checking their files does not prove activation or successful delivery on a host.

## Update, roll back, and remove

**Update one project:** obtain the reviewed new complete bundle and record its
source revision or checksum. Save the old installed folder and any local edits
outside every agent skill-discovery directory. Move the old folder out, then
use the install procedure for the new folder. Restart and repeat verification.
Keep the previous version until the new one works. Other projects retain their
own copies. Coordinate updates of any separate Claude copy in the same project.

**Roll back:** move the new folder outside discovery, restore the saved previous
folder to its original project path, restart, and verify the selected provider.
This manual process has no automatic lockfile, transaction, or crash recovery.

**Remove:** after preserving local changes, move only the named installed skill
folder outside discovery. Restart and check that the project provider is gone.
If the skill still appears, inspect other scopes. Keep project guides used by
other workflows; removing a skill does not undo commits or external actions.

For team sharing, review and commit the selected skill folders and project
guide to the target repository. Check its ignore rules and exclude credentials
and private runtime state. Record updates as ordinary reviewable changes.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Skill is missing | Correct repository root, folder name, valid `SKILL.md` frontmatter, trust, and a fresh session |
| Wrong version runs | The loaded path and duplicate personal/plugin/enterprise providers |
| Supporting file is missing | The entire bundle was copied, not just `SKILL.md` |
| Inailso command appears elsewhere | An unadapted shipping/cleanup skill is active; move it outside discovery |
| Delivery stops on a prerequisite | The selected owning skill, project guide, model, or delegation capability |
| GitHub installation finds no skills | Confirm the cloned source contains the chosen `skills/<name>/SKILL.md` |
