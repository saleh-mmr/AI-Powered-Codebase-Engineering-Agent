import { useEffect, useState } from 'react';
import { getReadiness } from '../../lib/api/client';

type ReadinessState =
  | { status: 'loading' }
  | { status: 'ready'; checkedAt: Date }
  | { status: 'error'; message: string };

export function useReadiness() {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<ReadinessState>({ status: 'loading' });
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timeout = setTimeout(() => {
      if (active)
        setState({
          status: 'error',
          message:
            'The health check timed out. Check the backend and try again.',
        });
      active = false;
      controller.abort();
    }, 8000);
    void getReadiness(controller.signal)
      .then(
        () => {
          if (active) setState({ status: 'ready', checkedAt: new Date() });
        },
        (error: unknown) => {
          if (active)
            setState({
              status: 'error',
              message:
                error instanceof Error
                  ? error.message
                  : 'Unable to reach the backend.',
            });
        },
      )
      .finally(() => clearTimeout(timeout));
    return () => {
      active = false;
      clearTimeout(timeout);
      controller.abort();
    };
  }, [attempt]);
  function refresh() {
    setState({ status: 'loading' });
    setAttempt((value) => value + 1);
  }
  return { state, refresh };
}
