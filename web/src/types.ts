export type AgentStage =
  | "requirements_review"
  | "plan_draft"
  | "budget_tradeoff"
  | "final_confirmation"
  | "completed"
  | "error";

export type AgentAction = "advise" | "accept" | "revise" | "confirm";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
}

export interface DecisionCard {
  id: string;
  stage: AgentStage;
  title: string;
  summary: string;
  recommended_action: string;
  options: string[];
  requires_user_input: boolean;
}

export interface QuoteOption {
  id: string;
  kind: "transport" | "hotel" | "attraction";
  name: string;
  provider: string;
  price_cny: number;
  refundable: boolean;
  requires_confirmation: boolean;
  metadata: Record<string, string | number | boolean>;
}

export interface MockBooking {
  id: string;
  quote_id: string;
  kind: "transport" | "hotel" | "attraction";
  status: "mock_confirmed" | "blocked";
  created_at: string;
  note: string;
}

export interface AgentSnapshot {
  stage: AgentStage;
  summary: string;
  itinerary: Array<Record<string, string | number>>;
  transport_options: QuoteOption[];
  hotel_options: QuoteOption[];
  attraction_options: QuoteOption[];
  selected_quote_ids: string[];
  bookings: MockBooking[];
}

export interface AgentSession {
  id: string;
  stage: AgentStage;
  messages: ChatMessage[];
  pending_decision: DecisionCard | null;
  snapshots: AgentSnapshot[];
  result: unknown | null;
  created_at: string;
  updated_at: string;
}

export interface AgentEvent {
  event: string;
  session_id: string;
  data: Record<string, unknown>;
  created_at: string;
}

