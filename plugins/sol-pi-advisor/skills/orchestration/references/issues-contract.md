# Issue ledger contract

Use this contract before any Pi run and throughout the delivery workflow. The
primary task owns the ledger. Pi must not create or edit it.

Create or update `issues.md` at the consuming repository root before calling
`pi_lane_start` or `pi_lane_batch_start`. Preserve unrelated content and existing
stable IDs. Decompose the entire settled goal from first principles into
fine-grained, independently verifiable work items. Give every item one stable
lowercase ID, preferably sequential `issue-001`, `issue-002`, and so on. Allocate
the next unused number; never renumber an existing item.

Each issue must represent one observable behavior or one root cause. One Pi run or
parallel lane binds exactly one issue ID to one Pi session. Schedule READY issues in
dependency order, one at a time by default. A parallel wave is allowed only when
the ledger proves the entries are independent, start from the same base, have
frozen shared contracts, and own disjoint paths.

`SUSPENDED` is an explicit human deferral, not an automatic recovery outcome. Use
it only after the user chooses to defer an issue and evidence proves that it is
independent of the current main flow, safety invariants, and every active DAG
dependency. A suspended issue must be `NON-BLOCKING`. It is excluded from READY
selection, Pi start/correction, active acceptance, completion counts, and
`fix-first` routing. Keep it visible in the ledger and final residual-risk report,
but do not ask the final reviewer to reconsider the deferred fix. Resume it only
after an explicit user decision by changing it to `READY` and refreshing its scope,
dependencies, ownership, and acceptance evidence. Never suspend an active lane;
settle or abort the lane first. Never suspend a P0.

If acceptance reveals another symptom of the same root cause, keep the existing ID
and return it to its bound Pi session. If it reveals a genuinely different root
cause, add a new ledger entry and ID before scheduling it as a separate task. Never
smuggle a new issue into another issue's correction packet.

## Lifecycle

Use these statuses:

- `READY`: first-principles scope, dependencies, ownership, and acceptance are set.
- `IN_PROGRESS`: bound Pi run/session is active.
- `VERIFYING`: Pi candidate is under primary acceptance.
- `PRIMARY_REPAIR`: two Pi corrections were exhausted and an eligible micro-fix is
  in the primary's bounded repair/test loop.
- `RESOLVED`: the core acceptance invariant passed with recorded evidence.
- `OPEN`: unresolved after its allowed recovery path or not eligible for repair.
- `SUSPENDED`: explicitly deferred by the user, proven non-blocking, and excluded
  from scheduling and active acceptance until the user explicitly resumes it.

Use `NORMAL` while an issue follows the ordinary queue. Reclassify an unresolved
issue from dependency and acceptance evidence:

- `P0`: blocks the current goal, a required invariant, or any dependent DAG node.
  Stop the affected goal and its dependents and never claim completion.
- `NON-BLOCKING`: proven independent of the current core path, safety invariants,
  and later task dependencies. Independent goals may continue, but the issue stays
  visible as residual risk.

## Required entry

~~~markdown
# Issues

## issue-001: <short core-problem title>

- Status: READY | IN_PROGRESS | VERIFYING | PRIMARY_REPAIR | RESOLVED | OPEN | SUSPENDED
- Classification: NORMAL | P0 | NON-BLOCKING
- Goal / user outcome: <observable result>
- First-principles root cause: <smallest causal explanation supported by evidence>
- Core acceptance invariant: <behavior and failure boundary that must hold>
- Dependencies: <issue IDs or none>
- Dispatch order: <why this item is next; serial by default or parallel-wave rationale>
- Ownership: <expected repository-relative paths; normally 1-5 files>
- Focused verification: <exact command/inspection and success evidence>
- Pi binding: <runId and piSessionId after start, or unassigned>
- Pi attempts: <attempt 1 and 2 instructions, evidence, checks, and actual results>
- Primary attempts: <round 1 and 2 edits, commands, and actual results, or not eligible>
- Current evidence: <candidate result, reproduction, diff state, and exact failing command>
- Suspension decision: <n/a, or explicit user decision, non-blocking evidence, and date/context>
- Resume condition: <n/a, or the user decision/evidence that returns this issue to READY>
- Continuation decision: <next issue, stop affected flow, or continue named independent issues>
- Next action: <concrete queued or unresolved action>
~~~

Update the entry at every lifecycle boundary: before dispatch, after receiving the
run/session binding, before and after each acceptance attempt, and at final
resolution or exhaustion. Never downgrade a P0 merely to keep moving. Never mark
an issue non-blocking because unrelated tests are green. Classification follows
the dependency DAG, failed invariant, and observable user impact.
