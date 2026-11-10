import type { KeyboardEvent } from 'react';

/* The arrows of a radio group (role=radiogroup of role=radio buttons). REV_VISTA V-12 (2026-11-09): the cards took no arrows.
   WAI-ARIA APG radio group (https://www.w3.org/WAI/ARIA/apg/patterns/radio/): Right/Down go to the next radio and Left/Up to
   the previous one, round at the ends; Tab enters on the checked one (tabIndex 0 on it, or on the first, -1 on the others: the
   caller's roving tabindex, rovingIndex). `select`: the arrow checks the radio it reaches, as APG says; false for a choice that
   does something costly at once (which model BAXY thinks with, a tool profile that restarts it): the arrow only moves, and Space
   or Enter checks, as APG's radio group inside a toolbar does. */
export function radioKeys(select: boolean) {
  return (e: KeyboardEvent<HTMLElement>) => {
    const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
    if (!step) return;
    const radios = [...e.currentTarget.querySelectorAll<HTMLElement>('[role="radio"]:not([disabled])')];
    const at = radios.indexOf(document.activeElement as HTMLElement);
    if (at < 0) return;
    e.preventDefault();
    const next = radios[(at + step + radios.length) % radios.length];
    next.focus();
    if (select) next.click();
  };
}

/** the tabIndex of radio `i` of a group whose checked one is `checked` (-1: none): 0 on the checked, or on the first */
export function rovingIndex(i: number, checked: number): 0 | -1 {
  return i === (checked < 0 ? 0 : checked) ? 0 : -1;
}

/** The keys of a vertical tab list (Settings' sections). REV_VISTA V-12: they were buttons with aria-pressed. WAI-ARIA APG
 *  tabs (https://www.w3.org/WAI/ARIA/apg/patterns/tabs/): Down/Right the next tab and Up/Left the previous one, round at the
 *  ends, Home the first and End the last; the tab reached is shown at once (automatic activation: a section is drawn with no
 *  wait). Roving tabindex is the caller's (rovingIndex). */
export function tabKeys(e: KeyboardEvent<HTMLElement>) {
  const tabs = [...e.currentTarget.querySelectorAll<HTMLElement>('[role="tab"]')];
  const at = tabs.indexOf(document.activeElement as HTMLElement);
  if (at < 0) return;
  const to = e.key === 'ArrowDown' || e.key === 'ArrowRight' ? (at + 1) % tabs.length
    : e.key === 'ArrowUp' || e.key === 'ArrowLeft' ? (at - 1 + tabs.length) % tabs.length
      : e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : -1;
  if (to < 0) return;
  e.preventDefault();
  tabs[to].focus();
  tabs[to].click();
}
