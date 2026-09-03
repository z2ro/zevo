import { request } from "./client";
import type { Evolution, GameEvent, Habitat, HistoryEntry, Legacy, ListResponse, Player, PlayerAction, SelectivePressure, Species, SpeciesInput, Strategy, ViabilityPreview, World } from "../types/api";

const post = <T>(path: string, body: unknown = {}) => request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const gameApi = {
  world: () => request<World>("/world"),
  worldSpecies: () => request<ListResponse<Species>>("/world/species"),
  worldHistory: (limit = 100) => request<ListResponse<HistoryEntry>>(`/world/history?limit=${limit}`),
  habitats: () => request<ListResponse<Habitat>>("/habitats"),
  species: () => request<ListResponse<Species>>("/species"),
  currentSpecies: () => request<Species>("/species/current"),
  speciesById: (id: number) => request<Species>(`/species/${id}`),
  evolutions: (id: number) => request<ListResponse<Evolution>>(`/species/${id}/evolutions`),
  pressures: (id: number) => request<ListResponse<SelectivePressure>>(`/species/${id}/pressures`),
  startEvolution: (id: number, evolutionId: string) => post(`/species/${id}/evolutions/${evolutionId}`),
  previewSpecies: (input: SpeciesInput) => post<ViabilityPreview>("/species/preview", input),
  createSpecies: (input: SpeciesInput) => post<Species>("/species", input),
  migrate: (id: number, destination_habitat_id: number) => post<PlayerAction>(`/species/${id}/migrate`, { destination_habitat_id }),
  split: (id: number) => post<Species>(`/species/${id}/split`, {}),
  changeStrategy: (id: number, strategy: Strategy) => post<Species>(`/species/${id}/strategy`, { strategy }),
  focusReproduction: (id: number) => post<PlayerAction>(`/species/${id}/focus-reproduction`),
  focusSurvival: (id: number) => post<PlayerAction>(`/species/${id}/focus-survival`),
  abandon: (id: number) => post<Species>(`/species/${id}/abandon`),
  events: (limit = 100) => request<ListResponse<GameEvent>>(`/events?limit=${limit}`),
  legacy: () => request<Legacy>("/legacy"),
  currentPlayer: () => request<Player>("/players/current"),
  simulate: (ticks: number) => post<World>("/dev/simulate", { ticks }),
};
