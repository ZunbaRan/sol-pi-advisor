---
name: cleanup
description: Inspect, archive, and safely remove completed or abandoned Sol Pi Advisor runs, including their detached Git worktrees, Pi sessions, event JSONL files, and revision artifacts. Use when a Sol Pi Advisor task batch is finished, disk usage under the Adviser state directory needs reclaiming, or stale terminal runs and worktrees need post-task cleanup.
---

# Clean Sol Pi Advisor Runs

Use the bundled cleanup script. It is dry-run by default and cleans exactly one
run/lane at a time. Parallel-wave lanes retain their shared `batchId` and `laneId`
in inventory and archive evidence; clean each only after the combined integration
outcome is established. Never replace Git-aware worktree removal with `rm`.

## Resolve the script

Resolve `scripts/cleanup-runs.py` relative to this `SKILL.md`. Invoke it with
`python3` and absolute paths.

## Inventory

List durable runs before selecting cleanup targets:

```sh
python3 <cleanup-runs.py> list
```

Treat only `ready`, `needs-attention`, `failed`, and `aborted` as terminal.
Never clean `preparing`, `running`, or `aborting` runs, or a run whose recorded
supervisor/Pi process is still alive.

If a dead run is stranded in `preparing` or `aborting`, finish its lifecycle with
the Adviser `pi_lane_drive` abort directive first. The cleanup skill must not
rewrite lifecycle state files.

## Establish the outcome

For an accepted run, confirm all of the following before cleanup:

- the candidate diff was integrated into a durable Git commit;
- the primary independently verified the candidate;
- the final fresh Sol reviewer returned `ship`; and
- the acceptance test summary is available.

Use `--outcome accepted`, the immutable accepted commit, `--review-verdict ship`,
and a concise `--test-summary`.

For an intentionally abandoned run, obtain explicit user authorization to discard
its unaccepted worktree changes. Use `--outcome discarded` and a concrete
`--discard-reason`.

## Dry-run first

Choose an archive directory outside the Adviser state root. Prefer the consuming
repository's durable evidence directory, for example
`docs/release-evidence/sol-pi`.

Accepted candidate:

```sh
python3 <cleanup-runs.py> clean <run-id> \
  --archive-dir <absolute-evidence-directory> \
  --outcome accepted \
  --accepted-commit <immutable-commit> \
  --review-verdict ship \
  --test-summary <concise-test-summary>
```

Discarded candidate:

```sh
python3 <cleanup-runs.py> clean <run-id> \
  --archive-dir <absolute-evidence-directory> \
  --outcome discarded \
  --discard-reason <why-the-candidate-is-being-discarded>
```

Report the proposed archive, worktree action, original byte count, and blockers.
Do not continue if the script reports an error.

## Execute only after approval

Cleanup deletes uncommitted files from the detached Pi worktree and removes raw
run logs. Obtain explicit user approval after showing the dry-run result. Then
repeat the exact command with `--execute`.

The script performs this order:

1. Revalidate terminal state, dead processes, repository, managed paths, patch
   digest, and accepted commit where applicable.
2. Atomically archive `cleanup-evidence.json` and the final patch, if present.
3. Remove the registered dirty worktree with `git worktree remove --force`; the
   force is intentional only after evidence and outcome validation.
4. Run `git worktree prune`.
5. Remove the run directory containing sessions, event JSONL, intermediate
   patches, and logs.

If execution stops after archiving, retain the archive and rerun the same command.
The archive is reusable only when its run identity, outcome, commit, and patch
digest match exactly.

## Verify the result

Run inventory again and confirm:

- the run no longer appears;
- the managed worktree is no longer registered;
- the evidence archive exists; and
- reclaimed bytes are reported.

Do not delete the archive. Git contains the accepted code; the archive retains the
minimal audit trail; Adviser sessions and event streams are temporary data.
