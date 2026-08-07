#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator


RUN_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
TERMINAL_STATES = {"ready", "needs-attention", "failed", "aborted"}


class CleanupError(RuntimeError):
    pass


def default_state_root() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    return (Path(codex_home).expanduser() if codex_home else Path.home() / ".codex") / "sol-pi-advisor"


def canonical(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def is_within(path: Path, parent: Path) -> bool:
    try:
        canonical(path).relative_to(canonical(parent))
        return True
    except ValueError:
        return False


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CleanupError(f"missing state file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CleanupError(f"invalid JSON state: {path}") from exc
    if not isinstance(value, dict):
        raise CleanupError(f"state file must contain an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for root, directories, files in os.walk(path, followlinks=False):
        for name in directories + files:
            candidate = Path(root) / name
            try:
                total += candidate.lstat().st_size
            except FileNotFoundError:
                continue
    return total


def process_alive(value: Any) -> bool:
    if not isinstance(value, int) or value <= 0:
        return False
    try:
        os.kill(value, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def run_git(repository: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise CleanupError(detail)
    return completed


def validate_repository(raw: Any) -> Path:
    if not isinstance(raw, str) or not raw:
        raise CleanupError("manifest repoRoot is missing")
    repository = canonical(Path(raw))
    completed = run_git(repository, "rev-parse", "--show-toplevel")
    if canonical(Path(completed.stdout.strip())) != repository:
        raise CleanupError(f"manifest repoRoot is not the Git top-level: {repository}")
    return repository


def registered_worktrees(repository: Path) -> set[Path]:
    completed = run_git(repository, "worktree", "list", "--porcelain")
    result: set[Path] = set()
    for line in completed.stdout.splitlines():
        if line.startswith("worktree "):
            result.add(canonical(Path(line.removeprefix("worktree "))))
    return result


def resolve_commit(repository: Path, value: str) -> str:
    completed = run_git(repository, "rev-parse", "--verify", f"{value}^{{commit}}")
    commit = completed.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise CleanupError(f"accepted commit did not resolve to an immutable object: {value}")
    return commit


@contextlib.contextmanager
def exclusive_run_lock(run_path: Path) -> Iterator[None]:
    lock_path = run_path / ".lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CleanupError("run state is currently locked") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def validate_run_id(run_id: str) -> None:
    if not RUN_ID_RE.fullmatch(run_id):
        raise CleanupError("run id must be a canonical lowercase UUID")


def load_candidate(state_root: Path, run_id: str) -> dict[str, Any]:
    validate_run_id(run_id)
    state_root = canonical(state_root)
    run_path = state_root / "runs" / run_id
    if run_path.is_symlink() or not run_path.is_dir():
        raise CleanupError(f"run does not exist as a managed directory: {run_path}")

    manifest = read_json(run_path / "manifest.json")
    status = read_json(run_path / "status.json")
    if manifest.get("runId") != run_id:
        raise CleanupError("manifest runId does not match the selected run")

    state = status.get("state")
    if state not in TERMINAL_STATES:
        raise CleanupError(f"run is not terminal: {state}")
    live = [name for name in ("pid", "piPid") if process_alive(status.get(name))]
    if live:
        raise CleanupError(f"recorded processes are still alive: {', '.join(live)}")

    repository = validate_repository(manifest.get("repoRoot"))
    expected_worktree = canonical(state_root / "worktrees" / run_id)
    raw_worktree = manifest.get("worktree")
    if not isinstance(raw_worktree, str) or canonical(Path(raw_worktree)) != expected_worktree:
        raise CleanupError("manifest worktree is outside the managed run path")
    if expected_worktree.is_symlink():
        raise CleanupError("managed worktree path must not be a symlink")

    registrations = registered_worktrees(repository)
    worktree_exists = expected_worktree.exists()
    worktree_registered = expected_worktree in registrations
    if worktree_exists and not worktree_registered:
        raise CleanupError("managed worktree exists but is not registered with Git")

    revision = status.get("revision", 0)
    if not isinstance(revision, int) or revision < 0:
        raise CleanupError("status revision is invalid")
    patch = run_path / f"diff-revision-{revision}.patch"
    patch_digest = sha256_file(patch) if patch.is_file() and not patch.is_symlink() else None
    recorded_digest = status.get("evidence", {}).get("diffDigest") if isinstance(status.get("evidence"), dict) else None
    if recorded_digest is not None and patch_digest != recorded_digest:
        raise CleanupError("final patch digest does not match host-recorded evidence")

    dirty = None
    if worktree_exists:
        dirty = bool(run_git(expected_worktree, "status", "--porcelain").stdout)

    return {
        "runPath": run_path,
        "manifest": manifest,
        "status": status,
        "state": state,
        "revision": revision,
        "repository": repository,
        "worktree": expected_worktree,
        "worktreeExists": worktree_exists,
        "worktreeRegistered": worktree_registered,
        "worktreeDirty": dirty,
        "patch": patch if patch_digest else None,
        "patchDigest": patch_digest,
        "runBytes": directory_size(run_path),
        "worktreeBytes": directory_size(expected_worktree),
    }


def list_runs(state_root: Path) -> dict[str, Any]:
    state_root = canonical(state_root)
    runs_root = state_root / "runs"
    if not runs_root.is_dir():
        return {
            "stateRoot": str(state_root),
            "runCount": 0,
            "runBytes": 0,
            "worktreeBytes": 0,
            "totalBytes": 0,
            "runs": [],
        }
    records: list[dict[str, Any]] = []
    for run_path in sorted(runs_root.iterdir()):
        if not run_path.is_dir() or not RUN_ID_RE.fullmatch(run_path.name):
            continue
        worktree = state_root / "worktrees" / run_path.name
        record: dict[str, Any] = {
            "runId": run_path.name,
            "runBytes": directory_size(run_path),
            "worktreeBytes": directory_size(worktree),
        }
        try:
            manifest = read_json(run_path / "manifest.json")
            status = read_json(run_path / "status.json")
            record.update(
                {
                    "state": status.get("state", "unknown"),
                    "revision": status.get("revision", 0),
                    "createdAt": manifest.get("createdAt"),
                    "batchId": manifest.get("batchId"),
                    "laneId": manifest.get("laneId"),
                    "parallelLaneCount": manifest.get("parallelLaneCount"),
                    "finishedAt": status.get("finishedAt"),
                    "repoRoot": manifest.get("repoRoot"),
                    "worktree": manifest.get("worktree"),
                    "processAlive": process_alive(status.get("pid")) or process_alive(status.get("piPid")),
                }
            )
        except CleanupError as exc:
            record["error"] = str(exc)
        records.append(record)
    return {
        "stateRoot": str(state_root),
        "runCount": len(records),
        "runBytes": sum(item["runBytes"] for item in records),
        "worktreeBytes": sum(item["worktreeBytes"] for item in records),
        "totalBytes": sum(item["runBytes"] + item["worktreeBytes"] for item in records),
        "runs": records,
    }


def outcome_evidence(arguments: argparse.Namespace, candidate: dict[str, Any]) -> dict[str, Any]:
    if arguments.outcome == "accepted":
        if not arguments.accepted_commit:
            raise CleanupError("accepted cleanup requires --accepted-commit")
        if arguments.review_verdict != "ship":
            raise CleanupError("accepted cleanup requires --review-verdict ship")
        if not arguments.test_summary or not arguments.test_summary.strip():
            raise CleanupError("accepted cleanup requires --test-summary")
        if arguments.discard_reason:
            raise CleanupError("accepted cleanup cannot include --discard-reason")
        if candidate["patch"] is None:
            raise CleanupError("accepted cleanup requires a verified final patch")
        evidence = candidate["status"].get("evidence")
        violations = evidence.get("violations") if isinstance(evidence, dict) else None
        if violations != []:
            raise CleanupError("accepted cleanup requires host evidence with no policy violations")
        if evidence.get("diffDigest") != candidate["patchDigest"]:
            raise CleanupError("accepted cleanup requires host-recorded final patch evidence")
        commit = resolve_commit(candidate["repository"], arguments.accepted_commit)
        return {
            "outcome": "accepted",
            "acceptedCommit": commit,
            "reviewVerdict": "ship",
            "testSummary": arguments.test_summary.strip(),
            "discardReason": None,
        }

    if not arguments.discard_reason or not arguments.discard_reason.strip():
        raise CleanupError("discarded cleanup requires --discard-reason")
    if arguments.accepted_commit or arguments.review_verdict or arguments.test_summary:
        raise CleanupError("discarded cleanup cannot include acceptance evidence")
    return {
        "outcome": "discarded",
        "acceptedCommit": None,
        "reviewVerdict": None,
        "testSummary": None,
        "discardReason": arguments.discard_reason.strip(),
    }


def archive_payload(candidate: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    status = candidate["status"]
    manifest = candidate["manifest"]
    evidence = status.get("evidence") if isinstance(status.get("evidence"), dict) else {}
    return {
        "schemaVersion": 1,
        "runId": manifest["runId"],
        "batchId": manifest.get("batchId"),
        "laneId": manifest.get("laneId"),
        "parallelLaneCount": manifest.get("parallelLaneCount"),
        "state": candidate["state"],
        "revision": candidate["revision"],
        "reason": status.get("reason"),
        "createdAt": manifest.get("createdAt"),
        "finishedAt": status.get("finishedAt"),
        "repoRoot": str(candidate["repository"]),
        "baseCommit": manifest.get("baseCommit"),
        "allowedPaths": manifest.get("allowedPaths"),
        "changedPaths": evidence.get("changedPaths"),
        "patchDigest": candidate["patchDigest"],
        "sourceBytes": candidate["runBytes"] + candidate["worktreeBytes"],
        **outcome,
    }


def archive_candidate(archive_root: Path, candidate: dict[str, Any], payload: dict[str, Any]) -> tuple[Path, bool]:
    archive_root = canonical(archive_root)
    target = archive_root / payload["runId"]
    state_root = candidate["runPath"].parents[1]
    if is_within(archive_root, state_root):
        raise CleanupError("archive directory must be outside the Sol Pi Advisor state root")
    if is_within(archive_root, candidate["worktree"]):
        raise CleanupError("archive directory must be outside the managed worktree")

    evidence_path = target / "cleanup-evidence.json"
    if target.exists():
        if target.is_symlink() or not target.is_dir() or not evidence_path.is_file():
            raise CleanupError(f"existing archive is not reusable: {target}")
        existing = read_json(evidence_path)
        keys = (
            "runId",
            "outcome",
            "acceptedCommit",
            "reviewVerdict",
            "testSummary",
            "discardReason",
            "baseCommit",
            "revision",
            "patchDigest",
        )
        if any(existing.get(key) != payload.get(key) for key in keys):
            raise CleanupError(f"existing archive evidence does not match this cleanup: {target}")
        if payload["patchDigest"]:
            archived_patch = target / f"diff-revision-{payload['revision']}.patch"
            if not archived_patch.is_file() or sha256_file(archived_patch) != payload["patchDigest"]:
                raise CleanupError(f"existing archive patch is missing or corrupt: {target}")
        return target, False

    archive_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{payload['runId']}.", dir=archive_root))
    try:
        write_json(temporary / "cleanup-evidence.json", payload)
        patch = candidate["patch"]
        if patch is not None:
            shutil.copy2(patch, temporary / patch.name)
        os.replace(temporary, target)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target, True


def cleanup(arguments: argparse.Namespace) -> dict[str, Any]:
    state_root = canonical(arguments.state_root)
    candidate = load_candidate(state_root, arguments.run_id)
    outcome = outcome_evidence(arguments, candidate)
    archive_root = canonical(arguments.archive_dir)
    archive_target = archive_root / arguments.run_id
    if is_within(archive_root, state_root):
        raise CleanupError("archive directory must be outside the Sol Pi Advisor state root")

    actions = ["archive minimal evidence"]
    if candidate["worktreeExists"]:
        actions.append("remove registered worktree with git worktree remove --force")
    elif candidate["worktreeRegistered"]:
        actions.append("prune stale Git worktree registration")
    actions.extend(["git worktree prune", "remove raw run directory"])

    result = {
        "mode": "execute" if arguments.execute else "dry-run",
        "runId": arguments.run_id,
        "state": candidate["state"],
        "revision": candidate["revision"],
        "outcome": outcome["outcome"],
        "archive": str(archive_target),
        "runBytes": candidate["runBytes"],
        "worktreeBytes": candidate["worktreeBytes"],
        "worktreeExists": candidate["worktreeExists"],
        "worktreeRegistered": candidate["worktreeRegistered"],
        "worktreeDirty": candidate["worktreeDirty"],
        "patchDigest": candidate["patchDigest"],
        "actions": actions,
    }
    if not arguments.execute:
        return result

    with exclusive_run_lock(candidate["runPath"]):
        candidate = load_candidate(state_root, arguments.run_id)
        outcome = outcome_evidence(arguments, candidate)
        payload = archive_payload(candidate, outcome)
        archive_target, archive_created = archive_candidate(archive_root, candidate, payload)

        if candidate["worktreeExists"]:
            run_git(candidate["repository"], "worktree", "remove", "--force", str(candidate["worktree"]))
            if candidate["worktree"].exists():
                raise CleanupError("Git reported success but the managed worktree still exists")
        run_git(candidate["repository"], "worktree", "prune")
        if candidate["worktree"] in registered_worktrees(candidate["repository"]):
            raise CleanupError("managed worktree remains registered after pruning")

        source_bytes = candidate["runBytes"] + candidate["worktreeBytes"]
        shutil.rmtree(candidate["runPath"])
        archive_bytes = directory_size(archive_target)
        result.update(
            {
                "archive": str(archive_target),
                "archiveCreated": archive_created,
                "archiveBytes": archive_bytes,
                "sourceBytesRemoved": source_bytes,
                "estimatedNetBytesReclaimed": max(0, source_bytes - archive_bytes),
                "runRemoved": not candidate["runPath"].exists(),
                "worktreeRemoved": not candidate["worktree"].exists(),
            }
        )
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Safely clean terminal Sol Pi Advisor runs")
    root.add_argument("--state-root", type=Path, default=default_state_root())
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list durable runs without changing state")

    clean = commands.add_parser("clean", help="dry-run or execute cleanup for one run")
    clean.add_argument("run_id")
    clean.add_argument("--archive-dir", type=Path, required=True)
    clean.add_argument("--outcome", choices=("accepted", "discarded"), required=True)
    clean.add_argument("--accepted-commit")
    clean.add_argument("--review-verdict", choices=("ship",))
    clean.add_argument("--test-summary")
    clean.add_argument("--discard-reason")
    clean.add_argument("--execute", action="store_true")
    return root


def main() -> int:
    arguments = parser().parse_args()
    try:
        value = list_runs(arguments.state_root) if arguments.command == "list" else cleanup(arguments)
    except (CleanupError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
