#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
cd "$repo_root"

python3 scripts/task_graph.py validate
python3 scripts/task_graph.py ready | grep -q '^domain-model'
python3 scripts/task_graph.py parallel | grep -q '^post-simulation-rules[[:space:]]\+not-ready'
./scripts/run-task.sh domain-model --dry-run >/dev/null
./scripts/validate-agent-scope.sh simulation-core --files backend/app/simulation/core.py backend/tests/simulation/test_core.py agent_reports/simulation-core.md >/dev/null

if ./scripts/validate-agent-scope.sh simulation-core --files frontend/src/App.tsx >/dev/null 2>&1; then
  echo "Expected out-of-scope validation to fail" >&2
  exit 1
fi

if ./scripts/run-task.sh simulation-core --dry-run >/dev/null 2>&1; then
  echo "Expected unsatisfied dependency check to fail" >&2
  exit 1
fi

for script in scripts/*.sh; do bash -n "$script"; done
echo "MULTI-AGENT SELF-TEST: PASS"
