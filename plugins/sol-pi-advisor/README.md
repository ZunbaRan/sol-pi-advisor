# Sol Pi Advisor

Sol Pi Advisor keeps architecture and acceptance in a GPT-5.6 Sol Codex task at
`high`, `xhigh`, or `max` reasoning, delegates implementation to persistent local
Pi coding-agent sessions, and uses a fresh read-only Sol / High reviewer for the
final verdict.

Version 0.1 supports either one supervised local Git implementation lane or one
safe parallel wave of 2-4 independent lanes per repository. Every Pi works in its
own detached worktree, returns a structured handoff, and cannot commit, push,
merge, rebase, or operate on pull requests. Parallel waves require one immutable
base and pairwise-disjoint path ownership. The primary Sol task inspects every
actual diff, integrates accepted patches, and reruns verification independently.

`pi_lane_batch_start` creates the wave; `pi_lane_batch_drive` waits, recoverably
pauses, or permanently aborts active lanes. Corrections remain lane-specific
through `pi_lane_drive` and reuse the same Pi session after a pause. Shared-file and
dependent work is intentionally rejected from the parallel path and must run in a
later serial/DAG wave.

The supervisor checks actual Git state after completed Bash/handoff calls and at turn
settlement. Policy findings never depend on command-output phrases. Dependency
install/resolution and repository-wide dead-code checks stay with primary Sol, and
each run receives an external scratch directory for disposable experiments.

Pi does not provide a sandbox. This plugin's initial execution mode is explicitly
`supervised-local`; use it only with trusted repositories and review the returned
worktree before integration.

Use the bundled `$sol-pi-advisor:cleanup` skill after an accepted or explicitly
abandoned task batch. It defaults to dry-run, preserves minimal evidence, and
removes registered worktrees before deleting raw sessions and event logs.

Run `sh scripts/verify.sh` from the plugin root to validate the package.
