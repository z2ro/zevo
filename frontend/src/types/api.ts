export type SpeciesType = "AUTOTROPH" | "CHEMOSYNTHETIC" | "HETEROTROPH" | "PARASITIC";
export type EnergySource = "SOLAR" | "CHEMICAL" | "ORGANIC" | "PARASITIC";
export type Strategy = "COLONIZER" | "COMPETITOR" | "RESISTANT" | "OPPORTUNIST" | "PARASITE";
export type SpeciesStatus = "ACTIVE" | "WILD" | "EXTINCT";
export type GrowthTrend = "positive" | "stable" | "negative";

export interface Traits {
  thermal_tolerance: number;
  radiation_tolerance: number;
  ph_tolerance: number;
  metabolic_efficiency: number;
  reproduction_rate: number;
  mutation_rate: number;
  energy_efficiency: number;
  structural_resistance: number;
}

export interface Species {
  id: number; name: string; creator_id: number; species_type: SpeciesType;
  status: SpeciesStatus; is_player_controlled: boolean; population: number;
  generation: number; fitness: number; habitat_id: number; strategy: Strategy;
  energy_source: EnergySource; created_at: string; abandoned_at: string | null;
  extinct_at: string | null; traits: Traits;
  resources?: { biomass: number; energy: number; genetic_material: number; adaptation_points: number };
  resource_rates?: { biomass: number; energy: number; genetic_material: number };
}

export interface Evolution { id: string; name: string; category: string; level: number; cost: Record<string, number>; duration_ticks: number; requirements: unknown[]; status: string | null; ticks_remaining?: number | null; available?: boolean; pressure?: Record<string, string>; selection_bias?: Record<string, string | number>; tradeoffs?: Record<string, number>; }
export interface SelectivePressure { type: string; score: number; severity: string; description: string; }

export interface World {
  id: number; name: string; generation: number; tick: number; temperature: number;
  oxygen: number; co2: number; radiation: number; water_availability: number;
  average_ph: number; solar_energy: number; chemical_energy: number;
  geological_activity: number; species_alive: number; species_extinct: number;
  dev_mode: boolean;
}

export interface Habitat {
  id: number; name: string; temperature: number; radiation: number; ph: number;
  water: number; solar_energy: number; chemical_energy: number;
  organic_resources: number; carrying_capacity: number;
}

export interface Player { id: number; username: string; current_species_id: number | null; }
export interface GameEvent { id: number; code: string; name: string; description: string; rarity: string; triggered_at: string; generation: number; historical: boolean; global_unique: boolean; metadata: Record<string, unknown>; }
export interface HistoryEntry { kind: string; generation: number; title: string; description: string; species_id?: number; player_id?: number; metadata: Record<string, unknown>; }
export interface PlayerAction { id: number; action_type: string; status: string; species_id: number; payload: Record<string, unknown>; }
export interface ListResponse<T> { items: T[]; }
export interface SpeciesInput { name: string; species_type: SpeciesType; energy_source: EnergySource; strategy: Strategy; habitat_id: number; traits: Traits; }
export interface ViabilityPreview { estimated_fitness: number; estimated_growth: GrowthTrend; risk: string; environment_compatibility: number; }
export interface Legacy { total_species: number; active: number; wild: number; extinct: number; total_population: number; species: Species[]; world_firsts: GameEvent[]; }

export interface ApiErrorBody { error: { code: string; message: string; details: Record<string, unknown>; }; }
