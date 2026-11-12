import type { Step } from './types';
import type { Words } from './i18n';

/* How a request ended, said on its card (interfaz v5, documentacion/interfaz/V5.md §4). It is read only from the typed
   statuses the host gives each step (FieldStepProjection): no text is read and nothing is guessed. The card never says
   more than was checked: a reply saying «Listo» with a failed step shows «Hecho en parte» or «No pude». */

export type OutcomeKind = 'ok' | 'same' | 'read' | 'sent' | 'maybe' | 'part' | 'fail' | 'skip';

export interface Outcome { kind: OutcomeKind; ic: string; label: Words }

const SAID: Record<OutcomeKind, Outcome> = {
  ok: { kind: 'ok', ic: '✓', label: { es: 'Hecho y comprobado', en: 'Done and checked' } },
  same: { kind: 'same', ic: '=', label: { es: 'Ya estaba así', en: 'Already like that' } },
  read: { kind: 'read', ic: '✓', label: { es: 'Leído del PC', en: 'Read from your PC' } },
  sent: { kind: 'sent', ic: '↗', label: { es: 'Hecho, sin poder comprobarlo', en: 'Done, couldn’t check it' } },
  maybe: { kind: 'maybe', ic: '?', label: { es: 'Puede que se haya hecho', en: 'It may have happened' } },
  part: { kind: 'part', ic: '◐', label: { es: 'Hecho en parte', en: 'Partly done' } },
  fail: { kind: 'fail', ic: '✕', label: { es: 'No pude', en: 'Couldn’t do it' } },
  skip: { kind: 'skip', ic: '–', label: { es: 'No se hizo', en: 'Not done' } },
};

const READ_FROM_WEB: Outcome = { kind: 'read', ic: '✓', label: { es: 'Leído de la web', en: 'Read from the web' } };

/** null while a step still runs, and for a reply with no steps (talk). */
export function outcomeOf(steps: readonly Step[]): Outcome | null {
  if (!steps.length || steps.some((s) => s.status === 'run')) return null;
  const has = (...k: Step['status'][]) => steps.some((s) => k.includes(s.status));
  const all = (...k: Step['status'][]) => steps.every((s) => k.includes(s.status));
  if (has('fail')) return has('ok', 'same', 'read', 'sent', 'maybe') ? SAID.part : SAID.fail;
  if (has('maybe')) return SAID.maybe;
  if (has('sent')) return SAID.sent;
  if (all('skip')) return SAID.skip;
  if (all('same')) return SAID.same;
  if (has('ok', 'same')) return has('skip') ? SAID.part : SAID.ok;
  if (has('read')) return has('skip') ? SAID.part : steps.some((s) => s.status === 'read' && s.net) ? READ_FROM_WEB : SAID.read;
  return SAID.skip;
}
