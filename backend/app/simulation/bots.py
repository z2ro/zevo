from __future__ import annotations

from random import Random
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.game_balance import BALANCE
from app.models.entities import Habitat, Player, Species, World
from app.models.enums import EnergySource, SpeciesStatus, SpeciesType, Strategy


_ECOLOGY = {
    "DARWIN": (SpeciesType.AUTOTROPH, EnergySource.SOLAR, Strategy.COMPETITOR),
    "WALLACE": (SpeciesType.HETEROTROPH, EnergySource.ORGANIC, Strategy.COLONIZER),
    "MENDEL": (SpeciesType.CHEMOSYNTHETIC, EnergySource.CHEMICAL, Strategy.OPPORTUNIST),
    "GAIA": (SpeciesType.AUTOTROPH, EnergySource.SOLAR, Strategy.RESISTANT),
    "CHAOS": (SpeciesType.PARASITIC, EnergySource.PARASITIC, Strategy.PARASITE),
}


def run_bots(session: Session, world: World, rng: Random) -> int:
    if world.tick % BALANCE.bot_action_interval_ticks:
        return 0
    habitats = list(session.scalars(select(Habitat).where(Habitat.world_id == world.id).order_by(Habitat.id)))
    if not habitats:
        return 0
    actions = 0
    for index, player in enumerate(session.scalars(select(Player).where(Player.is_bot.is_(True)).order_by(Player.id))):
        current = session.scalar(select(Species).where(
            Species.creator_id == player.id, Species.is_player_controlled.is_(True)))
        if current is None:
            kind = player.bot_kind or "DARWIN"
            species_type, source, strategy = _ECOLOGY.get(kind, _ECOLOGY["DARWIN"])
            traits = {name: 10 for name in BALANCE.trait_costs}
            if kind in ("MENDEL", "CHAOS"):
                traits["mutation_rate"], traits["structural_resistance"] = 20, 0
            session.add(Species(name=f"{player.username} lineage {world.tick}", creator_id=player.id,
                habitat_id=habitats[index % len(habitats)].id, species_type=species_type,
                status=SpeciesStatus.ACTIVE, is_player_controlled=True,
                population=BALANCE.initial_population, generation=0, fitness=1.0,
                strategy=strategy, energy_source=source, **traits))
            actions += 1
        elif player.bot_kind in ("WALLACE", "CHAOS") and rng.random() < 0.35:
            choices = [h for h in habitats if h.id != current.habitat_id]
            if choices:
                current.habitat_id = rng.choice(choices).id
                current.population = max(1, int(current.population * (1 - BALANCE.migration_mortality)))
                actions += 1
    session.flush()
    return actions
