/* Settings › Personalización (owner, 2026-11-08): how this view looks to the person, kept in this view only
   (localStorage), never sent to the host and never something BAXY can or cannot do. */

export interface Look {
  /** the size of BAXY's replies in the conversation */
  reply: 'm' | 'l' | 'xl';
  /** the size of the person's own messages */
  you: 's' | 'm';
  /** the conversation's width: narrow is the one it always had */
  chat: 'n' | 'm' | 'w';
  /** «Cómo lo comprobé» open on every reply, not only while a step runs or after one failed */
  steps: boolean;
  /** BAXY's words also as captions under the face */
  captions: boolean;
  /** the PC's readings in the rail */
  gauges: boolean;
  /** the coloured light round the window's border: running, still or off */
  ring: 'on' | 'still' | 'off';
  /** how fast it runs */
  ringSpeed: 'slow' | 'normal' | 'fast';
}

export const LOOK_DEFAULT: Look = { reply: 'm', you: 's', chat: 'n', steps: false, captions: true, gauges: true, ring: 'on', ringSpeed: 'normal' };

export const CHAT_WIDTH: Record<Look['chat'], number> = { n: 330, m: 390, w: 450 };
export const REPLY_PX: Record<Look['reply'], number> = { m: 14.5, l: 16, xl: 18 };
export const RING_SPEED: Record<Look['ringSpeed'], number> = { slow: 0.5, normal: 1, fast: 1.8 };
export const YOU_PX: Record<Look['you'], number> = { s: 12.5, m: 14 };

const KEY = 'baxy.look';

function one<T>(v: unknown, allowed: readonly T[], fallback: T): T {
  return allowed.includes(v as T) ? (v as T) : fallback;
}

/** the look kept last time; a value that is missing or not one of the choices falls back to its default */
export function readLook(): Look {
  let kept: Partial<Record<keyof Look, unknown>> = {};
  try { kept = JSON.parse(localStorage.getItem(KEY) ?? '{}') ?? {}; } catch { /* nothing kept */ }
  const d = LOOK_DEFAULT;
  return {
    reply: one(kept.reply, ['m', 'l', 'xl'] as const, d.reply),
    you: one(kept.you, ['s', 'm'] as const, d.you),
    chat: one(kept.chat, ['n', 'm', 'w'] as const, d.chat),
    steps: one(kept.steps, [true, false] as const, d.steps),
    captions: one(kept.captions, [true, false] as const, d.captions),
    gauges: one(kept.gauges, [true, false] as const, d.gauges),
    ring: one(kept.ring, ['on', 'still', 'off'] as const, d.ring),
    ringSpeed: one(kept.ringSpeed, ['slow', 'normal', 'fast'] as const, d.ringSpeed),
  };
}

export function keepLook(look: Look): void {
  try { localStorage.setItem(KEY, JSON.stringify(look)); } catch { /* presentation only */ }
}
