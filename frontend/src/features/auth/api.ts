import type { AuthSession, Credentials, Registration } from './types';

export class AuthError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'AuthError';
  }
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}
function parseSession(value: unknown): AuthSession {
  if (
    !record(value) ||
    !record(value.user) ||
    typeof value.user.id !== 'string' ||
    typeof value.user.email !== 'string' ||
    typeof value.user.name !== 'string' ||
    typeof value.user.created_at !== 'string' ||
    typeof value.csrf_token !== 'string' ||
    typeof value.expires_at !== 'string' ||
    !Number.isFinite(Date.parse(value.expires_at))
  ) {
    throw new Error('The server returned an invalid session response.');
  }
  return {
    user: {
      id: value.user.id,
      email: value.user.email,
      name: value.user.name,
      created_at: value.user.created_at,
    },
    csrf_token: value.csrf_token,
    expires_at: value.expires_at,
  };
}
async function request(
  path: string,
  options: RequestInit = {},
): Promise<unknown> {
  const response = await fetch(`/api/auth/${path}`, {
    ...options,
    credentials: 'same-origin',
    cache: 'no-store',
    signal: options.signal ?? AbortSignal.timeout(12000),
    headers: { Accept: 'application/json', ...options.headers },
  });
  if (!response.ok) {
    let message = 'Unable to complete the request. Please try again.';
    const data: unknown = await response.json().catch(() => null);
    if (
      record(data) &&
      record(data.error) &&
      typeof data.error.message === 'string'
    ) {
      message = data.error.message;
    }
    throw new AuthError(response.status, message);
  }
  return response.status === 204 ? null : response.json();
}
export async function getSession(
  signal?: AbortSignal,
): Promise<AuthSession | null> {
  try {
    return parseSession(await request('me', { signal }));
  } catch (error) {
    if (error instanceof AuthError && error.status === 401) return null;
    throw error;
  }
}
export async function authenticate(
  mode: 'login' | 'register',
  data: Credentials | Registration,
): Promise<AuthSession> {
  return parseSession(
    await request(mode, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-RepoPilot-Request': '1',
      },
      body: JSON.stringify(data),
    }),
  );
}
export async function logout(csrf: string): Promise<void> {
  await request('logout', {
    method: 'POST',
    body: '{}',
    headers: {
      'Content-Type': 'application/json',
      'X-RepoPilot-Request': '1',
      'X-CSRF-Token': csrf,
    },
  });
}
