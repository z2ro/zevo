#!/usr/bin/env python3
"""Validate and query graph/tasks.yaml using only Python's standard library.

The graph is encoded as JSON, which is a valid YAML 1.2 subset.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "graph" / "tasks.yaml"
REQUIRED = {
    "id": str,
    "description": str,
    "agent": str,
    "status": str,
    "depends_on": list,
    "read_context": list,
    "write_scope": list,
    "validation": list,
    "review_required": bool,
}
TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class GraphError(ValueError):
    pass


def load_graph() -> dict:
    try:
        return json.loads(GRAPH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GraphError(f"cannot load {GRAPH.relative_to(ROOT)}: {exc}") from exc


def safe_relative(value: str, label: str) -> None:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("./"):
        raise GraphError(f"{label} must be a normalized repository-relative path: {value}")


def validate_graph(graph: dict) -> None:
    if graph.get("schema_version") not in {1, 2}:
        raise GraphError("schema_version must be 1 or 2")
    statuses = graph.get("statuses")
    expected = {"pending", "ready", "running", "blocked", "review", "failed", "done"}
    if not isinstance(statuses, list) or set(statuses) != expected:
        raise GraphError(f"statuses must contain exactly: {', '.join(sorted(expected))}")
    tasks = graph.get("tasks")
    if not isinstance(tasks, dict) or not tasks:
        raise GraphError("tasks must be a non-empty object")

    for task_id, task in tasks.items():
        if not TASK_ID_RE.fullmatch(task_id):
            raise GraphError(f"invalid task id: {task_id}")
        if not isinstance(task, dict):
            raise GraphError(f"task {task_id} must be an object")
        missing = set(REQUIRED) - set(task)
        extra = set(task) - set(REQUIRED)
        if missing or extra:
            raise GraphError(f"task {task_id} fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
        for field, field_type in REQUIRED.items():
            if not isinstance(task[field], field_type):
                raise GraphError(f"task {task_id}.{field} must be {field_type.__name__}")
        if task["id"] != task_id:
            raise GraphError(f"task key {task_id} differs from embedded id {task['id']}")
        if task["status"] not in expected:
            raise GraphError(f"task {task_id} has invalid status {task['status']}")
        if task_id in task["depends_on"]:
            raise GraphError(f"task {task_id} depends on itself")
        agent_file = ROOT / "agents" / f"{task['agent']}.md"
        if not agent_file.is_file():
            raise GraphError(f"task {task_id} references missing {agent_file.relative_to(ROOT)}")
        for dep in task["depends_on"]:
            if dep not in tasks:
                raise GraphError(f"task {task_id} references unknown dependency {dep}")
        for field in ("read_context", "write_scope", "validation"):
            if not all(isinstance(item, str) and item for item in task[field]):
                raise GraphError(f"task {task_id}.{field} must contain non-empty strings")
        if not task["write_scope"]:
            raise GraphError(f"task {task_id}.write_scope cannot be empty")
        for value in task["read_context"] + task["write_scope"]:
            safe_relative(value, f"task {task_id}")
        for context in task["read_context"]:
            if any(ch in context for ch in "*?["):
                if not list(ROOT.glob(context)):
                    raise GraphError(f"task {task_id} context glob matches nothing: {context}")
            elif not (ROOT / context).exists():
                raise GraphError(f"task {task_id} context does not exist: {context}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise GraphError(f"dependency cycle detected at {task_id}")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dep in tasks[task_id]["depends_on"]:
            visit(dep)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id)

    parallel_groups = graph.get("parallel_groups")
    if not isinstance(parallel_groups, dict):
        raise GraphError("parallel_groups must be an object")
    for group_name, members in parallel_groups.items():
        if not isinstance(group_name, str) or not isinstance(members, list) or len(members) < 2:
            raise GraphError("each parallel group must have a name and at least two task ids")
        if len(members) != len(set(members)):
            raise GraphError(f"parallel group {group_name} contains duplicate tasks")
        for member in members:
            if member not in tasks:
                raise GraphError(f"parallel group {group_name} references unknown task {member}")

        def ancestors(task_id: str) -> set[str]:
            result: set[str] = set()
            stack = list(tasks[task_id]["depends_on"])
            while stack:
                current = stack.pop()
                if current not in result:
                    result.add(current)
                    stack.extend(tasks[current]["depends_on"])
            return result

        for index, left in enumerate(members):
            for right in members[index + 1:]:
                if left in ancestors(right) or right in ancestors(left):
                    raise GraphError(f"parallel group {group_name} contains dependent tasks {left} and {right}")
                overlap = set(tasks[left]["write_scope"]) & set(tasks[right]["write_scope"])
                if overlap:
                    raise GraphError(f"parallel group {group_name} has identical write scopes: {sorted(overlap)}")


def get_task(graph: dict, task_id: str) -> dict:
    try:
        return graph["tasks"][task_id]
    except KeyError as exc:
        raise GraphError(f"unknown task: {task_id}") from exc


def deps_done(graph: dict, task: dict) -> bool:
    return all(graph["tasks"][dep]["status"] == "done" for dep in task["depends_on"])


def glob_regex(pattern: str) -> re.Pattern[str]:
    safe_relative(pattern, "scope pattern")
    index = 0
    result = ""
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                index += 2
                if index < len(pattern) and pattern[index] == "/":
                    result += "(?:.*/)?"
                    index += 1
                else:
                    result += ".*"
                continue
            result += "[^/]*"
        elif char == "?":
            result += "[^/]"
        else:
            result += re.escape(char)
        index += 1
    return re.compile(f"^{result}$")


def path_allowed(path: str, patterns: list[str]) -> bool:
    safe_relative(path, "changed path")
    return any(glob_regex(pattern).fullmatch(path) for pattern in patterns)


def prompt(graph: dict, task_id: str, review: bool) -> str:
    task = get_task(graph, task_id)
    if review:
        agent = "reviewer"
        write_scope = [
            "agent_reports/final-review.md"
            if task_id == "final-review"
            else f"agent_reports/{task_id}-review.md"
        ]
        mode = "REVIEW. Não implemente nem corrija features."
    else:
        agent = task["agent"]
        write_scope = task["write_scope"]
        mode = "IMPLEMENTAÇÃO/COORDENAÇÃO conforme a tarefa."
    agent_text = (ROOT / "agents" / f"{agent}.md").read_text(encoding="utf-8")
    return f"""{agent_text}

--- TASK ENVELOPE (authoritative) ---
MODE: {mode}
TASK_ID: {task_id}
DESCRIPTION: {task['description']}
STATUS_AT_START: {task['status']}
READ_CONTEXT: {json.dumps(task['read_context'], ensure_ascii=False)}
WRITE_SCOPE: {json.dumps(write_scope, ensure_ascii=False)}
VALIDATION: {json.dumps(task['validation'], ensure_ascii=False)}
HANDOFF: {write_scope[-1]}

Leia todos os READ_CONTEXT antes de agir. WRITE_SCOPE é o limite efetivo desta execução.
Não altere graph/tasks.yaml; o Orchestrator controla estados. Registre no handoff arquivos,
contratos, testes, falhas, questões e notas. Se algo fora do escopo precisar mudar, reporte e pare
essa parte; não faça a correção silenciosamente.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    sub.add_parser("ready")
    sub.add_parser("parallel")
    task_parser = sub.add_parser("task")
    task_parser.add_argument("task_id")
    prompt_parser = sub.add_parser("prompt")
    prompt_parser.add_argument("task_id")
    prompt_parser.add_argument("--review", action="store_true")
    check_parser = sub.add_parser("check-runnable")
    check_parser.add_argument("task_id")
    check_parser.add_argument("--review", action="store_true")
    scope_parser = sub.add_parser("scope")
    scope_parser.add_argument("task_id")
    scope_parser.add_argument("paths", nargs="+")
    scope_parser.add_argument("--review", action="store_true")
    args = parser.parse_args()

    try:
        graph = load_graph()
        validate_graph(graph)
        if args.command == "validate":
            print(f"GRAPH VALID: {len(graph['tasks'])} tasks")
        elif args.command == "ready":
            found = False
            for task_id, task in graph["tasks"].items():
                if deps_done(graph, task) and task["status"] in {"ready", "pending"}:
                    label = "ready" if task["status"] == "ready" else "candidate (promote to ready)"
                    print(f"{task_id}\t{label}\t{task['agent']}")
                    found = True
            if not found:
                print("No ready tasks")
        elif args.command == "parallel":
            for name, members in graph["parallel_groups"].items():
                runnable = all(
                    deps_done(graph, graph["tasks"][member])
                    and graph["tasks"][member]["status"] == "ready"
                    for member in members
                )
                state = "runnable" if runnable else "not-ready"
                print(f"{name}\t{state}\t{','.join(members)}")
        elif args.command == "task":
            print(json.dumps(get_task(graph, args.task_id), ensure_ascii=False, indent=2))
        elif args.command == "prompt":
            print(prompt(graph, args.task_id, args.review))
        elif args.command == "check-runnable":
            task = get_task(graph, args.task_id)
            if args.review:
                allowed = task["status"] == "review" or (
                    args.task_id == "final-review" and task["status"] == "ready"
                )
                if not allowed:
                    raise GraphError(f"review requires status review (or ready for final-review), got {task['status']}")
            else:
                if task["status"] not in {"ready", "failed"}:
                    raise GraphError(f"task {args.task_id} is {task['status']}, expected ready")
                if not deps_done(graph, task):
                    pending = [dep for dep in task["depends_on"] if graph["tasks"][dep]["status"] != "done"]
                    raise GraphError(f"unsatisfied dependencies: {', '.join(pending)}")
            print("RUNNABLE")
        elif args.command == "scope":
            task = get_task(graph, args.task_id)
            patterns = (["agent_reports/final-review.md"] if args.task_id == "final-review" else
                        [f"agent_reports/{args.task_id}-review.md"]) if args.review else task["write_scope"]
            denied = [path for path in args.paths if not path_allowed(path, patterns)]
            if denied:
                print("SCOPE VALIDATION: FAIL", file=sys.stderr)
                print("Disallowed files:", file=sys.stderr)
                for path in denied:
                    print(f"  {path}", file=sys.stderr)
                print("Allowed patterns:", file=sys.stderr)
                for pattern in patterns:
                    print(f"  {pattern}", file=sys.stderr)
                return 3
            print(f"SCOPE VALIDATION: PASS ({len(args.paths)} paths)")
    except GraphError as exc:
        print(f"GRAPH ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
