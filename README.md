# Project agent skills

Four complete skill bundles for project-local installation. Use the
[pinned installation guide](docs/installation.md), inspect the
[source provenance](source-provenance.json), and review the selected Git commit
before installing.

| Skill | Scope and prerequisites |
| --- | --- |
| [next-step](skills/next-step/SKILL.md) | Session follow-up within the project's instructions and authorization. Includes its `agents/openai.yaml` metadata. |
| [min-delivery](skills/min-delivery/SKILL.md) | Delivery coordination; requires the external owning skills, runtime adapter, model and delegation capabilities described in its bundle. |
| [ship-to-main](skills/ship-to-main/SKILL.md) | Inailso shipping workflow with owned verification worktrees and preservation preflight; requires Inailso project utilities and policies. Adapt and validate before using elsewhere. |
| [clean-worktree](skills/clean-worktree/SKILL.md) | Inailso retirement workflow with ignored-state preservation, custody and merge proof; requires its project utilities and shipping workflow. Adapt and validate before using elsewhere. |

The root `scripts/project-install.py` helper installs all four bundles into
`.agents/skills` from the selected clean Git commit. It includes every tracked
payload file and Git executable mode, requires exact destination preimages,
and records the source revision and complete file hashes in
`.agents/project-skills.json`. First adoption of existing folders requires a
reviewed preimage inventory. Updates refuse local drift.

An exclusive project lock serializes apply and recovery. Verified backups,
staging and a durable recovery journal stay outside discovery; a pending marker
blocks another installation after interruption. Recovery validates every current
pre/postimage before restoring installation-owned paths. The guide documents
check, apply and explicit recovery commands.

The archived destructive verification-worktree recipe has been replaced with
owned-worktree and complete-state checks, backed by real Git/filesystem tests.
This source change does not certify runtime activation. Inailso-specific links,
PR validation, custody, close-plan and cleanup commands still require the owning
project; those application utilities are not distributed here.

Project installations are independent copies. The bundled user-level
`sync-installations.py` is a separate operation and refuses a project-installed
bundle. Personal/global skills and settings are outside this installer's scope.

[Superpowers](https://github.com/obra/superpowers) remains an external dependency.
The min-delivery version/manifest describes that bundle, not a repository release.
No license has been selected. Codex and Antigravity discovery and successful
workflow execution require the fresh-session checks in the guide; this repository
does not claim qualification for other runtimes.
