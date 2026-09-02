#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"

usage() {
  echo "Usage: $0 --list-ready | <task-id> [--dry-run] [--review] [--allow-dirty]" >&2
}

if [[ "${1:-}" == "--list-ready" ]]; then
  cd "$repo_root"
  exec python3 scripts/task_graph.py ready
fi
[[ $# -ge 1 ]] || { usage; exit 2; }
task_id="$1"
shift
dry_run=0
review=0
allow_dirty=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --review) review=1 ;;
    --allow-dirty) allow_dirty=1 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

cd "$repo_root"
check_args=(check-runnable "$task_id")
(( review == 1 )) && check_args+=(--review)
python3 scripts/task_graph.py "${check_args[@]}" >/dev/null

task_json="$(python3 scripts/task_graph.py task "$task_id")"
agent="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["agent"])' <<<"$task_json")"
(( review == 1 )) && agent="reviewer"

echo "Task: $task_id"
echo "Agent: $agent"
python3 -c '
import json, sys
t=json.load(sys.stdin)
for key in ("depends_on", "read_context", "write_scope", "validation"):
    print(f"{key}:")
    for value in t[key]: print(f"  - {value}")
' <<<"$task_json"
echo "Command: codex exec --sandbox workspace-write -C $repo_root -"

if (( dry_run == 1 )); then
  exit 0
fi
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Refusing mutable run: repository is not initialized as Git. Dry-run remains available." >&2
  exit 4
fi
if (( allow_dirty == 0 )) && [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing mutable run on a dirty worktree. Commit/stash changes or pass --allow-dirty knowingly." >&2
  exit 4
fi
command -v codex >/dev/null || { echo "codex CLI not found; run the command shown above after installation." >&2; exit 127; }

prompt_tmp="$(mktemp)"
cleanup() { rm -f -- "$prompt_tmp"; }
trap cleanup EXIT
prompt_args=(prompt "$task_id")
(( review == 1 )) && prompt_args+=(--review)
python3 scripts/task_graph.py "${prompt_args[@]}" > "$prompt_tmp"

codex exec --sandbox workspace-write -C "$repo_root" - < "$prompt_tmp"
scope_args=("$task_id")
(( review == 1 )) && scope_args+=(--review)
./scripts/validate-agent-scope.sh "${scope_args[@]}"

if (( review == 0 )); then
  while IFS= read -r -d '' validation; do
    echo "Running validation: $validation"
    bash -lc "$validation"
  done < <(python3 -c 'import json,sys; [sys.stdout.buffer.write(x.encode()+b"\0") for x in json.load(sys.stdin)["validation"]]' <<<"$task_json")
  review_required="$(python3 -c 'import json,sys; print(str(json.load(sys.stdin)["review_required"]).lower())' <<<"$task_json")"
  if [[ "$review_required" == "true" ]]; then
    echo "Implementation validated. Orchestrator should move task to review."
  else
    echo "Task validated. Orchestrator may move it to done."
  fi
else
  echo "Review completed. Orchestrator must read the review report and apply PASS/FAIL transition."
fi
