import { NavLink, Outlet } from "react-router-dom";
import { gameApi } from "../api/gameApi";
import { usePolling } from "./usePolling";

const links = [["/", "Dashboard"], ["/world", "Mundo"], ["/world/history", "História"], ["/legacy", "Legado"], ["/events", "Eventos"]] as const;

export function AppShell() {
  const player = usePolling(gameApi.currentPlayer);
  const speciesPath = player.data?.current_species_id ? `/species/${player.data.current_species_id}` : "/species/create";
  return <div className="app-shell"><header><NavLink className="brand" to="/">ZEVO <span>Eos-1</span></NavLink><nav><NavLink to={speciesPath}>Minha espécie</NavLink>{links.map(([to, label]) => <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>)}</nav></header><main><Outlet /></main><footer>Simulação persistente • atualização a cada 5 segundos</footer></div>;
}
