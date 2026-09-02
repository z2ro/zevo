import { NavLink, Outlet } from "react-router-dom";

const links = [["/", "Dashboard"], ["/world", "Mundo"], ["/world/history", "História"], ["/legacy", "Legado"], ["/events", "Eventos"]] as const;

export function AppShell() {
  return <div className="app-shell"><header><NavLink className="brand" to="/">ZEVO <span>Eos-1</span></NavLink><nav>{links.map(([to, label]) => <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>)}</nav></header><main><Outlet /></main><footer>Simulação persistente • atualização a cada 5 segundos</footer></div>;
}
