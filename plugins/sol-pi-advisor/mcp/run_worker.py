from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import LaneError, collect_git_evidence, read_json, update_status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--revision", required=True, type=int)
    parser.add_argument("--message-file", required=True)
    return parser.parse_args()


def extract_event(event: dict[str, Any], observed: dict[str, Any]) -> None:
    if event.get("type") == "session":
        observed["sessionId"] = event.get("id")
        observed["sessionCwd"] = event.get("cwd")

    message = event.get("message")
    if isinstance(message, dict) and message.get("role") == "assistant":
        for key in ("provider", "model", "stopReason"):
            if message.get(key) is not None:
                observed[key] = message[key]

    if event.get("type") == "agent_end":
        observed["agentEndSeen"] = True

    if event.get("type") == "tool_execution_end" and event.get("toolName") == "submit_handoff":
        result = event.get("result")
        if isinstance(result, dict) and isinstance(result.get("details"), dict):
            observed["handoff"] = result["details"]


def main() -> int:
    args = parse_args()
    run_path = Path(args.run_dir).resolve()
    manifest = read_json(run_path / "manifest.json")
    revision = args.revision
    message_file = Path(args.message_file).resolve()
    worktree = Path(manifest["worktree"])

    update_status(
        run_path,
        state="running",
        revision=revision,
        pid=os.getpid(),
        startedAt=time.time(),
        messageFile=str(message_file),
        error=None,
    )

    command = [
        manifest["nodePath"],
        manifest["piPath"],
        "--mode",
        "json",
        "--print",
        "--session-id",
        manifest["piSessionId"],
        "--session-dir",
        manifest["sessionDir"],
        "--no-extensions",
        "--extension",
        manifest["workerExtension"],
        "--no-skills",
        "--no-prompt-templates",
        "--no-approve",
        "--offline",
        "--tools",
        "read,bash,edit,write,grep,find,ls,submit_handoff",
    ]
    if revision == 0:
        command.extend(["--name", f"Sol Pi Advisor {manifest['runId'][:8]}"])
    if manifest.get("provider"):
        command.extend(["--provider", manifest["provider"]])
    if manifest.get("model"):
        command.extend(["--model", manifest["model"]])
    if manifest.get("thinking"):
        command.extend(["--thinking", manifest["thinking"]])
    command.extend(
        [
            f"@{message_file}",
            "Implement this Sol Pi Advisor task packet. Your final action must call submit_handoff exactly once.",
        ]
    )

    environment = dict(os.environ)
    environment.update(
        {
            "PI_OFFLINE": "1",
            "PI_SKIP_VERSION_CHECK": "1",
            "SOL_PI_ALLOWED_PATHS_JSON": json.dumps(manifest["allowedPaths"]),
            "SOL_PI_BASE_COMMIT": manifest["baseCommit"],
            "SOL_PI_RUN_ID": manifest["runId"],
        }
    )

    event_path = run_path / f"events-revision-{revision}.jsonl"
    stderr_path = run_path / f"stderr-revision-{revision}.log"
    observed: dict[str, Any] = {"agentEndSeen": False, "handoff": None}

    try:
        with event_path.open("a", encoding="utf-8") as events, stderr_path.open(
            "a", encoding="utf-8"
        ) as errors:
            process = subprocess.Popen(
                command,
                cwd=worktree,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=errors,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            update_status(run_path, piPid=process.pid)
            assert process.stdout is not None
            for line in process.stdout:
                events.write(line)
                events.flush()
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    observed.setdefault("protocolWarnings", []).append("non-JSON stdout line")
                    continue
                if isinstance(event, dict):
                    extract_event(event, observed)
            exit_code = process.wait()

        evidence = collect_git_evidence(run_path, revision)
        handoff = observed.get("handoff")
        violations = evidence["violations"]
        if violations:
            state = "needs-attention"
            reason = "host-observed policy violation"
        elif exit_code != 0:
            state = "failed"
            reason = f"Pi exited with status {exit_code}"
        elif not isinstance(handoff, dict):
            state = "needs-attention"
            reason = "Pi settled without submit_handoff"
        elif handoff.get("status") != "complete":
            state = "needs-attention"
            reason = f"Pi reported {handoff.get('status', 'unknown')}"
        else:
            state = "ready"
            reason = "candidate ready for primary inspection"

        update_status(
            run_path,
            state=state,
            revision=revision,
            pid=None,
            piPid=None,
            finishedAt=time.time(),
            exitCode=exit_code,
            reason=reason,
            observed=observed,
            handoff=handoff,
            evidence=evidence,
            error=None,
        )
        return 0 if state in {"ready", "needs-attention"} else 1
    except (LaneError, OSError, subprocess.SubprocessError) as exc:
        code = exc.code if isinstance(exc, LaneError) else type(exc).__name__
        update_status(
            run_path,
            state="failed",
            revision=revision,
            pid=None,
            piPid=None,
            finishedAt=time.time(),
            reason="worker infrastructure failure",
            error={"code": code, "message": str(exc)},
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
