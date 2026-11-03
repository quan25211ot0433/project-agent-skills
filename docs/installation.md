# Install pinned project skills

Install complete copies of `min-delivery`, `next-step`, `ship-to-main` and
`clean-worktree` into one project's `.agents/skills`. Each project keeps its
own reviewed pin. The Python 3 helper uses the standard library, Git and POSIX
`flock`; its supported environment is macOS/Linux. It changes only those four
bundles, their installation record and transaction state.

`ship-to-main` and `clean-worktree` contain current Inailso safeguards and still
require that project's utilities and policies. Before using them elsewhere,
adapt the GitHub repository, default branch, CI, custody, PR-body validation,
close-plan and cleanup contracts, then test the adaptation. Copying these files
does not supply those dependencies or authorize shipping or cleanup.

## Select the source and target

Keep an ordinary source clone outside every skill-discovery directory. On the
Mini, the selected source clone is `/Users/m4/dev/project-agent-skills`; the
installation target is the retained Orca project workspace, not the primary.
Use an exact reviewed commit, not a mutable branch name:

```bash
git clone https://github.com/quan25211ot0433/project-agent-skills.git /absolute/path/project-agent-skills
export SKILLS_REPO="/absolute/path/project-agent-skills"
export PROJECT="/absolute/path/retained-project-workspace"
export SOURCE_SHA="<reviewed 40-character commit SHA>"
git -C "$SKILLS_REPO" status --short
git -C "$SKILLS_REPO" checkout --detach "$SOURCE_SHA"
```

Preserve any existing source edits before selecting another commit; do not use
reset or clean to force the checkout. Read the target's `AGENTS.md` and project
installation rules. For Inailso, use a linked worktree under recorded custody.
Do not change the primary checkout, personal skills, or unrelated submodules.
The source clone HEAD, project source gitlink and installed record must agree
when that project tracks `tools/project-agent-skills`.

Use explicit paths without `..` components; these are refused before path
normalization so a symlink followed by `..` cannot select another location.
The helper refuses dirty source state, symlinked roots/ancestors/payloads,
tracked nonregular payloads, and untracked or ignored payload extras. Every
payload byte, path and executable mode comes from Git tree/blob objects in the
selected commit. Tracked ignored metadata such as `next-step/agents/openai.yaml`
is included. Source edits after preflight cannot change the staged payload.

## Check, adopt and apply

Check creates no files or directories, including a lockfile. Source Git
inspection disables optional writes, preserving cached index stat metadata:

```bash
python3 "$SKILLS_REPO/scripts/project-install.py" \
  --source "$SKILLS_REPO" --project "$PROJECT" --revision "$SOURCE_SHA" --check
```

A result with `status: ready` means reviewed initial destinations can be installed;
`status: installed` means the existing record and full payload match that pin.
An existing folder without a record requires explicit adoption. Unknown files,
missing files, edited bytes, executable-mode drift or symlinks refuse mutation.
Unrelated skill names are outside the four-bundle scope.

For first adoption, prepare a JSON file outside discovery and review it against
the current folders. All four keys are required. Use `null` only for an absent
folder; for an existing folder, enumerate **every** regular file by relative
path, SHA-256 and Git executable mode. For example, a project with only an
existing `ship-to-main/SKILL.md` has this shape (replace the hash):

```json
{
  "schema_version": 1,
  "bundles": {
    "min-delivery": null,
    "next-step": null,
    "ship-to-main": {
      "SKILL.md": {"sha256": "<64 lowercase hexadecimal characters>", "mode": "100644"}
    },
    "clean-worktree": null
  }
}
```

Use `100755` for an executable file and `100644` otherwise. A changed destination
after review invalidates adoption. Do not omit additional references/scripts or
unknown files to make adoption pass. Preserve and resolve any local changes first.

Choose an owned backup root outside discovery, without symlinked ancestors, on
the same filesystem as the project. Then apply:

```bash
export BACKUP_ROOT="/absolute/path/owned-project-skills-backups"
python3 "$SKILLS_REPO/scripts/project-install.py" \
  --source "$SKILLS_REPO" --project "$PROJECT" --revision "$SOURCE_SHA" \
  --apply --backup-root "$BACKUP_ROOT" \
  --adopt-preimages /absolute/path/reviewed-preimages.json
```

Omit `--adopt-preimages` when all four folders are absent, or on later updates
using an existing record. Every apply requires an explicit `--backup-root`;
omission refuses before creating a lock or changing any project path. Keep
the chosen backup root out of Git and discovery. Apply
preflights all destinations, stages complete bundles, verifies backups, writes
and fsyncs its recovery journal/pending marker, then replaces the four folders
and record. Its JSON result reports absolute `journal` and `backup` paths.
Keep that rollback material until the installation is validated.

The record is `.agents/project-skills.json`:

```json
{
  "schema_version": 1,
  "mode": "project",
  "source_revision": "<40-character commit SHA>",
  "files": {
    ".agents/skills/next-step/SKILL.md": {"sha256": "<SHA-256>", "mode": "100644"}
  }
}
```

The real record contains the complete inventory of all four bundles. Review and
track those files and this record together; check ignored metadata explicitly.
The root installer and its modules stay in the source clone and are not skill
payloads. Do not run bundled `min-delivery/scripts/sync-installations.py --apply`
on a project installation; it maintains separate user-level discovery aliases.

## Interruption and recovery

Apply/recovery hold an exclusive lock in `.agents/project-skills.lock`.
The lockfile persists after success; its existence alone does not mean a process
is running. A read-only check uses an existing shared lock without creating one.
A losing concurrent process refuses before payload or backup mutations.

A process termination may leave `.agents/project-skills.pending.json`, which
records the transaction's absolute journal path. A fresh check/apply refuses
this pending state. Inspect the marker and journal, preserve backups, then run:

```bash
python3 "$SKILLS_REPO/scripts/project-install.py" \
  --source "$SKILLS_REPO" --project "$PROJECT" --revision "$SOURCE_SHA" \
  --recover /absolute/path/from-pending-marker/journal.json
```

Recovery uses the journal and verified backup, independently of the current
source checkout. Under the same exclusive lock, it checks **all** destination
pre/postimages and backups before writing. It restores only known transaction
images, retaining displaced postimages outside discovery. Unknown concurrent
edits refuse recovery without replacing another destination. Preserve that
pending state and resolve the changed files with their owner; never remove the
marker just to retry. A recovery process can itself be interrupted and resumed
using the same journal. It restores the previous bundles and installation record,
including absence on a first install, and leaves backup evidence in place.

## Update and validate discovery

For an update, select a reviewed clean source commit and repeat check/apply.
Check reports a mismatched pin; apply validates current bytes against the old
record before replacing anything. Reapplying the same pin preserves bundle and
record bytes/modes and retains another transaction backup/journal for audit;
it does not create duplicate discovery providers. It never treats an edited
record or local bundle drift as permission to overwrite. Other projects keep
their prior pin.
The legacy Inailso `clean-worktree --install-skill` entry is only an installation
check: use this root helper for adoption and updates.

Before delivery work, prepare the target's real `docs/min-delivery.md` and
owning dependencies, including the external
[Superpowers skills](https://github.com/obra/superpowers). Codex requires the
model/delegation capabilities in the bundled runtime adapter; Antigravity uses
the active session's selection. Missing capabilities block the affected workflow.

Open fresh Codex and Antigravity sessions from the retained project root and
verify all four selected paths are under this project's `.agents/skills`.
Invoke `next-step` with no pending session work and `min-delivery check`; inspect
ship/clean without executing shipping or cleanup. Separate tool-read evidence
from an agent self-report and record unknown effective-model metadata honestly.
Discovery is distinct from successful delivery. Do not delete a personal/plugin
provider or change global settings to force precedence. This installer does not
qualify Claude Code, Pi or other runtime surfaces.

To remove a project installation, preserve local changes and move only its
reviewed named folders outside discovery, with its record; restart and inspect
selected providers. Removal does not undo commits or external operations.
