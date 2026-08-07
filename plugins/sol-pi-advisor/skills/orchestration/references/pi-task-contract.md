# Pi implementation task contract

Use this contract only after current-turn authorization for the Sol Pi Advisor
workflow. The primary Sol task owns design, verification, corrections, Git/PR
actions, review, and acceptance. Pi owns only implementation inside the supplied
packet and worktree.

## Tool sequence

1. Confirm prerequisites with `pi_lane_preflight`.
2. Resolve the canonical repository root and an exact intended base ref.
3. Build the dependency DAG and every complete task packet below before starting Pi.
4. For one serial slice, call `pi_lane_start`. For one wave of 2-4 independent
   slices with pairwise-disjoint ownership, call `pi_lane_batch_start`. Use
   `execution_mode: supervised-local`.
5. Record the batch identity when present and every returned run, session,
   worktree, base commit, revision, and process.
6. Wait using bounded `pi_lane_drive` calls for a serial lane or
   `pi_lane_batch_drive` for a parallel wave until all relevant lanes settle.
   Use `pause` for a recoverable safety review and `abort` only for permanent
   abandonment.
7. Inspect host-observed evidence and the actual worktree. Rerun checks independently.
8. Send corrections to the same run with `pi_lane_drive`; wait, inspect, and verify
   again.
9. Keep all commit, push, and PR operations outside Pi and after acceptance.

The primary must prove that siblings in one parallel wave have the same immutable
base, no dependency on another sibling's output, frozen shared contracts,
pairwise-disjoint `allowedPaths`, and independent acceptance tests. Parent/child
paths overlap. Shared files, lockfiles, generated artifacts, migrations, and
dependent state-machine changes stay serial. Corrections always use
`pi_lane_drive` on the exact affected run; batches do not have shared corrections.

Before step 3, reject or split a lane whose architecture is unsettled, whose
expected scope exceeds 12 changed files without written justification, or which
combines three or more independent high-risk domains. A speed-tier/default Pi model
is not sufficient evidence of fitness for cross-module security, atomicity, or
concurrency work. Ask the user to authorize a stronger model or reduce the slice.

## Required task packet

Replace every placeholder. A partial packet is invalid.

~~~text
ROLE
Act as the implementation worker in the Sol Pi Advisor workflow. Implement only the
settled specification and owned files. Do not redesign architecture, broaden scope,
revert unrelated edits, perform Git history or remote operations, or delegate work.

OBJECTIVE
<Observable outcome, why it matters, and exact acceptance conditions.>

LANE FIT AND BUDGET
- Slice: <One coherent vertical outcome; list later planned slices separately.>
- DAG position: <Serial dependency, or parallel wave/lane ID plus later dependencies.>
- Parallel siblings: <Lane IDs and their non-overlapping ownership, or none.>
- Frozen shared contracts: <Interfaces/schemas fixed by Sol before parallel start, or n/a.>
- Risk domains: <Exact domains; normally no more than two independent high-risk domains.>
- Expected diff: <Expected files/path prefixes and approximate size.>
- Settled Sol decisions: <Architecture, interfaces, trust/transaction ordering, and exclusions.>
- Failure invariants: <Negative paths that must fail closed or preserve prior state.>
- Pi model fit: <Observed/configured model facts and why this slice fits it.>
- Budget: initial implementation + at most two corrections; 45-minute checkpoint per turn.

FILES AND OWNERSHIP
You own only:
- <Exact repository-relative files or directory prefixes.>
You do not own:
- <Excluded paths and responsibilities.>
You are not alone in the codebase. Preserve other edits and stop with a blocker
before changing anything outside ownership.

INTERFACES
- <Signatures, schemas, commands, routes, APIs, and required behavior.>

CONSTRAINTS
- <Repository rules, safety limits, fixed decisions, and excluded scope.>
- Use the simplest implementation that fully satisfies this packet.
- Do not add compatibility layers for retired code unless explicitly required.

STARTING STATE
- Repository: <canonical root>
- Base ref and commit: <exact values>
- Environment: detached worktree managed by Sol Pi Advisor
- Run and session identity: <none for initial run; exact existing values for correction>
- Accepted dependency state: <exact commit or none>
- Batch/lane identity: <none for serial; batchId is assigned by the host and laneId is supplied by Sol>

VERIFICATION
- Baseline: <Focused test/lint/type-check commands and known failures before implementation.>
- Pi run: <focused, offline, package-scoped command that cannot install or resolve dependencies>
  Success: <expected exit status and concrete evidence>
- Primary run after handoff: <repository-wide, dependency-resolving, dead-code, or integration command>
  Success: <expected exit status and concrete evidence>
- First-candidate gate: <scope estimate comparison, package lint/type-check, standards/spec review.>
- Inspect: <diff, artifact, or runtime behavior>
  Success: <required evidence>

GIT / PR BOUNDARY
- You may use read-only `git status` and `git diff` commands.
- Do not run git add, commit, push, fetch, pull, merge, rebase, cherry-pick, reset,
  clean, checkout, switch, branch, tag, stash, or any PR command.
- Do not alter HEAD, refs, the index, `.git`, or another worktree.
- Put disposable experiments under `$SOL_PI_SCRATCH_DIR`; do not create repository
  scratch files.
- Do not run dependency installers/resolvers (`bunx`, `npx`, package-manager
  install/update commands) or repository-wide dead-code checks. Report those as
  primary-owned verification gaps instead of working around the restriction.

FINAL HANDOFF
Your final action must call `submit_handoff` exactly once with:
- status: complete | partial | blocked
- objective: one-line restatement
- changes: file-by-file summaries
- checks: exact commands and actual results
- gaps: unfinished work, blockers, or an empty list
- judgmentCalls: decisions left open by the packet or an empty list
Do not emit another assistant response after `submit_handoff`.
~~~

## Acceptance rules

Treat the structured handoff as an untrusted claim. Accept only after the primary
has inspected the complete actual diff, confirmed the changed-file scope, compared
HEAD with the base commit, rerun verification, and recorded the real worktree and
run state. In a parallel wave, accept or reject every lane independently. Then
apply only accepted patch artifacts to a dedicated integration worktree in DAG
order and run cross-lane verification. Corrections remain in the original run, Pi
session, and worktree.

Host-observed Git state and its digests are authoritative for mutation policy.
Never infer a lockfile or manifest mutation from command prose alone; confirm the
path in `dependencyStateChanges` or the actual diff. Use a recoverable pause while
that evidence is being inspected.

Do not accept a task packet that bundles independent product slices merely because
their files share a feature name. Do not use corrections as incremental discovery
of architecture. After two correction turns, stop when the same semantic defect
class remains, the diff has materially outgrown its estimate, or a new risk domain
appears. Replan/split or obtain explicit user authorization for a stronger model.
At 45 minutes, surface a checkpoint instead of silently polling further.
