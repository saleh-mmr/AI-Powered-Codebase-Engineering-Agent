import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RepositoryWorkspace } from '../src/features/repositories/RepositoryWorkspace';
import type { Repository } from '../src/features/repositories/api';
const repo: Repository = {
  id: 'repo-1',
  owner: 'owner',
  name: 'project',
  url: 'https://github.com/owner/project',
  github_repository_id: null,
  default_branch: null,
  last_commit_sha: null,
  imported_at: null,
  job: {
    id: 'job-1',
    status: 'queued',
    stage: 'queued',
    attempts: 0,
    files_scanned: 0,
    files_stored: 0,
    files_skipped: 0,
    error_code: null,
    error_message: null,
  },
};
function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
describe('repository workspace', () => {
  it('creates an import with the session CSRF proof and shows its queued state', async () => {
    let added = false;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((_path: string, options?: RequestInit) => {
        if (options?.method === 'POST') {
          expect(options.headers).toMatchObject({ 'X-CSRF-Token': 'proof' });
          expect(JSON.parse(String(options.body))).toEqual({ url: repo.url });
          added = true;
          return Promise.resolve(json(repo, 202));
        }
        return Promise.resolve(json(added ? [repo] : []));
      }),
    );
    render(<RepositoryWorkspace csrf="proof" onExpired={() => {}} />);
    await screen.findByText('No repositories connected yet.');
    fireEvent.change(screen.getByLabelText('Public GitHub repository'), {
      target: { value: repo.url },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Import repository' }));
    expect(await screen.findByText('owner/project')).toBeInTheDocument();
    expect(screen.getByText('queued')).toBeInTheDocument();
  });
  it('shows failed imports and retries them', async () => {
    const failed = {
      ...repo,
      job: {
        ...repo.job,
        status: 'failed',
        stage: 'failed',
        error_message: 'Repository exceeds the size limit.',
      },
    };
    let retried = false;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((path: string) => {
        if (path.endsWith('/retry')) {
          retried = true;
          return Promise.resolve(json(repo, 202));
        }
        return Promise.resolve(json([retried ? repo : failed]));
      }),
    );
    render(<RepositoryWorkspace csrf="proof" onExpired={() => {}} />);
    expect(
      await screen.findByText('Repository exceeds the size limit.'),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Retry import' }));
    expect(await screen.findByText('queued')).toBeInTheDocument();
  });
  it('renders source as text and lets the same file be reselected', async () => {
    const completed = {
      ...repo,
      last_commit_sha: 'a'.repeat(40),
      job: {
        ...repo.job,
        status: 'completed',
        stage: 'completed',
        files_stored: 1,
      },
    };
    const file = { id: 'file-1', path: 'app.py', language: 'python', size: 20 };
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((path: string) =>
        Promise.resolve(
          path.includes('/files?')
            ? json({ items: [file], next_offset: null })
            : path.endsWith('/files/file-1')
              ? json({
                  ...file,
                  content: '<script>alert("x")</script>',
                  commit_sha: 'a'.repeat(40),
                })
              : json([completed]),
        ),
      ),
    );
    const { container } = render(
      <RepositoryWorkspace csrf="proof" onExpired={() => {}} />,
    );
    fireEvent.click(
      await screen.findByRole('button', { name: 'Browse files' }),
    );
    fireEvent.click(await screen.findByRole('button', { name: 'app.py' }));
    expect(
      await screen.findByText('<script>alert("x")</script>'),
    ).toBeInTheDocument();
    expect(container.querySelector('script')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'app.py' }));
    expect(
      await screen.findByText('<script>alert("x")</script>'),
    ).toBeInTheDocument();
  });
  it('invalidates an expired session', async () => {
    const expired = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(json({ error: { message: 'Sign in.' } }, 401)),
    );
    render(<RepositoryWorkspace csrf="proof" onExpired={expired} />);
    await vi.waitFor(() => expect(expired).toHaveBeenCalled());
  });
});
