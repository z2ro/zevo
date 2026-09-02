# Zevo agent coordination

Before changing this repository, read `graph/execution-rules.md`, locate the task in `graph/tasks.yaml`, and use the matching prompt in `agents/`. The task's `write_scope` is authoritative and may be narrower than the agent's general WRITE section.

Do not edit `graph/tasks.yaml` unless acting as the Orchestrator. Do not silently cross domain ownership. Record handoffs in `agent_reports/`, contract changes in the owning document, and architectural proposals for Orchestrator review.

Useful checks:

- `python3 scripts/task_graph.py validate`
- `./scripts/run-task.sh --list-ready`
- `./scripts/validate-agent-scope.sh <task-id>`
