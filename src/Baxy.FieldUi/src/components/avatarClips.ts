import type { BaxyState } from '../types';

/* The video avatar's clip library (design v5): groups, variants per group, which group ends on the sleep pose, the
   likely next group to preload, and the group each state plays. */

export type Group = 'reposo' | 'contento' | 'escuchando' | 'pensando' | 'hablando' | 'error' | 'dormido' | 'dormirse' | 'despertar';

export const LIB: Record<Group, number> = {
  reposo: 5, contento: 5, escuchando: 5, pensando: 5, hablando: 5, error: 5, dormido: 5, dormirse: 1, despertar: 1,
};
export const SLEEP_END: Partial<Record<Group, true>> = { dormido: true, dormirse: true };
export const NEXT: Record<Group, Group[]> = {
  reposo: ['escuchando'], contento: ['escuchando'], escuchando: ['pensando'], pensando: ['hablando'], hablando: ['reposo'],
  error: ['reposo'], despertar: ['reposo'], dormido: ['despertar'], dormirse: ['despertar'],
};
export const clip = (g: Group, n: number) => `clips/${g}-${n}.mp4`;

export function groupFor(state: BaxyState, expr: string): Group {
  if (state === 'booting') return 'reposo'; // the master clip «powering up» (.s-booting), the same character from the start
  if (state === 'standby') return 'dormido';
  if (state === 'listening') return 'escuchando';
  if (state === 'thinking') return 'pensando';
  if (state === 'speaking') return 'hablando';
  if (state === 'error') return 'error';
  return expr === 'happy' ? 'contento' : 'reposo';
}
