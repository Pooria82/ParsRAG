import type { Language, RAGMode } from '../types';

export type ComposerTrigger = { kind: 'document' | 'command'; start: number; end: number; query: string };
export type CommandId = 'summary' | 'compare' | 'translate' | 'outline' | 'strict' | 'hybrid' | 'free' | 'documents' | 'help';

export const COMMANDS: Array<{ id: CommandId; label: string; fa: string; en: string }> = [
  { id: 'summary', label: '/summary', fa: 'خلاصهٔ مستند با منبع', en: 'Source-backed summary' },
  { id: 'compare', label: '/compare', fa: 'مقایسهٔ اسناد', en: 'Compare documents' },
  { id: 'translate', label: '/translate', fa: 'ترجمهٔ متن', en: 'Translate text' },
  { id: 'outline', label: '/outline', fa: 'ساختار و نکته‌های کلیدی', en: 'Outline key points' },
  { id: 'strict', label: '/strict', fa: 'فقط بر اساس اسناد', en: 'Documents only' },
  { id: 'hybrid', label: '/hybrid', fa: 'اسناد و دانش مدل', en: 'Documents and model' },
  { id: 'free', label: '/free', fa: 'گفت‌وگوی آزاد', en: 'Open conversation' },
  { id: 'documents', label: '/documents', fa: 'مدیریت اسناد', en: 'Manage documents' },
  { id: 'help', label: '/help', fa: 'نمایش راهنمای برنامه', en: 'Show app tour' },
];

export function activeComposerTrigger(value: string, cursor: number): ComposerTrigger | null {
  const before = value.slice(0, cursor);
  const mention = /(?:^|[\s([{])(@([^\n@{}]{0,80}))$/.exec(before);
  if (mention) return { kind: 'document', start: cursor - mention[1].length, end: cursor, query: mention[2] };
  const command = /(^|\n)(\/[a-z]{0,24})$/i.exec(before);
  if (command) return { kind: 'command', start: cursor - command[2].length, end: cursor, query: command[2].slice(1) };
  return null;
}

export function insertDocumentMention(value: string, trigger: ComposerTrigger, filename: string): { text: string; cursor: number } {
  const token = `@{${filename}}${/^\s/.test(value.slice(trigger.end)) ? '' : ' '}`;
  const text = value.slice(0, trigger.start) + token + value.slice(trigger.end);
  return { text, cursor: trigger.start + token.length };
}

export function applyComposerCommand(id: CommandId, language: Language, value: string, trigger: ComposerTrigger): { text: string; mode?: RAGMode; action?: 'documents' | 'help' } {
  const instructions: Partial<Record<CommandId, Record<Language, string>>> = {
    summary: { fa: 'اسناد انتخاب‌شده را خلاصه کن و نکته‌های مهم را با منبع بنویس: ', en: 'Summarize the selected documents with key takeaways and sources: ' },
    compare: { fa: 'اسناد انتخاب‌شده را مقایسه کن و شباهت‌ها و تفاوت‌ها را با منبع توضیح بده: ', en: 'Compare the selected documents, citing similarities and differences: ' },
    translate: { fa: 'متن زیر را روان و دقیق به فارسی ترجمه کن: ', en: 'Translate the following text into English accurately: ' },
    outline: { fa: 'ساختار و نکته‌های کلیدی موضوع زیر را با منبع فهرست کن: ', en: 'Outline the key points of the following with sources: ' },
  };
  const replacement = instructions[id]?.[language] ?? '';
  const text = value.slice(0, trigger.start) + replacement + value.slice(trigger.end);
  if (id === 'strict' || id === 'hybrid') return { text, mode: id };
  if (id === 'free') return { text, mode: 'llm-only' };
  if (id === 'documents' || id === 'help') return { text, action: id };
  return { text };
}
