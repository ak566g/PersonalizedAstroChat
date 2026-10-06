export interface Profile {
  user_id: string;
  name: string | null;
  dob: string | null;
  time_of_birth: string | null;
  birth_place: string | null;
  preferred_language: string | null;
  zodiac_sign: string | null;
  degraded: boolean;
}
export type ProfileInput = Partial<
  Pick<
    Profile,
    "name" | "dob" | "time_of_birth" | "birth_place" | "preferred_language"
  >
>;
export interface Fact {
  id: string;
  type: "goal" | "preference" | "interest" | "memory";
  label: string;
  status: "active" | "superseded" | "retracted";
  confidence: number;
  life_area: string | null;
  timeframe: string | null;
  target_year: number | null;
  supersedes_id: string | null;
  created_at: string;
  updated_at: string;
}
export interface MemoryUpdate {
  action:
    | "created"
    | "reinforced"
    | "superseded"
    | "retracted"
    | "profile_updated";
  type: string;
  label: string;
  life_area: string | null;
  details: Record<string, unknown>;
}
export interface ChatReply {
  response: string;
  user_id: string;
  session_id: string;
  context_used: string[];
  intent: string;
  memory_updates: MemoryUpdate[];
  degraded: boolean;
}
export interface SessionSummary {
  session_id: string;
  title: string;
  message_count: number;
  last_message_at: string;
}
export interface StoredMessage {
  role: "user" | "assistant";
  content: string;
  created_at: string;
}
export interface Health {
  status: "ok" | "degraded";
  graph_backend: string;
  llm_provider: string;
}
const BASE = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}
const FIELD_LABELS: Record<string, string> = {
  email: "Email",
  password: "Password",
  dob: "Date of birth",
  time_of_birth: "Time of birth",
  name: "Name",
  birth_place: "Birth place",
  preferred_language: "Language",
  message: "Message",
  session_id: "Conversation",
};
function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((err: { loc?: unknown[]; msg?: string }) => {
        const field = String(err.loc?.[err.loc.length - 1] ?? "");
        const msg = (err.msg ?? "is invalid").replace(/^Value error, /, "");
        return `${FIELD_LABELS[field] ?? field}: ${msg}`;
      })
      .join(" · ");
  }
  return status >= 500
    ? "Something went wrong on the server. Please try again."
    : `Request
failed (${status})`;
}
async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; token?: string | null } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.token) headers.Authorization = `Bearer ${options.token}`;
  let response: Response;
  try {
    response = await fetch(BASE + path, {
      method: options.method ?? "GET",
      headers,
      body:
        options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(
      0,
      "Can't reach the server. Check that the backend is running.",
    );
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new ApiError(response.status, errorMessage(body, response.status));
  return body as T;
}
const clean = (data: ProfileInput): ProfileInput =>
  Object.fromEntries(
    Object.entries(data).map(([k, v]) => [
      k,
      typeof v === "string" && v.trim() === "" ? null : v,
    ]),
  );
export const api = {
  signup: (email: string, password: string, profile: ProfileInput) =>
    request<{ session_token: string; user_id: string; degraded: boolean }>(
      "/auth/signup",
      {
        method: "POST",
        body: {
          email,
          password,
          ...Object.fromEntries(
            Object.entries(clean(profile)).filter(([, v]) => v != null),
          ),
        },
      },
    ),
  login: (email: string, password: string) =>
    request<{ session_token: string }>("/auth/login", {
      method: "POST",
      body: { email, password },
    }),
  logout: (token: string) =>
    request<void>("/auth/logout", { method: "POST", token }),
  me: (token: string) => request<Profile>("/me", { token }),
  updateMe: (token: string, profile: ProfileInput) =>
    request<Profile>("/me", { method: "PATCH", token, body: clean(profile) }),
  brain: (token: string) =>
    request<{ facts: Fact[]; degraded: boolean }>("/me/brain", {
      token,
    }),
  sessions: (token: string) =>
    request<{ sessions: SessionSummary[] }>("/me/sessions", {
      token,
    }),
  history: (token: string, sessionId: string) =>
    request<{ messages: StoredMessage[] }>(
      `/me/sessions/${encodeURIComponent(sessionId)}/messages`,
      { token },
    ),
  chat: (token: string, sessionId: string, message: string) =>
    request<ChatReply>("/chat", {
      method: "POST",
      token,
      body: { session_id: sessionId, message },
    }),
  health: () => request<Health>("/health"),
};
