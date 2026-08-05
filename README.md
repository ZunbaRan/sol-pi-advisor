# Sol Pi Advisor

Sol Pi Advisor is a Codex plugin for supervised local software delivery. It keeps
architecture and acceptance in a GPT-5.6 Sol task, delegates implementation to a
persistent local Pi coding-agent session, and asks a fresh read-only Sol reviewer
for the final verdict.

```text
Primary Sol (plan + accept)
          |
          v
Pi in a detached Git worktree (implement)
          |
          v
Primary Sol (inspect diff + rerun checks)
          |
          v
Fresh Sol / High (read-only review)
```

The current `0.1.0` release intentionally supports one implementation lane per
repository at a time.

## Why this exists

Agentic coding works better when planning, implementation, acceptance, and final
review have explicit owners. Sol Pi Advisor enforces that separation:

- The primary Sol task owns requirements, architecture, scope, and acceptance.
- Pi implements only inside an isolated detached Git worktree.
- The host records the actual base commit, changed paths, full diff, and SHA-256
  digest instead of trusting the worker's prose.
- The primary task independently reruns verification and sends corrections back to
  the same Pi session.
- A fresh GPT-5.6 Sol / High agent performs the final read-only review and returns
  exactly one verdict: `ship`, `fix-first`, or `rethink`.

Pi cannot commit, push, merge, rebase, change branches, or operate on pull requests
through this workflow. Those actions remain with the primary Sol task.

## Safety boundary

> [!WARNING]
> Pi does not provide a sandbox. This release runs in `supervised-local` mode and
> should be used only with trusted repositories. Worktree isolation protects Git
> state; it is not a security boundary.

The plugin restricts Pi's write tools to paths selected by the primary task and
blocks Git history, remote, worktree, and PR operations. The primary still needs to
inspect the returned diff before integrating it.

## Requirements

- Codex CLI with plugin and multi-agent support
- A GPT-5.6 Sol primary task using `high`, `xhigh`, or `max` reasoning
- Git, Python 3, a POSIX shell, and Node.js
- `@earendil-works/pi-coding-agent` version `0.83.0`

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

Authorization is intentionally explicit. In a GPT-5.6 Sol task, ask Codex to use
the plugin for the current implementation request, for example:

```text
Use Sol Pi Advisor to implement this task through local Pi and fresh Sol review.
```

The primary task will preflight the environment, create a detached worktree, start
one Pi implementation lane, verify the resulting diff, and obtain the final fresh
Sol review.

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
  scripts/                             Installer, preflight, and verification
```

## Current limitations

- One active Pi run per repository
- `supervised-local` execution only
- Pi `0.83.0` is required exactly
- The plugin produces a working-tree diff; it does not commit, push, merge, or
  create pull requests
