import { getJson } from './api';
import type { T } from './i18n';

/* RUT3: a routine (RUT1's contract, documentacion/RUTINAS.md §1) in the person's words, and the panel's reading of it
   from the App's routes (§6, GET /catalog, GET /settings/tools). */

/* RUT4: the App gives each call step the title the conversation's cards give it, with its target (`title`), and why it
   would not run today (`blocked`: off in the tool profile, or an action BAXY no longer has); an App that gives neither
   is read as before, from the catalog and the profile. */
export type Step = { op: string; arguments?: Record<string, unknown>; title?: string; blocked?: string } | { say: string };
export type Day = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun';
export type Trigger = { phrase: string } | { at: string; repeat?: 'once' | 'daily' | 'days'; days?: Day[]; date?: string };
/* RUT6: a routine of a phrase kept as an order has no steps: `order` is what the person asked for, in their words. */
export interface Routine { id: string; name: string; trigger: Trigger; steps: Step[]; order?: string; active: boolean }
interface Routines { routines: Routine[]; count: number }
interface Catalog { groups: { items: { name: string; title: string }[] }[] }
interface Tools { on: string[] }
/** the routines with what names their steps; null titles or profile = that route could not be read */
export interface Shown { list: Routine[]; titles: Map<string, string> | null; on: Set<string> | null }

const DAYS: Day[] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const DAY_ES: Record<Day, string> = { mon: 'lunes', tue: 'martes', wed: 'miércoles', thu: 'jueves', fri: 'viernes', sat: 'sábados', sun: 'domingos' };
const DAY_EN: Record<Day, string> = { mon: 'Mondays', tue: 'Tuesdays', wed: 'Wednesdays', thu: 'Thursdays', fri: 'Fridays', sat: 'Saturdays', sun: 'Sundays' };

function and(t: T, xs: string[]): string {
  return xs.length < 2 ? xs.join('') : xs.slice(0, -1).join(', ') + t(' y ', ' and ') + xs[xs.length - 1];
}

/** «09:00» as a clock says it: «9:00» */
function clock(at: string): string {
  return at.replace(/^0(\d)/, '$1');
}

function localDay(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** how the routine starts, in plain words */
export function when(t: T, trigger: Trigger, now = new Date()): string {
  if ('phrase' in trigger) return t('Cuando dices “', 'When you say “') + trigger.phrase + '”';
  const at = clock(trigger.at);
  if (trigger.repeat === 'daily' || (trigger.repeat === 'days' && trigger.days?.length === 7)) return t('Todos los días a las ', 'Every day at ') + at;
  if (trigger.repeat === 'days') {
    const days = DAYS.filter((d) => trigger.days?.includes(d)).map((d) => (t.lang === 'en' ? DAY_EN : DAY_ES)[d]);
    return t('Los ', 'On ') + and(t, days) + t(' a las ', ' at ') + at;
  }
  if (!trigger.date) return t('A las ', 'At ') + at + t(', una vez', ', once');
  const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  if (trigger.date === localDay(now)) return t('Hoy a las ', 'Today at ') + at + t(', una vez', ', once');
  if (trigger.date === localDay(tomorrow)) return t('Mañana a las ', 'Tomorrow at ') + at + t(', una vez', ', once');
  const [y, m, d] = trigger.date.split('-').map(Number);
  const day = new Date(y, m - 1, d).toLocaleDateString(t.locale, { day: 'numeric', month: 'long', ...(y !== now.getFullYear() ? { year: 'numeric' } : null) });
  return t('El ', 'On ') + day + t(' a las ', ' at ') + at + t(', una vez', ', once');
}

/** what it does: the order the person saved, in their own words, or each step by the title the history's cards give
    it, or what BAXY says */
export function what(t: T, steps: Step[], titles: Map<string, string> | null, order?: string): string {
  if (order) return t('Hace lo que pediste: “', 'Does what you asked: “') + order + '”';
  return steps.map((s) => ('say' in s ? t('Dice: “', 'Says: “') + s.say + '”'
    : s.title ?? titles?.get(s.op) ?? (s.blocked === 'unknown_operation' || titles ? t('Una acción que BAXY ya no tiene', 'An action BAXY no longer has') : t('Una acción de BAXY', 'One of BAXY’s actions')))).join(' → ');
}

/** why it will not run, from what the App says today (the catalog and the tool profile); null when nothing stops it */
export function blocked(t: T, steps: Step[], shown: Shown): string | null {
  const why: string[] = [];
  for (const s of steps) {
    if ('say' in s) continue;
    const title = s.title ?? shown.titles?.get(s.op);
    // what the App said of this step is all there is to say; only an App that says nothing of it is worked out here
    const told = s.title !== undefined || s.blocked !== undefined;
    if (told ? s.blocked === 'unknown_operation' : shown.titles && title === undefined) why.push(t('un paso usa una acción que BAXY ya no tiene', 'a step uses an action BAXY no longer has'));
    else if (title !== undefined && (told ? s.blocked !== undefined : shown.on && !shown.on.has(s.op))) why.push(t('«', '“') + title + t('»', '”') + t(' está apagada en tu perfil de herramientas (Ajustes › Herramientas)', ' is off in your tool profile (Settings › Tools)'));
  }
  const once = [...new Set(why)];
  return once.length ? t('No correrá: ', 'Won’t run: ') + once.join('; ') + '.' : null;
}

export async function read(): Promise<Shown | null> {
  const [r, c, p] = await Promise.all([getJson<Routines>('/routines'), getJson<Catalog>('/catalog'), getJson<Tools>('/settings/tools')]);
  if (!r || !Array.isArray(r.routines)) return null;
  const titles = c ? new Map(c.groups.flatMap((g) => g.items.map((i) => [i.name, i.title] as const))) : null;
  return { list: r.routines, titles, on: p && Array.isArray(p.on) ? new Set(p.on) : null };
}
