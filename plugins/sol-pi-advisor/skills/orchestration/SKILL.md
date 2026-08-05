---
name: orchestration
description: Orchestrate software delivery with a GPT-5.6 Sol primary task at high, xhigh, or max reasoning that plans and accepts, a supervised local Pi coding-agent session that implements in an isolated Git worktree, and a fresh Sol / High native reviewer that returns the final verdict. Use only when the user explicitly asks to use Sol Pi Advisor, invokes this skill for implementation, or requests the Sol-plan/Pi-implement/Sol-review route.
---

# Sol Pi Advisor

Use exactly one implementation lane:

~~~text
primary Sol / high-or-higher -> local Pi implementation lane -> primary verification -> fresh Sol / High review
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
4. Confirm the MCP tool list exposes `pi_lane_preflight`, `pi_lane_start`, and
   `pi_lane_drive` from Sol Pi Advisor.
5. Call `pi_lane_preflight`. Require Pi `0.83.0`, a usable Git executable, and an
   available state directory. Record the actual Pi and Node paths; do not infer them.
6. This release supports only `supervised-local` execution. Pi has no built-in
   sandbox. State that fact before starting a run and stop if the user requests an
   unattended or untrusted-repository execution boundary.

## Keep ownership in the primary Sol task

The primary task must:

- resolve requirements and material ambiguity;
- choose architecture, interfaces, scope, and file ownership;
- write the complete Pi task packet;
- select an exact Git base ref and inspect the returned run, session, worktree,
  base commit, HEAD, changed paths, policy findings, and complete diff artifact;
- rerun verification independently inside the actual Pi worktree;
- send precise corrections to the same Pi run and session;
- authorize and perform any later commit, push, or PR action outside Pi; and
- accept or reject the final result.

Do not implement delegated changes in the primary task merely to repair an
incomplete Pi result. Tighten the packet and return corrections to the same run.

## Start and monitor Pi

Build the complete packet before calling `pi_lane_start`. Supply:

- the canonical Git repository root;
- an exact base ref chosen by the primary;
- the complete task packet as one string;
- non-empty repository-relative allowed paths without globs; and
- optional provider, model, and thinking values only when explicitly settled.

Use `execution_mode: supervised-local`. Record the returned `runId`, Pi session ID,
worktree, base commit, revision, and process metadata. Pi does not inherit the
primary conversation; the packet must contain every relevant decision.

Monitor with bounded `pi_lane_drive` calls using `directive: wait`. Treat a
`running` result as progress, not failure. Treat Pi prose and its structured handoff
as claims. A `ready` result is only a candidate and must include host-observed Git
evidence.

Inspect the complete diff artifact and changed paths, confirm ownership, and rerun
every stated verification command independently. If correction is required, call
`pi_lane_drive` with `directive: correct`, the precise instruction, and concrete
evidence. Corrections are allowed only after the previous Pi turn settles and must
reuse the same run, session, and worktree. Repeat monitoring and verification.

Do not create a replacement run to bypass a correction loop. Any correction
increments the run revision and invalidates all earlier verification evidence,
diff digests, acceptance, and reviewer verdicts.

## Obtain fresh Sol review

After the primary accepts the actual diff and independently rerun checks, spawn
exactly:

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

Any post-review file change or diff-digest change invalidates the verdict. The
reviewer must remain read-only and never implement findings.

## Preserve the Git boundary

Pi must never commit, add, push, fetch, pull, merge, rebase, cherry-pick, reset,
clean, create or delete branches, or perform any PR operation. Its only deliverable
is a working-tree diff. Worktree isolation is not a sandbox or merge-safety proof.
Keep shared-file and dependent work serial. This release supports one active Pi run
per repository.
