// Typed client for the FastAPI backend. Mirrors the backend response shapes.
// Base URL comes from NEXT_PUBLIC_API_BASE (see .env.local.example).

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

// --- Backend shapes ---------------------------------------------------------

export interface ResolvedDocument {
  id: string;
  label: string;
  group: string;
  source_rule_ids: string[];
  refine_flag: boolean;
}

export interface RuleTrace {
  rule_id: string;
  condition_label: string;
  triggering_question: string;
  status: "applies" | "excluded" | "pending";
  reason: string;
  nested: boolean;
}

export interface RefineFlag {
  rule_id: string;
  label: string;
  note: string;
}

export interface TrackerState {
  required: ResolvedDocument[];
  excluded: RuleTrace[];
  pending: RuleTrace[];
  refine_flags: RefineFlag[];
}

export interface EscalationRecord {
  turn_index: number;
  category:
    | "tax_advice"
    | "outcome_speculation"
    | "out_of_scope"
    | "unmapped_answer";
  client_utterance: string;
  reason: string;
}

export interface ChatMessage {
  role: "assistant" | "user";
  text: string;
  checkpoint: boolean;
  escalated: boolean;
}

// Profile is intentionally loose here — the review surface renders it generically.
export type Profile = Record<string, unknown>;

export interface SessionSnapshot {
  session_id: string;
  firm: string;
  profile: Profile;
  messages: ChatMessage[];
  tracker_state: TrackerState;
  escalation_log: EscalationRecord[];
  approved: boolean;
  complete: boolean;
}

export interface CreateSessionResponse {
  session_id: string;
  opening_turn: string;
  tracker_state: TrackerState;
}

export interface MessageResponse {
  reply_text: string;
  tracker_state: TrackerState;
  escalated: boolean;
  complete: boolean;
  checkpoint: boolean;
}

export interface RulesResponse {
  firm: string;
  rules: Array<Record<string, unknown>>;
  documents: Record<string, { id: string; label: string; group: string }>;
}

// --- Fetch helpers ----------------------------------------------------------

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  createSession: () =>
    req<CreateSessionResponse>("/session", { method: "POST" }),

  getSession: (sessionId: string) =>
    req<SessionSnapshot>(`/session/${sessionId}`),

  sendMessage: (sessionId: string, text: string) =>
    req<MessageResponse>(`/session/${sessionId}/message`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  patchProfile: (sessionId: string, fieldUpdates: Record<string, unknown>) =>
    req<SessionSnapshot>(`/session/${sessionId}/profile`, {
      method: "PATCH",
      body: JSON.stringify({ field_updates: fieldUpdates }),
    }),

  approve: (sessionId: string) =>
    req<SessionSnapshot>(`/session/${sessionId}/approve`, { method: "POST" }),

  getRules: () => req<RulesResponse>("/rules"),
};
