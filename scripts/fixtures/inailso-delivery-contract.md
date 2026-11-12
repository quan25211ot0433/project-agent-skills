# Inailso delivery contract fixture

Simplified project requirements for portable-skill evaluation. These are raw
fixture inputs, not this source repository's operating instructions. The active
Inailso guide remains the owning authority in an actual Inailso checkout.

The active project requires its `docs/min-delivery.md` and applicable AGENTS
instructions. Implementation uses a linked worktree under recorded custody via
`node scripts/delivery/worktree-custody.mjs`; the primary checkout is preserved.

Select affected workspace test/type/lint/build tasks from actual manifests and
preview through `pnpm verify:workspaces`. Required graph analysis, documentation,
package-boundary and real persistence lanes remain applicable to their changed
boundaries. Validate PR bodies with `node scripts/ci/pr-body-contract.cjs`.

Required persistent self-hosted runner preflight uses
`scripts/ci/self-hosted-runner/manage.sh status`, with Linux and macOS runners
online. An unavailable runner or required utility is a prerequisite, not authority
to change infrastructure or substitute a weaker gate. Match CI to the exact head
and integrated revision. Preserve the original full base-to-integrated range
through follow-up repairs and run integrated local checks as well as real CI.

Cleanup uses the project utility's `--require-merged` proof mode and its recorded
source-head provenance, followed by the required
`scripts/delivery/close-merged-plan.mjs` closure contract. Missing required tooling
blocks its action; a generic fallback cannot waive it. Ignored/hidden state,
foreign ownership and active unowned processes preserve resources. Publication
and resource-removal authority come from the session, never this fixture.
