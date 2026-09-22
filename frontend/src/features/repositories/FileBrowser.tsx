import { useEffect, useState } from 'react';
import { RepositorySearch } from '../search/RepositorySearch';
import { IndexInspector } from '../indexing/IndexInspector';
import { ApiError } from '../../lib/api/http';
import {
  listFiles,
  readFile,
  type FileContent,
  type Repository,
  type SourceFile,
} from './api';
interface Props {
  repository: Repository;
  csrf: string;
  onClose: () => void;
  onExpired: () => void;
}
export function FileBrowser({ repository, csrf, onClose, onExpired }: Props) {
  const [files, setFiles] = useState<SourceFile[]>([]);
  const [offset, setOffset] = useState(0);
  const [next, setNext] = useState<number | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [readAttempt, setReadAttempt] = useState(0);
  const [content, setContent] = useState<FileContent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reading, setReading] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    void listFiles(
      repository.id,
      offset,
      AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]),
    )
      .then((page) => {
        if (active) {
          setFiles((previous) =>
            offset === 0 ? page.items : [...previous, ...page.items],
          );
          setNext(page.next_offset);
        }
      })
      .catch((reason: unknown) => {
        if (!active) return;
        if (reason instanceof ApiError && reason.status === 401) onExpired();
        else
          setError(
            'Unable to load files. Close and reopen the browser to retry.',
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [repository.id, offset, onExpired]);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    let active = true;
    void readFile(
      repository.id,
      selected,
      AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]),
    )
      .then((file) => {
        if (active) setContent(file);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        if (reason instanceof ApiError && reason.status === 401) onExpired();
        else setError('Unable to read this file. Select it again to retry.');
      })
      .finally(() => {
        if (active) setReading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [repository.id, selected, readAttempt, onExpired]);
  return (
    <section className="source-browser" aria-label="Repository files">
      <div className="card-heading">
        <h3>
          {repository.owner}/{repository.name}
        </h3>
        <button className="text-button" onClick={onClose}>
          Close files
        </button>
      </div>
      <p className="field-help">
        Snapshot {repository.last_commit_sha} · imported source, not a live
        branch view.
      </p>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      <div className="source-grid">
        <nav aria-label="Source files">
          {loading && <p role="status">Loading files…</p>}
          {files.map((file) => (
            <button
              className={`file-link ${selected === file.id ? 'selected' : ''}`}
              key={file.id}
              onClick={() => {
                setSelected(file.id);
                setReadAttempt((value) => value + 1);
                setReading(true);
                setContent(null);
                setError(null);
              }}
            >
              {file.path}
            </button>
          ))}
          {next !== null && (
            <button
              disabled={loading}
              onClick={() => {
                setLoading(true);
                setOffset(next);
              }}
            >
              Load more files
            </button>
          )}
        </nav>
        <div className="source-content">
          {reading ? (
            <p role="status">Reading file…</p>
          ) : content ? (
            <>
              <h4>{content.path}</h4>
              <pre tabIndex={0} aria-label={content.path}>
                {content.content}
              </pre>
            </>
          ) : (
            <p>Select a file to inspect its source.</p>
          )}
        </div>
      </div>
      <IndexInspector
        repositoryId={repository.id}
        fileId={selected}
        csrf={csrf}
        onExpired={onExpired}
      />
      <RepositorySearch
        repositoryId={repository.id}
        csrf={csrf}
        onExpired={onExpired}
      />
    </section>
  );
}
