---
name: orchestration
description: Orchestrate software delivery with a GPT-5.6 Sol primary task at high, xhigh, or max reasoning that plans and accepts, a supervised local Pi coding-agent session that implements in an isolated Git worktree, and a fresh Sol / High native reviewer that returns the final verdict. Use only when the user explicitly asks to use Sol Pi Advisor, invokes this skill for implementation, or requests the Sol-plan/Pi-implement/Sol-review route.
---

# Sol Pi Advisor

Use one serial implementation lane or one safe parallel wave:

~~~text
primary Sol / high-or-higher
  -> one local Pi lane OR 2-4 independent local Pi lanes in parallel worktrees
  -> primary lane-by-lane verification and integration
  -> fresh Sol / High review
~~~

Do not route implementation through Luna, Terra, a native worker, another Codex
task, or another external agent. Pi is the only implementation worker in this
workflow. Read [references/pi-task-contract.md](references/pi-task-contract.md)
before starting Pi. Read
[references/sol-review-contract.md](references/sol-review-contract.md) before
spawning the final reviewer.

## Require current-turn authorization

Start Pi only when the current user request explicitly asks to use Sol Pi Advisor,
the Sol/Pi/Sol route, or this skill for implementation. Earlier authorization, an
ordinary coding request, or implicit skill matching is insufficient. If current-turn
authorization is absent, explain the route and stop before calling `pi_lane_start`.

## Confirm prerequisites

1. Run the primary task on `gpt-5.6-sol` with reasoning set to `high`, `xhigh`, or
   `max`. Use exposed runtime metadata when available. These three values are all
   valid; do not reject `xhigh` or `max` for exceeding the minimum. If the model is
   different or reasoning is below `high`, ask the user to start an eligible Sol
   task and stop. Never claim an unobserved value.
2. Resolve `../../scripts/install-agent.sh` from this file and run
   `sh <path> --check`. Require an exact installed
   `sol_pi_advisor_sol_reviewer` profile.
3. Confirm the native agent list exposes `sol_pi_advisor_sol_reviewer`.
4. Confirm the MCP tool list exposes `pi_lane_preflight`, `pi_lane_start`,
   `pi_lane_batch_start`, `pi_lane_drive`, and `pi_lane_batch_drive` from Sol Pi
   Advisor.
5. Call `pi_lane_preflight`. Require a usable Pi executable, Git executable, and
   available state directory. Record the actual Pi version plus Pi and Node paths;
   do not infer them. Do not reject an installed Pi based on its version number;
   validate compatibility through the lane's observed behavior and verification.
6. This release supports only `supervised-local` execution. Pi has no built-in
   sandbox. State that fact before starting a run and stop if the user requests an
   unattended or untrusted-repository execution boundary.

## Gate lane fit before starting Pi

Use Pi for one settled vertical slice, not for unresolved architecture or a whole
multi-system program. Before `pi_lane_start`, write down the slice, risk domains,
expected changed paths, failure invariants, verification commands, model fit, and
the correction/time budget.

Stop and split the work before starting Pi when any default replan trigger applies:

- the packet still asks Pi to choose architecture, trust boundaries, transaction
  ordering, public interfaces, or scope;
- the slice spans three or more independent risk domains such as cryptographic
  trust, durable transactions, concurrency/cache coherence, business credentials,
  public API compatibility, and UI state;
- the expected implementation exceeds 12 changed files or mixes a security/
  transaction/concurrency core with UI, localization, documentation, and release
  wiring in one lane; or
- the configured/default Pi model is unobserved or is a speed-tier model (for
  example a `flash`/`mini` variant) while the slice depends on cross-module security,
  atomicity, or concurrency reasoning.

These are replan triggers, not mechanical quotas. Exceed one only with a written
rationale in the packet and a user-visible warning. Split the work into a dependency
DAG before choosing execution order. A lane is eligible for the same parallel wave
only when all of the following are true:

- every sibling starts from the same immutable base commit;
- no sibling depends on another sibling's unaccepted implementation;
- repository-relative `allowedPaths` are pairwise disjoint, including parent/child
  path overlap;
- shared interfaces, schemas, generated artifacts, lockfiles, and behavioral
  contracts are already frozen by Sol; and
- each lane has an independent acceptance test and can be accepted or rejected
  without modifying a sibling lane.

Use `pi_lane_batch_start` for one wave of 2-4 qualifying lanes. The MCP server
rejects overlapping ownership before creating any worktree. Keep shared-file,
dependent, migration-order, and cross-cutting state-machine work serial. Execute a
later DAG wave only after the primary has accepted and integrated its dependencies.
Never create a new run merely to escape corrections on the current slice.

## Keep ownership in the primary Sol task

The primary task must:

- resolve requirements and material ambiguity;
- choose architecture, interfaces, scope, and file ownership;
- classify the implementation DAG into serial dependencies and safe parallel waves;
- write the complete Pi task packet;
- select an exact Git base ref and inspect the returned run, session, worktree,
  base commit, HEAD, changed paths, policy findings, and complete diff artifact;
- rerun verification independently inside the actual Pi worktree;
- send precise corrections to the same Pi run and session;
- accept every parallel lane independently, then apply accepted diff artifacts in
  dependency order to a dedicated integration worktree and run cross-lane checks;
- authorize and perform any later commit, push, or PR action outside Pi; and
- accept or reject the final result.

Do not implement delegated changes in the primary task merely to repair an
incomplete Pi result. Tighten the packet and return corrections to the same run.

## Start and monitor Pi

Build every complete lane packet before calling `pi_lane_start` or
`pi_lane_batch_start`. Supply:

- the canonical Git repository root;
- an exact base ref chosen by the primary;
- the complete task packet as one string;
- non-empty repository-relative allowed paths without globs; and
- optional provider, model, and thinking values only when explicitly settled.

For a parallel wave, also supply a stable lowercase `laneId` for each lane. Record
the returned `batchId` and every lane's run ID, Pi session ID, worktree, base commit,
revision, and process metadata. All lanes in a batch share one base commit but have
separate sessions, worktrees, ownership, corrections, and evidence.

Use `execution_mode: supervised-local`. Record the returned `runId`, Pi session ID,
worktree, base commit, revision, and process metadata. Pi does not inherit the
primary conversation; the packet must contain every relevant decision.

Monitor a serial lane with bounded `pi_lane_drive` calls using `directive: wait`.
Monitor a parallel wave with bounded `pi_lane_batch_drive` calls; it settles only
after every lane settles. Treat a `running` result as progress, not failure. Treat
Pi prose and every structured handoff as claims. A `ready` lane is only a candidate
and must include host-observed Git evidence. Batch `ready` means every lane is ready
for inspection, not that the combined feature is accepted.

If a running lane needs safety inspection but may still be recoverable, use
`directive: pause`, not `abort`. Pause stops the current turn, records Git evidence,
and settles the lane as `needs-attention`; after primary inspection, a precise
`correct` directive reuses the same run, Pi session, and worktree. Reserve `abort`
for intentional permanent abandonment. Apply the same distinction to a parallel
wave with `pi_lane_batch_drive`.

Base policy decisions on the returned `policyBasis: git-worktree-state`, changed
paths, dependency-state changes, violations, and digests. Command output is only
diagnostic evidence. A line such as `Saved lockfile` does not prove a mutation when
the host-observed Git state reports no lockfile change. Conversely, a clean-looking
log never overrides an actual Git violation.

Inspect each complete diff artifact and changed paths, confirm ownership, and rerun
every stated verification command independently. If correction is required, call
`pi_lane_drive` for that exact run with `directive: correct`, the precise
instruction, and concrete evidence. Corrections are lane-specific and allowed only
after that Pi turn settles; they must reuse the same run, session, and worktree.
Never send one sibling's defect as a correction to another sibling. Repeat
monitoring and verification.

Keep Pi verification focused, offline, and package-scoped. Dependency resolution,
dependency installation, and repository-wide dead-code checks such as
`bun run dead-code`, `bunx`, `npx`, or `knip` are primary-owned integration checks.
If the lane environment lacks a dependency, Pi must report the blocked check and
must not install, copy, or synthesize dependencies. Run disposable experiments only
under the returned `scratchDir`, never as repository scratch files.

Run the first acceptance gate as soon as the initial candidate is `ready`, before
building a large correction packet:

- compare actual paths and diff size with the lane-fit estimate;
- run diff/ownership checks, focused tests, package-scoped lint, and type checks;
- review both documented standards and the originating spec;
- trace negative paths manually for security, trust, transaction, credential,
  concurrency, and stale-authority invariants; and
- distinguish baseline failures from candidate failures with evidence.

Treat green tests as evidence, never as semantic acceptance. A candidate that grows
outside the planned risk domains must be replanned, not normalized by adding more
tests after the fact.

Use an initial implementation turn plus at most two correction turns per lane by
default. If the same semantic defect class survives the second correction, the
actual diff grows by roughly 50% beyond the estimate, a new risk domain appears, or
the correction requires architecture redesign, stop the lane and return to Sol
planning. Split the slice, explicitly select a stronger Pi model/provider when the
user authorizes it, or ask the user to choose a new direction. Do not grind through
an unbounded revision loop.

Use a 45-minute wall-clock checkpoint for each Pi turn. At the checkpoint, report
elapsed time, observed model/provider, current diff scope, completed checks, and the
specific remaining blocker. Do not silently keep polling or let a Pi turn run
overnight; require explicit user direction before extending the budget.

Do not create a replacement run to bypass a correction loop. Any lane correction
increments the run revision and invalidates all earlier verification evidence,
diff digests, acceptance, and reviewer verdicts.

After every lane in a wave is independently accepted, apply only the accepted patch
artifacts to a dedicated integration worktree. Do not merge Pi branches (Pi has
none), copy whole worktrees, or hand-resolve an ownership collision. A collision
means the wave was partitioned incorrectly: stop and replan. Run the cross-lane
tests against the integrated diff before requesting final review.

## Obtain fresh Sol review

After the primary accepts every lane, integrates their immutable patch artifacts,
and independently reruns lane and cross-lane checks, spawn exactly:

~~~text
agent_type: sol_pi_advisor_sol_reviewer
fork_turns: none
~~~

Do not attach per-spawn model or reasoning overrides. Give the reviewer the complete
packet from the Sol review contract. The only verdicts are:

~~~text
ship | fix-first | rethink
~~~

- On `ship`, report completion with primary verification evidence and residual risk.
- On `fix-first`, send corrections to the same Pi run, verify again, and obtain a
  new fresh reviewer.
- On `rethink`, revise architecture with the user before further implementation.

Any post-review integrated change or lane/integration diff-digest change invalidates
the verdict. The reviewer must remain read-only and never implement findings.

## Preserve the Git boundary

Pi must never commit, add, push, fetch, pull, merge, rebase, cherry-pick, reset,
clean, create or delete branches, or perform any PR operation. Its only deliverable
is a working-tree diff. Worktree isolation is not a sandbox or merge-safety proof.
Keep shared-file and dependent work serial. This release supports one active serial
lane or one active parallel wave of at most four Pi lanes per repository.
