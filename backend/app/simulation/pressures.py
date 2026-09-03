from __future__ import annotations

from dataclasses import dataclass

from .fitness import compatibility, FitnessContext


@dataclass(frozen=True)
class SelectivePressure:
    type: str
    score: float
    severity: str
    description: str


def _severity(score: float) -> str:
    return "CRITICAL" if score >= .75 else "HIGH" if score >= .5 else "MEDIUM" if score >= .25 else "LOW"


def resolve_pressures(species: object, habitat: object, context: FitnessContext = FitnessContext()) -> list[SelectivePressure]:
    values = [
        ("TEMPERATURE", 1 - compatibility(species.thermal_tolerance, habitat.temperature), "A temperatura do habitat excede a tolerância atual."),
        ("RADIATION", 1 - compatibility(species.radiation_tolerance, habitat.radiation), "A radiação do habitat excede a tolerância atual."),
        ("PH", 1 - compatibility(species.ph_tolerance, habitat.ph * 10), "O pH do habitat está distante da tolerância atual."),
    ]
    source = getattr(getattr(species, "energy_source", None), "value", species.energy_source)
    available = {"SOLAR": habitat.solar_energy, "CHEMICAL": habitat.chemical_energy, "ORGANIC": habitat.organic_resources, "PARASITIC": habitat.organic_resources}.get(source, 0)
    values.append(("ENERGY_SCARCITY", max(0.0, 1 - available / 100), "A fonte de energia preferida está escassa no habitat."))
    values.append(("COMPETITION", max(0.0, min(1.0, context.competition)), "Outras espécies disputam recursos neste habitat."))
    return [SelectivePressure(kind, round(score, 4), _severity(score), description) for kind, score, description in values if score > 0]
