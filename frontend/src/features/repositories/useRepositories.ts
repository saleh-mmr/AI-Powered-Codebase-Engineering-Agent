import { useEffect, useState } from 'react';
import { ApiError } from '../../lib/api/http';
import { listRepositories, type Repository } from './api';
export function useRepositories(onExpired: () => void) {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let active = true;
    async function refresh() {
      let interval = 15000;
      try {
        const rows = await listRepositories(
          AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]),
        );
        if (!active) return;
        setRepositories(rows);
        setError(null);
        if (rows.some((row) => ['queued', 'running'].includes(row.job.status)))
          interval = 2000;
      } catch (reason) {
        if (!active) return;
        if (reason instanceof ApiError && reason.status === 401) {
          onExpired();
          return;
        }
        setError(
          reason instanceof ApiError
            ? reason.message
            : 'Unable to load repositories. Retry shortly.',
        );
        interval = 5000;
      } finally {
        if (active) {
          setLoading(false);
          timer = setTimeout(() => {
            void refresh();
          }, interval);
        }
      }
    }
    void refresh();
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [version, onExpired]);
  return {
    repositories,
    loading,
    error,
    refresh: () => setVersion((value) => value + 1),
  };
}
