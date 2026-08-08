# Sol Pi Advisor

Sol Pi Advisor is a Codex plugin for supervised local software delivery. The
primary Codex task owns architecture and acceptance, persistent local Pi
coding-agent sessions implement, and a fresh read-only Sol reviewer gives the
final verdict. The orchestration flow does not gate the primary or Pi model,
reasoning level, provider, or installed Pi version.

```text
Primary task (plan + accept)
          |
          v
One Pi lane, or 2-4 independent Pi lanes in detached worktrees
          |
          v
Primary task (inspect diff + rerun checks)
          |
          v
Fresh Sol / High (read-only review)
```

The current `0.1.0` release supports one serial lane or one safe parallel wave of
2-4 independent lanes per repository at a time.

## First-principles acceptance and bounded recovery

Every goal is reduced to its core problem, evidence-backed causal model, and
non-negotiable acceptance invariant before it becomes a Pi task. Pi receives small,
independently testable work—normally one behavior or root-cause defect, one risk
domain, one focused acceptance test, and roughly 1-5 expected changed files.

Before Pi starts, the primary creates or updates repository-root `issues.md` as the
execution ledger, lists the complete known decomposition, assigns stable IDs such
as `issue-001`, records dependencies, and schedules READY entries one at a time by
default. Every serial run and parallel lane must supply one ledger `issueId`; the
MCP server permanently binds it to that run and Pi session.
Starts are rejected unless the exact ledger entry exists and is `READY`, and Pi
cannot own the ledger file. A user may explicitly mark a proven-independent
`NON-BLOCKING` issue `SUSPENDED`; suspended issues are excluded from dispatch,
correction, active acceptance, and completion counts until the user resumes them.

An acceptance failure is returned to the same Pi run and session with a stable
root-cause `issueId`. A missing or mismatched ID is rejected. The MCP supervisor
allows at most two Pi correction attempts for that issue and rejects a third.
Renaming the same cause or opening a replacement run does not reset the workflow
budget. A genuinely different root cause first becomes a new ledger entry and task.

After Pi's two attempts, the primary task may perform at most two `fix -> focused
test` rounds only when the remaining change is a settled micro-fix. Any still-open
issue updates its existing ledger entry: dependency blockers are `P0` and stop the
affected flow; proven-independent small issues are `NON-BLOCKING` and may remain
while independent goals continue. Suspending one of those issues requires an
explicit user decision and a recorded resume condition.

## Why this exists

Agentic coding works better when planning, implementation, acceptance, and final
review have explicit owners. Sol Pi Advisor enforces that separation:

- The primary task owns requirements, architecture, scope, and acceptance.
- Pi implements only inside an isolated detached Git worktree. Parallel lanes all
  share one immutable base and must own pairwise-disjoint paths.
- The host records the actual base commit, changed paths, full diff, and SHA-256
  digest instead of trusting the worker's prose.
- The host checks Git policy after completed Bash and handoff calls; output text such as
  `Saved lockfile` is diagnostic only and cannot establish a policy violation.
- The primary task independently reruns verification and sends corrections back to
  the same Pi session, with at most two attempts for one root-cause issue.
- A fresh GPT-5.6 Sol / High agent performs the final read-only review and returns
  exactly one verdict: `ship`, `fix-first`, or `rethink`.

Pi cannot commit, push, merge, rebase, change branches, or operate on pull requests
through this workflow. Those actions remain with the primary task.

## Safety boundary

> [!WARNING]
> Pi does not provide a sandbox. This release runs in `supervised-local` mode and
> should be used only with trusted repositories. Worktree isolation protects Git
> state; it is not a security boundary.

The plugin restricts Pi's write tools to paths selected by the primary task (plus a
run-owned scratch directory), blocks Git history, remote, worktree, and PR
operations, and stops a turn when host-observed Git state introduces an ownership
violation. Dependency installers/resolvers and repository-wide dead-code commands
are primary-owned. The primary still needs to inspect the returned diff before
integrating it.

## Requirements

- Codex CLI with plugin and multi-agent support
- Git, Python 3, a POSIX shell, and Node.js
- An installed `@earendil-works/pi-coding-agent` CLI

The primary task may use any available model and reasoning level. Pi may use its
configured default or an explicitly requested provider/model/thinking combination.
Those values and the installed Pi version are diagnostic metadata, never workflow
eligibility gates.

By default, the plugin discovers Pi under `~/.nvm/versions/node/*`. Set both
`SOL_PI_NODE` and `SOL_PI_CLI` when Node or Pi lives elsewhere.

## Install

Clone the marketplace, install the plugin, and install its native reviewer profile:

```sh
git clone https://github.com/ZunbaRan/sol-pi-advisor.git
cd sol-pi-advisor
codex plugin marketplace add .
codex plugin add sol-pi-advisor@sol-pi-advisor
sh plugins/sol-pi-advisor/scripts/install-agent.sh
```

Restart Codex after installation so the plugin tools, skill, and reviewer profile
are loaded. You can confirm the local prerequisites with:

```sh
sh plugins/sol-pi-advisor/scripts/check-pi.sh
```

## Use

Authorization is intentionally explicit. In the current Codex task, ask Codex to
use the plugin for the implementation request, for example:

```text
Use Sol Pi Advisor to implement this task through local Pi and fresh Sol review.
```

The primary task will preflight the environment, build a dependency DAG, run either
one Pi lane or one safe parallel wave, verify every resulting diff independently,
integrate accepted patches in a dedicated worktree, and obtain the final fresh Sol
review.

### Parallel waves

`pi_lane_batch_start` accepts 2-4 lane packets. The batch has one generated
`batchId`; each lane has its own stable `laneId`, run ID, Pi session, allowed paths,
and detached worktree. The server resolves one base commit for the whole wave and
rejects exact or parent/child ownership overlap before creating any worktree.

Use `pi_lane_batch_drive` to wait until every lane settles, recoverably pause active
lanes for inspection, or permanently abort them. A pause settles as
`needs-attention`; send fixes with ordinary `pi_lane_drive` against the exact run
to reuse its Pi session and worktree. A batch becoming `ready` means all lane
candidates are available for independent Sol inspection—it does not mean their
combined behavior is accepted.

Tasks that share files, generated outputs, lockfiles, migrations, or unaccepted
interfaces belong in separate dependency waves and remain serial.

After a task batch is accepted or explicitly abandoned, invoke
`$sol-pi-advisor:cleanup`. The cleanup skill inventories durable runs, performs a
dry-run, archives the final patch and minimal acceptance evidence, and only after
explicit approval removes the detached worktree and raw Pi logs.

## Validate the package

Run the bundled verifier from the plugin directory:

```sh
cd plugins/sol-pi-advisor
sh scripts/verify.sh
```

The verifier checks the manifests and agent contract, validates shell and Python
syntax, runs an MCP smoke test, and exercises the worker flow with a fake Pi.

## Related project

**Sol Luna Advisor** is the sibling workflow for teams that prefer a Codex-native
Luna implementation lane: primary Sol plans and accepts, Luna implements, and a
fresh read-only Sol reviewer gives the final verdict. Together, the two projects
offer the same supervised Sol-led delivery pattern with a choice of Pi or Luna for
implementation.

## Repository layout

```text
.agents/plugins/marketplace.json       Codex marketplace entry
plugins/sol-pi-advisor/
  .codex-plugin/plugin.json            Plugin metadata
  .mcp.json                            MCP server registration
  agents/                              Fresh Sol reviewer profile
  bin/                                 MCP launcher
  mcp/                                 Local lane supervisor
  pi-extensions/                       Pi handoff and policy extension
  skills/orchestration/                Sol/Pi/Sol workflow contract
  skills/cleanup/                      Safe post-task run and worktree cleanup
  scripts/                             Installer, preflight, and verification
```

## Current limitations

- One active serial lane or one active parallel wave (maximum four lanes) per repository
- Parallel lanes require the same base commit, no sibling dependency, frozen shared
  contracts, and pairwise-disjoint path ownership
- `supervised-local` execution only
- No primary or Pi model, provider, reasoning, or Pi-version gate; explicitly
  supplied Pi runtime values are passed through and observed only
- Two Pi corrections per stable root-cause issue, followed by at most two eligible
  primary micro-fix rounds; exhausted issues are preserved in `issues.md`
- Repository-root `issues.md` is required before Pi dispatch; each listed ID binds
  one fine-grained task to one run/session and corrections must match that binding
- The plugin produces a working-tree diff; it does not commit, push, merge, or
  create pull requests
