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

/* Lip-sync (owner, 2026-10-21): the speaking clips move their mouth on their own and close it while the voice goes on
   (hablando-5 keeps it closed its last 2 s). The view opens a soft hole in the video where the mouth is (v4.css
   `.bx-avid.lip video`) and draws there one of these mouths, chosen by the voice's loudness (lip.ts). They are cut from
   the clips themselves when the view starts (mouths.ts), with the view's own decoder, so they match the clip exactly:
   the head does not move, the mouth is always in this box of the 960 px master frame (the blushes start at x <= 370
   and x >= 590; the visor's rim glow below y 660). */
export const MOUTH_BOX = { x: 380, y: 522, w: 196, h: 136, frame: 960, fps: 24, featherX: 12, featherY: 10 };
/** [clip, frame] per level of openness: closed smile, small, half open, open, wide, widest */
export const MOUTHS: [string, number][][] = [
  [['hablando-3', 0], ['hablando-1', 11]],
  [['hablando-2', 20], ['hablando-2', 19], ['hablando-3', 18]],
  [['hablando-2', 55], ['hablando-2', 3], ['hablando-2', 4]],
  [['hablando-3', 21], ['hablando-1', 10], ['hablando-3', 27], ['hablando-2', 88]],
  [['hablando-1', 9], ['hablando-3', 22], ['hablando-1', 0], ['hablando-2', 0]],
  [['hablando-3', 23], ['hablando-1', 71], ['hablando-2', 6], ['hablando-3', 24], ['hablando-2', 7]],
];
export const MOUTH_LEVELS = MOUTHS.map((level) => level.length);
/** the loudness (0..1) from which each level is shown */
export const MOUTH_AT = [0, 0.15, 0.35, 0.5, 0.65, 0.8];

export function mouthLevel(level: number): number {
  let k = 0;
  for (let i = 0; i < MOUTH_AT.length; i++) if (level >= MOUTH_AT[i]) k = i;
  return k;
}
