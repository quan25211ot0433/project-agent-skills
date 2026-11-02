# Project agent skills

Initial public source snapshot of four existing skill bundles. Start with the
[manual installation guide](docs/installation.md) and inspect the
[source provenance and file hashes](source-provenance.json).

| Skill | Scope and prerequisites |
| --- | --- |
| [next-step](skills/next-step/SKILL.md) | Generic session follow-up workflow; follows the target project's instructions and authorization boundaries. |
| [min-delivery](skills/min-delivery/SKILL.md) | Generic delivery coordinator with external owning-skill dependencies, including Superpowers. Requires the runtime adapters, model selection, and delegation capabilities documented in its bundle. |
| [ship-to-main](skills/ship-to-main/SKILL.md) | **REFERENCE-ONLY.** Archived Inailso shipping workflow with an inherited destructive worktree recipe; review and adapt it before direct activation in any project, including Inailso. |
| [clean-worktree](skills/clean-worktree/SKILL.md) | **REFERENCE-ONLY.** Archived Inailso retirement workflow depends on `ship-to-main` and inherits its worktree hazards; review and adapt before direct activation, including in Inailso. |

Keep both reference-only bundles outside every skill discovery directory until
review and adaptation are complete, including in the original Inailso project.
The inherited `ship-to-main` recipe reuses an existing `VERIFY_WT` with
`checkout --detach`, `reset --hard`, and `clean -fd` before an explicit dirty-work
and ownership preflight, and later uses forced worktree removal. It can discard
tracked or untracked work or disrupt another session's processes. Before any
activation, require preservation of all local work, proof of worktree ownership,
a clean-state check before destructive actions, and identification and shutdown
of only owned processes; preserve the worktree when any check is unresolved.
The installation guide describes [the required review](docs/installation.md#reference-only-inailso-workflows).

Their original project-document links
require access to the private Inailso repository; those documents and supporting
application utilities are not included here.

The bundled policies and behavior are preserved. Absolute personal home prefixes
in published Markdown are replaced with `${HOME}`, and original project-document
links are labeled and mapped to their owner. The provenance file records these
editorial changes and original/public SHA-256 hashes. The min-delivery bundle's
existing version metadata and manifest describe that copied bundle, not a release
of this repository.

This snapshot provides source folders and manual copy instructions. Runtime
discovery is separate from successful workflow execution. There is no automatic
installer, provider override mechanism, or seven-host qualification claim.
Superpowers is an external dependency and is not vendored; follow its
[upstream installation instructions](https://github.com/obra/superpowers).
No license has been selected for this snapshot.
