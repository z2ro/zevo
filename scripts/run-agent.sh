#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"

usage() {
  echo "Usage: $0 <agent-name> [--dry-run] [instruction ...]" >&2
}

[[ $# -ge 1 ]] || { usage; exit 2; }
agent="$1"
shift
[[ "$agent" =~ ^[a-z0-9-]+$ ]] || { echo "Invalid agent name" >&2; exit 2; }
prompt_file="$repo_root/agents/$agent.md"
[[ -f "$prompt_file" ]] || { echo "Unknown agent: $agent" >&2; exit 2; }

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then dry_run=1; shift; fi
instruction="${*:-Leia seu prompt, inspecione o estado e produza somente um diagnóstico dentro do seu papel.}"

echo "Agent: $agent"
echo "Prompt: ${prompt_file#$repo_root/}"
echo "Command: codex exec --sandbox workspace-write -C $repo_root -"
(( dry_run == 1 )) && exit 0
command -v codex >/dev/null || { echo "codex CLI not found; run the command shown above after installation." >&2; exit 127; }
{ sed -n '1,$p' "$prompt_file"; printf '\n\nUSER INSTRUCTION:\n%s\n' "$instruction"; } |
  codex exec --sandbox workspace-write -C "$repo_root" --skip-git-repo-check -
