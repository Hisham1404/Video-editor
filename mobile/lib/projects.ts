/**
 * Saved projects.
 *
 * Mock data until the API layer exists. Dates are deliberately uneven — a list
 * where every project was made at the same tidy hour reads as fake.
 */

export interface Project {
  id: string;
  name: string;
  updatedAt: string; // ISO
  shots: number;
  gaps: number;
  /** Deterministic seed so a project's frames look the same on every render. */
  seed: number;
}

export const PROJECTS: Project[] = [
  {
    id: "dusk-city",
    name: "Dusk city walk",
    updatedAt: "2026-09-09T18:27:00",
    shots: 16,
    gaps: 3,
    seed: 41,
  },
  {
    id: "roof-session",
    name: "Rooftop session",
    updatedAt: "2026-09-06T22:14:00",
    shots: 21,
    gaps: 0,
    seed: 7,
  },
  {
    id: "market-cut",
    name: "Market, early",
    updatedAt: "2026-08-31T09:41:00",
    shots: 12,
    gaps: 5,
    seed: 88,
  },
];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/**
 * "9 Sep, 18:27".
 *
 * Deliberately absolute and deliberately not built from `Date`. A relative
 * label ("Today", "2 hours ago") is computed from the clock, so the server
 * renders one string and the client hydrates with another — React throws a
 * hydration mismatch, and near midnight the label is simply wrong. Parsing the
 * ISO parts by hand also avoids the timezone shift `new Date(iso)` would apply
 * to a wall-clock timestamp that carries no offset.
 */
export function formatWhen(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso);
  if (!m) return iso;
  const [, , month, day, hh, mm] = m;
  return `${Number(day)} ${MONTHS[Number(month) - 1]}, ${hh}:${mm}`;
}
