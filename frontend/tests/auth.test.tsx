import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AuthWorkspace } from '../src/features/auth/AuthWorkspace';

const session = {
  user: {
    id: 'user-1',
    name: 'Saleh',
    email: 'saleh@example.com',
    created_at: '2026-01-01T00:00:00Z',
  },
  csrf_token: 'csrf-proof',
  expires_at: new Date(Date.now() + 3600000).toISOString(),
};
function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
function guest() {
  return json({ error: { message: 'Please sign in.' } }, 401);
}
function health() {
  return json({ status: 'ok', service: 'repopilot-api' });
}
function enterCredentials() {
  fireEvent.change(screen.getByLabelText('Email'), {
    target: { value: 'saleh@example.com' },
  });
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'correct horse battery staple' },
  });
}

describe('authentication workspace', () => {
  it('restores an existing session and revokes it on sign out', async () => {
    const fetcher = vi
      .fn()
      .mockImplementation((path: string, options?: RequestInit) => {
        if (path.endsWith('/repositories')) return Promise.resolve(json([]));
        if (path.endsWith('/me')) return Promise.resolve(json(session));
        if (path.endsWith('/logout')) {
          expect(options?.headers).toMatchObject({
            'X-CSRF-Token': 'csrf-proof',
            'X-RepoPilot-Request': '1',
          });
          return Promise.resolve(new Response(null, { status: 204 }));
        }
        return Promise.resolve(health());
      });
    vi.stubGlobal('fetch', fetcher);
    render(<AuthWorkspace />);
    expect(screen.getByRole('status')).toHaveTextContent(
      'Checking your session',
    );
    expect(await screen.findByText('Welcome, Saleh.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(
      await screen.findByRole('button', { name: 'Sign in' }),
    ).toBeInTheDocument();
    expect(screen.queryByText('saleh@example.com')).not.toBeInTheDocument();
  });
  it('registers and displays the protected workspace', async () => {
    const fetcher = vi
      .fn()
      .mockImplementation((path: string, options?: RequestInit) => {
        if (path.endsWith('/repositories')) return Promise.resolve(json([]));
        if (path.endsWith('/me')) return Promise.resolve(guest());
        if (path.endsWith('/register')) {
          expect(options?.headers).toMatchObject({
            'Content-Type': 'application/json',
            'X-RepoPilot-Request': '1',
          });
          expect(JSON.parse(String(options?.body))).toEqual({
            name: 'Saleh',
            email: 'saleh@example.com',
            password: 'correct horse battery staple',
          });
          return Promise.resolve(json(session, 201));
        }
        return Promise.resolve(health());
      });
    vi.stubGlobal('fetch', fetcher);
    render(<AuthWorkspace />);
    fireEvent.click(
      await screen.findByRole('button', {
        name: 'New here? Create an account',
      }),
    );
    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Saleh' },
    });
    enterCredentials();
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByText('Welcome, Saleh.')).toBeInTheDocument();
  });
  it('keeps a failed login in the form and shows a useful error', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockImplementation((path: string) =>
          Promise.resolve(
            path.endsWith('/repositories')
              ? json([])
              : path.endsWith('/me')
                ? guest()
                : json(
                    { error: { message: 'Email or password is incorrect.' } },
                    401,
                  ),
          ),
        ),
    );
    render(<AuthWorkspace />);
    await screen.findByRole('button', { name: 'Sign in' });
    enterCredentials();
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Email or password is incorrect.',
    );
    expect(screen.queryByText('Welcome, Saleh.')).not.toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled(),
    );
  });
  it('distinguishes server failure from an anonymous session and supports retry', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          json({ error: { message: 'Database unavailable.' } }, 503),
        )
        .mockResolvedValueOnce(guest()),
    );
    render(<AuthWorkspace />);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Database unavailable.',
    );
    expect(
      screen.queryByRole('button', { name: 'Sign in' }),
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', { name: 'Retry session check' }),
    );
    expect(
      await screen.findByRole('button', { name: 'Sign in' }),
    ).toBeInTheDocument();
  });
  it('does not pretend sign-out succeeded when the server rejects it', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockImplementation((path: string) =>
          Promise.resolve(
            path.endsWith('/repositories')
              ? json([])
              : path.endsWith('/me')
                ? json(session)
                : path.endsWith('/logout')
                  ? json({ error: { message: 'Sign-out failed.' } }, 503)
                  : health(),
          ),
        ),
    );
    render(<AuthWorkspace />);
    fireEvent.click(await screen.findByRole('button', { name: 'Sign out' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Sign-out failed.',
    );
    expect(screen.getByText('Welcome, Saleh.')).toBeInTheDocument();
  });
});
