---
name: orchestration
description: Orchestrate software delivery with a primary Codex task on any model or reasoning level that plans and accepts, one or more supervised local Pi coding-agent sessions on any model or Pi version that implement in isolated Git worktrees, and a fresh Sol / High native reviewer that returns the final verdict. Use only when the user explicitly asks to use Sol Pi Advisor, invokes this skill for implementation, or requests the primary-plan/Pi-implement/Sol-review route.
---

# Sol Pi Advisor

Use one serial implementation lane or one safe parallel wave:

~~~text
primary task / any model and reasoning level
  -> one local Pi lane OR 2-4 independent local Pi lanes in parallel worktrees
  -> primary lane-by-lane verification and integration
  -> fresh Sol / High review
~~~

Do not route implementation through Luna, a native worker, another Codex task, or
another external agent. Pi is the only implementation worker in this workflow.
Read [references/pi-task-contract.md](references/pi-task-contract.md)
before starting Pi. Read
[references/sol-review-contract.md](references/sol-review-contract.md) before
spawning the final reviewer. Read
[references/issues-contract.md](references/issues-contract.md) before decomposing
the goal or starting any Pi run.

## Require current-turn authorization

Start Pi only when the current user request explicitly asks to use Sol Pi Advisor,
the primary/Pi/Sol route, or this skill for implementation. Earlier authorization,
an ordinary coding request, or implicit skill matching is insufficient. If
current-turn authorization is absent, explain the route and stop before calling
`pi_lane_start`.

## Confirm prerequisites

1. Do not require, recommend, inspect, or reject the primary task based on its
   model or reasoning level. Any available primary model and reasoning level is
   eligible; the primary is responsible for the workflow duties below.
2. Resolve `../../scripts/install-agent.sh` from this file and run
   `sh <path> --check`. Require an exact installed
   `sol_pi_advisor_sol_reviewer` profile.
3. Confirm the native agent list exposes `sol_pi_advisor_sol_reviewer`.
4. Confirm the MCP tool list exposes `pi_lane_preflight`, `pi_lane_start`,
   `pi_lane_batch_start`, `pi_lane_drive`, and `pi_lane_batch_drive` from Sol Pi
   Advisor.
5. Call `pi_lane_preflight`. Require a usable Pi executable, Git executable, and
   available state directory. Record the reported Pi identity plus Pi and Node
   paths as diagnostics; do not infer them. Never reject, split, or redirect work
   based on the Pi version or its absence from a supported-version list.
6. This release supports only `supervised-local` execution. Pi has no built-in
   sandbox. State that fact before starting a run and stop if the user requests an
   unattended or untrusted-repository execution boundary.

## Gate lane fit before starting Pi

Derive every goal, task split, acceptance criterion, and bug fix from first
principles before assigning work. State the observable goal, the core problem that
prevents it, the smallest causal explanation supported by evidence, and the
non-negotiable invariants. Acceptance criteria must test the core behavior and its
failure boundary, not a proxy such as files changed, commands run, or worker prose.
For a bug, target the root cause; do not accept symptom suppression as a fix.

Before any Pi start, create or update repository-root `issues.md` using the issue
ledger contract. Decompose the settled goal into the complete known list of
fine-grained tasks, assign one stable ID to each entry, record dependencies and
acceptance invariants, and mark dispatchable entries `READY`. Do not call Pi with an
unlisted task. Schedule READY entries in dependency order, one at a time by default;
use a parallel wave only with a written independence and ownership rationale.
The MCP server requires the file, exact issue heading, and `READY` status before
creating a worktree, and `issues.md` is primary-owned—it must never appear in Pi
`allowedPaths`.

Treat `SUSPENDED` as a human-controlled exclusion state. Propose it only for an
issue already proven `NON-BLOCKING`, and apply it only after the user explicitly
chooses deferral. A suspended issue is outside READY selection, Pi start and
correction, active acceptance, completion counts, and reviewer `fix-first` routing.
Keep it in `issues.md` and disclose it as residual risk, but do not spend workflow
budget reconsidering it. Resume it only on an explicit user decision: change it to
`READY`, refresh its causal evidence and dependencies, then schedule normally.
Never suspend an active lane or a P0; settle or abort an active lane first.

Use Pi for one settled, fine-grained, independently testable task, not unresolved
architecture, a broad vertical slice, or a whole multi-system program. A lane should
normally own one behavior or one root-cause defect, one risk domain, one focused
acceptance test, and roughly 1-5 expected changed files. Before `pi_lane_start`,
write down the slice, first-principles causal model, risk domain, expected changed
paths, failure invariants, verification commands, and correction/time budget.
Lane-fit decisions must be based only on workflow shape, scope, ownership,
dependencies, and risk—not on model, provider, reasoning level, or Pi version.

Stop and split the work before starting Pi when any default replan trigger applies:

- the packet still asks Pi to choose architecture, trust boundaries, transaction
  ordering, public interfaces, or scope;
- the slice spans more than one independent risk domain such as cryptographic
  trust, durable transactions, concurrency/cache coherence, business credentials,
  public API compatibility, and UI state;
- the expected implementation exceeds 5 changed files or mixes a security/
  transaction/concurrency core with UI, localization, documentation, and release
  wiring in one lane.

These are replan triggers, not mechanical quotas. Exceed one only with a written
rationale in the packet and a user-visible warning. Split the work into a dependency
DAG before choosing execution order. A lane is eligible for the same parallel wave
only when all of the following are true:

- every sibling starts from the same immutable base commit;
- no sibling depends on another sibling's unaccepted implementation;
- repository-relative `allowedPaths` are pairwise disjoint, including parent/child
  path overlap;
- shared interfaces, schemas, generated artifacts, lockfiles, and behavioral
  contracts are already frozen by the primary; and
- each lane has an independent acceptance test and can be accepted or rejected
  without modifying a sibling lane.

Use `pi_lane_batch_start` for one wave of 2-4 qualifying lanes. The MCP server
rejects overlapping ownership before creating any worktree. Keep shared-file,
dependent, migration-order, and cross-cutting state-machine work serial. Execute a
later DAG wave only after the primary has accepted and integrated its dependencies.
Never create a new run merely to escape corrections on the current slice.

## Keep ownership in the primary task

The primary task must:

- resolve requirements and material ambiguity;
- derive the core problem, causal model, architecture, interfaces, scope, file
  ownership, and acceptance invariants from first principles;
- create and maintain the repository-root `issues.md` execution ledger, stable
  issue IDs, lifecycle state, dependency order, and run/session bindings;
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

Do not implement delegated changes in the primary task while Pi still has a retry
for the same core issue. Tighten the issue-specific packet and return it to the same
run/session. The bounded primary micro-fix loop below is the only exception after
Pi's retry budget is exhausted.

## Start and monitor Pi

Build every complete lane packet before calling `pi_lane_start` or
`pi_lane_batch_start`. Supply:

- the canonical Git repository root;
- an exact base ref chosen by the primary;
- the stable `issueId` from the repository-root `issues.md` entry;
- the complete task packet as one string;
- non-empty repository-relative allowed paths without globs; and
- optional provider, model, and thinking values only when explicitly requested or
  already configured. Pass them through without rating their suitability; omission
  means Pi chooses its own defaults.

For a parallel wave, also supply a stable lowercase `laneId` and a unique ledger
`issueId` for each lane. Record the returned `batchId` and every lane's issue ID,
run ID, Pi session ID, worktree, base commit, revision, and process metadata in
`issues.md`. All lanes in a batch share one base commit but have separate issue
entries, sessions, worktrees, ownership, corrections, and evidence.

Use `execution_mode: supervised-local`. Record the returned `runId`, Pi session ID,
bound issue ID, worktree, base commit, revision, and process metadata in the ledger.
Pi does not inherit the primary conversation; the packet must contain every
relevant decision.

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
instruction, concrete evidence, and a stable lowercase `issueId` that names the
first-principles root cause rather than its symptom. Corrections are lane-specific
and allowed only after that Pi turn settles; they must reuse the same run, session,
and worktree. Never send one sibling's defect as a correction to another sibling.
Repeat monitoring and verification.

The MCP server binds the initial `issueId` to the run manifest. A correction must
repeat that exact ID or it is rejected with `IssueIdMismatch`. If acceptance finds
a genuinely different root cause, add a new `issues.md` entry and assign a new ID
before scheduling a separate Pi task. Do not route it through the current session.

The returned `issueAttempts` map is authoritative. The same core issue may receive
at most two Pi correction turns. Reuse its `issueId` even when the visible symptom
changes; never rename an issue or start a replacement run to reset the counter. A
third correction is rejected with `PiIssueRetryLimit`. After the second failed
correction, stop sending that issue to Pi.

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

If the actual diff materially exceeds the estimate, a new risk domain appears, or
the correction requires architecture redesign, stop the lane and return to primary
planning. Split the slice or ask the user to choose a new direction. Do not grind
through an unbounded revision loop, and do not turn a workflow failure into a model
eligibility judgment.

## Close exhausted issues without looping

When the same core issue remains after two Pi corrections, reassess it from first
principles. The primary may enter a self-contained `fix -> focused test` loop only
when the remaining scope is genuinely tiny: one settled root cause, no architecture
or public-interface decision, no migration or trust-boundary change, a small local
edit, and one focused acceptance test. Keep the `issueId` and Pi evidence.

The primary gets at most two repair/test rounds for that issue. Each round must
record the causal hypothesis, exact edit, exact command, and actual result. Stop
immediately if the scope expands or an invariant becomes uncertain. Do not delegate
the issue back to Pi and do not create another Pi run.

If the issue still fails after two primary rounds, or was never eligible for the
micro-fix loop, update its existing `issues.md` entry to `OPEN`. Record the
first-principles root cause, failed acceptance invariant, both Pi attempts, any
primary attempts, smallest remaining scope, and the continuation decision.

- Mark an issue `P0` when it blocks the current goal or any dependent DAG node.
  Stop the affected goal and its dependents; never report them complete.
- Mark it `NON-BLOCKING` only when evidence proves the unresolved behavior cannot
  affect the current core path, safety invariants, or later task dependencies. It
  may remain documented while independent later goals continue to development and
  testing.
- If the user explicitly chooses not to pursue a proven `NON-BLOCKING` issue, mark
  it `SUSPENDED`, record the human decision and resume condition, and exclude it
  from later scheduling and acceptance consideration. Do not suspend automatically.

An unresolved issue must never disappear into chat history. A non-blocking issue is
residual risk, not a successful fix; a P0 issue is a blocker, not reviewer evidence.

Use a 45-minute wall-clock checkpoint for each Pi turn. At the checkpoint, report
elapsed time, current diff scope, completed checks, and the specific remaining
blocker. Do not silently keep polling or let a Pi turn run
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
independently reruns lane and cross-lane checks, and audits every `issues.md` entry,
binding, attempt count, unresolved defect, and human-suspended entry, spawn exactly:

~~~text
agent_type: sol_pi_advisor_sol_reviewer
fork_turns: none
~~~

Do not attach per-spawn model or reasoning overrides. Give the reviewer the complete
packet from the Sol review contract. The only verdicts are:

~~~text
ship | fix-first | rethink
~~~

- On `ship`, report completion with primary verification evidence, documented
  NON-BLOCKING issues, human-suspended issues, and residual risk. `ship` is
  forbidden while a P0 is open. A valid `SUSPENDED` issue does not block ship and
  must not be routed through `fix-first` unless the user resumes it.
- On `fix-first`, map the finding to its existing ledger root cause. If it is the
  same issue and has a Pi retry remaining, send it to the bound run/session. If it
  is a new root cause, create a new `issues.md` entry and ID before dispatch.
  Otherwise follow the bounded primary micro-fix rules. After any change, verify
  again and obtain a new fresh reviewer.
- On `rethink`, revise architecture with the user before further implementation.

Any post-review integrated change or lane/integration diff-digest change invalidates
the verdict. The reviewer must remain read-only and never implement findings.

## Preserve the Git boundary

Pi must never commit, add, push, fetch, pull, merge, rebase, cherry-pick, reset,
clean, create or delete branches, or perform any PR operation. Its only deliverable
is a working-tree diff. Worktree isolation is not a sandbox or merge-safety proof.
Keep shared-file and dependent work serial. This release supports one active serial
lane or one active parallel wave of at most four Pi lanes per repository.
