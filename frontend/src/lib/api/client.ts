export interface HealthResponse {
  status: 'ok';
  service: 'repopilot-api';
}

export async function getReadiness(
  signal: AbortSignal,
): Promise<HealthResponse> {
  const response = await fetch('/api/health/ready', {
    signal,
    headers: { Accept: 'application/json' },
    cache: 'no-store',
  });
  if (!response.ok) {
    throw new Error(
      response.status === 503
        ? 'The API is running, but the database is not ready. Check database availability and migrations.'
        : 'The API could not complete the health check. Check the backend logs.',
    );
  }
  const data: unknown = await response.json();
  if (
    typeof data !== 'object' ||
    data === null ||
    !('status' in data) ||
    data.status !== 'ok' ||
    !('service' in data) ||
    data.service !== 'repopilot-api'
  )
    throw new Error('The API returned an unexpected health response.');
  return { status: 'ok', service: 'repopilot-api' };
}
