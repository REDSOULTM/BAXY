import { useT } from '../../i18n';
import { GIB, size } from '../../size';
import { num } from '../../numbers';

/* A download in Settings (Ollama itself, or a model Ollama pulls): how much of it is here as a bar and a percentage, how
   fast it goes and how long it has left (OpenModels in the App, DownloadRate), and the button that stops it or, once it
   stopped, goes on from where it was. Owner, 2026-11-08: «un porcentaje de descarga que se vea bonito, que yo pueda ver,
   ah, se está descargando». */
export function DownloadBar({ what, done, total, bytesPerSecond, secondsLeft, stopped, onStop, onResume }: {
  what: string;
  done: number;
  total: number;
  bytesPerSecond?: number | null;
  secondsLeft?: number | null;
  stopped?: boolean;
  onStop?: () => void;
  onResume?: () => void;
}) {
  const t = useT();
  const gb = (bytes: number) => size(bytes, t.locale, 2);
  // Never 100 % before it ends: the last bytes still have to arrive and be checked.
  const percent = total > 0 ? Math.min(Math.floor((done / total) * 100), done >= total ? 100 : 99) : 0;
  // REV_APP DL-d / REV_VISTA V-13: in the unit of the sizes beside it (size.ts: 2³⁰ bytes written «GB», so 2²⁰ written «MB»);
  // in 10⁶ the speed and the sizes of one bar differed by 7 %.
  const speed = bytesPerSecond != null ? num(bytesPerSecond / (GIB / 1024), t.locale, 0, 1) + ' MB/s' : '';
  const left = (seconds: number) => seconds < 60 ? t(`quedan ${seconds} s`, `${seconds} s left`)
    : seconds < 3600 ? t(`quedan ${Math.ceil(seconds / 60)} min`, `${Math.ceil(seconds / 60)} min left`)
      : t(`quedan ${Math.floor(seconds / 3600)} h ${Math.ceil((seconds % 3600) / 60)} min`, `${Math.floor(seconds / 3600)} h ${Math.ceil((seconds % 3600) / 60)} min left`);
  const details = [
    total > 0 ? t(`${gb(done)} de ${gb(total)}`, `${gb(done)} of ${gb(total)}`) : t('Empezando…', 'Starting…'),
    stopped ? t('detenida: sigue desde aquí', 'stopped: it goes on from here') : speed,
    !stopped && secondsLeft != null && secondsLeft > 0 ? left(secondsLeft) : '',
  ].filter(Boolean).join(' · ');
  return (
    <div className="dl" role="group" aria-label={t(`Descarga de ${what}`, `Download of ${what}`)}>
      <div className="dl-head">
        <span className="dl-what">{stopped ? t('Descarga detenida: ', 'Download stopped: ') : t('Descargando ', 'Downloading ')}{what}</span>
        <span className="dl-percent" aria-hidden="true">{percent} %</span>
      </div>
      <div className="dl-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}
        aria-valuetext={t(`${percent} por ciento. ${details}`, `${percent} percent. ${details}`)} aria-label={t('Avance', 'Progress')}>
        <div className={stopped ? 'dl-fill stopped' : 'dl-fill'} style={{ width: `${percent}%` }} />
      </div>
      <div className="dl-foot">
        <span className="dl-details">{details}</span>
        {stopped
          ? (onResume ? <button className="panel-btn" onClick={onResume}>{t('Reanudar', 'Resume')}</button> : null)
          : (onStop ? <button className="panel-btn ghost" onClick={onStop}>{t('Detener', 'Stop')}</button> : null)}
      </div>
    </div>
  );
}
