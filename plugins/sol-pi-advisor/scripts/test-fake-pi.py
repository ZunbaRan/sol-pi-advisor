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
    subprocess.run(["git", "-C", str(repo), "add", "src/seed.txt"], check=True)
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
import sys

args = sys.argv[2:]
if "--version" in args:
    print("0.83.0")
    raise SystemExit(0)

message = next((item[1:] for item in args if item.startswith("@")), None)
text = pathlib.Path(message).read_text() if message else ""
target = pathlib.Path.cwd() / "src" / "implemented.txt"
target.write_text("corrected\\n" if "CORRECTION" in text else "implemented\\n")
handoff = {
    "status": "complete",
    "objective": "fake implementation",
    "changes": [{"file": "src/implemented.txt", "summary": "fake change"}],
    "checks": [{"command": "fake-check", "result": "passed"}],
    "gaps": [],
    "judgmentCalls": [],
}
print(json.dumps({"type": "session", "version": 3, "id": "fake-session", "cwd": str(pathlib.Path.cwd())}))
print(json.dumps({"type": "tool_execution_end", "toolName": "submit_handoff", "result": {"details": handoff}}))
print(json.dumps({"type": "agent_end", "messages": [], "willRetry": False}))
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
                    "taskPacket": "ROLE\\nImplement the fake task.\\n",
                    "allowedPaths": ["src"],
                    "executionMode": "supervised-local",
                },
            },
        },
    )
    assert started_result["isError"] is False, started_result
    started = started_result["structuredContent"]
    run_id = started["runId"]

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
    assert snapshot["evidence"]["changedPaths"] == ["src/implemented.txt"]
    assert snapshot["evidence"]["violations"] == []
    assert Path(snapshot["evidence"]["diffArtifact"]).is_file()

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
                    "instruction": "Apply the fake correction.",
                    "evidence": ["The primary requested corrected output."],
                },
            },
        },
    )
    assert corrected_result["isError"] is False, corrected_result
    snapshot = corrected_result["structuredContent"]
    assert snapshot["revision"] == 1

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

    process.stdin.close()
    process.wait(timeout=5)
    if process.returncode != 0:
        stderr = process.stderr.read() if process.stderr else ""
        raise RuntimeError(f"MCP end-to-end server failed: {stderr}")

print("FAKE PI END-TO-END PASSED")
