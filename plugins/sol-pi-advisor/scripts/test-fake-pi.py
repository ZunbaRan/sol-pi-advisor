from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import time
from pathlib import Path


plugin = Path(__file__).resolve().parent.parent


def write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def exchange(process: subprocess.Popen[str], payload: dict) -> dict:
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()
    line = process.stdout.readline()
    if not line:
        stderr = process.stderr.read() if process.stderr else ""
        raise RuntimeError(f"MCP server exited without response: {stderr}")
    response = json.loads(line)
    return response["result"]


with tempfile.TemporaryDirectory(prefix="sol-pi-advisor-e2e-") as raw_root:
    root = Path(raw_root)
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "src").mkdir()
    (repo / "src" / "seed.txt").write_text("seed\n", encoding="utf-8")
    (repo / "issues.md").write_text(
        "# Issues\n\n"
        + "\n\n".join(
            f"## issue-{index:03d}: fake work item {index}\n\n- Status: READY"
            for index in range(1, 11)
        )
        + "\n\n## issue-011: intentionally suspended work item\n\n"
        + "- Status: SUSPENDED\n"
        + "- Classification: NON-BLOCKING\n"
        + "- Suspension decision: explicit test-user decision\n"
        + "- Resume condition: explicit test-user request\n"
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "src/seed.txt", "issues.md"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Sol Pi Test",
            "-c",
            "user.email=sol-pi@example.invalid",
            "commit",
            "-q",
            "-m",
            "seed",
        ],
        check=True,
    )

    fake_cli = root / "fake-pi-cli.js"
    fake_cli.write_text("// fake\n", encoding="utf-8")
    fake_node = root / "fake-node"
    write_executable(
        fake_node,
        """#!/usr/bin/python3
import json
import pathlib
import re
import sys
import time

args = sys.argv[2:]
if "--version" in args:
    print("999.0.0-test")
    raise SystemExit(0)

message = next((item[1:] for item in args if item.startswith("@")), None)
text = pathlib.Path(message).read_text() if message else ""
matched = re.search(r"^TARGET: (.+)$", text, re.MULTILINE)
relative_target = matched.group(1).split("\\\\n", 1)[0].strip() if matched else "src/implemented.txt"
target = pathlib.Path.cwd() / relative_target
target.parent.mkdir(parents=True, exist_ok=True)
if "PAUSE_WAIT" in text:
    time.sleep(5)
else:
    time.sleep(0.4)
remove_match = re.search(r"^REMOVE: (.+)$", text, re.MULTILINE)
if remove_match:
    remove_target = pathlib.Path.cwd() / remove_match.group(1).split("\\\\n", 1)[0].strip()
    remove_target.unlink(missing_ok=True)
target.write_text("corrected\\n" if "CORRECTION" in text else "implemented\\n")
if "LOG_SAVED_LOCKFILE" in text:
    print("Saved lockfile", flush=True)
violation_match = re.search(r"^VIOLATE: (.+)$", text, re.MULTILINE)
if violation_match:
    violation_target = pathlib.Path.cwd() / violation_match.group(1).split("\\\\n", 1)[0].strip()
    violation_target.parent.mkdir(parents=True, exist_ok=True)
    violation_target.write_text("outside ownership\\n")
    print(json.dumps({"type": "tool_execution_end", "toolName": "bash", "result": {"details": {}}}), flush=True)
    time.sleep(5)
handoff = {
    "status": "complete",
    "objective": "fake implementation",
    "changes": [{"file": relative_target, "summary": "fake change"}],
    "checks": [{"command": "fake-check", "result": "passed"}],
    "gaps": [],
    "judgmentCalls": [],
}
print(json.dumps({"type": "session", "version": 3, "id": "fake-session", "cwd": str(pathlib.Path.cwd())}), flush=True)
print(json.dumps({"type": "tool_execution_end", "toolName": "submit_handoff", "result": {"details": handoff}}), flush=True)
print(json.dumps({"type": "agent_end", "messages": [], "willRetry": False}), flush=True)
""",
    )

    environment = {
        **os.environ,
        "CODEX_HOME": str(root / "codex"),
        "SOL_PI_NODE": str(fake_node),
        "SOL_PI_CLI": str(fake_cli),
    }
    process = subprocess.Popen(
        [str(plugin / "bin" / "sol-pi-advisor-mcp")],
        cwd=plugin,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "e2e", "version": "1"}},
        },
    )
    assert process.stdin is not None
    process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    process.stdin.flush()

    missing_start_issue_id = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 18,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_start",
                "arguments": {
                    "repoRoot": str(repo),
                    "baseRef": "HEAD",
                    "taskPacket": "A start without a ledger issue ID must be rejected.\n",
                    "allowedPaths": ["src"],
                    "executionMode": "supervised-local",
                },
            },
        },
    )
    assert missing_start_issue_id["isError"] is True, missing_start_issue_id
    assert missing_start_issue_id["structuredContent"]["code"] == "InvalidIssueId"

    unlisted_start_issue_id = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_start",
                "arguments": {
                    "repoRoot": str(repo),
                    "baseRef": "HEAD",
                    "issueId": "issue-999",
                    "taskPacket": "An unlisted issue must be rejected.\n",
                    "allowedPaths": ["src"],
                    "executionMode": "supervised-local",
                },
            },
        },
    )
    assert unlisted_start_issue_id["isError"] is True, unlisted_start_issue_id
    assert unlisted_start_issue_id["structuredContent"]["code"] == "IssueLedgerEntryMissing"

    suspended_start = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 221,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_start",
                "arguments": {
                    "repoRoot": str(repo),
                    "baseRef": "HEAD",
                    "issueId": "issue-011",
                    "taskPacket": "A suspended issue must stay outside Pi scheduling.\n",
                    "allowedPaths": ["src"],
                    "executionMode": "supervised-local",
                },
            },
        },
    )
    assert suspended_start["isError"] is True, suspended_start
    assert suspended_start["structuredContent"]["code"] == "IssueSuspended"

    pi_owned_ledger = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 22,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_start",
                "arguments": {
                    "repoRoot": str(repo),
                    "baseRef": "HEAD",
                    "issueId": "issue-001",
                    "taskPacket": "Pi must not own the primary issue ledger.\n",
                    "allowedPaths": ["issues.md"],
                    "executionMode": "supervised-local",
                },
            },
        },
    )
    assert pi_owned_ledger["isError"] is True, pi_owned_ledger
    assert pi_owned_ledger["structuredContent"]["code"] == "InvalidOwnership"

    started_result = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_start",
                "arguments": {
                    "repoRoot": str(repo),
                    "baseRef": "HEAD",
                    "issueId": "issue-001",
                    "taskPacket": "ROLE\\nImplement the fake task.\\nLOG_SAVED_LOCKFILE\\n",
                    "allowedPaths": ["src"],
                    "executionMode": "supervised-local",
                },
            },
        },
    )
    assert started_result["isError"] is False, started_result
    started = started_result["structuredContent"]
    run_id = started["runId"]
    assert started["issueId"] == "issue-001"
    assert Path(started["issueLedgerPath"]) == (repo / "issues.md").resolve()
    assert started["issueAttempts"] == {"issue-001": 0}
    assert started["pi"]["version"] == "999.0.0-test"
    assert started["limits"] == {"piCorrectionsPerIssue": 2}

    deadline = time.monotonic() + 10
    snapshot = started
    while snapshot["state"] not in {"ready", "needs-attention", "failed", "aborted"}:
        assert time.monotonic() < deadline, snapshot
        waited = exchange(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "pi_lane_drive",
                    "arguments": {"runId": run_id, "directive": "wait", "waitMs": 1000},
                },
            },
        )
        assert waited["isError"] is False, waited
        snapshot = waited["structuredContent"]

    assert snapshot["state"] == "ready", snapshot
    assert snapshot["revision"] == 0
    assert snapshot["evidence"]["policyBasis"] == "git-worktree-state"
    assert snapshot["evidence"]["stdoutUsedForPolicy"] is False
    assert snapshot["evidence"]["dependencyStateChanges"] == []
    assert snapshot["observed"]["protocolWarnings"] == ["non-JSON stdout line"]
    assert snapshot["evidence"]["changedPaths"] == ["src/implemented.txt"]
    assert snapshot["evidence"]["violations"] == []
    assert Path(snapshot["evidence"]["diffArtifact"]).is_file()
    assert Path(snapshot["scratchDir"]).is_dir()

    missing_issue_id = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 17,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_drive",
                "arguments": {
                    "runId": run_id,
                    "directive": "correct",
                    "instruction": "A correction without a core issue ID must be rejected.",
                    "evidence": ["Acceptance failed."],
                },
            },
        },
    )
    assert missing_issue_id["isError"] is True, missing_issue_id
    assert missing_issue_id["structuredContent"]["code"] == "InvalidIssueId"

    mismatched_issue_id = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 19,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_drive",
                "arguments": {
                    "runId": run_id,
                    "directive": "correct",
                    "issueId": "issue-999",
                    "instruction": "A correction for another ledger item must be rejected.",
                    "evidence": ["This run is bound to issue-001."],
                },
            },
        },
    )
    assert mismatched_issue_id["isError"] is True, mismatched_issue_id
    assert mismatched_issue_id["structuredContent"]["code"] == "IssueIdMismatch"

    ledger_path = repo / "issues.md"
    ready_ledger = ledger_path.read_text(encoding="utf-8")
    suspended_ledger = ready_ledger.replace(
        "## issue-001: fake work item 1\n\n- Status: READY",
        "## issue-001: fake work item 1\n\n- Status: SUSPENDED",
        1,
    )
    assert suspended_ledger != ready_ledger
    ledger_path.write_text(suspended_ledger, encoding="utf-8")
    suspended_correction = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 191,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_drive",
                "arguments": {
                    "runId": run_id,
                    "directive": "correct",
                    "issueId": "issue-001",
                    "instruction": "A suspended issue must not receive another correction.",
                    "evidence": ["The user deferred this non-blocking issue."],
                },
            },
        },
    )
    assert suspended_correction["isError"] is True, suspended_correction
    assert suspended_correction["structuredContent"]["code"] == "IssueSuspended"
    ledger_path.write_text(ready_ledger, encoding="utf-8")

    corrected_result = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_drive",
                "arguments": {
                    "runId": run_id,
                    "directive": "correct",
                    "issueId": "issue-001",
                    "instruction": "Apply the fake correction.",
                    "evidence": ["The primary requested corrected output."],
                },
            },
        },
    )
    assert corrected_result["isError"] is False, corrected_result
    snapshot = corrected_result["structuredContent"]
    assert snapshot["revision"] == 1
    assert snapshot["issueAttempts"] == {"issue-001": 1}
    assert snapshot["activeIssue"] == {
        "issueId": "issue-001",
        "attempt": 1,
        "limit": 2,
    }

    deadline = time.monotonic() + 10
    while snapshot["state"] not in {"ready", "needs-attention", "failed", "aborted"}:
        assert time.monotonic() < deadline, snapshot
        waited = exchange(
            process,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "pi_lane_drive",
                    "arguments": {"runId": run_id, "directive": "wait", "waitMs": 1000},
                },
            },
        )
        assert waited["isError"] is False, waited
        snapshot = waited["structuredContent"]

    assert snapshot["state"] == "ready", snapshot
    assert snapshot["revision"] == 1
    assert (Path(snapshot["worktree"]) / "src" / "implemented.txt").read_text() == "corrected\n"
    assert snapshot["piSessionId"] == run_id

    second_same_issue = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_drive",
                "arguments": {
                    "runId": run_id,
                    "directive": "correct",
                    "issueId": "issue-001",
                    "instruction": "Retry the same acceptance-output root cause once more.",
                    "evidence": ["The same root cause remains after the first correction."],
                },
            },
        },
    )
    assert second_same_issue["isError"] is False, second_same_issue
    snapshot = second_same_issue["structuredContent"]
    deadline = time.monotonic() + 10
    while snapshot["state"] not in {"ready", "needs-attention", "failed", "aborted"}:
        assert time.monotonic() < deadline, snapshot
        waited = exchange(
            process,
            {
                "jsonrpc": "2.0",
                "id": 15,
                "method": "tools/call",
                "params": {
                    "name": "pi_lane_drive",
                    "arguments": {"runId": run_id, "directive": "wait", "waitMs": 1000},
                },
            },
        )
        assert waited["isError"] is False, waited
        snapshot = waited["structuredContent"]
    assert snapshot["revision"] == 2
    assert snapshot["issueAttempts"] == {"issue-001": 2}

    exhausted_same_issue = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 16,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_drive",
                "arguments": {
                    "runId": run_id,
                    "directive": "correct",
                    "issueId": "issue-001",
                    "instruction": "This third correction must be rejected.",
                    "evidence": ["The same root cause still remains."],
                },
            },
        },
    )
    assert exhausted_same_issue["isError"] is True, exhausted_same_issue
    assert exhausted_same_issue["structuredContent"]["code"] == "PiIssueRetryLimit"

    live_violation_result = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_start",
                "arguments": {
                    "repoRoot": str(repo),
                    "baseRef": "HEAD",
                    "issueId": "issue-002",
                    "taskPacket": "TARGET: src/live.txt\nVIOLATE: outside/scratch.txt\n",
                    "allowedPaths": ["src"],
                    "executionMode": "supervised-local",
                },
            },
        },
    )
    assert live_violation_result["isError"] is False, live_violation_result
    live_snapshot = live_violation_result["structuredContent"]
    live_run_id = live_snapshot["runId"]
    deadline = time.monotonic() + 10
    while live_snapshot["state"] not in {"ready", "needs-attention", "failed", "aborted"}:
        assert time.monotonic() < deadline, live_snapshot
        waited = exchange(
            process,
            {
                "jsonrpc": "2.0",
                "id": 101,
                "method": "tools/call",
                "params": {
                    "name": "pi_lane_drive",
                    "arguments": {
                        "runId": live_run_id,
                        "directive": "wait",
                        "waitMs": 1000,
                    },
                },
            },
        )
        assert waited["isError"] is False, waited
        live_snapshot = waited["structuredContent"]
    assert live_snapshot["state"] == "needs-attention", live_snapshot
    assert live_snapshot["observed"]["policyStop"]["code"] == "LiveGitPolicyViolation"
    assert live_snapshot["observed"]["policyStop"]["stdoutUsedForPolicy"] is False
    assert live_snapshot["evidence"]["outsideAllowedPaths"] == ["outside/scratch.txt"]

    recovered_result = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 102,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_drive",
                "arguments": {
                    "runId": live_run_id,
                    "directive": "correct",
                    "issueId": "issue-002",
                    "instruction": "TARGET: src/live.txt\nREMOVE: outside/scratch.txt\nRemove the unauthorized scratch file.",
                    "evidence": ["Git evidence found outside/scratch.txt outside ownership."],
                },
            },
        },
    )
    assert recovered_result["isError"] is False, recovered_result
    live_snapshot = recovered_result["structuredContent"]
    deadline = time.monotonic() + 10
    while live_snapshot["state"] not in {"ready", "needs-attention", "failed", "aborted"}:
        assert time.monotonic() < deadline, live_snapshot
        waited = exchange(
            process,
            {
                "jsonrpc": "2.0",
                "id": 103,
                "method": "tools/call",
                "params": {
                    "name": "pi_lane_drive",
                    "arguments": {
                        "runId": live_run_id,
                        "directive": "wait",
                        "waitMs": 1000,
                    },
                },
            },
        )
        assert waited["isError"] is False, waited
        live_snapshot = waited["structuredContent"]
    assert live_snapshot["state"] == "ready", live_snapshot
    assert live_snapshot["revision"] == 1
    assert live_snapshot["evidence"]["outsideAllowedPaths"] == []

    pause_result = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 104,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_start",
                "arguments": {
                    "repoRoot": str(repo),
                    "baseRef": "HEAD",
                    "issueId": "issue-003",
                    "taskPacket": "TARGET: pause/value.txt\nPAUSE_WAIT\n",
                    "allowedPaths": ["pause"],
                    "executionMode": "supervised-local",
                },
            },
        },
    )
    assert pause_result["isError"] is False, pause_result
    pause_snapshot = pause_result["structuredContent"]
    paused = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 105,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_drive",
                "arguments": {
                    "runId": pause_snapshot["runId"],
                    "directive": "pause",
                    "reason": "inspect a recoverable safety concern",
                },
            },
        },
    )
    assert paused["isError"] is False, paused
    pause_snapshot = paused["structuredContent"]
    assert pause_snapshot["state"] == "needs-attention", pause_snapshot
    assert pause_snapshot["reason"] == "inspect a recoverable safety concern"
    paused_correction = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 106,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_drive",
                "arguments": {
                    "runId": pause_snapshot["runId"],
                    "directive": "correct",
                    "issueId": "issue-003",
                    "instruction": "TARGET: pause/value.txt\nComplete after the recoverable pause.",
                    "evidence": ["Primary inspection permits the same session to continue."],
                },
            },
        },
    )
    assert paused_correction["isError"] is False, paused_correction
    pause_snapshot = paused_correction["structuredContent"]
    deadline = time.monotonic() + 10
    while pause_snapshot["state"] not in {"ready", "needs-attention", "failed", "aborted"}:
        assert time.monotonic() < deadline, pause_snapshot
        waited = exchange(
            process,
            {
                "jsonrpc": "2.0",
                "id": 107,
                "method": "tools/call",
                "params": {
                    "name": "pi_lane_drive",
                    "arguments": {
                        "runId": pause_snapshot["runId"],
                        "directive": "wait",
                        "waitMs": 1000,
                    },
                },
            },
        )
        assert waited["isError"] is False, waited
        pause_snapshot = waited["structuredContent"]
    assert pause_snapshot["state"] == "ready", pause_snapshot
    assert pause_snapshot["revision"] == 1

    runs_root = root / "codex" / "sol-pi-advisor" / "runs"
    worktrees_root = root / "codex" / "sol-pi-advisor" / "worktrees"
    runs_before_overlap = {item.name for item in runs_root.iterdir()}
    worktrees_before_overlap = {item.name for item in worktrees_root.iterdir()}
    duplicate_issue_result = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 21,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_batch_start",
                "arguments": {
                    "repoRoot": str(repo),
                    "baseRef": "HEAD",
                    "executionMode": "supervised-local",
                    "lanes": [
                        {
                            "laneId": "duplicate-a",
                            "issueId": "issue-004",
                            "taskPacket": "TARGET: duplicate-a/value.txt\n",
                            "allowedPaths": ["duplicate-a"],
                        },
                        {
                            "laneId": "duplicate-b",
                            "issueId": "issue-004",
                            "taskPacket": "TARGET: duplicate-b/value.txt\n",
                            "allowedPaths": ["duplicate-b"],
                        },
                    ],
                },
            },
        },
    )
    assert duplicate_issue_result["isError"] is True, duplicate_issue_result
    assert duplicate_issue_result["structuredContent"]["code"] == "InvalidParallelWave"

    overlap_result = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_batch_start",
                "arguments": {
                    "repoRoot": str(repo),
                    "baseRef": "HEAD",
                    "executionMode": "supervised-local",
                    "lanes": [
                        {
                            "laneId": "overlap-a",
                            "issueId": "issue-004",
                            "taskPacket": "TARGET: shared/a.txt\\n",
                            "allowedPaths": ["shared"],
                        },
                        {
                            "laneId": "overlap-b",
                            "issueId": "issue-005",
                            "taskPacket": "TARGET: shared/nested/b.txt\\n",
                            "allowedPaths": ["shared/nested"],
                        },
                    ],
                },
            },
        },
    )
    assert overlap_result["isError"] is True, overlap_result
    assert overlap_result["structuredContent"]["code"] == "ParallelOwnershipOverlap"
    assert {item.name for item in runs_root.iterdir()} == runs_before_overlap
    assert {item.name for item in worktrees_root.iterdir()} == worktrees_before_overlap

    batch_result = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_batch_start",
                "arguments": {
                    "repoRoot": str(repo),
                    "baseRef": "HEAD",
                    "executionMode": "supervised-local",
                    "lanes": [
                        {
                            "laneId": "server-core",
                            "issueId": "issue-006",
                            "taskPacket": "TARGET: server/core.txt\\n",
                            "allowedPaths": ["server"],
                        },
                        {
                            "laneId": "ui-shell",
                            "issueId": "issue-007",
                            "taskPacket": "TARGET: ui/shell.txt\\n",
                            "allowedPaths": ["ui"],
                        },
                    ],
                },
            },
        },
    )
    assert batch_result["isError"] is False, batch_result
    batch = batch_result["structuredContent"]
    assert batch["state"] == "running", batch
    assert batch["laneCount"] == 2
    assert all(lane["state"] in {"preparing", "running"} for lane in batch["lanes"])
    assert len({lane["pid"] for lane in batch["lanes"]}) == 2
    assert {lane["laneId"] for lane in batch["lanes"]} == {"server-core", "ui-shell"}
    assert {lane["issueId"] for lane in batch["lanes"]} == {"issue-006", "issue-007"}
    assert all(lane["batchId"] == batch["batchId"] for lane in batch["lanes"])
    assert len({lane["runId"] for lane in batch["lanes"]}) == 2
    assert len({lane["worktree"] for lane in batch["lanes"]}) == 2
    assert len({lane["piSessionId"] for lane in batch["lanes"]}) == 2
    assert all(lane["baseCommit"] == batch["baseCommit"] for lane in batch["lanes"])

    busy_result = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_start",
                "arguments": {
                    "repoRoot": str(repo),
                    "baseRef": "HEAD",
                    "issueId": "issue-008",
                    "taskPacket": "This must not start during a parallel wave.\\n",
                    "allowedPaths": ["other"],
                    "executionMode": "supervised-local",
                },
            },
        },
    )
    assert busy_result["isError"] is True, busy_result
    assert busy_result["structuredContent"]["code"] == "RepositoryBusy"

    deadline = time.monotonic() + 10
    while batch["state"] == "running":
        assert time.monotonic() < deadline, batch
        waited = exchange(
            process,
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "pi_lane_batch_drive",
                    "arguments": {
                        "batchId": batch["batchId"],
                        "directive": "wait",
                        "waitMs": 1000,
                    },
                },
            },
        )
        assert waited["isError"] is False, waited
        batch = waited["structuredContent"]

    assert batch["state"] == "ready", batch
    by_lane = {lane["laneId"]: lane for lane in batch["lanes"]}
    assert by_lane["server-core"]["evidence"]["changedPaths"] == ["server/core.txt"]
    assert by_lane["ui-shell"]["evidence"]["changedPaths"] == ["ui/shell.txt"]
    assert all(lane["evidence"]["violations"] == [] for lane in batch["lanes"])

    corrected_lane = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_drive",
                "arguments": {
                    "runId": by_lane["server-core"]["runId"],
                    "directive": "correct",
                    "issueId": "issue-006",
                    "instruction": "TARGET: server/core.txt\\nApply the lane-specific correction.",
                    "evidence": ["Only server-core needs correction."],
                },
            },
        },
    )
    assert corrected_lane["isError"] is False, corrected_lane
    batch["state"] = "running"
    deadline = time.monotonic() + 10
    while batch["state"] == "running":
        assert time.monotonic() < deadline, batch
        waited = exchange(
            process,
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "pi_lane_batch_drive",
                    "arguments": {
                        "batchId": batch["batchId"],
                        "directive": "wait",
                        "waitMs": 1000,
                    },
                },
            },
        )
        assert waited["isError"] is False, waited
        batch = waited["structuredContent"]
    assert batch["state"] == "ready", batch
    by_lane = {lane["laneId"]: lane for lane in batch["lanes"]}
    assert by_lane["server-core"]["revision"] == 1
    assert by_lane["ui-shell"]["revision"] == 0
    assert (Path(by_lane["server-core"]["worktree"]) / "server" / "core.txt").read_text() == "corrected\n"

    abort_start = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_batch_start",
                "arguments": {
                    "repoRoot": str(repo),
                    "baseRef": "HEAD",
                    "executionMode": "supervised-local",
                    "lanes": [
                        {
                            "laneId": "abort-a",
                            "issueId": "issue-009",
                            "taskPacket": "TARGET: abort-a/value.txt\\n",
                            "allowedPaths": ["abort-a"],
                        },
                        {
                            "laneId": "abort-b",
                            "issueId": "issue-010",
                            "taskPacket": "TARGET: abort-b/value.txt\\n",
                            "allowedPaths": ["abort-b"],
                        },
                    ],
                },
            },
        },
    )
    assert abort_start["isError"] is False, abort_start
    abort_batch = abort_start["structuredContent"]
    aborted = exchange(
        process,
        {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": "pi_lane_batch_drive",
                "arguments": {
                    "batchId": abort_batch["batchId"],
                    "directive": "abort",
                    "reason": "fake parallel abort test",
                },
            },
        },
    )
    assert aborted["isError"] is False, aborted
    abort_batch = aborted["structuredContent"]
    assert abort_batch["state"] == "needs-attention", abort_batch
    assert abort_batch["counts"] == {"aborted": 2}, abort_batch
    assert all(lane["state"] == "aborted" for lane in abort_batch["lanes"])

    process.stdin.close()
    process.wait(timeout=5)
    if process.returncode != 0:
        stderr = process.stderr.read() if process.stderr else ""
        raise RuntimeError(f"MCP end-to-end server failed: {stderr}")

print("FAKE PI END-TO-END PASSED")
