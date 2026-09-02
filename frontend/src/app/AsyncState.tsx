import type { ReactNode } from "react";

interface Props<T> { loading: boolean; error: Error | null; data: T | null; retry: () => void; empty?: (data: T) => boolean; emptyMessage?: string; children: (data: T) => ReactNode; }

export function AsyncState<T>({ loading, error, data, retry, empty, emptyMessage = "Nada para mostrar ainda.", children }: Props<T>) {
  if (loading && data === null) return <div className="state" role="status">Carregando…</div>;
  if (error && data === null) return <div className="state state-error" role="alert"><p>{error.message}</p><button onClick={retry}>Tentar novamente</button></div>;
  if (data === null) return <div className="state">{emptyMessage}</div>;
  if (empty?.(data)) return <div className="state">{emptyMessage}</div>;
  return <>{error && <p className="stale-warning">Dados podem estar desatualizados.</p>}{children(data)}</>;
}
