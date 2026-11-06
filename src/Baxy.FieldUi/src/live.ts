import { translator, type T } from './i18n';

/** What the screen reader's live region says now: the internet banner, else a notice, else a failure, else nothing. */
export function liveText(banner: string | null, notice: { b: string; t: string } | null, error: string | null, t: T = translator('es')): string {
  if (banner) return t('Salió a internet: ', 'Went online: ') + banner;
  if (notice) return notice.b + ': ' + notice.t;
  return error ?? '';
}
