export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}
export async function requestJSON(
  path: string,
  options: RequestInit = {},
): Promise<unknown> {
  const response = await fetch(`/api${path}`, {
    ...options,
    credentials: 'same-origin',
    cache: 'no-store',
    signal: options.signal ?? AbortSignal.timeout(12000),
    headers: { Accept: 'application/json', ...options.headers },
  });
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null);
    const message =
      record(data) &&
      record(data.error) &&
      typeof data.error.message === 'string'
        ? data.error.message
        : 'Unable to complete the request. Please try again.';
    throw new ApiError(response.status, message);
  }
  return response.status === 204 ? null : response.json();
}
export function writeHeaders(csrf: string): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-RepoPilot-Request': '1',
    'X-CSRF-Token': csrf,
  };
}
