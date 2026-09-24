export type ShortcutAction = 'newChat' | 'searchChats' | 'documents' | 'settings' | 'composer' | 'guide' | 'theme';

type Shortcut = { action: ShortcutAction; key: string; shift?: boolean; modifier?: boolean };

export const SHORTCUTS: readonly Shortcut[] = [
  { action: 'newChat', key: 'o', shift: true, modifier: true },
  { action: 'searchChats', key: 'k', shift: true, modifier: true },
  { action: 'documents', key: 'd', shift: true, modifier: true },
  { action: 'settings', key: ',', modifier: true },
  { action: 'composer', key: '/' },
  { action: 'guide', key: 'h', shift: true, modifier: true },
  { action: 'theme', key: 'y', shift: true, modifier: true },
];

export function isApplePlatform(platform: string): boolean {
  return /mac|iphone|ipad|ipod/i.test(platform);
}

export function shortcutLabel(action: ShortcutAction, apple: boolean): string {
  const shortcut = SHORTCUTS.find(item => item.action === action)!;
  const parts = [shortcut.modifier ? apple ? '⌘' : 'Ctrl' : '', shortcut.shift ? apple ? '⇧' : 'Shift' : '', shortcut.key.toUpperCase()].filter(Boolean);
  return parts.join(apple ? '' : '+');
}

export function resolveShortcut(event: Pick<KeyboardEvent, 'key' | 'ctrlKey' | 'metaKey' | 'shiftKey' | 'altKey' | 'isComposing'>, apple: boolean, editable: boolean): ShortcutAction | null {
  if (event.isComposing || event.altKey) return null;
  const modifier = apple ? event.metaKey && !event.ctrlKey : event.ctrlKey && !event.metaKey;
  if ((event.ctrlKey || event.metaKey) && !modifier) return null;
  const shortcut = SHORTCUTS.find(item => item.key === event.key.toLowerCase()
    && Boolean(item.modifier) === modifier && Boolean(item.shift) === event.shiftKey);
  if (!shortcut || (editable && !shortcut.modifier)) return null;
  return shortcut.action;
}
