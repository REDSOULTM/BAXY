import { useCallback, useState, useSyncExternalStore, type FocusEvent } from 'react';
import type { SettingsTab } from './components/panels/SettingsPanel';

/* What the person wrote in Settings and has not saved yet. REV_VISTA V-05 (2026-11-09): the behavior's texts, the API's key, address
   and model name, the spending cap and the custom tool profile lived in the box that held them, and Escape, a click outside or
   another tab took the box and the words with it, under a footer that said «Los cambios se guardan al momento». Here a draft
   outlives its box: back on that tab, or with Settings open again, it is where it was. Only in this view's memory, never in the
   browser's storage (a key among them); the host's settings change only with «Guardar». It goes when BAXY's window does: closing
   it then asks (App). */

const drafts = new Map<string, unknown>();
const listeners = new Set<() => void>();
let version = 0;

function changed() {
  version++;
  for (const listen of listeners) listen();
}

function subscribe(listen: () => void) {
  listeners.add(listen);
  return () => { listeners.delete(listen); };
}

/** the keys of the drafts kept now (a section's prefix before the dot: «behavior.personality», «external.key», «tools.custom») */
export function draftKeys(): string[] {
  return [...drafts.keys()];
}

/** draftKeys(), re-read whenever a draft starts or goes */
export function useDraftKeys(): string[] {
  useSyncExternalStore(subscribe, () => version);
  return draftKeys();
}

// the Settings tab each draft is written in
const TAB: Record<string, SettingsTab> = { behavior: 'comportamiento', external: 'modelo', tools: 'herramientas' };

/** the Settings tab a draft's key belongs to */
export function draftTab(key: string): SettingsTab {
  return TAB[key.split('.')[0]] ?? 'general';
}

/** Drops a draft (after it was saved, or when the person discards it on purpose). */
export function forgetDraft(key: string) {
  if (drafts.delete(key)) changed();
}

/**
 * A value the person edits, kept under `key` while it differs from `saved` (what the host says now). Equal again (written back,
 * or saved), it is no draft. `same` says when two values are the same text (the behavior's ignore the spaces around them).
 */
export function useDraft<V>(key: string, saved: V, same: (a: V, b: V) => boolean = Object.is): [V, (v: V) => void] {
  const [value, setValue] = useState<V>(() => {
    if (!drafts.has(key)) return saved;
    const kept = drafts.get(key) as V;
    if (same(kept, saved)) { drafts.delete(key); queueMicrotask(changed); return saved; }
    return kept;
  });
  const set = useCallback((v: V) => {
    setValue(v);
    if (same(v, saved)) { if (drafts.delete(key)) changed(); }
    else { const fresh = !drafts.has(key); drafts.set(key, v); if (fresh) changed(); }
  }, [key, saved, same]);
  return [value, set];
}

/** Whether a box that saves when it is left should save now: not when Escape left it (App marks it data-escaped). VIS2 blind
 *  review: Escape in the API's address, model or cap saved what was being written; it keeps it as a draft instead. */
export function savesOnBlur(e: FocusEvent<HTMLElement>): boolean {
  const escaped = e.currentTarget.hasAttribute('data-escaped');
  e.currentTarget.removeAttribute('data-escaped');
  return !escaped;
}
