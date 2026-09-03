from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.enums import RelationType, SpeciesStatus


@dataclass(frozen=True)
class EventCandidate:
    identity: str
    species: Any | None = None
    player: Any | None = None
    host: Any | None = None
    parasite: Any | None = None
    relation: Any | None = None
    mutation: Any | None = None
    values: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def event_candidates(scope: str, species, players, relations, mutations, world):
    living = {item.id: item for item in species if item.status != SpeciesStatus.EXTINCT and item.population > 0}
    if scope == "SPECIES":
        return [EventCandidate(f"species:{item.id}", species=item, player=players.get(item.creator_id),
            values={"species.generation": item.generation, "species.population": item.population,
                    "species.status": item.status.value, "species.species_type": item.species_type.value,
                    "species.mutation_rate": item.mutation_rate},
            metadata={"species_id": item.id, "player_id": item.creator_id,
                      "planet_age_years": world.age_years, "species_generation": item.generation}) for item in sorted(living.values(), key=lambda x: x.id)]
    if scope == "PARASITISM_RELATION":
        result = []
        for relation in sorted((r for r in relations if r.relation_type == RelationType.PARASITISM), key=lambda x: x.id):
            parasite, host = living.get(relation.predator_or_parasite_id), living.get(relation.target_species_id)
            if not parasite or not host or parasite.habitat_id != host.habitat_id: continue
            result.append(EventCandidate(f"relation:{relation.id}", species=parasite, parasite=parasite, host=host,
                player=players.get(parasite.creator_id), relation=relation,
                values={"parasite.species_type": parasite.species_type.value, "parasite.mutation_rate": parasite.mutation_rate,
                        "host.population": host.population, "relation.strength": relation.strength,
                        "relation.infection_rate": relation.infection_rate, "relation.transmission_rate": relation.transmission_rate},
                metadata={"parasite_species_id": parasite.id, "host_species_id": host.id,
                          "parasite_original_creator_id": parasite.creator_id, "host_creator_id": host.creator_id,
                          "habitat_id": host.habitat_id, "planet_age_years": world.age_years,
                          "species_generation": parasite.generation}))
        return result
    if scope == "MUTATION":
        result = []
        for species_id, mutation in sorted(mutations.items()):
            item = living.get(species_id)
            if item:
                result.append(EventCandidate(f"mutation:{species_id}", species=item, player=players.get(item.creator_id), mutation=mutation,
                    values={"mutation.fitness_delta": mutation.fitness_after - mutation.fitness_before},
                    metadata={"species_id": item.id, "player_id": item.creator_id,
                              "planet_age_years": world.age_years, "species_generation": item.generation}))
        return result
    raise ValueError(f"unsupported event scope: {scope}")
