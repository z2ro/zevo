import { request } from "./client";
import type { GameEvent, Habitat, HistoryEntry, Legacy, ListResponse, Player, PlayerAction, Species, SpeciesInput, Strategy, ViabilityPreview, World } from "../types/api";

const post = <T>(path: string, body: unknown = {}) => request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const gameApi = {
  world: () => request<World>("/world"),
  worldSpecies: () => request<ListResponse<Species>>("/world/species"),
  worldHistory: (limit = 100) => request<ListResponse<HistoryEntry>>(`/world/history?limit=${limit}`),
  habitats: () => request<ListResponse<Habitat>>("/habitats"),
  species: () => request<ListResponse<Species>>("/species"),
  currentSpecies: () => request<Species>("/species/current"),
  speciesById: (id: number) => request<Species>(`/species/${id}`),
  previewSpecies: (input: SpeciesInput) => post<ViabilityPreview>("/species/preview", input),
  createSpecies: (input: SpeciesInput) => post<Species>("/species", input),
  migrate: (id: number, destination_habitat_id: number) => post<PlayerAction>(`/species/${id}/migrate`, { destination_habitat_id }),
  split: (id: number, population_fraction: number) => post<Species>(`/species/${id}/split`, { population_fraction }),
  changeStrategy: (id: number, strategy: Strategy) => post<Species>(`/species/${id}/strategy`, { strategy }),
  focusReproduction: (id: number) => post<PlayerAction>(`/species/${id}/focus-reproduction`),
  focusSurvival: (id: number) => post<PlayerAction>(`/species/${id}/focus-survival`),
  abandon: (id: number) => post<Species>(`/species/${id}/abandon`),
  events: (limit = 100) => request<ListResponse<GameEvent>>(`/events?limit=${limit}`),
  legacy: () => request<Legacy>("/legacy"),
  currentPlayer: () => request<Player>("/players/current"),
  simulate: (ticks: number) => post<World>("/dev/simulate", { ticks }),
};
