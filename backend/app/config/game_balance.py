from __future__ import annotations

from dataclasses import dataclass, field


TRAIT_NAMES = (
    "thermal_tolerance", "radiation_tolerance", "ph_tolerance",
    "metabolic_efficiency", "reproduction_rate", "mutation_rate",
    "energy_efficiency", "structural_resistance",
)


@dataclass(frozen=True)
class BalanceConfig:
    initial_population: int = 100
    trait_budget: int = 100
    trait_min: int = 0
    trait_max: int = 100
    trait_costs: dict[str, int] = field(default_factory=lambda: {name: 1 for name in TRAIT_NAMES})
    fitness_min: float = 0.0
    fitness_max: float = 2.5
    fitness_base: float = 0.45
    fitness_scale: float = 1.45
    fitness_environment_weight: float = 0.58
    fitness_metabolism_weight: float = 0.18
    fitness_reproduction_weight: float = 0.08
    fitness_structural_weight: float = 0.08
    fitness_competition_penalty: float = 0.55
    parasite_no_host_multiplier: float = 0.28
    parasite_host_bonus: float = 0.35
    resource_profiles: dict[str, tuple[float, float, float]] = field(default_factory=lambda: {
        "SOLAR": (1.0, 0.0, 0.0), "CHEMICAL": (0.0, 1.0, 0.0),
        "ORGANIC": (0.0, 0.0, 1.0), "PARASITIC": (0.0, 0.0, 0.0),
    })
    host_abundance_scale: float = 1_000.0
    host_compatibility_weights: tuple[float, float, float, float, float] = (0.30, 0.25, 0.20, 0.15, 0.10)
    host_compatibility_threshold: float = 0.25
    parasite_trait_scale: float = 200.0
    parasite_strength_weights: tuple[float, float] = (0.5, 0.5)
    energy_efficiency_base: float = 0.55
    strategy_bonuses: dict[str, float] = field(default_factory=lambda: {
        "COLONIZER": 0.10, "COMPETITOR": 0.08, "RESISTANT": 0.10,
        "OPPORTUNIST": 0.06, "PARASITE": 0.05,
    })
    growth_responsiveness_base: float = 0.08
    growth_reproduction_factor: float = 0.22
    overcapacity_pressure_max: float = 0.25
    overcapacity_pressure_factor: float = 0.15
    population_delta_limit: float = 0.35
    extinction_threshold: int = 2
    mutation_chance: float = 0.08
    dev_mutation_multiplier: float = 4.0
    mutation_magnitude: tuple[int, int] = (1, 3)
    bottleneck_population: int = 50
    bottleneck_mutation_magnitude: tuple[int, int] = (1, 6)
    selection_beneficial_threshold: float = 0.005
    selection_harmful_threshold: float = -0.005
    beneficial_fixation_chance: float = 0.82
    neutral_fixation_chance: float = 0.38
    harmful_fixation_chance: float = 0.10
    preview_positive_threshold: float = 1.05
    preview_negative_threshold: float = 0.95
    preview_low_risk_threshold: float = 1.25
    preview_moderate_risk_threshold: float = 0.8
    migration_mortality: float = 0.08
    split_mortality: float = 0.05
    founder_expedition_fraction: float = 0.25
    migration_duration_ticks: int = 1
    strategy_cooldown_ticks: int = 4
    focus_duration_ticks: int = 3
    focus_bonus: float = 0.20
    focus_penalty: float = 0.15
    stable_life_generations: int = 10_000
    major_adaptation_delta: float = 0.12
    gray_blood_base_probability: float = 0.015
    gray_blood_dev_multiplier: float = 100.0
    gray_blood_mutation_threshold: int = 20
    gray_blood_host_population_threshold: int = 500
    gray_blood_infection_threshold: float = 0.05
    gray_blood_transmission_threshold: float = 0.10
    gray_blood_host_population_loss: float = 0.18
    bot_action_interval_ticks: int = 4
    environment_delta_limit: float = 0.05


BALANCE = BalanceConfig()

WORLD_INITIAL = {
    "name": "Eos-1", "temperature": 68.0, "oxygen": 0.4, "co2": 72.0,
    "radiation": 82.0, "water_availability": 58.0, "average_ph": 5.4,
    "solar_energy": 46.0, "chemical_energy": 76.0, "geological_activity": 88.0,
}

HABITATS_INITIAL = (
    ("Shallow Ocean", 54, 48, 6.1, 92, 74, 34, 48, 15_000),
    ("Deep Ocean", 30, 18, 6.4, 98, 4, 58, 42, 12_000),
    ("Hydrothermal Vents", 86, 34, 4.8, 72, 0, 100, 68, 9_000),
    ("Volcanic Coast", 78, 72, 4.2, 45, 82, 72, 34, 7_000),
    ("Acidic Lake", 62, 56, 2.8, 84, 60, 46, 40, 8_000),
)

BOT_USERNAMES = ("DarwinBot", "WallaceBot", "MendelBot", "GaiaBot", "ChaosBot")
