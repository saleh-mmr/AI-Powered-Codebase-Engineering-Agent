import type { SearchResult } from './api';
export function SearchResults({ result }: { result: SearchResult }) {
  return (
    <div aria-label="Search results">
      <p role="status">
        {result.results.length} results · {result.duration_ms} ms ·{' '}
        {result.context_tokens} context tokens
      </p>
      <p className="field-help">
        Commit {result.commit_sha}. Ranking scores are not confidence
        probabilities.
      </p>
      {result.query_tokens > 0 && (
        <p className="field-help">
          Query: {result.query_tokens} embedding tokens · estimated $
          {result.estimated_query_cost_usd.toFixed(6)}
        </p>
      )}
      {result.context_omitted > 0 && (
        <p>
          {result.context_omitted} results omitted from the context budget;
          source results remain inspectable below.
        </p>
      )}
      {result.results.length === 0 && (
        <p>
          No matching code found. Try a symbol name or a more specific question.
        </p>
      )}
      {result.results.map((hit) => {
        const citation = result.context.find(
          (entry) => entry.chunk_id === hit.chunk_id,
        )?.citation_id;
        return (
          <details className="chunk-detail" key={hit.chunk_id}>
            <summary>
              {hit.path} · L{hit.start_line}–{hit.end_line}
              {citation ? ` · ${citation}` : ''}
            </summary>
            {hit.symbol && (
              <p>
                <code>{hit.symbol}</code>
              </p>
            )}
            <p className="field-help">
              {Object.entries(hit.channel_ranks)
                .map(([channel, rank]) => `${channel} #${rank}`)
                .join(' · ')}{' '}
              · fused score {hit.score.toFixed(4)}
            </p>
            <pre tabIndex={0} aria-label={`${hit.path} search source`}>
              {hit.content}
            </pre>
          </details>
        );
      })}
    </div>
  );
}
