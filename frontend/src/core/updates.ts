import type { ReleaseNote, UpdateStatus } from '../types';

export const UPDATE_STORAGE = {
  /** The version whose notes the user has seen (or had nothing to see). */
  seenVersion: 'parsrag_seen_version_v1',
  /** A release the user chose to skip; its badge stays hidden. */
  skippedUpdate: 'parsrag_skipped_update_v1',
  /** The version this tab already reloaded for, so a reload never repeats. */
  reloadedFor: 'parsrag_reloaded_for_v1',
};

function parts(version: string): [number, number, number] | null {
  const match = /^v?(\d+)\.(\d+)\.(\d+)$/.exec(version.trim());
  return match ? [Number(match[1]), Number(match[2]), Number(match[3])] : null;
}

/** Whether `candidate` is a later release than `current` (MAJOR.MINOR.PATCH). */
export function isNewerVersion(candidate: string, current: string): boolean {
  const a = parts(candidate);
  const b = parts(current);
  if (!a || !b) return false;
  for (let index = 0; index < 3; index += 1) if (a[index] !== b[index]) return a[index] > b[index];
  return false;
}

/**
 * Which notes to show after loading `current`. Undefined: nothing to show.
 * `since: null` shows only the current version's notes: someone who used the
 * app before this mechanism existed (they have conversations) just updated;
 * a first visit shows nothing.
 */
export function notesToShow(seen: string | null, current: string, hasHistory: boolean): { since: string | null } | undefined {
  if (seen === null) return hasHistory ? { since: null } : undefined;
  return isNewerVersion(current, seen) ? { since: seen } : undefined;
}

/** The newer release the badge offers, unless the user skipped it. */
export function offeredUpdate(status: UpdateStatus | null, skipped: string | null): string | undefined {
  const latest = status?.update_available ? status.latest_version : null;
  return latest && latest !== skipped ? latest : undefined;
}

/** The one command that backs up and updates, for the user's system. */
export function updateCommand(platform: string): string {
  return /win/i.test(platform)
    ? 'powershell -ExecutionPolicy Bypass -File scripts/update.ps1'
    : 'sh scripts/update.sh';
}

/** Notes of one release in the interface language, falling back to English. */
export function releaseNotesText(release: { notes_fa: string; notes_en: string }, language: 'fa' | 'en'): string {
  return (language === 'fa' ? release.notes_fa : release.notes_en) || release.notes_en || release.notes_fa;
}

export type { ReleaseNote };
