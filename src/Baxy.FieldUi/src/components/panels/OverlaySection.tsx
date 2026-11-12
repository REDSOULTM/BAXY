import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Seg, Toggle } from '../Panel';
import { getJson, send, sendTold } from '../../api';
import { useT } from '../../i18n';
import { radioKeys, rovingIndex } from '../../utils/radioKeys';

/* Settings › Personalización › Overlay (owner, 2026-11-08; design: artifact «BAXY interfaz v5», board 12). The overlay is
   the App's own window (OverlayPresenter): what BAXY does, in a corner, while BAXY is behind. Its settings are the
   host's (GET/PUT /settings/overlay); «Probar» shows it for a few seconds (POST /settings/overlay/preview). */

interface Overlay { unsaved?: boolean; on: boolean; corner: 'tl' | 'tr' | 'bl' | 'br'; size: 's' | 'm' | 'l'; opacity: number; hideSeconds: number; notFullscreen: boolean; answer: boolean }

function Row({ label, hint, children }: { label: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="bxs-row">
      <div className="bxs-l"><span>{label}</span>{hint ? <span className="h">{hint}</span> : null}</div>
      <div className="bxs-c">{children}</div>
    </div>
  );
}

export function OverlaySection() {
  const t = useT();
  const [o, setO] = useState<Overlay | null>(null);
  // the last the host said it has: `o` also holds a press not answered yet and the slider while it is dragged
  const host = useRef<Overlay | null>(null);
  // a change not kept: the host refused it or has something else ('refused'), or it said nothing at all, not even what
  // it has ('silent')
  const [unsaved, setUnsaved] = useState<'refused' | 'silent' | null>(null);
  useEffect(() => { void getJson<Overlay>('/settings/overlay').then((v) => { if (v && typeof v.on === 'boolean') { host.current = v; setO(v); } }); }, []);
  if (!o) return null;
  const change = async (patch: Partial<Overlay>) => {
    setO({ ...o, ...patch });
    const told = await sendTold<Overlay>('PUT', '/settings/overlay', patch);
    let kept = told.value;
    let saved = !!kept && typeof kept.on === 'boolean';
    if (!saved) {
      // VIS1: refused, or no answer (field-native-bridge.js answers 503 when the host takes too long, and the host may
      // still have taken it). What shows is what the host has, asked again; if it doesn't say, the last it said.
      kept = await getJson<Overlay>('/settings/overlay');
      const now = kept && typeof kept.on === 'boolean' ? kept : null;
      saved = !!now && (Object.keys(patch) as (keyof Overlay)[]).every((k) => now[k] === patch[k]);
      kept = now;
    }
    if (kept) host.current = kept;
    if (host.current) setO(host.current);
    setUnsaved(saved ? null : kept || told.refused ? 'refused' : 'silent');
  };
  const corners: [Overlay['corner'], string][] = [
    ['tl', t('Arriba a la izquierda', 'Top left')], ['tr', t('Arriba a la derecha', 'Top right')],
    ['bl', t('Abajo a la izquierda', 'Bottom left')], ['br', t('Abajo a la derecha', 'Bottom right')],
  ];
  const where = corners.find(([c]) => c === o.corner)?.[1] ?? '';
  return (
    <>
      {o.unsaved ? <div className="bx-mem-empty" role="status">{t('No pude guardar este cambio en el disco. Vale mientras BAXY siga abierta y lo intento de nuevo con cada cambio; si cierras BAXY antes, vuelve lo de antes.', 'I couldn’t save this change to disk. It holds while BAXY stays open and I try again with each change; if you close BAXY first, the old setting comes back.')}</div> : null}
      <div className="st-tip" style={{ marginTop: 6 }}>{t('Lo que BAXY hace, en una esquina, cuando su ventana no está al frente. No roba el foco ni el teclado; un clic trae a BAXY.', 'What BAXY does, in a corner, when its window isn’t in front. It never takes the focus or the keyboard; a click brings BAXY back.')}</div>
      {unsaved ? <div className="st-tip" role="alert">{unsaved === 'refused' ? t('No se pudo guardar: se muestra lo que BAXY tiene.', 'Couldn’t save it: this shows what BAXY has.')
        : t('BAXY no contestó: no se sabe si se guardó. Se muestra lo último que dijo.', 'BAXY didn’t answer: it isn’t known whether it was saved. This shows the last it said.')}</div> : null}
      <Row label={t('Mostrar el overlay', 'Show the overlay')}>
        <Toggle on={o.on} label={t('Mostrar el overlay', 'Show the overlay')} onChange={(v) => void change({ on: v })} />
      </Row>
      <Row label={t('Esquina', 'Corner')} hint={where}>
        <div className="bx-corners" role="radiogroup" aria-label={t('Esquina del overlay', 'Overlay corner')} onKeyDown={radioKeys(true)}>
          {corners.map(([c, l], i) => <button key={c} className={'c-' + c + (o.corner === c ? ' on' : '')} role="radio" aria-checked={o.corner === c} aria-label={l}
            tabIndex={rovingIndex(i, corners.findIndex(([x]) => x === o.corner))} title={l} onClick={() => void change({ corner: c })}></button>)}
        </div>
      </Row>
      <Row label={t('Tamaño', 'Size')}>
        <Seg label={t('Tamaño del overlay', 'Overlay size')} value={o.size} onChange={(v) => void change({ size: v })}
          options={[['s', t('Compacto', 'Compact')], ['m', t('Normal', 'Normal')], ['l', t('Grande', 'Large')]]} />
      </Row>
      <Row label={t('Opacidad', 'Opacity')} hint={o.opacity + ' %'}>
        <input className="bx-range" type="range" min={40} max={100} step={2} value={o.opacity} aria-label={t('Opacidad del overlay', 'Overlay opacity')}
          onChange={(e) => setO({ ...o, opacity: Number(e.target.value) })} onPointerUp={(e) => void change({ opacity: Number((e.target as HTMLInputElement).value) })}
          onKeyUp={(e) => void change({ opacity: Number((e.target as HTMLInputElement).value) })} />
      </Row>
      <Row label={t('Ocultar al terminar', 'Hide when done')} hint={t('Si algo falla, se queda 20 s', 'If something fails, it stays 20 s')}>
        <Seg label={t('Ocultar al terminar', 'Hide when done')} value={String(o.hideSeconds) as '5' | '8' | '15' | '0'} onChange={(v) => void change({ hideSeconds: Number(v) })}
          options={[['5', '5 s'], ['8', '8 s'], ['15', '15 s'], ['0', t('Nunca', 'Never')]]} />
      </Row>
      <Row label={t('No mostrar en pantalla completa', 'Not over full screen')} hint={t('Juegos y vídeos a pantalla completa quedan limpios', 'Full-screen games and videos stay clean')}>
        <Toggle on={o.notFullscreen} label={t('No mostrar en pantalla completa', 'Not over full screen')} onChange={(v) => void change({ notFullscreen: v })} />
      </Row>
      <Row label={t('Responder confirmaciones desde el overlay', 'Answer confirmations from the overlay')} hint={t('Si no, dice que espera tu sí y un clic te lleva a BAXY', 'Otherwise it says it’s waiting and a click takes you to BAXY')}>
        <Toggle on={o.answer} label={t('Responder confirmaciones desde el overlay', 'Answer confirmations from the overlay')} onChange={(v) => void change({ answer: v })} />
      </Row>
      <div style={{ marginTop: 10 }}><button className="panel-btn ghost" aria-label={t('Probar el overlay', 'Try the overlay')} onClick={() => void send('POST', '/settings/overlay/preview')}>{t('Probar', 'Try it')}</button></div>
    </>
  );
}
