from __future__ import annotations

from pathlib import Path
from typing import Any
import operator
from app.config.game_balance import TRAIT_NAMES
from app.models.enums import EventRarity, Strategy

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


OPERATORS = {"eq", "neq", "gt", "gte", "lt", "lte", "in"}
EFFECT_TYPES = {"modify_population", "add_historical_flag", "modify_trait"}
TARGETS = {"parasite", "host", "species", "world"}
CONDITION_FIELDS = {
    "species.generation", "species.population", "species.status", "species.species_type",
    "species.mutation_rate", "parasite.species_type", "parasite.mutation_rate",
    "host.population", "relation.infection_rate", "relation.transmission_rate", "relation.strength",
    "mutation.fitness_delta",
}
EVENT_SCOPES = {"SPECIES", "PARASITISM_RELATION", "MUTATION"}
PRESSURE_TYPES = {"TEMPERATURE", "RADIATION", "PH", "ENERGY_SCARCITY", "COMPETITION", "POPULATION_DECLINE"}
condition_registry = frozenset(OPERATORS) | {"all", "any", "not"}
def safe_in(actual, expected): return actual in expected
CONDITION_OPERATORS = {"eq": operator.eq, "neq": operator.ne, "gt": operator.gt,
                       "gte": operator.ge, "lt": operator.lt, "lte": operator.le, "in": safe_in}
from .effects import EFFECT_HANDLERS
effect_registry = EFFECT_HANDLERS


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
            if self.field not in CONDITION_FIELDS:
                raise ValueError(f"unknown condition field: {self.field}")
            if self.op == "in" and not isinstance(self.value, (list, tuple, set)):
                raise ValueError("in condition value must be a list")
        elif sum(composite) != 1:
            raise ValueError("condition must define field, all, any, or not")
        return self


class EffectSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    target: str
    multiplier: float | None = None
    flag: str | None = None
    trait: str | None = None
    amount: int | None = None

    @model_validator(mode="after")
    def valid_effect(self):
        if self.type not in EFFECT_TYPES:
            raise ValueError(f"unknown effect type: {self.type}")
        if self.target not in TARGETS:
            raise ValueError(f"unknown effect target: {self.target}")
        if self.type == "modify_population":
            if self.multiplier is None or self.flag is not None or not 0 <= self.multiplier <= 10:
                raise ValueError("modify_population requires only multiplier between 0 and 10")
        if self.type == "add_historical_flag":
            if not self.flag or self.multiplier is not None:
                raise ValueError("add_historical_flag requires only flag")
        if self.type == "modify_trait" and (self.target != "species" or self.trait not in TRAIT_NAMES or self.amount is None or self.multiplier is not None or self.flag is not None):
            raise ValueError("modify_trait requires species, a known trait, and amount")
        return self


class ContentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    name: str | None = None
    description: str | None = None
    rarity: str | None = None
    scope: str | None = None
    global_unique: bool = False
    repeat_policy: str = "ALWAYS"
    duration_years: int | None = Field(default=None, ge=1)
    modifiers: dict[str, float] = Field(default_factory=dict)
    trigger: ConditionSpec | None = None
    chance: float | None = Field(default=None, ge=0, le=1)
    dev_chance_multiplier: float = Field(default=1.0, ge=1)
    effects: list[EffectSpec] = Field(default_factory=list)
    category: str | None = None
    level: int | None = Field(default=None, ge=1)
    cost: dict[str, int] = Field(default_factory=dict)
    requirements: list[dict[str, int | str]] = Field(default_factory=list)
    pressure: dict[str, str] = Field(default_factory=dict)
    selection_bias: dict[str, float | str] = Field(default_factory=dict)
    tradeoffs: dict[str, float] = Field(default_factory=dict)


def _load_directory(root: Path, pattern: str) -> dict[str, ContentDefinition]:
    parsed: dict[str, ContentDefinition] = {}
    for path in sorted(root.glob(pattern)):
        try:
            definition = ContentDefinition.model_validate(yaml.safe_load(path.read_text()) or {})
        except (OSError, yaml.YAMLError, ValidationError, ValueError) as exc:
            raise ValueError(f"invalid content {path}: {exc}") from exc
        if definition.id in parsed:
            raise ValueError(f"duplicate content id {definition.id} in {path}")
        if root.name == "events" and (not definition.name or not definition.description or not definition.rarity or definition.trigger is None):
            raise ValueError(f"event content {path} requires name, description, rarity and trigger")
        if root.name == "events" and definition.scope not in EVENT_SCOPES:
            raise ValueError(f"event content {path} requires a valid scope")
        if root.name != "events" and definition.scope is not None:
            raise ValueError(f"only events may define scope: {path}")
        if root.name == "events" and definition.rarity == EventRarity.WORLD_FIRST.value and definition.chance is not None:
            raise ValueError(f"world first {path} must not define chance")
        if root.name == "events" and definition.rarity != EventRarity.WORLD_FIRST.value and definition.chance is None:
            raise ValueError(f"probabilistic event {path} requires chance")
        if definition.repeat_policy not in {"ALWAYS", "ONCE_PER_WORLD", "ONCE_PER_SPECIES", "ONCE_PER_PLAYER"}:
            raise ValueError(f"unknown repeat_policy {definition.repeat_policy} in {path}")
        if root.name == "actions" and (definition.duration_years is None or not definition.modifiers):
            raise ValueError(f"action content {path} requires duration_years and modifiers")
        if root.name == "strategies" and (not definition.name or "fitness_bonus" not in definition.modifiers):
            raise ValueError(f"strategy content {path} requires name and fitness_bonus")
        if root.name == "evolutions" and (not definition.name or definition.duration_years is None or not definition.cost):
            raise ValueError(f"evolution content {path} requires name, cost and duration_years")
        if root.name == "evolutions":
            trait, strength = definition.selection_bias.get("trait"), definition.selection_bias.get("strength")
            if (definition.pressure.get("type") not in PRESSURE_TYPES
                    or definition.pressure.get("minimum_severity") not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
                    or trait not in TRAIT_NAMES or not isinstance(strength, (int, float)) or not 0 <= strength <= 1):
                raise ValueError(f"adaptive response {path} requires pressure and valid selection_bias")
            if definition.effects:
                raise ValueError(f"adaptive response {path} must not grant direct effects")
            if any(key not in {"reproduction_modifier", "mortality_modifier"} or value <= 0 for key, value in definition.tradeoffs.items()):
                raise ValueError(f"invalid adaptive response tradeoff in {path}")
        if any(value < 0 for value in definition.cost.values()):
            raise ValueError(f"negative evolution cost in {path}")
        if definition.rarity and definition.rarity not in {item.value for item in EventRarity}:
            raise ValueError(f"unknown event rarity {definition.rarity} in {path}")
        parsed[definition.id] = definition
    return parsed


def load_content(root: Path | None = None) -> dict[str, dict[str, ContentDefinition]]:
    root = root or Path(__file__).resolve().parents[3] / "game_data"
    if not root.exists():
        root = Path("/app/game_data")
    result = {
        "events": _load_directory(root / "events", "*.yaml"),
        "actions": _load_directory(root / "actions", "*.yaml"),
        "strategies": _load_directory(root / "strategies", "*.yaml"),
        "evolutions": _load_directory(root / "evolutions", "*.yaml"),
    }
    expected = {item.value for item in Strategy}
    if set(result["strategies"]) != expected:
        raise ValueError(f"strategy content must exactly cover {sorted(expected)}")
    return result


CONTENT = load_content()
modifier_registry = CONTENT["actions"]


def evaluate_condition(condition: ConditionSpec, values: dict[str, Any]) -> bool:
    if condition.field is not None:
        actual = values.get(condition.field)
        if actual is None: return False
        return CONDITION_OPERATORS[condition.op](actual, condition.value)
    if condition.all is not None:
        return all(evaluate_condition(item, values) for item in condition.all)
    if condition.any is not None:
        return any(evaluate_condition(item, values) for item in condition.any)
    return not evaluate_condition(condition.not_, values)
