import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./AppShell";
import { PlaceholderPage } from "./PlaceholderPage";

export function App() {
  return <BrowserRouter><Routes><Route element={<AppShell />}><Route index element={<PlaceholderPage title="Dashboard" description="Acompanhe o planeta, sua espécie e a atividade do ecossistema." />} /><Route path="species/create" element={<PlaceholderPage title="Criar espécie" description="Projete uma nova linhagem para sobreviver em Eos-1." />} /><Route path="species/:id" element={<PlaceholderPage title="Espécie" description="Observe a evolução e tome decisões estratégicas." />} /><Route path="world" element={<PlaceholderPage title="Mundo" description="Explore habitats e espécies vivas de Eos-1." />} /><Route path="world/history" element={<PlaceholderPage title="História do mundo" description="Uma linha do tempo da evolução do planeta." />} /><Route path="legacy" element={<PlaceholderPage title="Legado" description="Veja tudo que suas linhagens deixaram no mundo." />} /><Route path="events" element={<PlaceholderPage title="Eventos" description="Descubra marcos raros e mudanças históricas." />} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Routes></BrowserRouter>;
}
