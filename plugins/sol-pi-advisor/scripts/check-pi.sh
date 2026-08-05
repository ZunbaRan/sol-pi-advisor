#!/bin/sh

set -eu
script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd) || exit 1
plugin_dir=$(CDPATH= cd "$script_dir/.." && pwd) || exit 1

PYTHONPATH=$plugin_dir/mcp /usr/bin/python3 - <<'PY'
import json
from common import preflight

print(json.dumps(preflight(), indent=2, sort_keys=True))
PY
