#!/bin/sh

set -eu

fail() {
  printf '%s\n' "VERIFY FAILED: $*" >&2
  exit 1
}

script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd) || exit 1
plugin_dir=$(CDPATH= cd "$script_dir/.." && pwd) || exit 1
manifest=$plugin_dir/.codex-plugin/plugin.json
mcp_manifest=$plugin_dir/.mcp.json
skill=$plugin_dir/skills/orchestration/SKILL.md
reviewer=$plugin_dir/agents/sol-pi-advisor-sol-reviewer.toml
installer=$plugin_dir/scripts/install-agent.sh

python3 - "$manifest" "$mcp_manifest" <<'PY' || fail 'manifest validation failed.'
import json
import pathlib
import sys

manifest = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert manifest["name"] == "sol-pi-advisor"
assert manifest["version"].split("+", 1)[0] == "0.1.0"
assert manifest["skills"] == "./skills/"
assert manifest["mcpServers"] == "./.mcp.json"
assert manifest["interface"]["displayName"] == "Sol Pi Advisor"

mcp = json.loads(pathlib.Path(sys.argv[2]).read_text())
server = mcp["mcpServers"]["sol-pi-advisor"]
assert server["command"] == "./bin/sol-pi-advisor-mcp"
assert server["cwd"] == "."
PY

grep -q '^name: orchestration$' "$skill" || fail 'skill name is invalid.'
grep -q 'pi_lane_preflight' "$skill" || fail 'Pi preflight tool is missing.'
grep -q 'pi_lane_start' "$skill" || fail 'Pi start tool is missing.'
grep -q 'pi_lane_drive' "$skill" || fail 'Pi drive tool is missing.'
grep -q 'sol_pi_advisor_sol_reviewer' "$skill" || fail 'reviewer role is missing.'
grep -q 'supervised-local' "$skill" || fail 'execution boundary is missing.'
grep -q '`high`, `xhigh`, or' "$skill" || fail 'eligible primary reasoning levels are missing.'
grep -q 'do not reject `xhigh` or `max`' "$skill" || fail 'higher primary reasoning levels are not explicitly accepted.'

grep -q '^name = "sol_pi_advisor_sol_reviewer"$' "$reviewer" || fail 'reviewer name is invalid.'
grep -q '^model = "gpt-5.6-sol"$' "$reviewer" || fail 'reviewer model is invalid.'
grep -q '^model_reasoning_effort = "high"$' "$reviewer" || fail 'reviewer effort is invalid.'
grep -q '^sandbox_mode = "read-only"$' "$reviewer" || fail 'reviewer sandbox request is invalid.'
grep -q 'ship,' "$reviewer" || fail 'ship verdict is missing.'
grep -q 'fix-first' "$reviewer" || fail 'fix-first verdict is missing.'
grep -q 'rethink' "$reviewer" || fail 'rethink verdict is missing.'

if grep -R -n 'gpt-5.6-luna\|luna_worker\|sol_luna_advisor' \
  "$plugin_dir/.codex-plugin" "$plugin_dir/agents" "$plugin_dir/skills" \
  "$plugin_dir/mcp" "$plugin_dir/pi-extensions" >/dev/null; then
  fail 'a Luna implementation path is wired into Sol Pi Advisor.'
fi

sh -n "$installer" || fail 'installer shell syntax is invalid.'
sh -n "$plugin_dir/scripts/check-pi.sh" || fail 'check-pi shell syntax is invalid.'
sh -n "$plugin_dir/scripts/verify.sh" || fail 'verifier shell syntax is invalid.'
sh -n "$plugin_dir/bin/sol-pi-advisor-mcp" || fail 'MCP launcher syntax is invalid.'

python3 - "$plugin_dir/mcp/common.py" "$plugin_dir/mcp/run_worker.py" \
  "$plugin_dir/mcp/server.py" "$plugin_dir/scripts/smoke-mcp.py" \
  "$plugin_dir/scripts/test-fake-pi.py" <<'PY' || fail 'Python syntax validation failed.'
import pathlib
import sys

for raw in sys.argv[1:]:
    path = pathlib.Path(raw)
    compile(path.read_text(), str(path), "exec")
PY

test_root=$(mktemp -d "${TMPDIR:-/tmp}/sol-pi-advisor-verify.XXXXXX") ||
  fail 'could not create test directory.'
trap 'rm -rf "$test_root"' EXIT HUP INT TERM

sh "$installer" --target-dir "$test_root/agents" >/dev/null
sh "$installer" --target-dir "$test_root/agents" --check >/dev/null
cmp -s "$reviewer" "$test_root/agents/sol-pi-advisor-sol-reviewer.toml" ||
  fail 'installed reviewer differs from template.'

CODEX_HOME=$test_root/codex "$plugin_dir/scripts/check-pi.sh" >"$test_root/preflight.json" ||
  fail 'Pi preflight failed.'
python3 - "$test_root/preflight.json" <<'PY' || fail 'Pi preflight result is invalid.'
import json
import pathlib
import sys

data = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert data["piVersion"] == "0.83.0"
assert data["versionCompatible"] is True
assert data["sandboxEnforced"] is False
assert data["executionModes"] == ["supervised-local"]
PY

CODEX_HOME=$test_root/codex python3 "$plugin_dir/scripts/smoke-mcp.py" >/dev/null ||
  fail 'MCP smoke test failed.'

python3 "$plugin_dir/scripts/test-fake-pi.py" >/dev/null ||
  fail 'fake Pi end-to-end test failed.'

quick_validate=
if [ -n "${CODEX_HOME-}" ]; then
  quick_validate=$CODEX_HOME/skills/.system/skill-creator/scripts/quick_validate.py
elif [ -n "${HOME-}" ]; then
  quick_validate=$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py
fi
if [ -n "$quick_validate" ] && [ -f "$quick_validate" ]; then
  python3 "$quick_validate" "$plugin_dir/skills/orchestration" >/dev/null ||
    fail 'skill validation failed.'
fi

printf '%s\n' 'VERIFY PASSED'
