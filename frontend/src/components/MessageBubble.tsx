import Markdown from "react-markdown";
import { AlertTriangle, BookmarkCheck, RotateCcw } from "lucide-react";
import type { ChatReply } from "../api";
import { contextLabel, describeUpdate } from "../format";
export interface UiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: Pick<
    ChatReply,
    "context_used" | "intent" | "memory_updates" | "degraded"
  >;
  error?: string;
}
interface Props {
  message: UiMessage;
  onRetry?: () => void;
}
export function MessageBubble({ message, onRetry }: Props) {
  const { role, content, meta, error } = message;
  return (
    <article
      className={`message ${role}`}
      aria-label={role === "user" ? "You said" : "AstroChat replied"}
    >
      <div className={error ? "bubble failed" : "bubble"}>
        {role === "assistant" ? (
          <Markdown>{content}</Markdown>
        ) : (
          <p>{content}</p>
        )}
      </div>
      {error && (
        <div className="message-error" role="alert">
          <span>{error}</span>
          {onRetry && (
            <button type="button" className="link-button" onClick={onRetry}>
              <RotateCcw size={14} /> Retry
            </button>
          )}
        </div>
      )}
      {meta && (
        <div className="message-meta">
          {meta.degraded && (
            <span
              className="pill warning"
              title="Some services were unavailable; the
answer may be less personalized."
            >
              <AlertTriangle size={12} /> Limited mode
            </span>
          )}
          {meta.context_used.length > 0 && (
            <div className="context" aria-label="Context used for this answer">
              <span className="muted small">Used:</span>
              {meta.context_used.map((key) => (
                <span key={key} className="pill">
                  {contextLabel(key)}
                </span>
              ))}
            </div>
          )}
          {meta.memory_updates.length > 0 && (
            <ul
              className="memory-updates"
              aria-label="Saved to your Shared Brain"
            >
              {meta.memory_updates.map((u, i) => (
                <li key={i}>
                  <BookmarkCheck size={14} aria-hidden="true" />{" "}
                  {describeUpdate(u)}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </article>
  );
}
