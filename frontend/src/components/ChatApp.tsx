import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  ApiError,
  type Fact,
  type Health,
  type Profile,
  type ProfileInput,
  type SessionSummary,
} from "../api";
import { newSessionId } from "../format";
import { BrainPanel } from "./BrainPanel";
import { ChatView } from "./ChatView";
import type { UiMessage } from "./MessageBubble";
import { ProfileDialog } from "./ProfileDialog";
import { Sidebar } from "./Sidebar";
interface Props {
  token: string;
  onSignOut: () => void;
}
let messageCounter = 0;
const nextId = () => `m${++messageCounter}`;
export function ChatApp({ token, onSignOut }: Props) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [sessionId, setSessionId] = useState(newSessionId);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<"sessions" | "brain" | null>(null);
  const [editingProfile, setEditingProfile] = useState(false);
  const sessionRef = useRef(sessionId);
  sessionRef.current = sessionId;
  // Every authenticated call goes through here so an expired session logs the user out.
  const guard = useCallback(
    async <T,>(call: () => Promise<T>): Promise<T | undefined> => {
      try {
        return await call();
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          onSignOut();
          return undefined;
        }
        throw err;
      }
    },
    [onSignOut],
  );
  const refreshBrain = useCallback(async () => {
    const [me, brain] = await Promise.all([
      guard(() => api.me(token)),
      guard(() => api.brain(token)),
    ]);
    if (me) setProfile(me);
    if (brain) setFacts(brain.facts);
  }, [guard, token]);
  const refreshSessions = useCallback(async () => {
    const result = await guard(() => api.sessions(token));
    if (result) setSessions(result.sessions);
  }, [guard, token]);
  const refreshHealth = useCallback(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);
  useEffect(() => {
    Promise.all([refreshBrain(), refreshSessions()]).catch((err) =>
      setBanner(
        err instanceof ApiError ? err.message : "Could not load your data.",
      ),
    );
    refreshHealth();
  }, [refreshBrain, refreshSessions, refreshHealth]);
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawer(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawer]);
  async function send(text: string) {
    const target = sessionRef.current;
    const userMessage: UiMessage = {
      id: nextId(),
      role: "user",
      content: text,
    };
    setMessages((m) => [...m, userMessage]);
    setSending(true);
    try {
      const reply = await guard(() => api.chat(token, target, text));
      if (!reply) return;
      if (sessionRef.current === target) {
        setMessages((m) => [
          ...m,
          {
            id: nextId(),
            role: "assistant",
            content: reply.response,
            meta: {
              context_used: reply.context_used,
              intent: reply.intent,
              memory_updates: reply.memory_updates,
              degraded: reply.degraded,
            },
          },
        ]);
      }
      if (reply.degraded) refreshHealth();
      void refreshSessions();
      if (reply.memory_updates.length > 0) void refreshBrain();
    } catch (err) {
      const error =
        err instanceof ApiError ? err.message : "Message failed to send.";
      setMessages((m) =>
        m.map((msg) => (msg.id === userMessage.id ? { ...msg, error } : msg)),
      );
    } finally {
      setSending(false);
    }
  }
  function retry(failed: UiMessage) {
    setMessages((m) => m.filter((msg) => msg.id !== failed.id));
    void send(failed.content);
  }
  function startNewChat() {
    setSessionId(newSessionId());
    setMessages([]);
    setDrawer(null);
  }
  async function openSession(id: string) {
    setDrawer(null);
    if (id === sessionId) return;
    setSessionId(id);
    setMessages([]);
    setLoadingHistory(true);
    try {
      const result = await guard(() => api.history(token, id));
      if (result && sessionRef.current === id) {
        setMessages(
          result.messages.map((m) => ({
            id: nextId(),
            role: m.role,
            content: m.content,
          })),
        );
      }
    } catch (err) {
      setBanner(
        err instanceof ApiError
          ? err.message
          : "Could not load that conversation.",
      );
    } finally {
      setLoadingHistory(false);
    }
  }
  async function saveProfile(input: ProfileInput) {
    const updated = await guard(() => api.updateMe(token, input));
    if (updated) setProfile(updated);
  }
  async function signOut() {
    await api.logout(token).catch(() => undefined);
    onSignOut();
  }
  const title =
    sessions.find((s) => s.session_id === sessionId)?.title ||
    "New conversation";
  return (
    <div className="app">
      <Sidebar
        open={drawer === "sessions"}
        profile={profile}
        sessions={sessions}
        activeSessionId={sessionId}
        onNewChat={startNewChat}
        onSelect={openSession}
        onClose={() => setDrawer(null)}
        onSignOut={signOut}
      />
      <main className="main">
        {banner && (
          <div className="banner" role="alert">
            <span>{banner}</span>
            <button
              type="button"
              className="link-button"
              onClick={() => setBanner(null)}
            >
              Dismiss
            </button>
          </div>
        )}
        <ChatView
          title={title}
          profile={profile}
          messages={messages}
          loadingHistory={loadingHistory}
          sending={sending}
          health={health}
          onSend={send}
          onRetry={retry}
          onOpenSessions={() => setDrawer("sessions")}
          onOpenBrain={() => setDrawer("brain")}
        />
      </main>
      <BrainPanel
        open={drawer === "brain"}
        profile={profile}
        facts={facts}
        onEditProfile={() => setEditingProfile(true)}
        onClose={() => setDrawer(null)}
      />
      {drawer && (
        <div
          className={`backdrop backdrop-${drawer}`}
          aria-hidden="true"
          onClick={() => setDrawer(null)}
        />
      )}
      {editingProfile && (
        <ProfileDialog
          profile={profile}
          onSave={saveProfile}
          onClose={() => setEditingProfile(false)}
        />
      )}
    </div>
  );
}
