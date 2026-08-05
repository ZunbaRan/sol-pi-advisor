# Pi implementation task contract

Use this contract only after current-turn authorization for the Sol Pi Advisor
workflow. The primary Sol task owns design, verification, corrections, Git/PR
actions, review, and acceptance. Pi owns only implementation inside the supplied
packet and worktree.

## Tool sequence

1. Confirm prerequisites with `pi_lane_preflight`.
2. Resolve the canonical repository root and an exact intended base ref.
3. Build the complete task packet below before starting Pi.
4. Call `pi_lane_start` once with `execution_mode: supervised-local`.
5. Record the returned run, session, worktree, base commit, revision, and process.
6. Wait using bounded `pi_lane_drive` calls until `ready`, `needs-attention`,
   `failed`, or `aborted`.
7. Inspect host-observed evidence and the actual worktree. Rerun checks independently.
8. Send corrections to the same run with `pi_lane_drive`; wait, inspect, and verify
   again.
9. Keep all commit, push, and PR operations outside Pi and after acceptance.

## Required task packet

Replace every placeholder. A partial packet is invalid.

~~~text
ROLE
Act as the implementation worker in the Sol Pi Advisor workflow. Implement only the
settled specification and owned files. Do not redesign architecture, broaden scope,
revert unrelated edits, perform Git history or remote operations, or delegate work.

OBJECTIVE
<Observable outcome, why it matters, and exact acceptance conditions.>

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

VERIFICATION
- Run: <focused command>
  Success: <expected exit status and concrete evidence>
- Run: <broader command when needed>
  Success: <expected exit status and concrete evidence>
- Inspect: <diff, artifact, or runtime behavior>
  Success: <required evidence>

GIT / PR BOUNDARY
- You may use read-only `git status` and `git diff` commands.
- Do not run git add, commit, push, fetch, pull, merge, rebase, cherry-pick, reset,
  clean, checkout, switch, branch, tag, stash, or any PR command.
- Do not alter HEAD, refs, the index, `.git`, or another worktree.

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
run state. Corrections remain in the original run, Pi session, and worktree.
