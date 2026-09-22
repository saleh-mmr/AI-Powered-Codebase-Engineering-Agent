import type { AuthSession, Credentials, Registration } from './types';

import { ApiError as AuthError, requestJSON } from '../../lib/api/http';
export { ApiError as AuthError } from '../../lib/api/http';

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
export async function getSession(
  signal?: AbortSignal,
): Promise<AuthSession | null> {
  try {
    return parseSession(await requestJSON('/auth/me', { signal }));
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
    await requestJSON(`/auth/${mode}`, {
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
  await requestJSON('/auth/logout', {
    method: 'POST',
    body: '{}',
    headers: {
      'Content-Type': 'application/json',
      'X-RepoPilot-Request': '1',
      'X-CSRF-Token': csrf,
    },
  });
}
