from __future__ import annotations

from dataclasses import dataclass
from operator import eq, ge, gt, le, lt, ne
from typing import Any, Callable, Protocol, Sequence


class EvaluationContext(Protocol):
    rng: Any
    dev_mode: bool

    def resolve(self, path: str) -> Any: ...


class Condition(Protocol):
    """A side-effect free predicate over an event evaluation context."""

    def evaluate(self, context: EvaluationContext) -> bool: ...


@dataclass(frozen=True)
class Predicate:
    name: str
    function: Callable[[EvaluationContext], bool]

    def evaluate(self, context: EvaluationContext) -> bool:
        return bool(self.function(context))


_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": eq,
    "ne": ne,
    "gt": gt,
    "ge": ge,
    "lt": lt,
    "le": le,
    "in": lambda value, expected: value in expected,
    "contains": lambda value, expected: expected in value,
}


@dataclass(frozen=True)
class FieldCondition:
    """Compare a dotted context path without embedding domain rules in the engine."""

    path: str
    operator: str
    expected: Any

    def evaluate(self, context: EvaluationContext) -> bool:
        try:
            operation = _OPERATORS[self.operator]
        except KeyError as exc:
            raise ValueError(f"Unsupported condition operator: {self.operator}") from exc
        try:
            return bool(operation(context.resolve(self.path), self.expected))
        except (KeyError, AttributeError, TypeError):
            return False


@dataclass(frozen=True)
class All:
    conditions: Sequence[Condition]

    def evaluate(self, context: EvaluationContext) -> bool:
        return all(condition.evaluate(context) for condition in self.conditions)


@dataclass(frozen=True)
class Any:
    conditions: Sequence[Condition]

    def evaluate(self, context: EvaluationContext) -> bool:
        return any(condition.evaluate(context) for condition in self.conditions)


@dataclass(frozen=True)
class Not:
    condition: Condition

    def evaluate(self, context: EvaluationContext) -> bool:
        return not self.condition.evaluate(context)


@dataclass(frozen=True)
class RandomRoll:
    probability: float
    dev_multiplier: float = 1.0

    def evaluate(self, context: EvaluationContext) -> bool:
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError("RandomRoll probability must be between 0 and 1")
        chance = self.probability * (self.dev_multiplier if context.dev_mode else 1.0)
        return context.rng.random() < min(1.0, chance)
