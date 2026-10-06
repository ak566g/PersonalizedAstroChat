import type { Fact, MemoryUpdate } from "./api";
// U+FE0E asks for the monochrome text glyph instead of the colour emoji (Windows renders emoji by default).
export const ZODIAC_GLYPHS: Record<string, string> = Object.fromEntries(
  Object.entries({
    Aries: "♈",
    Taurus: "♉",
    Gemini: "♊",
    Cancer: "♋",
    Leo: "♌",
    Virgo: "♍",
    Libra: "♎",
    Scorpio: "♏",
    Sagittarius: "♐",
    Capricorn: "♑",
    Aquarius: "♒",
    Pisces: "♓",
  }).map(([sign, glyph]) => [sign, `${glyph}\uFE0E`]),
);
export function backendLabel(backend: string): string {
  return backend === "neo4j"
    ? "Neo4j"
    : backend === "memory"
      ? "in-memory"
      : backend;
}
const CONTEXT_LABELS: Record<string, string> = {
  user_profile: "Your profile",
  zodiac_sign: "Sun sign",
  recent_conversation: "This conversation",
  preference: "Your preferences",
  interest: "Your interests",
};
const PROFILE_FIELD_LABELS: Record<string, string> = {
  name: "name",
  dob: "date of birth",
  time_of_birth: "time of birth",
  birth_place: "birth place",
  preferred_language: "language",
};
export const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
export function contextLabel(key: string): string {
  if (CONTEXT_LABELS[key]) return CONTEXT_LABELS[key];
  const [area, type] = key.split("_");
  return type ? `${capitalize(area)} ${type}` : capitalize(key);
}
export function describeUpdate(update: MemoryUpdate): string {
  switch (update.action) {
    case "profile_updated":
      return `Saved your ${PROFILE_FIELD_LABELS[update.label] ?? update.label}:
${String(update.details.value ?? "")}`;
    case "created":
      return `New ${update.type}: ${update.label}`;
    case "reinforced":
      return `Strengthened ${update.type}: ${update.label}`;
    case "superseded":
      return `Updated ${update.type}: ${String(update.details.replaced ?? "")} →
${update.label}`;
    case "retracted":
      return `Removed ${update.type}: ${update.label}`;
  }
}
export function factWhen(fact: Fact): string | null {
  if (fact.target_year) return `Target ${fact.target_year}`;
  return fact.timeframe ? capitalize(fact.timeframe) : null;
}
export const FACT_TYPE_LABELS: Record<Fact["type"], string> = {
  goal: "Goals",
  interest: "Interests",
  preference: "Preferences",
  memory: "Life details",
};
export function formatDate(iso: string | null): string | null {
  if (!iso) return null;
  const date = new Date(`${iso}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString(undefined, {
        day: "numeric",
        month: "long",
        year: "numeric",
      });
}
export function relativeTime(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((now.getTime() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return days < 7 ? `${days}d ago` : new Date(iso).toLocaleDateString();
}
export function newSessionId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
