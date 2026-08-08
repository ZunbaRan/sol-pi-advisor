# Sol Pi Advisor

Sol Pi Advisor keeps architecture and acceptance in the primary Codex task,
delegates implementation to persistent local Pi coding-agent sessions, and uses a
fresh read-only Sol / High reviewer for the final verdict. The primary and Pi may
use any available model, provider, and reasoning configuration, and any installed
Pi version; the plugin enforces the workflow rather than model eligibility.

Goals, task splits, acceptance criteria, and bug fixes start from the core problem,
causal evidence, and required invariant. Each Pi lane is a fine-grained task. A
repository-root `issues.md` execution ledger is created before dispatch, assigns a
stable ID to every task, and schedules READY entries one at a time by default. Each
Pi run/lane binds one listed `issueId` to one session. A failed acceptance issue
returns to that session; missing or mismatched IDs are rejected, and the MCP host
permits two Pi corrections before rejecting a third. An eligible micro-fix then
receives at most two primary repair/test rounds. Remaining entries become `P0`
blockers or proven `NON-BLOCKING` residuals.

The MCP host rejects a start unless repository-root `issues.md` contains the exact
issue heading with status `READY`. The ledger remains primary-owned and cannot be
assigned to Pi. With an explicit user decision, a proven-independent
`NON-BLOCKING` issue may become `SUSPENDED`; it is excluded from Pi dispatch and
correction, active acceptance, and completion counts until the user resumes it.

Version 0.1 supports either one supervised local Git implementation lane or one
safe parallel wave of 2-4 independent lanes per repository. Every Pi works in its
own detached worktree, returns a structured handoff, and cannot commit, push,
merge, rebase, or operate on pull requests. Parallel waves require one immutable
base and pairwise-disjoint path ownership. The primary task inspects every
actual diff, integrates accepted patches, and reruns verification independently.

`pi_lane_batch_start` creates the wave; `pi_lane_batch_drive` waits, recoverably
pauses, or permanently aborts active lanes. Corrections remain lane-specific
through `pi_lane_drive` and reuse the same Pi session after a pause. Shared-file and
dependent work is intentionally rejected from the parallel path and must run in a
later serial/DAG wave.

The supervisor checks actual Git state after completed Bash/handoff calls and at turn
settlement. Policy findings never depend on command-output phrases. Dependency
install/resolution and repository-wide dead-code checks stay with the primary task, and
each run receives an external scratch directory for disposable experiments.

Pi does not provide a sandbox. This plugin's initial execution mode is explicitly
`supervised-local`; use it only with trusted repositories and review the returned
worktree before integration.

Use the bundled `$sol-pi-advisor:cleanup` skill after an accepted or explicitly
abandoned task batch. It defaults to dry-run, preserves minimal evidence, and
removes registered worktrees before deleting raw sessions and event logs.

Run `sh scripts/verify.sh` from the plugin root to validate the package.
