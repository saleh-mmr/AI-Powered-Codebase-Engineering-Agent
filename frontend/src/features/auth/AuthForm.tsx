import { useState, type FormEvent } from 'react';
import { authenticate } from './api';
import type { AuthSession } from './types';

interface Props {
  onAuthenticated: (session: AuthSession) => void;
}
export function AuthForm({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    const credentials = {
      email: String(values.get('email') ?? ''),
      password: String(values.get('password') ?? ''),
    };
    setPending(true);
    setError(null);
    try {
      const data =
        mode === 'register'
          ? { ...credentials, name: String(values.get('name') ?? '') }
          : credentials;
      const session = await authenticate(mode, data);
      form.reset();
      onAuthenticated(session);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'Unable to sign in. Please try again.',
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <section className="status-card auth-card" aria-labelledby="auth-title">
      <span className="eyebrow">YOUR WORKSPACE</span>
      <h2 id="auth-title">
        {mode === 'login'
          ? 'Welcome back.'
          : 'Make room for better understanding.'}
      </h2>
      <p>
        {mode === 'login'
          ? 'Sign in to your RepoPilot account.'
          : 'Create an account to start your workspace.'}
      </p>
      <form
        onSubmit={(event) => {
          void submit(event);
        }}
      >
        <fieldset disabled={pending}>
          {mode === 'register' && (
            <label htmlFor="name">
              Name
              <input
                id="name"
                name="name"
                autoComplete="name"
                maxLength={100}
                required
              />
            </label>
          )}
          <label htmlFor="email">
            Email
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="username"
              maxLength={254}
              required
            />
          </label>
          <label htmlFor="password">
            Password
            <input
              id="password"
              name="password"
              type="password"
              autoComplete={
                mode === 'login' ? 'current-password' : 'new-password'
              }
              minLength={mode === 'register' ? 15 : 1}
              maxLength={128}
              aria-describedby={
                mode === 'register' ? 'password-help' : undefined
              }
              required
            />
          </label>
          {mode === 'register' && (
            <p id="password-help" className="field-help">
              Use a passphrase of 15–128 characters. Spaces are welcome.
            </p>
          )}
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
          <button type="submit">
            {pending
              ? 'Please wait…'
              : mode === 'login'
                ? 'Sign in'
                : 'Create account'}
          </button>
          <button
            type="button"
            className="text-button"
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login');
              setError(null);
            }}
          >
            {mode === 'login'
              ? 'New here? Create an account'
              : 'Already have an account? Sign in'}
          </button>
        </fieldset>
      </form>
    </section>
  );
}
