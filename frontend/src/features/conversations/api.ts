import { z } from 'zod';
import { requestJSON, writeHeaders } from '../../lib/api/http';
import { answerSchema } from '../answers/api';
const conversation = z.object({
  id: z.string(),
  repository_id: z.string(),
  title: z.string(),
  message_count: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Conversation = z.infer<typeof conversation>;
const page = z.object({
  items: z.array(
    z.object({
      id: z.string(),
      turn_id: z.string(),
      position: z.number(),
      role: z.enum(['user', 'assistant', 'tool']),
      content: z.string(),
      token_count: z.number().nullable(),
      answer: answerSchema.nullable(),
      created_at: z.string(),
    }),
  ),
  next_before: z.number().nullable(),
});
export type MessagePage = z.infer<typeof page>;
export async function listConversations(
  repositoryId: string,
  signal: AbortSignal,
): Promise<Conversation[]> {
  return z.object({ items: z.array(conversation) }).parse(
    await requestJSON(`/repositories/${repositoryId}/conversations`, {
      signal: AbortSignal.any([signal, AbortSignal.timeout(12000)]),
    }),
  ).items;
}
export async function createConversation(
  repositoryId: string,
  title: string,
  csrf: string,
): Promise<Conversation> {
  return conversation.parse(
    await requestJSON(`/repositories/${repositoryId}/conversations`, {
      method: 'POST',
      headers: writeHeaders(csrf),
      body: JSON.stringify({ title }),
    }),
  );
}
export async function deleteConversation(
  id: string,
  csrf: string,
): Promise<void> {
  await requestJSON(`/conversations/${id}`, {
    method: 'DELETE',
    headers: writeHeaders(csrf),
  });
}
export async function getMessages(
  id: string,
  before: number | null,
  signal: AbortSignal,
): Promise<MessagePage> {
  return page.parse(
    await requestJSON(
      `/conversations/${id}/messages${before === null ? '' : `?before=${before}`}`,
      {
        signal: AbortSignal.any([signal, AbortSignal.timeout(12000)]),
      },
    ),
  );
}
