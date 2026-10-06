import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App, { TOKEN_KEY } from "../App";
type Handler = (body: any) => { status?: number; json?: unknown };
const profile = {
  user_id: "u1",
  name: "Rahul",
  dob: "1995-08-15",
  time_of_birth: null,
  birth_place: "Delhi",
  preferred_language: null,
  zodiac_sign: "Leo",
  degraded: false,
};
const goal = {
  id: "f1",
  type: "goal",
  label: "switch jobs",
  status: "active",
  confidence: 0.6,
  life_area: "career",
  timeframe: "next year",
  target_year: 2027,
  supersedes_id: null,
  created_at: "2026-10-05T00:00:00Z",
  updated_at: "2026-10-05T00:00:00Z",
};
let routes: Record<string, Handler>;
let calls: { method: string; path: string; body: any; auth: string | null }[];
function mockBackend(overrides: Record<string, Handler> = {}) {
  routes = {
    "GET /health": () => ({
      json: { status: "ok", graph_backend: "neo4j", llm_provider: "mock" },
    }),
    "GET /me": () => ({ json: profile }),
    "GET /me/brain": () => ({ json: { facts: [], degraded: false } }),
    "GET /me/sessions": () => ({ json: { sessions: [] } }),
    "POST /auth/logout": () => ({ status: 204 }),
    ...overrides,
  };
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const method = init.method ?? "GET";
      const path = url.replace(/^\/api/, "");
      const body = init.body ? JSON.parse(String(init.body)) : undefined;
      const auth =
        (init.headers as Record<string, string> | undefined)?.Authorization ??
        null;
      calls.push({ method, path, body, auth });
      const handler = routes[`${method} ${path}`];
      if (!handler)
        return new Response(JSON.stringify({ detail: "Not found" }), {
          status: 404,
        });
      const { status = 200, json } = handler(body);
      return new Response(status === 204 ? null : JSON.stringify(json), {
        status,
      });
    }),
  );
}
describe("authentication", () => {
  beforeEach(() => mockBackend());
  it("logs in and shows the chat with the user profile", async () => {
    routes["POST /auth/login"] = () => ({ json: { session_token: "tok-1" } });
    render(<App />);
    await userEvent.type(screen.getByLabelText("Email"), "rahul@example.com");
    await userEvent.type(screen.getByLabelText(/^Password/), "correct-horse");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText(/Namaste, Rahul/)).toBeInTheDocument();
    expect(localStorage.getItem(TOKEN_KEY)).toBe("tok-1");
    expect(calls.find((c) => c.path === "/me")?.auth).toBe("Bearer tok-1");
  });
  it("shows the server error for bad credentials", async () => {
    routes["POST /auth/login"] = () => ({
      status: 401,
      json: { detail: "Invalid email or password" },
    });
    render(<App />);
    await userEvent.type(screen.getByLabelText("Email"), "x@example.com");
    await userEvent.type(screen.getByLabelText(/^Password/), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid email or password",
    );
  });
  it("signs up with only the birth details that were filled in", async () => {
    routes["POST /auth/signup"] = () => ({
      status: 201,
      json: { session_token: "tok-2", user_id: "u1", degraded: false },
    });
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "Sign up" }));
    await userEvent.type(screen.getByLabelText("Email"), "new@example.com");
    await userEvent.type(screen.getByLabelText(/^Password/), "long-enough-pw");
    await userEvent.type(screen.getByLabelText("Name"), "Rahul");
    await userEvent.click(
      screen.getByRole("button", { name: "Create account" }),
    );
    await screen.findByText(/Namaste, Rahul/);
    expect(calls.find((c) => c.path === "/auth/signup")?.body).toEqual({
      email: "new@example.com",
      password: "long-enough-pw",
      name: "Rahul",
    });
  });
  it("returns to the login screen when the session has expired", async () => {
    localStorage.setItem(TOKEN_KEY, "stale");
    routes["GET /me"] = () => ({
      status: 401,
      json: { detail: "Missing or invalid sessiontoken" },
    });
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "Welcome back" }),
    ).toBeInTheDocument();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});
describe("chat", () => {
  beforeEach(() => {
    mockBackend();
    localStorage.setItem(TOKEN_KEY, "tok-1");
  });
  it("sends a message and shows the reply, context used and saved memory", async () => {
    let brainFacts: unknown[] = [];
    routes["GET /me/brain"] = () => ({
      json: { facts: brainFacts, degraded: false },
    });
    routes["POST /chat"] = (body) => {
      brainFacts = [goal];
      return {
        json: {
          response: "Rahul, here is your guidance.",
          user_id: "u1",
          session_id: body.session_id,
          intent: "career",
          context_used: ["career_goal", "user_profile"],
          degraded: false,
          memory_updates: [
            {
              action: "created",
              type: "goal",
              label: "switch jobs",
              life_area: "career",
              details: {},
            },
          ],
        },
      };
    };
    render(<App />);
    const input = await screen.findByLabelText("Message");
    await userEvent.type(
      input,
      "I'm planning to switch jobs next year.{Enter}",
    );
    expect(
      await screen.findByText("Rahul, here is your guidance."),
    ).toBeInTheDocument();
    const reply = screen.getByRole("article", { name: "AstroChat replied" });
    expect(within(reply).getByText("Career goal")).toBeInTheDocument();
    expect(
      within(reply).getByText(/New goal: switch jobs/),
    ).toBeInTheDocument();
    const brain = screen.getByRole("complementary", { name: "Shared Brain" });
    expect(await within(brain).findByText("Switch jobs")).toBeInTheDocument();
    expect(within(brain).getByText("Target 2027")).toBeInTheDocument();
    expect(input).toHaveValue("");
  });
  it("keeps a failed message with a retry button", async () => {
    let attempts = 0;
    routes["POST /chat"] = (body) => {
      attempts += 1;
      return attempts === 1
        ? { status: 500, json: { detail: "Internal server error" } }
        : {
            json: {
              response: "Second time lucky.",
              user_id: "u1",
              session_id: body.session_id,
              intent: "general_astrology",
              context_used: [],
              memory_updates: [],
              degraded: false,
            },
          };
    };
    render(<App />);
    await userEvent.type(
      await screen.findByLabelText("Message"),
      "Hello{Enter}",
    );
    expect(
      await screen.findByText("Internal server error"),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Retry/ }));
    expect(await screen.findByText("Second time lucky.")).toBeInTheDocument();
    expect(screen.queryByText("Internal server error")).not.toBeInTheDocument();
  });
  it("opens a past conversation from the sidebar", async () => {
    routes["GET /me/sessions"] = () => ({
      json: {
        sessions: [
          {
            session_id: "s-old",
            title: "Career chat",
            message_count: 2,
            last_message_at: "2026-10-05T00:00:00Z",
          },
        ],
      },
    });
    routes["GET /me/sessions/s-old/messages"] = () => ({
      json: {
        messages: [
          {
            role: "user",
            content: "What about my career?",
            created_at: "2026-10-05T00:00:00Z",
          },
          {
            role: "assistant",
            content: "Focus on growth.",
            created_at: "2026-10-05T00:00:01Z",
          },
        ],
      },
    });
    render(<App />);
    await userEvent.click(
      await screen.findByRole("button", { name: /Career chat/ }),
    );
    expect(await screen.findByText("Focus on growth.")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Career chat" }),
    ).toBeInTheDocument();
  });
  it("shows limited mode when the memory backend is degraded", async () => {
    routes["GET /health"] = () => ({
      json: {
        status: "degraded",
        graph_backend: "in_memory",
        llm_provider: "mock",
      },
    });
    render(<App />);
    expect(await screen.findByText(/Limited mode/)).toBeInTheDocument();
  });
  it("logs out", async () => {
    render(<App />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Log out" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Welcome back" }),
      ).toBeInTheDocument(),
    );
    expect(
      calls.some((c) => c.method === "POST" && c.path === "/auth/logout"),
    ).toBe(true);
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});
