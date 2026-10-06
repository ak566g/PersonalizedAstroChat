import { useState, type FormEvent, type ReactNode } from "react";
import { ChevronDown, Loader2, Sparkles } from "lucide-react";
import { api, ApiError, type ProfileInput } from "../api";
interface Props {
  onAuthenticated: (token: string) => void;
}
type Mode = "login" | "signup";
export function AuthScreen({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [profile, setProfile] = useState<ProfileInput>({});
  const [showDetails, setShowDetails] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setField = (field: keyof ProfileInput) => (value: string) =>
    setProfile((p) => ({
      ...p,
      [field]: value,
    }));
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result =
        mode === "login"
          ? await api.login(email, password)
          : await api.signup(email, password, profile);
      onAuthenticated(result.session_token);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
  }
  return (
    <main className="auth">
      <section className="auth-hero" aria-hidden="true">
        <div className="auth-orb" />
        <h2>Guidance that remembers you.</h2>
        <p>
          Tell AstroChat about your goals once. It keeps a private Shared Brain
          of what matters to you and uses it to personalize every answer.
        </p>
      </section>
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="brand">
          <span className="brand-mark">
            <Sparkles size={18} />
          </span>
          <span>
            MyNaksh <strong>AstroChat</strong>
          </span>
        </div>
        <h1 id="auth-title">
          {mode === "login" ? "Welcome back" : "Create your account"}
        </h1>
        <div className="tabs" role="tablist" aria-label="Sign in or sign up">
          {(["login", "signup"] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              className={mode === m ? "tab active" : "tab"}
              onClick={() => switchMode(m)}
            >
              {m === "login" ? "Log in" : "Sign up"}
            </button>
          ))}
        </div>
        <form onSubmit={submit} className="form" noValidate={false}>
          <Field label="Email">
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
          <Field
            label="Password"
            hint={mode === "signup" ? "At least 8 characters" : undefined}
          >
            <input
              type="password"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              required
              minLength={mode === "signup" ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          {mode === "signup" && (
            <fieldset className="details">
              <legend>
                <button
                  type="button"
                  className="link-button"
                  aria-expanded={showDetails}
                  onClick={() => setShowDetails((s) => !s)}
                >
                  Birth details <span className="muted">(optional)</span>
                  <ChevronDown
                    size={16}
                    className={showDetails ? "chevron open" : "chevron"}
                  />
                </button>
              </legend>
              {showDetails && (
                <ProfileFields value={profile} onChange={setField} />
              )}
            </fieldset>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="button primary wide" disabled={busy}>
            {busy && <Loader2 size={16} className="spin" />}
            {mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>
      </section>
    </main>
  );
}
export function ProfileFields({
  value,
  onChange,
}: {
  value: ProfileInput;
  onChange: (f: keyof ProfileInput) => (v: string) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  return (
    <div className="field-grid">
      <Field label="Name">
        <input
          autoComplete="name"
          maxLength={100}
          value={value.name ?? ""}
          onChange={(e) => onChange("name")(e.target.value)}
        />
      </Field>
      <Field label="Date of birth">
        <input
          type="date"
          max={today}
          value={value.dob ?? ""}
          onChange={(e) => onChange("dob")(e.target.value)}
        />
      </Field>
      <Field label="Time of birth">
        <input
          type="time"
          value={value.time_of_birth ?? ""}
          onChange={(e) => onChange("time_of_birth")(e.target.value)}
        />
      </Field>
      <Field label="Birth place">
        <input
          maxLength={100}
          value={value.birth_place ?? ""}
          onChange={(e) => onChange("birth_place")(e.target.value)}
        />
      </Field>
      <Field label="Preferred language">
        <input
          list="languages"
          maxLength={40}
          value={value.preferred_language ?? ""}
          onChange={(e) => onChange("preferred_language")(e.target.value)}
        />
        <datalist id="languages">
          {[
            "English",
            "Hindi",
            "Tamil",
            "Telugu",
            "Bengali",
            "Marathi",
            "Gujarati",
            "Kannada",
            "Malayalam",
            "Punjabi",
          ].map((l) => (
            <option key={l} value={l} />
          ))}
        </datalist>
      </Field>
    </div>
  );
}
function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span className="field-label">
        {label}
        {hint && <span className="muted"> · {hint}</span>}
      </span>
      {children}
    </label>
  );
}
