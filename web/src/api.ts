import type { AgentAction, AgentSession } from "./types";

export async function createSession(message: string): Promise<AgentSession> {
  const response = await fetch("/api/agent/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message })
  });
  return parseResponse(response);
}

export async function sendMessage(params: {
  sessionId: string;
  message: string;
  decisionId?: string;
  action?: AgentAction;
}): Promise<AgentSession> {
  const response = await fetch(`/api/agent/sessions/${params.sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: params.message,
      decision_id: params.decisionId,
      action: params.action
    })
  });
  return parseResponse(response);
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

