import { LogOut, MessageSquare, Plus, Sparkles, X } from "lucide-react";
import type { Profile, SessionSummary } from "../api";
import { relativeTime, ZODIAC_GLYPHS } from "../format";
interface Props {
  open: boolean;
  profile: Profile | null;
  sessions: SessionSummary[];
  activeSessionId: string;
  onNewChat: () => void;
  onSelect: (sessionId: string) => void;
  onClose: () => void;
  onSignOut: () => void;
}
export function Sidebar({
  open,
  profile,
  sessions,
  activeSessionId,
  onNewChat,
  onSelect,
  onClose,
  onSignOut,
}: Props) {
  const initials = (profile?.name ?? "?").trim().charAt(0).toUpperCase();
  return (
    <aside
      className={open ? "panel panel-left open" : "panel panel-left"}
      aria-label="Conversations"
    >
      <div className="panel-header">
        <div className="brand">
          <span className="brand-mark">
            <Sparkles size={16} />
          </span>
          <span>AstroChat</span>
        </div>
        <button
          type="button"
          className="icon-button drawer-close"
          aria-label="Close
conversations"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </div>
      <button type="button" className="button primary wide" onClick={onNewChat}>
        <Plus size={16} /> New conversation
      </button>
      <nav className="session-list" aria-label="Past conversations">
        {sessions.length === 0 && (
          <p className="muted small empty-note">
            Your conversations will appear here.
          </p>
        )}
        {sessions.map((s) => (
          <button
            key={s.session_id}
            type="button"
            className={
              s.session_id === activeSessionId ? "session active" : "session"
            }
            aria-current={s.session_id === activeSessionId ? "true" : undefined}
            onClick={() => onSelect(s.session_id)}
          >
            <MessageSquare size={15} aria-hidden="true" />
            <span className="session-title">
              {s.title || "Untitled conversation"}
            </span>
            <span className="session-time">
              {relativeTime(s.last_message_at)}
            </span>
          </button>
        ))}
      </nav>
      <div className="user-card">
        <span className="avatar" aria-hidden="true">
          {initials}
        </span>
        <div className="user-meta">
          <span className="user-name">{profile?.name ?? "Your account"}</span>
          {profile?.zodiac_sign && (
            <span className="muted small">
              <span className="glyph" aria-hidden="true">
                {ZODIAC_GLYPHS[profile.zodiac_sign]}
              </span>{" "}
              {profile.zodiac_sign}
            </span>
          )}
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label="Log out"
          title="Log out"
          onClick={onSignOut}
        >
          <LogOut size={18} />
        </button>
      </div>
    </aside>
  );
}
