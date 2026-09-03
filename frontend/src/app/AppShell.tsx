import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { gameApi } from "../api/gameApi";
import { ApiError } from "../api/client";
import type { Species, World } from "../types/api";
import { usePolling } from "./usePolling";

export interface ShellContext { species: Species | null; world: World | null; refreshSpecies: () => Promise<void>; refreshWorld: () => Promise<void>; }
const number = (value: number, digits = 0) => value.toLocaleString("pt-BR", { maximumFractionDigits: digits });

export function AppShell() {
  const location = useLocation();
  const current = usePolling(async () => { try { return await gameApi.currentSpecies(); } catch (error) { if (error instanceof ApiError && error.status === 404) return null; throw error; } });
  const world = usePolling(gameApi.world);
  const species = current.data;
  const speciesPath = species ? `/species/${species.id}` : "/species/create";
  const links = [["/", "Visão geral", ""], [speciesPath, "Minha linhagem", ""], ...(species ? [[speciesPath, "Pressões", "#pressures"], [speciesPath, "Genoma", "#genome"]] : []), ["/world", "Ecossistema", ""], ["/events", "Eventos", ""], ["/world/history", "História", ""], ["/legacy", "Legado", ""]] as const;
  useEffect(() => { if (location.hash) requestAnimationFrame(() => document.getElementById(location.hash.slice(1))?.scrollIntoView()); }, [location.hash, location.pathname]);
  return <div className="game-shell">
    <header className="top-status-bar"><NavLink className="brand" to="/">ZEVO <span>{world.data?.name ?? "Eos-1"}</span></NavLink><div className="resource-strip">{species?.resources ? <><Hud label="Biomassa" value={number(species.resources.biomass)} rate={species.resource_rates?.biomass}/><Hud label="Energia" value={number(species.resources.energy)} rate={species.resource_rates?.energy}/><Hud label="Genética" value={number(species.resources.genetic_material)} rate={species.resource_rates?.genetic_material}/><Hud label="Adaptação" value={number(species.resources.adaptation_points)}/><Hud label="População" value={number(species.population)}/><Hud label="Fitness" value={number(species.fitness, 2)}/><Hud label="Geração" value={number(species.generation)}/></> : <><Hud label="Tick" value={number(world.data?.tick ?? 0)}/><Hud label="Geração global" value={number(world.data?.generation ?? 0)}/><Hud label="Espécies vivas" value={number(world.data?.species_alive ?? 0)}/></>}</div></header>
    <aside className="sidebar"><div className="nav-label">Centro evolutivo</div><nav>{links.map(([path, label, hash]) => { const active = location.pathname === path && location.hash === hash; return <Link className={active ? "active" : ""} key={`${path}-${label}`} to={`${path}${hash}`}><span>●</span>{label}</Link>; })}</nav></aside>
    <main className="main-panel"><Outlet context={{ species, world: world.data, refreshSpecies: current.retry, refreshWorld: world.retry } satisfies ShellContext}/></main>
    <aside className="context-rail"><div className="context-block"><small>AMBIENTE</small><strong>{world.data?.name ?? "Eos-1"}</strong><span>Tick {number(world.data?.tick ?? 0)}</span><span>Geração {number(world.data?.generation ?? 0)}</span></div>{species ? <div className="context-block"><small>LINHAGEM ATUAL</small><strong>{species.name}</strong><span>{species.status}</span><span>Fitness {number(species.fitness, 2)}</span></div> : <NavLink className="button" to="/species/create">Criar minha espécie</NavLink>}</aside>
    <footer>Eos-1 · simulação persistente · tick 5s</footer>
  </div>;
}

function Hud({ label, value, rate }: { label: string; value: string; rate?: number }) { return <div className="hud-item"><small>{label}</small><strong>{value}</strong>{rate !== undefined && <span>+{number(rate)}/tick</span>}</div>; }
