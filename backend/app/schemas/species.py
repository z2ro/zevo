from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config.game_balance import BALANCE, TRAIT_NAMES
from app.models.enums import EnergySource, SpeciesStatus, SpeciesType, Strategy


class SpeciesTraits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thermal_tolerance: int = Field(ge=BALANCE.trait_min, le=BALANCE.trait_max)
    radiation_tolerance: int = Field(ge=BALANCE.trait_min, le=BALANCE.trait_max)
    ph_tolerance: int = Field(ge=BALANCE.trait_min, le=BALANCE.trait_max)
    metabolic_efficiency: int = Field(ge=BALANCE.trait_min, le=BALANCE.trait_max)
    reproduction_rate: int = Field(ge=BALANCE.trait_min, le=BALANCE.trait_max)
    mutation_rate: int = Field(ge=BALANCE.trait_min, le=BALANCE.trait_max)
    energy_efficiency: int = Field(ge=BALANCE.trait_min, le=BALANCE.trait_max)
    structural_resistance: int = Field(ge=BALANCE.trait_min, le=BALANCE.trait_max)

    @property
    def cost(self) -> int:
        return sum(
            getattr(self, trait) * BALANCE.trait_costs[trait]
            for trait in TRAIT_NAMES
        )

    @model_validator(mode="after")
    def validate_budget(self) -> "SpeciesTraits":
        if self.cost > BALANCE.trait_budget:
            raise ValueError(
                f"trait budget exceeded: cost {self.cost}, maximum {BALANCE.trait_budget}"
            )
        return self


class SpeciesCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    species_type: SpeciesType
    energy_source: EnergySource
    strategy: Strategy
    habitat_id: int = Field(gt=0)
    traits: SpeciesTraits

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_ecology(self) -> "SpeciesCreate":
        parasitic = self.species_type is SpeciesType.PARASITIC
        parasite_configuration = (
            self.energy_source is EnergySource.PARASITIC
            and self.strategy is Strategy.PARASITE
        )
        if parasitic != parasite_configuration:
            raise ValueError(
                "PARASITIC type, energy source, and PARASITE strategy must be used together"
            )
        return self


SpeciesPreviewRequest = SpeciesCreate


class SpeciesPreview(BaseModel):
    estimated_fitness: float
    estimated_growth: str
    risk: str
    environment_compatibility: float


class SpeciesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    creator_id: int
    species_type: SpeciesType
    status: SpeciesStatus
    is_player_controlled: bool
    population: int
    generation: int
    fitness: float
    habitat_id: int
    strategy: Strategy
    energy_source: EnergySource
    thermal_tolerance: int
    radiation_tolerance: int
    ph_tolerance: int
    metabolic_efficiency: int
    reproduction_rate: int
    mutation_rate: int
    energy_efficiency: int
    structural_resistance: int
    created_at: datetime
    abandoned_at: datetime | None
    extinct_at: datetime | None
