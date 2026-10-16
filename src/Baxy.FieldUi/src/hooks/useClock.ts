import { useEffect, useState } from 'react';

function pad2(n: number): string {
  return n < 10 ? `0${n}` : `${n}`;
}
function nowClock(d = new Date()): string {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

export function useClock(): { clock: string } {
  const [clock, setClock] = useState(() => nowClock());
  useEffect(() => {
    const id = window.setInterval(() => setClock(nowClock()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return { clock };
}
