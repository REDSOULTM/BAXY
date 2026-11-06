import type { T } from './i18n';

/** A span the host gave in seconds, said in the view's language («2 minutos», «1 minuto», «45 segundos»; "2 minutes"); «—»
 *  when unknown. */
export function spoken(seconds: number | null | undefined, t: T): string {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds <= 0) return '—';
  if (seconds % 60 === 0) {
    const m = seconds / 60;
    return m === 1 ? t('1 minuto', '1 minute') : m + t(' minutos', ' minutes');
  }
  return Math.round(seconds) + t(' segundos', ' seconds');
}
