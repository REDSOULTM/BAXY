import { useEffect, useState } from 'react';
import { getJson } from '../../api';
import { useT, type T } from '../../i18n';
import { Fold } from './Fold';
import { num } from '../../numbers';

/* Settings › Modelo (owner, 2026-11-08): all the memory BAXY uses, RAM and video, piece by piece, read from the App
   (GET /metrics/breakdown, OwnMemory) every 3 s while the tab is open. A reading that could not be taken is «—». Folded by
   default with its totals as the summary (owner, 2026-11-08: «es mucha información … una flechita para desplegar»). */

interface Part { piece: string; name: string | null; ramGb: number | null; vramGb: number | null }
interface Breakdown { ramGb: number | null; vramGb: number | null; parts: Part[] }

function gb(v: number | null | undefined, locale: string): string {
  return typeof v === 'number' && Number.isFinite(v) ? num(v, locale, 1) + ' GB' : '—';
}

// INT16 (blind review): the App sums only the pieces it could read; with one «—» the total is a floor, never said as all
function total(v: number | null, parts: (number | null)[], t: T): string {
  const shown = gb(v, t.locale);
  return shown !== '—' && parts.some((p) => typeof p !== 'number') ? t('al menos ', 'at least ') + shown : shown;
}

function label(p: Part, model: string | null, t: T): string {
  switch (p.piece) {
    case 'app': return t('La App de BAXY', 'The BAXY app');
    case 'view': return t('La ventana (WebView2)', 'The window (WebView2)');
    case 'core': return t('Motor local', 'Local engine');
    case 'mind': return t('Mente y voz', 'Mind and voice');
    case 'model': return model ?? t('Modelo', 'Model');
    case 'model_aux': return t('Modelo auxiliar', 'Helper model');
    case 'ollama': return 'Ollama';
    default: return p.name ?? t('Otro', 'Other');
  }
}

export function MemoryBreakdown({ model }: { model: string | null }) {
  const t = useT();
  const [data, setData] = useState<Breakdown | null>(null);
  useEffect(() => {
    let alive = true;
    const read = () => void getJson<Breakdown>('/metrics/breakdown').then((b) => { if (alive && b?.parts) setData(b); });
    read();
    const every = setInterval(read, 3000);
    return () => { alive = false; clearInterval(every); };
  }, []);
  if (!data) return null;
  const sum = `RAM ${gb(data.ramGb, t.locale)} · VRAM ${gb(data.vramGb, t.locale)}`;
  return (
    <Fold id="memoria" title={t('Toda la memoria de BAXY', 'All the memory BAXY uses')} summary={sum}>
    <div className="bx-mem-all">
      <table>
        <thead><tr><th>{t('Pieza', 'Piece')}</th><th>RAM</th><th>{t('Memoria de vídeo', 'Video memory')}</th></tr></thead>
        <tbody>
          {data.parts.map((p, i) => <tr key={p.piece + (p.name ?? '') + i}><td>{label(p, model, t)}</td><td>{gb(p.ramGb, t.locale)}</td><td>{gb(p.vramGb, t.locale)}</td></tr>)}
        </tbody>
        <tfoot><tr><td>{t('Total', 'Total')}</td><td>{total(data.ramGb, data.parts.map((p) => p.ramGb), t)}</td><td>{total(data.vramGb, data.parts.map((p) => p.vramGb), t)}</td></tr></tfoot>
      </table>
    </div>
    </Fold>
  );
}
