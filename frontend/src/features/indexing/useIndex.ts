import { useEffect, useState } from 'react';
import { ApiError } from '../../lib/api/http';
import { getIndex, type IndexState } from './api';
export function useIndex(id: string, onExpired: () => void) {
  const [state, setState] = useState<IndexState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function poll() {
      let delay = 5000;
      try {
        const next = await getIndex(id, controller.signal);
        if (!active) return;
        setState(next);
        setError(null);
        delay =
          next.latest && ['queued', 'running'].includes(next.latest.status)
            ? 2000
            : 15000;
      } catch (reason) {
        if (!active) return;
        if (reason instanceof ApiError && reason.status === 401) {
          onExpired();
          return;
        }
        setError('Unable to load index status. Retrying…');
      }
      if (active)
        timer = setTimeout(() => {
          void poll();
        }, delay);
    }
    void poll();
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [id, onExpired, revision]);
  return { state, error, refresh: () => setRevision((value) => value + 1) };
}
