import type { Answer } from './api';

export function GroundedAnswer({ answer }: { answer: Answer }) {
  const sourceId = (citation: string) =>
    `answer-${answer.answer_id}-${citation}`;
  return (
    <article className="grounded-answer" aria-label="Grounded answer">
      <h4>
        {answer.status === 'answered'
          ? 'Answer with sources'
          : answer.status === 'refused'
            ? 'Request declined'
            : 'Not enough evidence'}
      </h4>
      <ol className="answer-claims">
        {answer.claims.map((claim, index) => (
          <li key={index}>
            <p>{claim.text}</p>
            <nav aria-label={`Sources for claim ${index + 1}`}>
              {claim.citation_ids.map((citation) => (
                <a
                  className="citation-link"
                  key={citation}
                  href={`#${sourceId(citation)}`}
                >
                  {citation}
                </a>
              ))}
            </nav>
          </li>
        ))}
      </ol>
      {answer.limitation && (
        <p className="answer-limitation">{answer.limitation}</p>
      )}
      <p className="field-help">
        Snapshot {answer.commit_sha} · {answer.retrieval_mode} retrieval
      </p>
      <p className="field-help">
        {answer.model ?? 'No model call'} · {answer.input_tokens} input /{' '}
        {answer.output_tokens} output tokens
        {' · '}estimated total $
        {(
          answer.estimated_generation_cost_usd +
          answer.estimated_retrieval_cost_usd
        ).toFixed(6)}
        {' · '}
        {(answer.duration_ms / 1000).toFixed(1)}s
      </p>
      <p className="field-help">
        {answer.context_tokens} estimated context tokens ·{' '}
        {answer.context_omitted} chunks omitted. Source references were checked;
        factual accuracy still needs review.
      </p>
      <p className="field-help">
        Conversation context: {answer.history_turn_ids.length} prior turns ·{' '}
        {answer.history_tokens} estimated history tokens. Earlier answers are
        not citation evidence.
      </p>
      {answer.evidence.map((source) => (
        <section
          key={source.citation_id}
          id={sourceId(source.citation_id)}
          className="answer-source"
          tabIndex={-1}
          aria-label={`Source ${source.citation_id}`}
        >
          <h5>
            {source.citation_id} · {source.path} · L{source.start_line}–
            {source.end_line}
          </h5>
          <pre tabIndex={0} aria-label={`Code for ${source.citation_id}`}>
            {source.content}
          </pre>
        </section>
      ))}
    </article>
  );
}
