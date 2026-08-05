from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (
    PLUGIN_ROOT,
    SUPPORTED_PI_VERSION,
    LaneError,
    active_run_for_repository,
    atomic_write_json,
    ensure_state_root,
    normalize_allowed_paths,
    preflight,
    process_alive,
    read_json,
    resolve_repository,
    run_dir,
    update_status,
)


SERVER_INFO = {"name": "sol-pi-advisor", "version": "0.1.0"}
TERMINAL_STATES = {"ready", "needs-attention", "failed", "aborted"}


TOOLS = [
    {
        "name": "pi_lane_preflight",
        "description": "Check the local Pi, Node, Git, state directory, supported version, and execution-boundary facts before starting a Sol Pi Advisor run.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "pi_lane_start",
        "description": "Start one supervised local Pi implementation turn in a new detached Git worktree. Returns immediately with a durable run identity.",
        "inputSchema": {
            "type": "object",
            "required": [
                "repoRoot",
                "baseRef",
                "taskPacket",
                "allowedPaths",
                "executionMode",
            ],
            "properties": {
                "repoRoot": {"type": "string"},
                "baseRef": {"type": "string"},
                "taskPacket": {"type": "string", "minLength": 1},
                "allowedPaths": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
                "executionMode": {"type": "string", "enum": ["supervised-local"]},
                "provider": {"type": "string"},
                "model": {"type": "string"},
                "thinking": {
                    "type": "string",
                    "enum": ["off", "minimal", "low", "medium", "high", "xhigh", "max"],
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "pi_lane_drive",
        "description": "Wait for, correct, or abort an existing Pi run. Corrections reuse the same Pi session and worktree and are accepted only after the prior turn settles.",
        "inputSchema": {
            "type": "object",
            "required": ["runId", "directive"],
            "properties": {
                "runId": {"type": "string"},
                "directive": {"type": "string", "enum": ["wait", "correct", "abort"]},
                "waitMs": {"type": "integer", "minimum": 0, "maximum": 30000},
                "instruction": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "reason": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
]


def public_snapshot(run_path: Path) -> dict[str, Any]:
    manifest = read_json(run_path / "manifest.json")
    status = read_json(run_path / "status.json")
    return {
        "runId": manifest["runId"],
        "piSessionId": manifest["piSessionId"],
        "revision": status.get("revision", 0),
        "state": status.get("state", "unknown"),
        "reason": status.get("reason"),
        "repoRoot": manifest["repoRoot"],
        "worktree": manifest["worktree"],
        "baseCommit": manifest["baseCommit"],
        "allowedPaths": manifest["allowedPaths"],
        "pid": status.get("pid"),
        "piPid": status.get("piPid"),
        "pi": {
            "version": manifest["piVersion"],
            "nodePath": manifest["nodePath"],
            "piPath": manifest["piPath"],
            "providerRequested": manifest.get("provider"),
            "modelRequested": manifest.get("model"),
            "thinkingRequested": manifest.get("thinking"),
        },
        "executionMode": manifest["executionMode"],
        "sandboxEnforced": False,
        "handoff": status.get("handoff"),
        "observed": status.get("observed"),
        "evidence": status.get("evidence"),
        "error": status.get("error"),
    }


def spawn_turn(run_path: Path, revision: int, message_file: Path) -> dict[str, Any]:
    log_path = run_path / "supervisor.log"
    with log_path.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                str(PLUGIN_ROOT / "mcp" / "run_worker.py"),
                "--run-dir",
                str(run_path),
                "--revision",
                str(revision),
                "--message-file",
                str(message_file),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=log,
            start_new_session=True,
        )
    update_status(
        run_path,
        state="preparing",
        revision=revision,
        pid=process.pid,
        piPid=None,
        reason="Pi turn is starting",
        handoff=None,
        observed=None,
        evidence=None,
        error=None,
    )
    return public_snapshot(run_path)


def handle_preflight(_: dict[str, Any]) -> dict[str, Any]:
    return preflight()


def handle_start(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("executionMode") != "supervised-local":
        raise LaneError("UnsupportedExecutionMode", "only supervised-local is supported")
    task_packet = arguments.get("taskPacket")
    if not isinstance(task_packet, str) or not task_packet.strip():
        raise LaneError("InvalidPacket", "taskPacket must be a non-empty string")

    identity = preflight()
    if not identity["versionCompatible"]:
        raise LaneError(
            "PiVersionMismatch",
            f"Pi {identity['piVersion']} is installed; version {SUPPORTED_PI_VERSION} is required",
        )
    allowed = normalize_allowed_paths(arguments.get("allowedPaths"))
    repository, base_commit = resolve_repository(arguments.get("repoRoot"), arguments.get("baseRef"))
    existing = active_run_for_repository(repository)
    if existing:
        raise LaneError("RepositoryBusy", f"active Pi run already exists: {existing}")

    run_id = str(uuid.uuid4())
    root = ensure_state_root()
    path = root / "runs" / run_id
    path.mkdir(mode=0o700)
    worktree = root / "worktrees" / run_id

    created = subprocess.run(
        ["git", "-C", str(repository), "worktree", "add", "--detach", str(worktree), base_commit],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if created.returncode != 0:
        raise LaneError("WorktreeStartFailed", created.stderr.strip() or created.stdout.strip())

    session_dir = path / "sessions"
    session_dir.mkdir(mode=0o700)
    packet_path = path / "task-packet-revision-0.md"
    packet_path.write_text(task_packet.rstrip() + "\n", encoding="utf-8")
    manifest = {
        "runId": run_id,
        "piSessionId": run_id,
        "repoRoot": str(repository),
        "baseCommit": base_commit,
        "worktree": str(worktree),
        "allowedPaths": allowed,
        "executionMode": "supervised-local",
        "sandboxEnforced": False,
        "nodePath": identity["nodePath"],
        "piPath": identity["piPath"],
        "piVersion": identity["piVersion"],
        "sessionDir": str(session_dir),
        "workerExtension": str(PLUGIN_ROOT / "pi-extensions" / "worker-contract.ts"),
        "provider": arguments.get("provider"),
        "model": arguments.get("model"),
        "thinking": arguments.get("thinking"),
        "createdAt": time.time(),
    }
    atomic_write_json(path / "manifest.json", manifest)
    atomic_write_json(path / "status.json", {"state": "preparing", "revision": 0})
    return spawn_turn(path, 0, packet_path)


def wait_for_snapshot(path: Path, wait_ms: int) -> dict[str, Any]:
    deadline = time.monotonic() + wait_ms / 1000
    while True:
        snapshot = public_snapshot(path)
        if snapshot["state"] in TERMINAL_STATES or time.monotonic() >= deadline:
            return snapshot
        time.sleep(0.25)


def abort_run(path: Path, reason: str) -> dict[str, Any]:
    status = read_json(path / "status.json")
    if status.get("state") in TERMINAL_STATES:
        return public_snapshot(path)
    pid = status.get("pid")
    update_status(path, state="aborting", reason=reason or "aborted by primary")
    if process_alive(pid):
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 3
        while process_alive(pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        if process_alive(pid):
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    update_status(
        path,
        state="aborted",
        pid=None,
        piPid=None,
        reason=reason or "aborted by primary",
        finishedAt=time.time(),
    )
    return public_snapshot(path)


def handle_drive(arguments: dict[str, Any]) -> dict[str, Any]:
    path = run_dir(arguments.get("runId", ""))
    if not (path / "manifest.json").exists():
        raise LaneError("RunNotFound", f"unknown run: {arguments.get('runId')}")
    directive = arguments.get("directive")

    if directive == "wait":
        wait_ms = arguments.get("waitMs", 0)
        if not isinstance(wait_ms, int) or not 0 <= wait_ms <= 30000:
            raise LaneError("InvalidWait", "waitMs must be an integer from 0 through 30000")
        return wait_for_snapshot(path, wait_ms)

    if directive == "abort":
        reason = arguments.get("reason")
        return abort_run(path, reason if isinstance(reason, str) else "")

    if directive == "correct":
        status = read_json(path / "status.json")
        if status.get("state") not in {"ready", "needs-attention"}:
            raise LaneError(
                "InvalidStateTransition",
                f"correction requires a settled candidate; current state is {status.get('state')}",
            )
        instruction = arguments.get("instruction")
        if not isinstance(instruction, str) or not instruction.strip():
            raise LaneError("InvalidCorrection", "instruction is required for correction")
        evidence = arguments.get("evidence", [])
        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
            raise LaneError("InvalidCorrection", "evidence must be an array of strings")
        revision = int(status.get("revision", 0)) + 1
        correction_path = path / f"task-packet-revision-{revision}.md"
        lines = [
            "ROLE",
            "Continue as the implementation worker in the existing Sol Pi Advisor run.",
            "Preserve the settled architecture, ownership, Git boundary, and original task packet.",
            "",
            "CORRECTION",
            instruction.strip(),
            "",
            "PRIMARY EVIDENCE",
        ]
        lines.extend(f"- {item}" for item in evidence)
        lines.extend(
            [
                "",
                "FINAL HANDOFF",
                "After correcting and verifying, call submit_handoff exactly once as your final action.",
            ]
        )
        correction_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return spawn_turn(path, revision, correction_path)

    raise LaneError("InvalidDirective", "directive must be wait, correct, or abort")


HANDLERS = {
    "pi_lane_preflight": handle_preflight,
    "pi_lane_start": handle_start,
    "pi_lane_drive": handle_drive,
}


def tool_result(value: dict[str, Any], is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, indent=2)}],
        "structuredContent": value,
        "isError": is_error,
    }


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        requested = request.get("params", {}).get("protocolVersion")
        protocol = requested if requested in {"2024-11-05", "2025-03-26", "2025-06-18"} else "2025-06-18"
        result = {
            "protocolVersion": protocol,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in HANDLERS:
            result = tool_result({"code": "UnknownTool", "message": f"unknown tool: {name}"}, True)
        else:
            try:
                result = tool_result(HANDLERS[name](arguments))
            except LaneError as exc:
                result = tool_result({"code": exc.code, "message": str(exc)}, True)
            except Exception as exc:
                print(f"unexpected tool failure: {type(exc).__name__}: {exc}", file=sys.stderr)
                result = tool_result(
                    {"code": "InternalError", "message": f"{type(exc).__name__}: {exc}"}, True
                )
    elif method in {"notifications/initialized", "notifications/cancelled"}:
        return None
    else:
        if request_id is None:
            return None
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    if request_id is None:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main() -> int:
    for raw in sys.stdin:
        line = raw.rstrip("\r\n")
        if not line:
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            response = handle_request(request)
        except (json.JSONDecodeError, ValueError) as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
