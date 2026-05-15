import { useEffect, useState } from 'react';

const DOWS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'] as const;
const MOS = [
  'jan', 'feb', 'mar', 'apr', 'may', 'jun',
  'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
] as const;

function pad2(n: number): string {
  return n < 10 ? `0${n}` : `${n}`;
}
function nowClock(d = new Date()): string {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}
function nowDate(d = new Date()): string {
  return `${DOWS[d.getDay()]} ${pad2(d.getDate())} ${MOS[d.getMonth()]}`;
}

export function useClock(): { clock: string; date: string } {
  const [clock, setClock] = useState(() => nowClock());
  const [date, setDate] = useState(() => nowDate());
  useEffect(() => {
    const id = window.setInterval(() => {
      const d = new Date();
      setClock(nowClock(d));
      setDate(nowDate(d));
    }, 1000);
    return () => window.clearInterval(id);
  }, []);
  return { clock, date };
}
