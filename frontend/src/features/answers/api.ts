import { z } from 'zod';
import { requestJSON, writeHeaders } from '../../lib/api/http';
import type { SearchMode } from '../search/api';

const settings = z.object({
  enabled: z.boolean(),
  embeddings_enabled: z.boolean(),
  model: z.string(),
  max_output_tokens: z.number(),
  input_price_per_million: z.number(),
  output_price_per_million: z.number(),
});
export type AnswerSettings = z.infer<typeof settings>;
const evidence = z.object({
  citation_id: z.string(),
  chunk_id: z.string(),
  path: z.string(),
  commit_sha: z.string(),
  start_line: z.number(),
  end_line: z.number(),
  content: z.string(),
});
export const answerSchema = z.object({
  answer_id: z.string(),
  status: z.enum(['answered', 'insufficient_evidence', 'refused']),
  claims: z.array(
    z.object({ text: z.string(), citation_ids: z.array(z.string()) }),
  ),
  limitation: z.string(),
  evidence: z.array(evidence),
  commit_sha: z.string(),
  retrieval_mode: z.enum(['keyword', 'hybrid']),
  prompt_version: z.string(),
  model: z.string().nullable(),
  input_tokens: z.number(),
  output_tokens: z.number(),
  estimated_generation_cost_usd: z.number(),
  estimated_retrieval_cost_usd: z.number(),
  context_tokens: z.number(),
  context_omitted: z.number(),
  duration_ms: z.number(),
});
export type Answer = z.infer<typeof answerSchema>;
export async function getAnswerSettings(
  id: string,
  signal: AbortSignal,
): Promise<AnswerSettings> {
  return settings.parse(
    await requestJSON(`/repositories/${id}/answers`, {
      signal: AbortSignal.any([signal, AbortSignal.timeout(12000)]),
    }),
  );
}
export async function askRepository(
  id: string,
  question: string,
  mode: SearchMode,
  csrf: string,
  signal: AbortSignal,
  conversationId?: string,
): Promise<Answer> {
  return answerSchema.parse(
    await requestJSON(
      conversationId
        ? `/conversations/${conversationId}/messages`
        : `/repositories/${id}/answers`,
      {
        method: 'POST',
        headers: writeHeaders(csrf),
        body: JSON.stringify({ question, mode }),
        signal: AbortSignal.any([signal, AbortSignal.timeout(65000)]),
      },
    ),
  );
}
