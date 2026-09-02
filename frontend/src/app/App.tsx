import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./AppShell";
import { CreateSpecies, Dashboard, EventsPage, HistoryPage, LegacyPage, SpeciesDetail, WorldPage } from "./Pages";

export function App() {
  return <BrowserRouter><Routes><Route element={<AppShell />}><Route index element={<Dashboard/>}/><Route path="species/create" element={<CreateSpecies/>}/><Route path="species/:id" element={<SpeciesDetail/>}/><Route path="world" element={<WorldPage/>}/><Route path="world/history" element={<HistoryPage/>}/><Route path="legacy" element={<LegacyPage/>}/><Route path="events" element={<EventsPage/>}/><Route path="*" element={<Navigate to="/" replace/>}/></Route></Routes></BrowserRouter>;
}
