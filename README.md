# Project agent skills

Install four complete skill bundles as independent project-local copies with
[`project-skills`](docs/installation.md). Use a reviewed compatible Git commit
and inspect the [source provenance](source-provenance.json) before installing.

| Skill | Scope and prerequisites |
| --- | --- |
| [next-step](skills/next-step/SKILL.md) | Session follow-up within the project's instructions and authorization. Includes its `agents/openai.yaml` metadata. |
| [min-delivery](skills/min-delivery/SKILL.md) | Delivery coordination; requires the external owning skills, runtime adapter, model and delegation capabilities described in its bundle. |
| [ship-to-main](skills/ship-to-main/SKILL.md) | Project-aware shipping with revision-bound CI and integration proof; discovers required project gates and preserves owned verification worktrees. |
| [clean-worktree](skills/clean-worktree/SKILL.md) | Project-aware retirement with ignored-state preservation, custody and integration proof; preserves resources when ownership or proof is unresolved. |

The root executable accepts a clean local Git source or a public GitHub snapshot:

```bash
/path/to/compatible-clone/project-skills install --from /path/to/clean-source
/path/to/compatible-clone/project-skills install --from github:owner/repo --revision "<reviewed-compatible-ref>"
/path/to/compatible-clone/project-skills check
/path/to/compatible-clone/project-skills update --revision "<reviewed-compatible-ref>"
```

Run from the target project's Git checkout, or supply `--project /absolute/path`.
Follow the [bootstrap and installation guide](docs/installation.md) first. The
CLI requires a compatible source commit containing the root executable and
`project-skills-source.json`. Verify the selected ref before use; branch names and
PR state do not establish compatibility. No released tag or npm/npx package is
claimed.

Codex and Antigravity use the copies in `.agents/skills`; Claude Code uses four
relative links in `.claude/skills` pointing to those same copies. These are the
documented discovery layouts, not evidence of activation in a fresh runtime.
No fresh-session runtime qualification is claimed.

Updates are explicit and refuse installed drift. The exact v1 receipt remains
`.agents/project-skills.json`; a transaction-owned source sidecar records origin,
pin and Claude alias ownership. Same-volume backups/cache default to
`.project-skills/`, outside discovery. An exclusive project lock, verified
backups and durable journal support interruption recovery with `project-skills
recover`, even offline without the original source/cache. See the guide for
legacy migration, dependency checks and recovery limits.

Project installations are independent copies; no live source links, automatic
updates or global settings changes are made. The bundled user-level
`sync-installations.py` is a separate operation and refuses project installations.
Inailso's indexed `tools/project-agent-skills` gitlink must separately match the
receipt revision where project policy requires it; this installer does not change
that pin or policy.

[Superpowers](https://github.com/obra/superpowers) remains an external dependency.
Project-specific custody, PR validation, closure and cleanup utilities are not
distributed here. Shipping and cleanup discover the active project contract;
required utilities remain mandatory, while projects without them use the
documented generic checks. Installing skills does not authorize publication or
resource removal.
The min-delivery version/manifest describes that bundle, not a repository release.
No license has been selected.

For contributions, run `python3 -B scripts/check.py` from this checkout. See the
[repository delivery guide](docs/min-delivery.md) for prerequisites, CI evidence,
worktree ownership and closure.
