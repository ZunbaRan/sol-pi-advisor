from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


plugin = Path(__file__).resolve().parent.parent
process = subprocess.Popen(
    [str(plugin / "bin" / "sol-pi-advisor-mcp")],
    cwd=plugin,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
assert process.stdin is not None
assert process.stdout is not None


def exchange(payload: dict) -> dict:
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()
    line = process.stdout.readline()
    if not line:
        stderr = process.stderr.read() if process.stderr else ""
        raise RuntimeError(f"MCP server exited without response: {stderr}")
    return json.loads(line)


initialized = exchange(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "1"}},
    }
)
assert initialized["result"]["serverInfo"]["name"] == "sol-pi-advisor"

process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
process.stdin.flush()

listed = exchange({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
names = {tool["name"] for tool in listed["result"]["tools"]}
assert names == {
    "pi_lane_preflight",
    "pi_lane_start",
    "pi_lane_batch_start",
    "pi_lane_drive",
    "pi_lane_batch_drive",
}, names

preflight = exchange(
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "pi_lane_preflight", "arguments": {}},
    }
)
parallel = preflight["result"]["structuredContent"]["parallelWave"]
assert parallel == {
    "minimumLanes": 2,
    "maximumLanes": 4,
    "requiresSameBaseCommit": True,
    "requiresDisjointAllowedPaths": True,
}

process.stdin.close()
process.wait(timeout=5)
if process.returncode != 0:
    stderr = process.stderr.read() if process.stderr else ""
    raise RuntimeError(f"MCP smoke failed: {stderr}")
print("MCP SMOKE PASSED")
