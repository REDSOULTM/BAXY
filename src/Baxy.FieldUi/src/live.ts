/** What the screen reader's live region says now: the internet banner, else a notice, else a failure, else nothing. */
export function liveText(banner: string | null, notice: { b: string; t: string } | null, error: string | null): string {
  if (banner) return 'Salió a internet: ' + banner;
  if (notice) return notice.b + ': ' + notice.t;
  return error ?? '';
}
