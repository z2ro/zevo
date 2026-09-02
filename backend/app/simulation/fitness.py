from __future__ import annotations

from dataclasses import dataclass

from app.config.game_balance import BALANCE, BalanceConfig

from .common import clamp, enum_value


@dataclass(frozen=True)
class FitnessContext:
    competition: float = 0.0
    host_compatibility: float = 0.0


@dataclass(frozen=True)
class FitnessResult:
    value: float
    environment_compatibility: float
    energy_compatibility: float


def compatibility(trait: float, requirement: float) -> float:
    return clamp(1.0 - abs(requirement - trait) / 100.0, 0.0, 1.0)


def _energy(species: object, habitat: object, balance: BalanceConfig) -> float:
    source = enum_value(getattr(species, "energy_source"))
    availability = {
        "SOLAR": getattr(habitat, "solar_energy"),
        "CHEMICAL": getattr(habitat, "chemical_energy"),
        "ORGANIC": getattr(habitat, "organic_resources"),
        "PARASITIC": getattr(habitat, "organic_resources"),
    }.get(source, 0.0)
    efficiency = getattr(species, "energy_efficiency") / 100.0
    return clamp((availability / 100.0) * (balance.energy_efficiency_base + efficiency), 0.0, 1.0)


def calculate_fitness(
    species: object,
    habitat: object,
    context: FitnessContext = FitnessContext(),
    *,
    balance: BalanceConfig = BALANCE,
) -> FitnessResult:
    thermal = compatibility(getattr(species, "thermal_tolerance"), getattr(habitat, "temperature"))
    acidity = compatibility(getattr(species, "ph_tolerance"), getattr(habitat, "ph") * 10.0)
    radiation = compatibility(getattr(species, "radiation_tolerance"), getattr(habitat, "radiation"))
    water = clamp(getattr(habitat, "water") / 100.0, 0.0, 1.0)
    environment = (thermal + acidity + radiation + water) / 4.0
    energy = _energy(species, habitat, balance)
    metabolic = getattr(species, "metabolic_efficiency") / 100.0
    reproduction = getattr(species, "reproduction_rate") / 100.0
    structural = getattr(species, "structural_resistance") / 100.0
    strategy = balance.strategy_bonuses.get(enum_value(getattr(species, "strategy")), 0.0)

    # Center the normalized score around fitness=1 so good environments grow and
    # hostile combinations decline, while retaining a bounded public value.
    score = balance.fitness_base + balance.fitness_scale * (
        balance.fitness_environment_weight * ((environment + energy) / 2.0)
        + balance.fitness_metabolism_weight * metabolic
        + balance.fitness_reproduction_weight * reproduction
        + balance.fitness_structural_weight * structural
    ) + strategy
    score -= clamp(context.competition, 0.0, 1.0) * balance.fitness_competition_penalty

    if enum_value(getattr(species, "species_type")) == "PARASITIC":
        host = clamp(context.host_compatibility, 0.0, 1.0)
        score = score * balance.parasite_no_host_multiplier if host == 0 else score + host * balance.parasite_host_bonus

    return FitnessResult(
        value=round(clamp(score, balance.fitness_min, balance.fitness_max), 6),
        environment_compatibility=round(environment, 6),
        energy_compatibility=round(energy, 6),
    )


def preview_fitness(species: object, habitat: object, context: FitnessContext = FitnessContext(), *, balance: BalanceConfig = BALANCE) -> dict[str, object]:
    result = calculate_fitness(species, habitat, context, balance=balance)
    if result.value > balance.preview_positive_threshold:
        growth = "positive"
    elif result.value < balance.preview_negative_threshold:
        growth = "negative"
    else:
        growth = "stable"
    risk = "low" if result.value >= balance.preview_low_risk_threshold else "moderate" if result.value >= balance.preview_moderate_risk_threshold else "high"
    return {
        "estimated_fitness": round(result.value, 2),
        "estimated_growth": growth,
        "risk": risk,
        "environment_compatibility": round(result.environment_compatibility, 2),
    }
