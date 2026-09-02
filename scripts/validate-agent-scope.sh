#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"

usage() {
  echo "Usage: $0 <task-id> [--review] [--files <path> ... | --files-from <file>]" >&2
}

[[ $# -ge 1 ]] || { usage; exit 2; }
task_id="$1"
shift
review=0
mode="git"
files_from=""
declare -a explicit_files=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --review) review=1; shift ;;
    --files) mode="explicit"; shift; explicit_files=("$@"); break ;;
    --files-from)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      mode="file"; files_from="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

cd "$repo_root"
python3 scripts/task_graph.py validate >/dev/null

declare -a changed=()
if [[ "$mode" == "explicit" ]]; then
  changed=("${explicit_files[@]}")
elif [[ "$mode" == "file" ]]; then
  [[ -f "$files_from" ]] || { echo "Files list not found: $files_from" >&2; exit 2; }
  mapfile -t changed < "$files_from"
else
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "SCOPE VALIDATION: UNAVAILABLE - this directory is not a Git worktree." >&2
    echo "Initialize/clone Git first, or test an explicit list with --files." >&2
    exit 4
  fi
  while IFS= read -r -d '' path; do changed+=("$path"); done < <(
    { git diff --name-only -z; git diff --cached --name-only -z; git ls-files --others --exclude-standard -z; }
  )
  if [[ ${#changed[@]} -gt 0 ]]; then
    mapfile -t changed < <(printf '%s\n' "${changed[@]}" | LC_ALL=C sort -u)
  fi
fi

if [[ ${#changed[@]} -eq 0 ]]; then
  echo "SCOPE VALIDATION: PASS (no changed paths)"
  exit 0
fi

args=(scope "$task_id")
(( review == 1 )) && args+=(--review)
args+=("${changed[@]}")
python3 scripts/task_graph.py "${args[@]}"
