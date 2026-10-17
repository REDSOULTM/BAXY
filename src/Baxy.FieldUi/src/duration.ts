/** A span the host gave in seconds, said in Spanish («2 minutos», «1 minuto», «45 segundos»); «—» when unknown. */
export function spoken(seconds: number | null | undefined): string {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds <= 0) return '—';
  if (seconds % 60 === 0) {
    const m = seconds / 60;
    return m === 1 ? '1 minuto' : m + ' minutos';
  }
  return Math.round(seconds) + ' segundos';
}
