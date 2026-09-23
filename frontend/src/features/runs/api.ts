import { z } from 'zod';
import { requestJSON, writeHeaders } from '../../lib/api/http';
import type { SearchMode } from '../search/api';
const run = z.object({
  id: z.string(),
  conversation_id: z.string(),
  request_key: z.string(),
  question: z.string(),
  mode: z.enum(['keyword', 'hybrid']),
  status: z.enum(['queued', 'running', 'completed', 'failed', 'cancelled']),
  model: z.string(),
  source_index_id: z.string(),
  usage_state: z.enum(['not_started', 'unknown', 'recorded']),
  input_tokens: z.number().nullable(),
  output_tokens: z.number().nullable(),
  estimated_cost_usd: z.number().nullable(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
  created_at: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
});
export type AnswerRun = z.infer<typeof run>;
export interface Submission {
  question: string;
  mode: SearchMode;
  request_key: string;
}
export async function listRuns(
  id: string,
  signal: AbortSignal,
): Promise<AnswerRun[]> {
  return z.object({ items: z.array(run) }).parse(
    await requestJSON(`/conversations/${id}/runs`, {
      signal: AbortSignal.any([signal, AbortSignal.timeout(12000)]),
    }),
  ).items;
}
export async function submitRun(
  id: string,
  data: Submission,
  csrf: string,
): Promise<AnswerRun> {
  return run.parse(
    await requestJSON(`/conversations/${id}/runs`, {
      method: 'POST',
      headers: writeHeaders(csrf),
      body: JSON.stringify(data),
    }),
  );
}
export async function cancelRun(id: string, csrf: string): Promise<AnswerRun> {
  return run.parse(
    await requestJSON(`/answer-runs/${id}/cancel`, {
      method: 'POST',
      headers: writeHeaders(csrf),
      body: '{}',
    }),
  );
}
