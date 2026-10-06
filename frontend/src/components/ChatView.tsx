import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { Brain, Loader2, Menu, SendHorizontal, Sparkles } from "lucide-react";
import type { Health, Profile } from "../api";
import { backendLabel } from "../format";
import { MessageBubble, type UiMessage } from "./MessageBubble";
const SUGGESTIONS = [
  "I'm planning to switch jobs next year.",
  "What should I focus on for my career?",
  "What do you remember about my goals?",
  "How can I bring more balance to my health?",
];
interface Props {
  title: string;
  profile: Profile | null;
  messages: UiMessage[];
  loadingHistory: boolean;
  sending: boolean;
  health: Health | null;
  onSend: (text: string) => void;
  onRetry: (message: UiMessage) => void;
  onOpenSessions: () => void;
  onOpenBrain: () => void;
}
export function ChatView(props: Props) {
  const {
    title,
    profile,
    messages,
    loadingHistory,
    sending,
    health,
    onSend,
    onRetry,
    onOpenSessions,
    onOpenBrain,
  } = props;
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages, sending]);
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [draft]);
  function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    onSend(text);
    setDraft("");
  }
  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      submit();
    }
  }
  const degraded = health?.status === "degraded";
  return (
    <section className="chat" aria-label="Chat">
      <header className="chat-header">
        <button
          type="button"
          className="icon-button only-mobile"
          aria-label="Open
conversations"
          onClick={onOpenSessions}
        >
          <Menu size={20} />
        </button>
        <div className="chat-title">
          <h1>{title}</h1>
          {health && (
            <span
              className={degraded ? "status degraded" : "status ok"}
              role="status"
            >
              <span className="dot" aria-hidden="true" />
              {degraded
                ? "Limited mode (memory offline)"
                : `Shared Brain online ·
${backendLabel(health.graph_backend)}`}
            </span>
          )}
        </div>
        <button
          type="button"
          className="icon-button only-narrow"
          aria-label="Open Shared
Brain"
          onClick={onOpenBrain}
        >
          <Brain size={20} />
        </button>
      </header>
      <div
        className="messages"
        aria-live="polite"
        aria-busy={sending || loadingHistory}
      >
        {loadingHistory && (
          <p className="muted center">
            <Loader2 size={16} className="spin" /> Loading conversation…
          </p>
        )}
        {!loadingHistory && messages.length === 0 && (
          <div className="welcome">
            <span className="welcome-icon">
              <Sparkles size={28} />
            </span>
            <h2>
              {profile?.name ? `Namaste, ${profile.name}.` : "Namaste."} What's
              on your mind?
            </h2>
            <p className="muted">
              Share your goals and plans. I'll remember what matters and use it
              to personalize future answers.
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="suggestion"
                  onClick={() => onSend(s)}
                  disabled={sending}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            message={m}
            onRetry={m.error ? () => onRetry(m) : undefined}
          />
        ))}
        {sending && (
          <div className="message assistant">
            <div className="bubble typing" aria-label="AstroChat is typing">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>
      <form className="composer" onSubmit={submit}>
        <label htmlFor="composer-input" className="sr-only">
          Message
        </label>
        <textarea
          id="composer-input"
          ref={inputRef}
          rows={1}
          maxLength={4000}
          placeholder="Ask about your career, relationships, health or finances…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <button
          type="submit"
          className="send"
          aria-label="Send message"
          disabled={!draft.trim() || sending}
        >
          {sending ? (
            <Loader2 size={18} className="spin" />
          ) : (
            <SendHorizontal size={18} />
          )}
        </button>
      </form>
    </section>
  );
}
