import type { AppSettings, Citation, Language, Session } from '../types';
import { isRecord, parseSessions, parseSettings } from './state';

/** Versioned envelope of a workspace backup file. */
export const BACKUP_FORMAT = 'parsrag-workspace';
export const BACKUP_VERSION = 1;

export type BackupError = 'invalid_backup' | 'unsupported_version' | 'empty_backup';

/** Serialize conversations and portable preferences (no endpoint, no secrets). */
export function createBackup(sessions: Session[], settings: AppSettings, now = Date.now()): string {
  const { backendUrl: _endpoint, ...portable } = settings;
  const saved = sessions.filter(session => session.messages.length || session.documents.length);
  return JSON.stringify({
    format: BACKUP_FORMAT, version: BACKUP_VERSION, exportedAt: new Date(now).toISOString(),
    settings: portable, sessions: saved,
  }, null, 2);
}

/** Validate a backup file with the same rules used for local storage. */
export function parseBackup(text: string, origin?: string): { sessions: Session[]; settings?: AppSettings } {
  let value: unknown;
  try { value = JSON.parse(text); } catch { throw new Error('invalid_backup' satisfies BackupError); }
  if (!isRecord(value) || value.format !== BACKUP_FORMAT || typeof value.version !== 'number') {
    throw new Error('invalid_backup' satisfies BackupError);
  }
  if (value.version > BACKUP_VERSION) throw new Error('unsupported_version' satisfies BackupError);
  const sessions = parseSessions(JSON.stringify(value.sessions ?? []));
  if (!sessions.length) throw new Error('empty_backup' satisfies BackupError);
  const settings = isRecord(value.settings) ? parseSettings(JSON.stringify(value.settings), origin) : undefined;
  return { sessions, settings };
}

/**
 * Add imported conversations; a conversation already present is replaced only
 * when the imported copy is newer, and keeps this machine's document list.
 */
export function mergeSessions(current: Session[], incoming: Session[]) {
  const byId = new Map(current.map(session => [session.id, session]));
  let added = 0;
  let updated = 0;
  for (const session of incoming) {
    const existing = byId.get(session.id);
    if (!existing) { byId.set(session.id, session); added += 1; }
    else if (session.updatedAt > existing.updatedAt) {
      byId.set(session.id, { ...session, documents: existing.documents });
      updated += 1;
    }
  }
  const sessions = [...byId.values()].sort((a, b) => b.updatedAt - a.updatedAt);
  return { sessions, added, updated };
}

const LABELS = {
  fa: { you: 'شما', assistant: 'پارس‌رگ', sources: 'منابع', exported: 'خروجی گرفته‌شده در', page: 'صفحه', slide: 'اسلاید', paragraph: 'بند', section: 'بخش' },
  en: { you: 'You', assistant: 'ParsRAG', sources: 'Sources', exported: 'Exported on', page: 'page', slide: 'slide', paragraph: 'paragraph', section: 'section' },
};

function sourceLine(citation: Citation, language: Language): string {
  const labels = LABELS[language];
  const where = citation.locations.map(location => `${labels[location.kind]} ${location.start}${location.end && location.end !== location.start ? `–${location.end}` : ''}`);
  return `- ${citation.filename}${where.length ? ` (${where.join(language === 'fa' ? '، ' : ', ')})` : ''}`;
}

/** Render one conversation as readable Markdown, including answer sources. */
export function conversationMarkdown(session: Session, language: Language, now = Date.now()): string {
  const labels = LABELS[language];
  const lines = [`# ${session.title || labels.assistant}`, '', `_${labels.exported} ${new Date(now).toISOString().slice(0, 10)}_`, ''];
  for (const message of session.messages) {
    if (message.role === 'system') { lines.push(`> ${message.content}`, ''); continue; }
    lines.push(`### ${message.role === 'user' ? labels.you : labels.assistant}`, '', message.content.trim(), '');
    if (message.role === 'assistant' && message.citations?.length) {
      lines.push(`**${labels.sources}:**`, ...message.citations.map(citation => sourceLine(citation, language)), '');
    }
  }
  return lines.join('\n').replace(/\n{3,}/g, '\n\n').trimEnd() + '\n';
}

/** A filesystem-safe name derived from a conversation title. */
export function exportFilename(title: string, extension: string, now = Date.now()): string {
  const stem = title.replace(/[\\/:*?"<>|\u0000-\u001f]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 60) || 'parsrag';
  return `${stem} ${new Date(now).toISOString().slice(0, 10)}.${extension}`;
}

/** Offer text as a file download in the browser. */
export function downloadText(filename: string, text: string, type: string): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement('a');
  link.href = url; link.download = filename; link.rel = 'noopener';
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
