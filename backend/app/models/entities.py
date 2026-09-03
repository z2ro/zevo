from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from .enums import ActionStatus, ActionType, EnergySource, EventRarity, EvolutionStatus, RelationType, SpeciesStatus, SpeciesType, Strategy, TraitChangeCause


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


enum = lambda cls, name: Enum(cls, name=name, native_enum=False, validate_strings=True)


class World(Base):
    __tablename__ = "worlds"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    generation: Mapped[int] = mapped_column(Integer, default=0)
    tick: Mapped[int] = mapped_column(Integer, default=0)
    temperature: Mapped[float] = mapped_column(Float)
    oxygen: Mapped[float] = mapped_column(Float)
    co2: Mapped[float] = mapped_column(Float)
    radiation: Mapped[float] = mapped_column(Float)
    water_availability: Mapped[float] = mapped_column(Float)
    average_ph: Mapped[float] = mapped_column(Float)
    solar_energy: Mapped[float] = mapped_column(Float)
    chemical_energy: Mapped[float] = mapped_column(Float)
    geological_activity: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Habitat(Base):
    __tablename__ = "habitats"
    id: Mapped[int] = mapped_column(primary_key=True)
    world_id: Mapped[int] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    temperature: Mapped[float] = mapped_column(Float); radiation: Mapped[float] = mapped_column(Float); ph: Mapped[float] = mapped_column(Float)
    water: Mapped[float] = mapped_column(Float); solar_energy: Mapped[float] = mapped_column(Float); chemical_energy: Mapped[float] = mapped_column(Float)
    organic_resources: Mapped[float] = mapped_column(Float); carrying_capacity: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("world_id", "name"), CheckConstraint("carrying_capacity > 0"),)


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    bot_kind: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Species(Base):
    __tablename__ = "species"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    creator_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    habitat_id: Mapped[int] = mapped_column(ForeignKey("habitats.id"), index=True)
    species_type: Mapped[SpeciesType] = mapped_column(enum(SpeciesType, "species_type"))
    status: Mapped[SpeciesStatus] = mapped_column(enum(SpeciesStatus, "species_status"), default=SpeciesStatus.ACTIVE)
    is_player_controlled: Mapped[bool] = mapped_column(Boolean, default=True)
    population: Mapped[int] = mapped_column(Integer, default=100)
    generation: Mapped[int] = mapped_column(Integer, default=0)
    fitness: Mapped[float] = mapped_column(Float, default=1.0)
    strategy: Mapped[Strategy] = mapped_column(enum(Strategy, "strategy"))
    energy_source: Mapped[EnergySource] = mapped_column(enum(EnergySource, "energy_source"))
    thermal_tolerance: Mapped[int] = mapped_column(Integer); radiation_tolerance: Mapped[int] = mapped_column(Integer); ph_tolerance: Mapped[int] = mapped_column(Integer)
    metabolic_efficiency: Mapped[int] = mapped_column(Integer); reproduction_rate: Mapped[int] = mapped_column(Integer); mutation_rate: Mapped[int] = mapped_column(Integer)
    energy_efficiency: Mapped[int] = mapped_column(Integer); structural_resistance: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); extinct_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    biomass: Mapped[int] = mapped_column(Integer, default=1000); energy: Mapped[int] = mapped_column(Integer, default=500)
    genetic_material: Mapped[int] = mapped_column(Integer, default=50); adaptation_points: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        CheckConstraint("population >= 0", name="ck_species_population_nonnegative"),
        CheckConstraint("thermal_tolerance BETWEEN 0 AND 100 AND radiation_tolerance BETWEEN 0 AND 100 AND ph_tolerance BETWEEN 0 AND 100 AND metabolic_efficiency BETWEEN 0 AND 100 AND reproduction_rate BETWEEN 0 AND 100 AND mutation_rate BETWEEN 0 AND 100 AND energy_efficiency BETWEEN 0 AND 100 AND structural_resistance BETWEEN 0 AND 100", name="ck_species_traits_range"),
        CheckConstraint("thermal_tolerance + radiation_tolerance + ph_tolerance + metabolic_efficiency + reproduction_rate + mutation_rate + energy_efficiency + structural_resistance <= 100", name="ck_species_trait_budget"),
        CheckConstraint("species_type != 'PARASITIC' OR (energy_source = 'PARASITIC' AND strategy = 'PARASITE')", name="ck_species_parasite_configuration"),
        CheckConstraint("is_player_controlled IS FALSE OR status = 'ACTIVE'", name="ck_species_controlled_is_active"),
        CheckConstraint("status != 'EXTINCT' OR (is_player_controlled IS FALSE AND population = 0)", name="ck_species_extinct_state"),
        Index("uq_species_one_controlled_per_player", "creator_id", unique=True, postgresql_where=text("is_player_controlled IS TRUE"), sqlite_where=text("is_player_controlled = 1")),
    )


class WorldSnapshot(Base):
    __tablename__ = "world_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True); world_id: Mapped[int] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    generation: Mapped[int] = mapped_column(Integer); tick: Mapped[int] = mapped_column(Integer)
    temperature: Mapped[float] = mapped_column(Float); oxygen: Mapped[float] = mapped_column(Float); co2: Mapped[float] = mapped_column(Float); radiation: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("world_id", "tick"),)


class SpeciesEvolution(Base):
    __tablename__ = "species_evolutions"
    id: Mapped[int] = mapped_column(primary_key=True)
    species_id: Mapped[int] = mapped_column(ForeignKey("species.id", ondelete="CASCADE"), index=True)
    evolution_id: Mapped[str] = mapped_column(String(80)); level: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[EvolutionStatus] = mapped_column(enum(EvolutionStatus, "evolution_status"))
    started_at_tick: Mapped[int] = mapped_column(Integer); complete_at_tick: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SpeciesPopulationSnapshot(Base):
    __tablename__ = "species_population_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True); species_id: Mapped[int] = mapped_column(ForeignKey("species.id", ondelete="CASCADE"), index=True)
    generation: Mapped[int] = mapped_column(Integer); population: Mapped[int] = mapped_column(Integer); fitness: Mapped[float] = mapped_column(Float)
    traits: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SpeciesTraitHistory(Base):
    __tablename__ = "species_trait_history"
    id: Mapped[int] = mapped_column(primary_key=True); species_id: Mapped[int] = mapped_column(ForeignKey("species.id", ondelete="CASCADE"), index=True)
    generation: Mapped[int] = mapped_column(Integer); trait: Mapped[str] = mapped_column(String(40)); old_value: Mapped[int] = mapped_column(Integer); new_value: Mapped[int] = mapped_column(Integer)
    cause: Mapped[TraitChangeCause] = mapped_column(enum(TraitChangeCause, "trait_change_cause")); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SpeciesRelation(Base):
    __tablename__ = "species_relations"
    id: Mapped[int] = mapped_column(primary_key=True); predator_or_parasite_id: Mapped[int] = mapped_column(ForeignKey("species.id", ondelete="CASCADE"), index=True)
    target_species_id: Mapped[int] = mapped_column(ForeignKey("species.id", ondelete="CASCADE"), index=True); relation_type: Mapped[RelationType] = mapped_column(enum(RelationType, "relation_type"))
    strength: Mapped[float] = mapped_column(Float); infection_rate: Mapped[float | None] = mapped_column(Float); virulence: Mapped[float | None] = mapped_column(Float); transmission_rate: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("predator_or_parasite_id", "target_species_id", "relation_type"), CheckConstraint("predator_or_parasite_id != target_species_id"),)


class GameEvent(Base):
    __tablename__ = "game_events"
    id: Mapped[int] = mapped_column(primary_key=True); world_id: Mapped[int] = mapped_column(ForeignKey("worlds.id"), index=True)
    code: Mapped[str] = mapped_column(String(80)); name: Mapped[str] = mapped_column(String(120)); description: Mapped[str] = mapped_column(Text)
    rarity: Mapped[EventRarity] = mapped_column(enum(EventRarity, "event_rarity")); triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    generation: Mapped[int] = mapped_column(Integer); historical: Mapped[bool] = mapped_column(Boolean, default=True); global_unique: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    repeat_scope: Mapped[str] = mapped_column(String(16), default="ALWAYS", server_default="ALWAYS")
    species_id: Mapped[int | None] = mapped_column(ForeignKey("species.id")); player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id")); event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    __table_args__ = (
        CheckConstraint("repeat_scope IN ('ALWAYS', 'WORLD', 'SPECIES', 'PLAYER')", name="ck_game_event_repeat_scope"),
        CheckConstraint("repeat_scope != 'SPECIES' OR species_id IS NOT NULL", name="ck_game_event_species_scope_subject"),
        CheckConstraint("repeat_scope != 'PLAYER' OR player_id IS NOT NULL", name="ck_game_event_player_scope_subject"),
        Index("uq_game_event_world_global_code", "world_id", "code", unique=True, postgresql_where=text("global_unique IS TRUE"), sqlite_where=text("global_unique = 1")),
        Index("uq_game_event_idempotency", "world_id", "code", "idempotency_key", unique=True, postgresql_where=text("idempotency_key IS NOT NULL"), sqlite_where=text("idempotency_key IS NOT NULL")),
        Index("uq_game_event_once_world", "world_id", "code", unique=True, postgresql_where=text("repeat_scope = 'WORLD'"), sqlite_where=text("repeat_scope = 'WORLD'")),
        Index("uq_game_event_once_species", "world_id", "code", "species_id", unique=True, postgresql_where=text("repeat_scope = 'SPECIES'"), sqlite_where=text("repeat_scope = 'SPECIES'")),
        Index("uq_game_event_once_player", "world_id", "code", "player_id", unique=True, postgresql_where=text("repeat_scope = 'PLAYER'"), sqlite_where=text("repeat_scope = 'PLAYER'")),
    )


class PlayerAction(Base):
    __tablename__ = "player_actions"
    id: Mapped[int] = mapped_column(primary_key=True); player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True); species_id: Mapped[int] = mapped_column(ForeignKey("species.id"), index=True)
    action_type: Mapped[ActionType] = mapped_column(enum(ActionType, "action_type")); status: Mapped[ActionStatus] = mapped_column(enum(ActionStatus, "action_status"), default=ActionStatus.PENDING)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict); execute_at_tick: Mapped[int | None] = mapped_column(Integer); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow); completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HistoricalFlag(Base):
    __tablename__ = "historical_flags"
    id: Mapped[int] = mapped_column(primary_key=True); world_id: Mapped[int] = mapped_column(ForeignKey("worlds.id"), index=True)
    species_id: Mapped[int | None] = mapped_column(ForeignKey("species.id"), index=True); player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), index=True)
    code: Mapped[str] = mapped_column(String(100)); generation: Mapped[int] = mapped_column(Integer); flag_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        CheckConstraint("species_id IS NULL OR player_id IS NULL", name="ck_historical_flag_single_subject"),
        Index("uq_historical_flag_global", "world_id", "code", unique=True, postgresql_where=text("species_id IS NULL AND player_id IS NULL"), sqlite_where=text("species_id IS NULL AND player_id IS NULL")),
        Index("uq_historical_flag_species", "world_id", "species_id", "code", unique=True, postgresql_where=text("species_id IS NOT NULL AND player_id IS NULL"), sqlite_where=text("species_id IS NOT NULL AND player_id IS NULL")),
        Index("uq_historical_flag_player", "world_id", "player_id", "code", unique=True, postgresql_where=text("species_id IS NULL AND player_id IS NOT NULL"), sqlite_where=text("species_id IS NULL AND player_id IS NOT NULL")),
    )
