from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Iterator


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
RUN_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
LANE_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
DEPENDENCY_STATE_FILENAMES = frozenset(
    {
        "bun.lock",
        "bun.lockb",
        "deno.lock",
        "npm-shrinkwrap.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "Cargo.lock",
        "Pipfile.lock",
        "poetry.lock",
        "uv.lock",
        "go.sum",
    }
)


class LaneError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def codex_home() -> Path:
    value = os.environ.get("CODEX_HOME")
    return Path(value).expanduser() if value else Path.home() / ".codex"


def state_root() -> Path:
    return codex_home() / "sol-pi-advisor"


def ensure_state_root() -> Path:
    root = state_root()
    for path in (root, root / "runs", root / "worktrees"):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def run_dir(run_id: str) -> Path:
    if not RUN_ID_RE.fullmatch(run_id):
        raise LaneError("InvalidRunId", "runId must be a canonical lowercase UUID")
    return ensure_state_root() / "runs" / run_id


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LaneError("RunNotFound", f"missing state file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LaneError("StateCorrupt", f"invalid JSON state: {path}") from exc


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


@contextlib.contextmanager
def locked(run_path: Path) -> Iterator[None]:
    run_path.mkdir(parents=True, exist_ok=True)
    lock_path = run_path / ".lock"
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def update_status(run_path: Path, **changes: Any) -> dict[str, Any]:
    with locked(run_path):
        status_path = run_path / "status.json"
        current = read_json(status_path) if status_path.exists() else {}
        current.update(changes)
        atomic_write_json(status_path, current)
        return current


def _version_key(path: Path) -> tuple[int, ...]:
    name = path.parents[1].name
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", name)
    return tuple(int(part) for part in match.group(1).split(".")) if match else (0,)


def discover_pi() -> dict[str, str]:
    configured_node = os.environ.get("SOL_PI_NODE")
    configured_cli = os.environ.get("SOL_PI_CLI")
    candidates: list[tuple[Path, Path]] = []

    if configured_node or configured_cli:
        if not configured_node or not configured_cli:
            raise LaneError(
                "PiConfigurationInvalid",
                "SOL_PI_NODE and SOL_PI_CLI must be provided together",
            )
        candidates.append((Path(configured_node).expanduser(), Path(configured_cli).expanduser()))
    else:
        for cli in sorted(
            (Path.home() / ".nvm" / "versions" / "node").glob("*/bin/pi"),
            key=_version_key,
            reverse=True,
        ):
            candidates.append((cli.with_name("node"), cli))

    failures: list[str] = []
    for node, cli in candidates:
        if not node.is_file() or not os.access(node, os.X_OK):
            failures.append(f"node unavailable: {node}")
            continue
        if not cli.exists():
            failures.append(f"Pi unavailable: {cli}")
            continue
        preflight_config = state_root() / "preflight-pi-config"
        preflight_config.mkdir(parents=True, exist_ok=True, mode=0o700)
        completed = subprocess.run(
            [str(node), str(cli), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            env={
                **os.environ,
                "PI_CODING_AGENT_DIR": str(preflight_config),
                "PI_OFFLINE": "1",
                "PI_SKIP_VERSION_CHECK": "1",
            },
            check=False,
        )
        version = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
        if completed.returncode == 0 and version:
            return {
                "nodePath": str(node.resolve()),
                "piPath": str(cli.resolve()),
                "piVersion": version,
            }
        failures.append(f"{cli}: exit {completed.returncode}")

    detail = "; ".join(failures) if failures else "no ~/.nvm Pi installation found"
    raise LaneError("PiUnavailable", detail)


def preflight() -> dict[str, Any]:
    identity = discover_pi()
    git = shutil.which("git")
    if not git:
        raise LaneError("GitUnavailable", "git is not available")
    git_version = subprocess.run(
        [git, "--version"], capture_output=True, text=True, timeout=10, check=True
    ).stdout.strip()
    root = ensure_state_root()
    return {
        **identity,
        "gitPath": git,
        "gitVersion": git_version,
        "stateRoot": str(root),
        "executionModes": ["supervised-local"],
        "sandboxEnforced": False,
    }


def normalize_allowed_paths(values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        raise LaneError("InvalidOwnership", "allowedPaths must be a non-empty array")
    normalized: list[str] = []
    for raw in values:
        if not isinstance(raw, str) or not raw.strip():
            raise LaneError("InvalidOwnership", "allowed paths must be non-empty strings")
        candidate = raw.strip().replace("\\", "/").rstrip("/")
        path = PurePosixPath(candidate)
        if path.is_absolute() or ".." in path.parts or candidate in ("", "."):
            raise LaneError("InvalidOwnership", f"invalid repository-relative path: {raw}")
        if path.parts[0] == ".git" or any(char in candidate for char in "*?[]{}"):
            raise LaneError("InvalidOwnership", f"protected or glob path is not allowed: {raw}")
        normalized.append(path.as_posix())
    return sorted(set(normalized))


def normalize_lane_id(value: Any) -> str:
    if not isinstance(value, str) or not LANE_ID_RE.fullmatch(value):
        raise LaneError(
            "InvalidLaneId",
            "laneId must start with a lowercase letter and contain only lowercase letters, digits, or hyphens (maximum 64 characters)",
        )
    return value


def ownership_paths_overlap(left: list[str], right: list[str]) -> list[tuple[str, str]]:
    overlaps: list[tuple[str, str]] = []
    for left_path in left:
        for right_path in right:
            if (
                left_path == right_path
                or left_path.startswith(right_path + "/")
                or right_path.startswith(left_path + "/")
            ):
                overlaps.append((left_path, right_path))
    return overlaps


def resolve_repository(repo_root: Any, base_ref: Any) -> tuple[Path, str]:
    if not isinstance(repo_root, str) or not repo_root:
        raise LaneError("InvalidRepository", "repoRoot is required")
    if not isinstance(base_ref, str) or not base_ref:
        raise LaneError("InvalidBase", "baseRef is required")
    root = Path(repo_root).expanduser().resolve()
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if completed.returncode != 0:
        raise LaneError("InvalidRepository", completed.stderr.strip() or "not a Git repository")
    top = Path(completed.stdout.strip()).resolve()
    if top != root:
        raise LaneError("InvalidRepository", f"repoRoot must be the Git top-level: {top}")
    base = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", f"{base_ref}^{{commit}}"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if base.returncode != 0:
        raise LaneError("InvalidBase", base.stderr.strip() or f"cannot resolve {base_ref}")
    return root, base.stdout.strip()


def path_is_allowed(path: str, allowed: list[str]) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in allowed)


def _nul_paths(command: list[str], cwd: Path) -> list[str]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, timeout=30, check=False)
    if completed.returncode != 0:
        raise LaneError(
            "GitEvidenceFailed",
            completed.stderr.decode("utf-8", errors="replace").strip(),
        )
    return [item.decode("utf-8", errors="surrogateescape") for item in completed.stdout.split(b"\0") if item]


def collect_git_policy_snapshot(run_path: Path) -> dict[str, Any]:
    manifest = read_json(run_path / "manifest.json")
    worktree = Path(manifest["worktree"])
    base = manifest["baseCommit"]
    allowed = manifest["allowedPaths"]

    head_result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=worktree, capture_output=True, text=True, timeout=15, check=True
    )
    head = head_result.stdout.strip()
    tracked = _nul_paths(
        ["git", "diff", "--name-only", "-z", "--no-renames", base], worktree
    )
    staged = _nul_paths(
        ["git", "diff", "--cached", "--name-only", "-z", "--no-renames"], worktree
    )
    untracked = _nul_paths(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"], worktree
    )
    changed = sorted(set(tracked + staged + untracked))

    violations: list[dict[str, str]] = []
    if head != base:
        violations.append({"code": "HeadMoved", "detail": f"HEAD {head} != base {base}"})
    if staged:
        violations.append({"code": "IndexModified", "detail": ", ".join(staged)})
    outside = [path for path in changed if not path_is_allowed(path, allowed)]
    if outside:
        violations.append({"code": "OwnershipViolation", "detail": ", ".join(outside)})

    dependency_state_changes = [
        path for path in changed if PurePosixPath(path).name in DEPENDENCY_STATE_FILENAMES
    ]
    digest_payload = {
        "baseCommit": base,
        "head": head,
        "changedPaths": changed,
        "stagedPaths": sorted(staged),
        "untrackedPaths": sorted(untracked),
        "outsideAllowedPaths": outside,
        "dependencyStateChanges": dependency_state_changes,
    }
    state_digest = hashlib.sha256(
        json.dumps(digest_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return {
        "policyBasis": "git-worktree-state",
        "stdoutUsedForPolicy": False,
        "worktree": str(worktree),
        "baseCommit": base,
        "head": head,
        "changedPaths": changed,
        "stagedPaths": sorted(staged),
        "untrackedPaths": sorted(untracked),
        "outsideAllowedPaths": outside,
        "dependencyStateChanges": dependency_state_changes,
        "allowedPaths": allowed,
        "stateDigest": state_digest,
        "violations": violations,
    }


def collect_git_evidence(run_path: Path, revision: int) -> dict[str, Any]:
    policy = collect_git_policy_snapshot(run_path)
    worktree = Path(policy["worktree"])
    base = policy["baseCommit"]
    untracked = policy["untrackedPaths"]

    diff_result = subprocess.run(
        ["git", "diff", "--binary", "--no-ext-diff", base],
        cwd=worktree,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if diff_result.returncode != 0:
        raise LaneError("GitEvidenceFailed", diff_result.stderr.decode(errors="replace"))

    artifact = bytearray(diff_result.stdout)
    for relative in untracked:
        file_path = worktree / relative
        marker = f"\n# sol-pi-advisor untracked: {relative}\n".encode()
        artifact.extend(marker)
        if file_path.is_symlink():
            artifact.extend(f"# symlink -> {os.readlink(file_path)}\n".encode())
            continue
        if not file_path.is_file():
            artifact.extend(b"# non-regular file\n")
            continue
        extra = subprocess.run(
            ["git", "diff", "--no-index", "--binary", "--", "/dev/null", relative],
            cwd=worktree,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if extra.returncode not in (0, 1):
            raise LaneError("GitEvidenceFailed", extra.stderr.decode(errors="replace"))
        artifact.extend(extra.stdout)

    diff_path = run_path / f"diff-revision-{revision}.patch"
    diff_path.write_bytes(bytes(artifact))
    digest = hashlib.sha256(bytes(artifact)).hexdigest()

    return {
        **policy,
        "diffArtifact": str(diff_path),
        "diffDigest": digest,
    }


def process_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    # The MCP server intentionally detaches supervisor Popen objects after
    # recording their PID. Reap a settled direct child here so a zombie is not
    # mistaken for a live lane during abort/busy checks.
    try:
        reaped, _ = os.waitpid(pid, os.WNOHANG)
        if reaped == pid:
            return False
    except (ChildProcessError, PermissionError):
        pass
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def active_run_for_repository(repo_root: Path) -> str | None:
    runs = ensure_state_root() / "runs"
    for candidate in runs.iterdir():
        if not candidate.is_dir() or not RUN_ID_RE.fullmatch(candidate.name):
            continue
        manifest_path = candidate / "manifest.json"
        status_path = candidate / "status.json"
        if not manifest_path.exists() or not status_path.exists():
            continue
        manifest = read_json(manifest_path)
        status = read_json(status_path)
        if manifest.get("repoRoot") != str(repo_root):
            continue
        if status.get("state") in {"preparing", "running", "pausing", "aborting"} and process_alive(status.get("pid")):
            return candidate.name
    return None


def run_paths_for_batch(batch_id: str) -> list[Path]:
    if not RUN_ID_RE.fullmatch(batch_id):
        raise LaneError("InvalidBatchId", "batchId must be a canonical lowercase UUID")
    result: list[Path] = []
    runs = ensure_state_root() / "runs"
    for candidate in runs.iterdir():
        if not candidate.is_dir() or not RUN_ID_RE.fullmatch(candidate.name):
            continue
        manifest_path = candidate / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = read_json(manifest_path)
        if manifest.get("batchId") == batch_id:
            result.append(candidate)
    return sorted(result, key=lambda path: read_json(path / "manifest.json").get("laneId", ""))
