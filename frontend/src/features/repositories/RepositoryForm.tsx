import { useState, type FormEvent } from 'react';
interface Props {
  onSubmit: (url: string) => Promise<void>;
  pending: boolean;
}
export function RepositoryForm({ onSubmit, pending }: Props) {
  const [url, setUrl] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit(url);
  }
  return (
    <form
      className="repository-form"
      onSubmit={(event) => {
        void submit(event);
      }}
    >
      <label htmlFor="repository-url">Public GitHub repository</label>
      <div className="import-controls">
        <input
          id="repository-url"
          type="url"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://github.com/owner/repository"
          maxLength={300}
          required
          disabled={pending}
        />
        <button disabled={pending || !url.trim()}>
          {pending ? 'Adding…' : 'Import repository'}
        </button>
      </div>
      <p className="field-help">
        Import reads source files only. It does not install dependencies or run
        repository code.
      </p>
    </form>
  );
}
