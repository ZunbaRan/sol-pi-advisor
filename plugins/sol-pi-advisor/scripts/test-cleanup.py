from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


plugin = Path(__file__).resolve().parent.parent
cleanup = plugin / "skills" / "cleanup" / "scripts" / "cleanup-runs.py"


def command(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["python3", str(cleanup), *arguments],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if check and completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return completed


def git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return completed.stdout.strip()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


with tempfile.TemporaryDirectory(prefix="sol-pi-cleanup-test-") as raw_root:
    root = Path(raw_root)
    repository = root / "repo"
    state_root = root / "state"
    runs = state_root / "runs"
    worktrees = state_root / "worktrees"
    archive_root = root / "evidence"
    repository.mkdir()
    runs.mkdir(parents=True)
    worktrees.mkdir()

    git(repository, "init", "-q")
    git(repository, "config", "user.name", "Sol Pi Cleanup Test")
    git(repository, "config", "user.email", "cleanup@example.invalid")
    source = repository / "src"
    source.mkdir()
    (source / "value.txt").write_text("base\n", encoding="utf-8")
    git(repository, "add", "src/value.txt")
    git(repository, "commit", "-q", "-m", "base")
    base_commit = git(repository, "rev-parse", "HEAD")

    run_id = "11111111-1111-4111-8111-111111111111"
    run_path = runs / run_id
    worktree = worktrees / run_id
    run_path.mkdir()
    git(repository, "worktree", "add", "--detach", str(worktree), base_commit)
    (worktree / "src" / "value.txt").write_text("accepted\n", encoding="utf-8")
    patch = subprocess.run(
        ["git", "-C", str(worktree), "diff", "--binary", base_commit],
        capture_output=True,
        timeout=30,
        check=True,
    ).stdout
    patch_path = run_path / "diff-revision-0.patch"
    patch_path.write_bytes(patch)
    patch_digest = hashlib.sha256(patch).hexdigest()
    (run_path / ".lock").touch()
    write_json(
        run_path / "manifest.json",
        {
            "runId": run_id,
            "batchId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "laneId": "cleanup-lane",
            "parallelLaneCount": 2,
            "repoRoot": str(repository.resolve()),
            "baseCommit": base_commit,
            "worktree": str(worktree.resolve()),
            "allowedPaths": ["src"],
            "createdAt": time.time(),
        },
    )
    write_json(
        run_path / "status.json",
        {
            "state": "ready",
            "revision": 0,
            "pid": None,
            "piPid": None,
            "finishedAt": time.time(),
            "evidence": {
                "changedPaths": ["src/value.txt"],
                "diffDigest": patch_digest,
                "violations": [],
            },
        },
    )

    (source / "value.txt").write_text("accepted\n", encoding="utf-8")
    git(repository, "add", "src/value.txt")
    git(repository, "commit", "-q", "-m", "accept candidate")
    accepted_commit = git(repository, "rev-parse", "HEAD")

    inventory = json.loads(command("--state-root", str(state_root), "list").stdout)
    assert inventory["runCount"] == 1
    assert inventory["runs"][0]["runId"] == run_id
    assert inventory["runs"][0]["batchId"] == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    assert inventory["runs"][0]["laneId"] == "cleanup-lane"

    cleanup_arguments = (
        "--state-root",
        str(state_root),
        "clean",
        run_id,
        "--archive-dir",
        str(archive_root),
        "--outcome",
        "accepted",
        "--accepted-commit",
        accepted_commit,
        "--review-verdict",
        "ship",
        "--test-summary",
        "cleanup integration test passed",
    )
    preview = json.loads(command(*cleanup_arguments).stdout)
    assert preview["mode"] == "dry-run"
    assert preview["worktreeDirty"] is True
    assert run_path.exists()
    assert worktree.exists()
    assert not archive_root.exists()

    executed = json.loads(command(*cleanup_arguments, "--execute").stdout)
    assert executed["runRemoved"] is True
    assert executed["worktreeRemoved"] is True
    assert executed["estimatedNetBytesReclaimed"] >= 0
    assert not run_path.exists()
    assert not worktree.exists()
    assert str(worktree) not in git(repository, "worktree", "list", "--porcelain")

    archive = archive_root / run_id
    evidence = json.loads((archive / "cleanup-evidence.json").read_text(encoding="utf-8"))
    assert evidence["batchId"] == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    assert evidence["laneId"] == "cleanup-lane"
    assert evidence["acceptedCommit"] == accepted_commit
    assert evidence["reviewVerdict"] == "ship"
    assert evidence["patchDigest"] == patch_digest
    assert hashlib.sha256((archive / patch_path.name).read_bytes()).hexdigest() == patch_digest

    after = json.loads(command("--state-root", str(state_root), "list").stdout)
    assert after["runCount"] == 0

    active_id = "22222222-2222-4222-8222-222222222222"
    active_run = runs / active_id
    active_worktree = worktrees / active_id
    active_run.mkdir()
    git(repository, "worktree", "add", "--detach", str(active_worktree), accepted_commit)
    (active_run / ".lock").touch()
    write_json(
        active_run / "manifest.json",
        {
            "runId": active_id,
            "repoRoot": str(repository.resolve()),
            "baseCommit": accepted_commit,
            "worktree": str(active_worktree.resolve()),
            "allowedPaths": ["src"],
            "createdAt": time.time(),
        },
    )
    write_json(
        active_run / "status.json",
        {"state": "running", "revision": 0, "pid": os.getpid(), "piPid": None},
    )
    refused = command(
        "--state-root",
        str(state_root),
        "clean",
        active_id,
        "--archive-dir",
        str(archive_root),
        "--outcome",
        "discarded",
        "--discard-reason",
        "test refusal",
        "--execute",
        check=False,
    )
    assert refused.returncode == 2
    assert "not terminal" in refused.stderr
    assert active_run.exists()
    assert active_worktree.exists()

    write_json(
        active_run / "status.json",
        {"state": "ready", "revision": 0, "pid": os.getpid(), "piPid": None},
    )
    live_process = command(
        "--state-root",
        str(state_root),
        "clean",
        active_id,
        "--archive-dir",
        str(archive_root),
        "--outcome",
        "discarded",
        "--discard-reason",
        "test live-process refusal",
        "--execute",
        check=False,
    )
    assert live_process.returncode == 2
    assert "still alive" in live_process.stderr
    assert active_run.exists()
    assert active_worktree.exists()

print("CLEANUP TEST PASSED")
