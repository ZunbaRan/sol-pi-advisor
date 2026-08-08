# Fresh Sol final-review contract

Spawn `sol_pi_advisor_sol_reviewer` only after the primary task has inspected
and accepted every actual Pi diff, integrated accepted patch artifacts, and
independently rerun lane and cross-lane verification. The reviewer has one
read-only final-review mode.

~~~text
ROLE
Act as a fresh final reviewer. Remain behaviorally read-only. Do not edit files,
implement fixes, broaden scope, or redesign merely to express a preference.

STATED GOAL
<User outcome and acceptance condition.>

ACCUMULATED CHANGE SET
- Initial issues.md decomposition and final ledger: <complete entries and diff>
- Execution shape: <serial lane or parallel DAG waves>
- Batch IDs, lane IDs, run IDs, and revisions: <exact values>
- Stable issue IDs plus one-to-one run/session bindings: <exact manifest and ledger values>
- Pi attempts used per issue: <exact issueAttempts values; maximum two each>
- Primary micro-fix rounds per exhausted issue: <zero, one, or two with evidence>
- Pi session IDs and worktrees: <actual values>
- Shared base commit plus each lane HEAD: <exact values>
- Per-lane diff digests and complete diff artifacts: <host-observed values/paths>
- Per-lane allowed and changed paths: <exact ownership comparison>
- Planned diff/risk domains vs actual diff/risk domains per lane: <exact comparison>
- Integration worktree, base, HEAD, complete diff, and digest: <actual values>
- Integration order and collision result: <DAG order; must report zero ownership collisions>
- Repository-root issues.md audit: <all planned/resolved/exhausted/suspended issues, lifecycle state, classification, human suspension evidence, resume condition, and continuation decisions>

INTERFACES AND CONSTRAINTS
- <Required interfaces, repository rules, safety limits, and excluded scope.>

PRIMARY VERIFICATION EVIDENCE
- first-principles goal -> core problem -> task split -> acceptance-invariant mapping
- every dispatched run/lane issueId -> exactly one pre-existing issues.md entry
- per-lane <command> -> <actual output evidence>
- cross-lane/integration <command> -> <actual output evidence>
- per-lane artifact or diff inspection -> <actual evidence>
- first-candidate standards/spec gates -> <actual evidence and when each ran>
- ownership, overlap, integration, and Git-policy audit -> <actual evidence>

REVIEW
Inspect the integrated files, combined change set, and every lane artifact. Judge correctness, completeness,
regressions, scope discipline, interface preservation, test adequacy, and material
risk. Treat Pi's handoff as a claim rather than proof.

SOL REVIEW
VERDICT: ship | fix-first | rethink
REASON: <decisive evidence-based reason>
FINDINGS: <precise file references and required fixes, or none>
RESIDUAL RISK: <largest remaining risk, or none>
~~~

Use `fix-first` only for bounded required corrections. Use `rethink` when the chosen
architecture or ownership is unsound. Also use `rethink` when a blocking semantic
defect remains after bounded recovery or the candidate materially exceeded its
planned scope/risk domains without an accepted rationale. Never base a verdict on
the primary or Pi model, provider, reasoning level, or Pi version. Any
implementation change invalidates the verdict and requires a new reviewer instance.

Do not request a third Pi correction for the same root cause. Verify that each
acceptance failure returned to its original Pi session with one stable `issueId`,
that `issueAttempts` never exceeds two, and that any primary micro-fix loop also
stopped after two rounds. An unresolved P0 forbids `ship`. A NON-BLOCKING exhausted
issue may remain only when `issues.md` proves it is independent of the shipped core
path and records it as residual risk.

Treat a valid `SUSPENDED` issue as outside active delivery consideration: confirm
that it is `NON-BLOCKING`, records an explicit user decision and resume condition,
was not dispatched or corrected after suspension, and is disclosed as residual
risk. Do not emit `fix-first` for it unless the user explicitly resumed it. Reject
the ledger audit if a P0 or active dependency was hidden through suspension.

Reject any delivery that started Pi before creating the issue ledger, dispatched an
unlisted ID, bound one issue to multiple replacement sessions, corrected a run with
a different issue ID, or hid a newly discovered root cause inside another entry.
