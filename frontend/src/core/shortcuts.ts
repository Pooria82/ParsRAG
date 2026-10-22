export type ShortcutAction = 'newChat' | 'searchChats' | 'documents' | 'settings' | 'composer' | 'guide' | 'theme';

/** `code` is the physical key, used when the layout types no Latin character (Persian). */
type Shortcut = { action: ShortcutAction; key: string; code: string; shift?: boolean; modifier?: boolean };

export const SHORTCUTS: readonly Shortcut[] = [
  { action: 'newChat', key: 'o', code: 'KeyO', shift: true, modifier: true },
  { action: 'searchChats', key: 'k', code: 'KeyK', shift: true, modifier: true },
  { action: 'documents', key: 'd', code: 'KeyD', shift: true, modifier: true },
  { action: 'settings', key: ',', code: 'Comma', modifier: true },
  { action: 'composer', key: '/', code: 'Slash' },
  { action: 'guide', key: 'h', code: 'KeyH', shift: true, modifier: true },
  { action: 'theme', key: 'y', code: 'KeyY', shift: true, modifier: true },
];

export function isApplePlatform(platform: string): boolean {
  return /mac|iphone|ipad|ipod/i.test(platform);
}

export function shortcutLabel(action: ShortcutAction, apple: boolean): string {
  const shortcut = SHORTCUTS.find(item => item.action === action)!;
  const parts = [shortcut.modifier ? apple ? '⌘' : 'Ctrl' : '', shortcut.shift ? apple ? '⇧' : 'Shift' : '', shortcut.key.toUpperCase()].filter(Boolean);
  return parts.join(apple ? '' : '+');
}

/**
 * The action for a key press. A Latin character is matched by what it types,
 * so other Latin layouts (Dvorak) keep their letters; any other character is
 * matched by the physical key, so Ctrl+Shift+O works on a Persian layout too.
 */
export function resolveShortcut(event: Pick<KeyboardEvent, 'key' | 'ctrlKey' | 'metaKey' | 'shiftKey' | 'altKey' | 'isComposing'> & { code?: string }, apple: boolean, editable: boolean): ShortcutAction | null {
  if (event.isComposing || event.altKey) return null;
  const modifier = apple ? event.metaKey && !event.ctrlKey : event.ctrlKey && !event.metaKey;
  if ((event.ctrlKey || event.metaKey) && !modifier) return null;
  const latin = /^[\x21-\x7e]$/.test(event.key);
  const shortcut = SHORTCUTS.find(item => (latin ? item.key === event.key.toLowerCase() : item.code === event.code)
    && Boolean(item.modifier) === modifier && Boolean(item.shift) === event.shiftKey);
  if (!shortcut || (editable && !shortcut.modifier)) return null;
  return shortcut.action;
}
