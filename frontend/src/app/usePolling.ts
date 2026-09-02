import { useCallback, useEffect, useState } from "react";

export function usePolling<T>(loader: () => Promise<T>, intervalMs = 5000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    try { setError(null); setData(await loader()); }
    catch (value) { setError(value instanceof Error ? value : new Error("Falha desconhecida")); }
    finally { setLoading(false); }
  }, [loader]);
  useEffect(() => {
    void load();
    const timer = window.setInterval(() => { if (!document.hidden) void load(); }, intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs, load]);
  return { data, error, loading, retry: load };
}
