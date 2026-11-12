# Install project skills

Install independent copies of `min-delivery`, `next-step`, `ship-to-main` and
`clean-worktree` into one project's `.agents/skills`. The root `project-skills`
executable uses Python 3 standard library, Git and POSIX `flock` on macOS/Linux.
It manages these four bundles, four Claude aliases, two records and its own
transaction state. Personal/global skills and unrelated project skills stay
outside its scope.

## Bootstrap a compatible executable

Keep the source clone outside discovery and outside the target project. Choose
an existing reviewed compatible commit or ref, then check it out in a new clone:

```bash
export COMPATIBLE_REF="<reviewed-existing-commit-or-ref>"
git clone --no-checkout https://github.com/quan25211ot0433/project-agent-skills.git /absolute/path/project-agent-skills
export SKILLS_REPO="/absolute/path/project-agent-skills"
git -C "$SKILLS_REPO" checkout --detach "$COMPATIBLE_REF"
export COMPATIBLE_REF="$(git -C "$SKILLS_REPO" rev-parse HEAD)"
git -C "$SKILLS_REPO" show "$COMPATIBLE_REF:project-skills-source.json"
git -C "$SKILLS_REPO" cat-file -e "$COMPATIBLE_REF:project-skills"
"$SKILLS_REPO/project-skills" --help
```

Select the ref from a reviewed publication or use a reviewed compatible local
checkout; this guide does not assert that any branch or PR has been published or
merged. If the selected commit lacks the executable or compatibility marker,
choose a compatible reviewed source before installing. No released tag or
npm/npx package is asserted. The marker declares schema 1 and the exact four
bundles. Markerless/incompatible sources refuse installation, including an
incompatible public default HEAD. The marker establishes format compatibility,
not trust in skill instructions. Review the selected source and its
[source provenance](../source-provenance.json).

Preserve existing source edits before selecting a commit. Never reset or clean a
user's source to make installation pass. The installer itself never checks out,
resets or cleans a local source. A local source must be a clean committed Git
root, with an optional revision resolving to its current HEAD. Dirty state,
untracked/ignored payload extras, symlinked ancestors/payloads and nonregular
payload files refuse installation. Payload bytes and executable modes come from
Git objects, including tracked ignored metadata such as `agents/openai.yaml`.
The selected source tree and index must not contain embedded submodule gitlinks;
they are refused before recursive status inspection. The source root itself may
be a linked worktree or a Git submodule, and gitlinks in the target project are
supported.

## Select a project and install

Read the target's instructions first. For Inailso use a retained linked worktree
under recorded custody, following its installation policy. Keep the source and
target separate: equality and ancestor/descendant overlap are refused. Use paths
without `..` or symlink ancestors; leading `~` is supported.

Run from any directory inside the target Git checkout to infer its root:

```bash
"$SKILLS_REPO/project-skills" install --from "$SKILLS_REPO"
"$SKILLS_REPO/project-skills" check
"$SKILLS_REPO/project-skills" doctor
```

Supply `--project /absolute/path/to/project` to select a different existing target
or a non-Git directory. Public acquisition accepts `github:owner/repo`, using a
credential-free public GitHub HTTPS snapshot:

```bash
"$SKILLS_REPO/project-skills" install \
  --from github:quan25211ot0433/project-agent-skills \
  --revision "$COMPATIBLE_REF" --project /absolute/path/to/project
```

Omitting `--revision` selects the source's current HEAD and records its immutable
40-character commit SHA. Use a reviewed compatible ref. Public
sources are acquired into installer-owned private cache operations; fetched
installers, hooks, filters and submodules are not executed. Arbitrary URLs,
credentials and option-like refs are refused. There is no source-compatibility
bypass. Acquisition failure leaves installed payloads unchanged.

The defaults are `<project>/.project-skills/backups` and
`<project>/.project-skills/cache`, outside discovery on the project's filesystem.
An explicit `--backup-root /absolute/path` must also be safe and on the same
filesystem and outside the local source, including its root. Foreign cache
state is refused rather than adopted or repaired.
The installer does not edit `.gitignore`; apply your project's policy to this
operational state and keep backups until validation. No cache-pruning command is
provided.

## Check and update explicitly

```bash
"$SKILLS_REPO/project-skills" check --project /absolute/path/to/project
"$SKILLS_REPO/project-skills" check --updates --project /absolute/path/to/project
"$SKILLS_REPO/project-skills" update --revision "$COMPATIBLE_REF" \
  --project /absolute/path/to/project
```

Default `check` and `doctor` are offline and read-only: they create no directories
or lockfiles. Check verifies complete payload bytes/modes, receipt, provenance
and recorded aliases. `check --updates` additionally looks up the recorded
origin; it reports current, available or unknown separately from installed
integrity. An unavailable upstream is not proof of installed corruption.
Doctor reports layout, integrity, pending state and dependency diagnostics,
distinguishing available, missing and unknown; it does not repair or certify
runtime activation.

`update` uses the recorded origin and resolves its current HEAD unless an
explicit revision is supplied. It validates exact old preimages before replacing
anything. Missing/extra files, byte or executable-mode drift, edited records and
changed/missing aliases refuse replacement. Preserve and resolve local edits
with their owner. Other projects retain their own pins. Repeating `install`
requires the same managed origin and pin; use `update` for a new pin. There is no
implicit origin switch, automatic update, general rollback or live linking.

## Receipts, aliases and legacy migration

The canonical `.agents/project-skills.json` retains its exact v1 field shape:

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

The real receipt inventories every file in all four bundles. The separate
`.agents/project-skills-source.json` has exactly `schema_version`,
`source_revision`, `source` and `aliases`. Its schema is 1 and its revision must
match the receipt. `source` records `kind` (`local` or `github`) and `location`
(absolute local root or `github:owner/repo`). `aliases` records the four owned
relative links, each `.claude/skills/<name> -> ../../.agents/skills/<name>`.
Both records and all aliases share the payload transaction. Track installed
payloads and records together according to project policy, checking ignored
metadata explicitly; the installer executable/modules remain in the source.

Initial Claude alias destinations must be absent. An existing file, folder,
dangling link or even an unowned link with the correct text is a collision.
Updates require exact recorded link text and safe real parent directories.
The installer never links whole discovery roots or infers link ownership.

An installation with only the v1 receipt is legacy. Check can validate its
payload and reports missing origin. Migrate explicitly with `install --from
SOURCE`, optionally selecting a revision; this still requires exact old payload
preimages and absent new aliases. `update` cannot guess legacy provenance.
The updated low-level `scripts/project-install.py --apply` refuses installations
with the source sidecar; its read-only check still validates the v1 receipt.
Historical distributed copies cannot acquire that guard retroactively: do not
use an old writer to update a managed installation.

For first adoption of existing folders without a receipt, pass
`--adopt-preimages /absolute/path/reviewed-preimages.json` to `install`.
Review the complete inventory outside discovery. All four bundle keys are
required; `null` means absent. Enumerate every regular file with a relative path,
SHA-256 and Git executable mode (`100644` or `100755`):

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

Do not omit extra files to make adoption pass. Destination changes after review
invalidate adoption. The legacy Inailso `clean-worktree --install-skill` entry is
only a check. Inailso's project gate also requires the indexed
`tools/project-agent-skills` gitlink to match receipt `source_revision`.
Coordinate that reviewed pin separately; generic install/update does not change
project gitlinks or policies.

## Interruption and recovery

Mutations and recovery hold the exclusive `.agents/project-skills.lock`.
Its persistent file alone does not mean a process is running. Read-only checks
use an existing shared lock without creating one. Concurrent losers refuse
before installation/backup mutations.

A durable journal and `.agents/project-skills.pending.json` precede replacements.
Termination can temporarily leave partial discovery; this is recoverable,
not simultaneous multi-path atomicity. Pending state blocks new installs and
updates; check refuses it, while doctor reports it without repair. Preserve the
marker, journal and backups, then run:

```bash
"$SKILLS_REPO/project-skills" recover --project /absolute/path/to/project
```

Recovery reads the pending journal under the project lock. It works offline
without the original source or cache; keep a compatible executable available.
It validates **all** current pre/postimages and backups before writing, then
restores previous payloads, aliases and both records, including their absence
on first install. Old v1 journals remain recoverable. A recovery process can
itself be interrupted and resumed with the same journal. Displaced postimages
and backup evidence stay outside discovery; newly created empty discovery
parents may remain.

Unknown concurrent edits refuse recovery before another destination is replaced.
Resolve them with their owner; never delete the pending marker merely to retry.
The advanced legacy journal entry point remains available when an explicit
journal path is needed:

```bash
python3 "$SKILLS_REPO/scripts/project-install.py" \
  --source "$SKILLS_REPO" --project /absolute/path/to/project \
  --revision "<original-40-character-SHA>" --recover /absolute/path/to/journal.json
```

Those legacy source/revision arguments are syntactically required, but recovery
uses journal/backup evidence independently of source contents. Legacy `--apply`
requires an explicit `--backup-root`; use the root CLI for managed installation
and provenance-preserving updates.

## Runtime discovery and dependencies

Codex and Antigravity use `.agents/skills/<name>`; Claude Code uses the four
relative `.claude/skills/<name>` aliases. These follow the documented
[Codex](https://learn.chatgpt.com/docs/build-skills),
[Claude Code](https://code.claude.com/docs/en/skills) and
[Antigravity](https://antigravity.google/docs/skills) discovery layouts.
Filesystem integrity and official layout support do not prove activation,
provider precedence or successful workflow execution. No fresh runtime session
has been qualified by this installer work.

When native runtime access is available, open a fresh session from the project
root and inspect the selected paths for all four skills. Invoke `next-step`
with no pending work and `min-delivery check`; inspect ship/clean without running
shipping or cleanup. Keep native tool evidence separate from agent self-report;
record unknown capabilities/model metadata honestly. Do not change global
settings or delete personal/plugin providers to force precedence.

Prepare the target's owning dependencies and real `docs/min-delivery.md` where
required. [Superpowers](https://github.com/obra/superpowers) remains external.
Codex needs the bundled runtime adapter's model/delegation capabilities;
Antigravity uses the active session's selection. Missing capabilities block the
affected workflow. `ship-to-main` and `clean-worktree` discover the active project
contract using their bundled [project contract](../skills/ship-to-main/references/project-contract.md).
Required project guides and utilities remain mandatory; a missing optional guide
uses repository evidence and generic Git/forge checks. They do not import
Inailso commands into other projects. Installation supplies neither external
utilities nor authorization for publication or resource removal. See this
source repository's [delivery guide](min-delivery.md) for its own gates; target
projects keep their own instructions and guide.
Do not run bundled `min-delivery/scripts/sync-installations.py --apply` on a
project installation; that separate helper manages user-level aliases.
