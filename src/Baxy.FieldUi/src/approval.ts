import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react';

/* OVL1: when the button that authorizes an effect (a card's Sí) takes a press: the overlay's rule (Baxy.App,
   ApprovalGuard.cs), for the conversation's card. A press counts only if the person made it after the Sí was drawn
   lit, and the Sí is drawn lit only once it has been in its place, drawn off, for the whole wait. When the person
   pressed is the event's own time (Event.timeStamp), never when the view got round to handling it: with the thread
   busy, a click meant for what was there before is handled late enough to pass any wait counted from the handler
   (Mozilla, MFSA 2023-20, CVE-2023-34414: «click-jacking … through rendering lag»; Chromium compares the event's
   time stamp too, ui/views/input_event_activation_protector.cc). No and Esc are never held. */

/** One second, as Firefox holds the buttons of its security dialogs (security.dialog_enable_delay = 1000 ms,
 *  modules/libpref/init/all.js): twice Windows' stock double-click time, the measure Chromium uses. */
export const WAIT = 1000;

export class ApprovalGuard {
  private placed: number | null = null;
  private armed: number | null = null;
  lit = false;

  /** the button is another one, moved, changed size, came back to view or was pressed too soon. */
  restart(): void { this.placed = null; this.armed = null; this.lit = false; }
  /** the button was drawn in its place, off. */
  place(now: number): void { this.placed ??= now; }
  /** milliseconds until it may be lit; null while it is not drawn in its place, or already lit. */
  left(now: number): number | null { return this.lit || this.placed === null ? null : Math.max(0, this.placed + WAIT - now); }
  /** lights the button if its wait is over; says whether it is lit. */
  light(now: number): boolean { if (this.left(now) === 0) this.lit = true; return this.lit; }
  /** the lit button was drawn. */
  arm(now: number): void { if (this.lit) this.armed ??= now; }
  /** whether a press made at that time counts. */
  takes(pressedAt: number): boolean { return this.armed !== null && pressedAt >= this.armed; }
}

// Since when the keys are the view's: a key typed for another window as this one takes the keyboard is not an answer
// (Firefox starts its dialogs' wait again when their window takes the focus: EnableDelayHelper, PromptUtils.sys.mjs).
// The Sí itself is off while the view does not have the focus, and its wait starts again when it takes it (inReach).
let keysSince: number | null = typeof document !== 'undefined' && document.hasFocus() ? -WAIT : null;
if (typeof window !== 'undefined') {
  window.addEventListener('focus', () => { keysSince = performance.now(); });
  window.addEventListener('blur', () => { keysSince = null; });
}

/** milliseconds until the keyboard is taken; null while the view does not have it. */
function keysLeft(now: number): number | null {
  return keysSince === null ? null : Math.max(0, keysSince + WAIT - now);
}

/** whether a key pressed then is the person's answer as far as the keyboard goes: not one still held from before (its
 *  repeats began before the wait: Chromium blocks them for that), and the view has had the keyboard for the wait. */
function keyCounts(e: { timeStamp: number; repeat: boolean }): boolean {
  return !e.repeat && keysLeft(e.timeStamp) === 0;
}

// The cards that wait with a Sí, by id: Enter is that button's key (it says so), and answers only when the button
// would: on the screen, where a press would reach it, and taking presses.
const drawn = new Map<string, (e: KeyboardEvent) => boolean>();

/** whether this Enter approves that card: only through a Sí that is on the screen and takes it. */
export function enterApproves(card: string, e: KeyboardEvent): boolean {
  return drawn.get(card)?.(e) ?? false;
}

/** whether a press on the middle of the button would reach it: on the screen, not hidden, nothing over it. */
function onScreen(b: HTMLElement): boolean {
  const r = b.getBoundingClientRect();
  const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return hit !== null && b.contains(hit);
}

/** whether a press on the button would be the person's, made for it: on the screen, and in a window that has the
 *  focus. A window without it may be under another one, and the click that brings it up was meant for something else
 *  (Firefox keeps its dialogs' buttons off while their window does not have the focus: EnableDelayHelper). */
function inReach(b: HTMLElement): boolean {
  return document.hasFocus() && onScreen(b);
}

/** runs once the frame being drawn now is on the screen; returns how to call it off. */
function painted(then: () => void): () => void {
  let frame = requestAnimationFrame(() => { frame = requestAnimationFrame(then); });
  return () => cancelAnimationFrame(frame);
}

export interface Approval {
  /** the Sí is to look ready. */
  lit: boolean;
  /** it has been drawn so: it takes the presses made from now on. */
  armed: boolean;
  /** the keyboard would be taken too. */
  keys: boolean;
  /** the mouse, a finger or a pen went down on the Sí. */
  down: (e: { timeStamp: number }) => void;
  /** a key went down on the focused Sí. */
  key: (e: { key: string; timeStamp: number; repeat: boolean }) => void;
  /** the Sí was clicked: whether that click approves. */
  click: (e: { timeStamp: number }) => boolean;
}

/** The Sí `el` of the card `card`, which asks for `asks`, while it waits for the person (`live`). */
export function useApproval(card: string, asks: string, live: boolean, el: RefObject<HTMLButtonElement | null>): Approval {
  const guard = useRef<ApprovalGuard | null>(null);
  const pressed = useRef<number | null>(null);
  const where = useRef('');
  const seen = useRef(false);
  // which drawing of the Sí is the one that counts: what an earlier one was waiting for no longer does
  const drawing = useRef(0);
  const [look, setLook] = useState({ lit: false, armed: false, n: 0 });
  const [keys, setKeys] = useState(() => keysLeft(performance.now()) === 0);

  const off = useCallback(() => {
    guard.current?.restart();
    drawing.current++;
    setLook((l) => ({ lit: false, armed: false, n: l.n + 1 }));
  }, []);

  // the same card asking for something else is another confirmation: off before it is drawn, a Sí meant for the one
  // before must not approve it
  const asked = useRef(asks);
  useLayoutEffect(() => {
    if (asked.current === asks) return;
    asked.current = asks;
    off();
  }, [asks, off]);

  // drawn off: its wait starts once that is on the screen (never while the Sí itself is not: folded away, scrolled
  // out, under something, in a window without the focus), and it is lit when the wait is over
  useEffect(() => {
    if (!live || look.lit) return;
    const g = guard.current ??= new ApprovalGuard();
    const mine = drawing.current;
    let timer = 0;
    const due = () => {
      const left = g.left(performance.now());
      if (left === 0) { g.light(performance.now()); setLook((l) => ({ ...l, lit: true })); }
      else if (left !== null) timer = window.setTimeout(due, left);
    };
    const cancel = painted(() => {
      if (drawing.current === mine && el.current && inReach(el.current)) { g.place(performance.now()); due(); }
    });
    return () => { cancel(); window.clearTimeout(timer); };
  }, [live, look, el]);

  // drawn lit: it takes the presses made from then on
  useEffect(() => {
    if (!live || !look.lit || look.armed) return;
    const mine = drawing.current;
    return painted(() => {
      if (drawing.current !== mine) return;
      guard.current?.arm(performance.now());
      setLook((l) => ({ ...l, armed: l.lit }));
    });
  }, [live, look]);

  // whether the Sí is not where it was, or not the size it was, or is in reach when it was not, since last looked at
  const moved = useCallback(() => {
    const b = el.current?.getBoundingClientRect();
    if (!b || !el.current) return false;
    seen.current = inReach(el.current);
    const now = [window.screenX, window.screenY, b.left, b.top, b.width, b.height].map((v) => Math.round(v * 2)).join(' ') + (seen.current ? '' : ' unseen');
    const did = where.current !== '' && now !== where.current;
    where.current = now;
    return did;
  }, [el]);

  // a Sí that moved, changed size or is seen again, or a view that is or that took or lost the focus, starts the wait
  // again (Chromium's WindowsStationarityMonitor; Firefox's PopupNotifications on «popuppositioned» and its
  // EnableDelayHelper on focus and blur): looked at on every frame
  useEffect(() => {
    if (!live) return;
    let frame = 0;
    const watch = () => {
      if (moved()) off();
      frame = requestAnimationFrame(watch);
    };
    frame = requestAnimationFrame(watch);
    const seen = () => { if (document.visibilityState === 'visible') off(); };
    // a press let go off the Sí clicks nothing: it is not the press of a later click (the click comes before this)
    const up = () => { window.setTimeout(() => { pressed.current = null; }, 0); };
    document.addEventListener('visibilitychange', seen);
    window.addEventListener('focus', off);
    window.addEventListener('blur', off);
    window.addEventListener('pointerup', up, true);
    window.addEventListener('pointercancel', up, true);
    return () => {
      cancelAnimationFrame(frame);
      // no longer waiting for the person: were it ever to wait again, its wait would be a new one
      off();
      where.current = '';
      document.removeEventListener('visibilitychange', seen);
      window.removeEventListener('focus', off);
      window.removeEventListener('blur', off);
      window.removeEventListener('pointerup', up, true);
      window.removeEventListener('pointercancel', up, true);
    };
  }, [live, off, moved]);

  // the Sí's Enter hint says whether the keyboard would be taken
  useEffect(() => {
    if (!live) return;
    let timer = 0;
    const tell = () => {
      window.clearTimeout(timer);
      const left = keysLeft(performance.now());
      setKeys(left === 0);
      if (left) timer = window.setTimeout(tell, left);
    };
    const left = keysLeft(performance.now());
    if (left) timer = window.setTimeout(tell, left);
    window.addEventListener('focus', tell);
    window.addEventListener('blur', tell);
    return () => { window.clearTimeout(timer); window.removeEventListener('focus', tell); window.removeEventListener('blur', tell); };
  }, [live]);

  // a press that came too soon starts the wait again (Firefox pushes its time forward on an early click), and so does
  // one that finds the Sí moved since the last frame looked, or out of reach
  const takes = useCallback((at: number) => {
    if (!moved() && seen.current && guard.current?.takes(at)) return true;
    off();
    return false;
  }, [moved, off]);

  useEffect(() => {
    if (!live) return;
    const enter = (e: KeyboardEvent) => takes(keyCounts(e) ? e.timeStamp : -Infinity);
    drawn.set(card, enter);
    return () => { if (drawn.get(card) === enter) drawn.delete(card); };
  }, [card, live, takes]);

  const down = useCallback((e: { timeStamp: number }) => {
    pressed.current = e.timeStamp;
    takes(e.timeStamp);
  }, [takes]);
  const key = useCallback((e: { key: string; timeStamp: number; repeat: boolean }) => {
    if (e.key === 'Enter' || e.key === ' ') pressed.current = keyCounts(e) ? e.timeStamp : -Infinity;
  }, []);
  // by the press that began it or, with none (an assistive tool), now
  const click = useCallback((e: { timeStamp: number }) => {
    const at = pressed.current ?? e.timeStamp;
    pressed.current = null;
    return takes(at);
  }, [takes]);

  return { lit: live && look.lit, armed: live && look.armed, keys, down, key, click };
}
