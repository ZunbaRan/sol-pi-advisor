# Sol Pi Advisor

Sol Pi Advisor keeps architecture and acceptance in a GPT-5.6 Sol Codex task at
`high`, `xhigh`, or `max` reasoning, delegates implementation to a persistent local
Pi coding-agent session, and uses a fresh read-only Sol / High reviewer for the
final verdict.

Version 0.1 intentionally supports one supervised local Git implementation lane at
a time. Pi works in a detached worktree, returns a structured handoff, and cannot
commit, push, merge, rebase, or operate on pull requests. The primary Sol task
inspects the actual diff and reruns verification independently.

Pi does not provide a sandbox. This plugin's initial execution mode is explicitly
`supervised-local`; use it only with trusted repositories and review the returned
worktree before integration.

Run `sh scripts/verify.sh` from the plugin root to validate the package.
