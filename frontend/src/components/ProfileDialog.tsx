import { useEffect, useRef, useState, type FormEvent } from "react";
import { Loader2, X } from "lucide-react";
import { ApiError, type Profile, type ProfileInput } from "../api";
import { ProfileFields } from "./AuthScreen";
interface Props {
  profile: Profile | null;
  onSave: (input: ProfileInput) => Promise<void>;
  onClose: () => void;
}
export function ProfileDialog({ profile, onSave, onClose }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [value, setValue] = useState<ProfileInput>({
    name: profile?.name ?? "",
    dob: profile?.dob ?? "",
    time_of_birth: profile?.time_of_birth ?? "",
    birth_place: profile?.birth_place ?? "",
    preferred_language: profile?.preferred_language ?? "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal?.();
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSave(value);
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not save your profile.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <dialog
      ref={dialogRef}
      className="dialog"
      aria-labelledby="profile-dialog-title"
      onCancel={onClose}
    >
      <form onSubmit={submit} className="form">
        <div className="dialog-header">
          <h2 id="profile-dialog-title">Your birth details</h2>
          <button
            type="button"
            className="icon-button"
            aria-label="Close"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>
        <p className="muted small">
          Used to personalize guidance. Your sun sign is calculated from your
          date of birth.
        </p>
        <ProfileFields
          value={value}
          onChange={(field) => (v) => setValue((p) => ({ ...p, [field]: v }))}
        />
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-actions">
          <button type="button" className="button ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="button primary" disabled={busy}>
            {busy && <Loader2 size={16} className="spin" />} Save
          </button>
        </div>
      </form>
    </dialog>
  );
}
