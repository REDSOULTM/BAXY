import { memo, type ReactNode } from 'react';
import { Globe, Icon } from './Icon';
import type { BaxyState, Metrics } from '../types';
import { useT, type Words } from '../i18n';
import { num } from '../numbers';

/* The left rail (design chat.jsx, BxRail): privacy, power, the PC's readings, the panels and Settings. A reading the PC
   did not give shows «—», never a 0. The accessibility profiles left it too (owner, 2026-11-08): the mode and the
   profiles to come are in Settings › Accesibilidad. The confirmation mode left it (owner, 2026-11-08): Sin frenos is
   chosen in Settings › Confirmación with a second yes, and a label at the top says it while it is on. */

export type PanelId = 'sessions' | 'memory' | 'triggers' | 'catalog' | 'proposals' | 'settings';

const GLYPH: Record<'mdl' | 'cpu' | 'gpu' | 'tmp', ReactNode> = {
  mdl: <><path d="M8 1.8L13.4 4.9V11.1L8 14.2L2.6 11.1V4.9Z"></path><circle cx="8" cy="5.4" r="1"></circle><circle cx="5.4" cy="9.6" r="1"></circle><circle cx="10.6" cy="9.6" r="1"></circle><path d="M7.5 6.3L5.9 8.7M8.5 6.3L10.1 8.7M6.4 9.6H9.6"></path></>,
  cpu: <><rect x="4.5" y="4.5" width="7" height="7" rx="1"></rect><rect x="6.6" y="6.6" width="2.8" height="2.8"></rect><path d="M6 2.5v2M10 2.5v2M6 11.5v2M10 11.5v2M2.5 6h2M2.5 10h2M11.5 6h2M11.5 10h2"></path></>,
  gpu: <><rect x="2" y="4.5" width="12" height="7" rx="1"></rect><circle cx="6.3" cy="8" r="1.7"></circle><path d="M10 6.6h2M10 9.4h2M4 11.5v2M7 11.5v2"></path></>,
  tmp: <><path d="M6.6 9.4V3.6Q6.6 2.2 8 2.2Q9.4 2.2 9.4 3.6V9.4A2.9 2.9 0 1 1 6.6 9.4Z"></path><circle cx="8" cy="11.6" r="1.1" fill="currentColor" stroke="none"></circle></>,
};

function Gauge({ k, v, unit, norm, hot, tip }: { k: keyof typeof GLYPH; v: string; unit: string; norm: number; hot?: boolean; tip: string }) {
  const C = 2 * Math.PI * 13, arc = 0.78;
  const fill = Math.max(0.02, Math.min(1, norm)) * arc;
  return (
    <div className={'bx-gauge' + (hot ? ' hot' : '')} title={tip}>
      <span className="ring">
        <svg width="30" height="30" viewBox="0 0 30 30">
          <circle cx="15" cy="15" r="13" className="trk" strokeDasharray={C * arc + ' ' + C} transform="rotate(130 15 15)"></circle>
          <circle cx="15" cy="15" r="13" className="val" strokeDasharray={C * fill + ' ' + C} transform="rotate(130 15 15)"></circle>
        </svg>
        <svg className="gl" width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round">{GLYPH[k]}</svg>
      </span>
      <span className="v">{v}<span className="u">{unit}</span></span>
    </div>
  );
}

const MODS: [Exclude<PanelId, 'settings'>, Words, ReactNode][] = [
  ['sessions', { es: 'Historial', en: 'History' }, <><path d="M2.9 8a5.1 5.1 0 1 0 1.5-3.6"></path><path d="M2.6 2.7v2.4H5"></path><path d="M8 5.3V8l1.9 1.3"></path></>],
  ['memory', { es: 'Memoria', en: 'Memory' }, <><path d="M8 2.5L13.5 5.5L8 8.5L2.5 5.5Z"></path><path d="M2.5 8.3L8 11.3L13.5 8.3"></path><path d="M2.5 11L8 14L13.5 11"></path></>],
  ['triggers', { es: 'Alarmas', en: 'Alarms' }, <><circle cx="8" cy="8.5" r="5"></circle><path d="M8 5.8V8.5L9.8 10M6.5 2h3"></path></>],
  ['catalog', { es: 'Capacidades', en: 'Capabilities' }, <><rect x="2.5" y="2.5" width="4.5" height="4.5" rx=".8"></rect><rect x="9" y="2.5" width="4.5" height="4.5" rx=".8"></rect><rect x="2.5" y="9" width="4.5" height="4.5" rx=".8"></rect><rect x="9" y="9" width="4.5" height="4.5" rx=".8"></rect></>],
  ['proposals', { es: 'Propuestas', en: 'Proposals' }, <><path d="M4 11V7a4 4 0 0 1 8 0v4l1.2 1.5H2.8Z"></path><path d="M6.6 14h2.8"></path></>],
];

interface RailProps {
  state: BaxyState;
  powered: boolean;
  onPower: () => void;
  metrics: Metrics | null;
  net: string | null;
  /** the model behind an API that is answering, null while it is the one on this PC */
  api: string | null;
  /** REV_VISTA V-03: some of this conversation went to an API earlier (the host marks its turns), though none answers now */
  apiPast: boolean;
  /** another model in use (by API or Ollama's): BAXY's own holds no memory then, and its reading is not that model's */
  other?: string | null;
  /** Personalización: the PC's readings in the rail */
  gauges: boolean;
  counts: Record<'sessions' | 'memory' | 'triggers' | 'catalog', number | null>;
  quiet: boolean;
  onPanel: (p: PanelId) => void;
}

function fixed(v: number | null | undefined, digits: number, locale: string): string | null {
  return typeof v === 'number' && Number.isFinite(v) ? num(v, locale, digits) : null;
}

function RailView({ state, powered, onPower, metrics, net, api, apiPast, other, gauges: showGauges, counts, quiet, onPanel }: RailProps) {
  const t = useT();
  const locale = t.locale;
  const m = metrics;
  const gauges: ['cpu' | 'gpu' | 'tmp', number | null | undefined, string, number, string][] = [
    ['cpu', m?.cpu, '%', 100, t('Procesador del PC', 'Processor')],
    ['gpu', m?.gpu, '%', 100, t('Gráfica del PC', 'Graphics card')],
    ['tmp', m?.temp, '°', 90, t('Temperatura de la gráfica', 'Graphics card temperature')],
  ];
  const vram = m?.model_vram_gb, ram = m?.model_ram_gb;
  const used = !other && typeof vram === 'number' ? vram : null;
  const modelTip = other ? t(`Otro modelo en uso (${other}): su memoria se ve en Ajustes › Modelo`, `Another model in use (${other}): its memory shows in Settings › Model`)
    : used !== null || typeof ram === 'number'
    ? t('Modelo BAXY · vídeo ', 'BAXY model · VRAM ') + (fixed(vram, 1, t.locale) ?? '—') + ' GB · RAM ' + (fixed(ram, 1, t.locale) ?? '—') + ' GB'
    : t('Modelo BAXY · aún no se puede leer', 'BAXY model · can’t be read yet');
  return (
    <div className="bx-left">
      <div className="left-header pywebview-drag-region">
        <div className="row">
          <span className="name">baxy</span>
        </div>
        <div className={'bx-priv' + (net || api || apiPast ? ' out' : '')} title={api ? t('Lo que le pases a BAXY sale hacia la API de ', 'What you give BAXY goes out to the API of ') + api : net ? t('Salió a internet: ', 'Went online: ') + net
          : apiPast ? t('En esta conversación, lo que le pasaste mientras usabas un modelo por API salió hacia esa empresa. Ahora el modelo corre en este PC.', 'In this conversation, what you gave BAXY while you used a model by API went out to that company. The model runs on this PC now.')
            : t('El modelo y tus datos se quedan en este PC', 'The model and your data stay on this PC')}>
          {api ? <><Globe s={10} /><span>{t('Modelo por API', 'Model by API')}</span></> : net ? <><Globe s={10} /><span>{t('Salió a internet', 'Went online')}</span></>
            : apiPast ? <><Globe s={10} /><span>{t('Salió por API', 'Went out by API')}</span></> : <><i></i><span>{t('Todo local', 'All local')}</span></>}
        </div>
      </div>
      <button className={'power-row' + (powered ? ' on' : ' off')} onClick={onPower} title={powered ? t('Poner en reposo', 'Put to sleep') : t('Activar', 'Wake up')}
        aria-label={state === 'booting' ? t('BAXY arrancando', 'BAXY starting') : powered ? t('BAXY activo · poner en reposo', 'BAXY active · put to sleep') : t('BAXY en reposo · activar', 'BAXY asleep · wake up')}>
        <span className="power-ic"><Icon name="power" size={15} /></span>
        <span className="power-lbl">{state === 'booting' ? t('Arrancando', 'Starting') : powered ? t('Activo', 'Active') : t('En reposo', 'Asleep')}</span>
        <span className="power-dot"></span>
      </button>
      {showGauges ? <div className="min-block">
        <div className="sec-head"><span>{t('sistema', 'system')}</span></div>
        <div className="bx-gauges">
          {gauges.map(([k, v, u, mx, tip]) => {
            const t = fixed(v, 0, locale);
            return <Gauge key={k} k={k} v={t ?? '—'} unit={t ? u : ''} norm={t ? Math.min(1, (v as number) / mx) : 0} hot={k === 'tmp' && t !== null && (v as number) > 76} tip={tip} />;
          })}
          <Gauge k="mdl" v={fixed(used, 1, t.locale) ?? '—'} unit={used !== null ? 'gb' : ''} norm={used !== null ? Math.min(1, used / 6) : 0} tip={modelTip} />
        </div>
      </div> : null}
      <div className="min-block bx-modblock">
        <div className="sec-head"><span>{t('paneles', 'panels')}</span></div>
        <div className="bx-mods">
          {MODS.map(([id, l, g]) => (
            <button key={id} className="bx-mod" onClick={() => onPanel(id)}>
              <span className="ic"><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{g}</svg></span>
              <span className="l">{t.w(l)}</span>
              <span className={'n' + (id === 'proposals' && quiet ? ' q' : '')}>
                {id === 'proposals' ? (quiet ? t('Silencio', 'Muted') : t('Activas', 'Active')) : counts[id] ?? '—'}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className="bx-foot">
        {/* owner, 2026-11-08: the rail's content as before with the v5 buttons; Settings is a labelled button at its foot */}
        <button className="bx-mod bx-gear" onClick={() => onPanel('settings')} aria-label={t('Ajustes', 'Settings')}>
          <span className="ic"><Icon name="settings" size={16} /></span>
          <span className="l">{t('Ajustes', 'Settings')}</span>
        </button>
      </div>
    </div>
  );
}

export const Rail = memo(RailView);
