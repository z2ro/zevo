from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


OPERATORS = {"eq", "neq", "gt", "gte", "lt", "lte", "in"}
EFFECT_TYPES = {"modify_population", "add_historical_flag"}
TARGETS = {"parasite", "host", "species", "world"}
FIELD_ROOTS = {"species", "parasite", "host", "relation", "world", "player"}
condition_registry = frozenset(OPERATORS) | {"all", "any", "not"}
effect_registry = frozenset(EFFECT_TYPES)


class ConditionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str | None = None
    op: str | None = None
    value: Any = None
    all: list["ConditionSpec"] | None = None
    any: list["ConditionSpec"] | None = None
    not_: ConditionSpec | None = Field(default=None, alias="not")

    @model_validator(mode="after")
    def valid_shape(self):
        composite = [self.all is not None, self.any is not None, self.not_ is not None]
        if self.field is not None:
            if any(composite) or self.op not in OPERATORS:
                raise ValueError("field conditions require a supported op")
            if self.field.split(".", 1)[0] not in FIELD_ROOTS:
                raise ValueError(f"unknown condition field: {self.field}")
        elif sum(composite) != 1:
            raise ValueError("condition must define field, all, any, or not")
        return self


class EffectSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    target: str
    multiplier: float | None = None
    flag: str | None = None

    @model_validator(mode="after")
    def valid_effect(self):
        if self.type not in EFFECT_TYPES:
            raise ValueError(f"unknown effect type: {self.type}")
        if self.target not in TARGETS:
            raise ValueError(f"unknown effect target: {self.target}")
        if self.type == "modify_population" and not 0 <= (self.multiplier or -1) <= 10:
            raise ValueError("population multiplier must be between 0 and 10")
        if self.type == "add_historical_flag" and not self.flag:
            raise ValueError("historical flag is required")
        return self


class ContentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    name: str | None = None
    description: str | None = None
    rarity: str | None = None
    duration_ticks: int | None = Field(default=None, ge=1)
    modifiers: dict[str, float] = {}
    trigger: ConditionSpec | None = None
    chance: float | None = Field(default=None, ge=0, le=1)
    effects: list[EffectSpec] = []


def _load_directory(root: Path, pattern: str) -> dict[str, ContentDefinition]:
    parsed: dict[str, ContentDefinition] = {}
    for path in sorted(root.glob(pattern)):
        try:
            definition = ContentDefinition.model_validate(yaml.safe_load(path.read_text()) or {})
        except (OSError, yaml.YAMLError, ValidationError, ValueError) as exc:
            raise ValueError(f"invalid content {path}: {exc}") from exc
        if definition.id in parsed:
            raise ValueError(f"duplicate content id {definition.id} in {path}")
        parsed[definition.id] = definition
    return parsed


def load_content(paths: list[Path] | None = None) -> dict[str, dict[str, ContentDefinition]]:
    root = (paths or [Path(__file__).resolve().parents[3] / "game_data", Path("/app/game_data")])[0]
    if not root.exists() and len(paths or []) == 0:
        root = Path("/app/game_data")
    return {
        "events": _load_directory(root / "events", "*.yaml"),
        "actions": _load_directory(root / "actions", "*.yaml"),
        "strategies": _load_directory(root / "strategies", "*.yaml"),
    }


CONTENT = load_content()
modifier_registry = CONTENT["actions"]


def evaluate_condition(condition: ConditionSpec, values: dict[str, Any]) -> bool:
    if condition.field is not None:
        actual = values.get(condition.field)
        expected = condition.value
        if condition.op == "eq": return actual == expected
        if condition.op == "neq": return actual != expected
        if actual is None: return False
        if condition.op == "gt": return actual > expected
        if condition.op == "gte": return actual >= expected
        if condition.op == "lt": return actual < expected
        if condition.op == "lte": return actual <= expected
        return actual in expected
    if condition.all is not None:
        return all(evaluate_condition(item, values) for item in condition.all)
    if condition.any is not None:
        return any(evaluate_condition(item, values) for item in condition.any)
    return not evaluate_condition(condition.not_, values)
