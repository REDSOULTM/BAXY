import { memo, type ReactNode } from 'react';
import { Globe, Icon } from './Icon';
import type { BaxyState, Metrics } from '../types';
import { useT, type Words } from '../i18n';

/* The left rail (design chat.jsx, BxRail): privacy, power, confirmation mode, the PC's readings, the panels and the
   presentation profiles. A reading the PC did not give shows «—», never a 0. */

export type PanelId = 'sessions' | 'memory' | 'triggers' | 'catalog' | 'proposals' | 'settings';
export type Profile = 'normal' | 'novidente' | 'movilidad';

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
  ['sessions', { es: 'Sesiones', en: 'Sessions' }, <><rect x="2.5" y="3" width="11" height="10" rx="1"></rect><path d="M2.5 6h11M5 8.6h6M5 10.6h4"></path></>],
  ['memory', { es: 'Memoria', en: 'Memory' }, <><path d="M8 2.5L13.5 5.5L8 8.5L2.5 5.5Z"></path><path d="M2.5 8.3L8 11.3L13.5 8.3"></path><path d="M2.5 11L8 14L13.5 11"></path></>],
  ['triggers', { es: 'Triggers', en: 'Triggers' }, <><circle cx="8" cy="8.5" r="5"></circle><path d="M8 5.8V8.5L9.8 10M6.5 2h3"></path></>],
  ['catalog', { es: 'Capacidades', en: 'Capabilities' }, <><rect x="2.5" y="2.5" width="4.5" height="4.5" rx=".8"></rect><rect x="9" y="2.5" width="4.5" height="4.5" rx=".8"></rect><rect x="2.5" y="9" width="4.5" height="4.5" rx=".8"></rect><rect x="9" y="9" width="4.5" height="4.5" rx=".8"></rect></>],
  ['proposals', { es: 'Propuestas', en: 'Proposals' }, <><path d="M4 11V7a4 4 0 0 1 8 0v4l1.2 1.5H2.8Z"></path><path d="M6.6 14h2.8"></path></>],
];

// FT/proveedores goal, the owner's decision on the modes (2026-10-18): only the standard mode (text) is ready; the
// blind and the mobility modes are «próximamente disponible», shown so and never chosen as if they were ready.
const PROFILES: [Profile, 'person' | 'eye-off' | 'wheelchair', Words, boolean][] = [
  ['normal', 'person', { es: 'Estándar', en: 'Standard' }, true],
  ['novidente', 'eye-off', { es: 'No vidente · próximamente disponible', en: 'Blind or low vision · coming soon' }, false],
  ['movilidad', 'wheelchair', { es: 'Movilidad · próximamente disponible', en: 'Mobility · coming soon' }, false],
];

interface RailProps {
  state: BaxyState;
  powered: boolean;
  onPower: () => void;
  bypass: boolean;
  onMode: () => void;
  metrics: Metrics | null;
  net: string | null;
  /** the model behind an API that is answering, null while it is the one on this PC */
  api: string | null;
  profile: Profile;
  onProfile: (p: Profile) => void;
  counts: Record<'sessions' | 'memory' | 'triggers' | 'catalog', number | null>;
  quiet: boolean;
  onPanel: (p: PanelId) => void;
}

function fixed(v: number | null | undefined, digits: number): string | null {
  return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : null;
}

function RailView({ state, powered, onPower, bypass, onMode, metrics, net, api, profile, onProfile, counts, quiet, onPanel }: RailProps) {
  const t = useT();
  const m = metrics;
  const gauges: ['cpu' | 'gpu' | 'tmp', number | null | undefined, string, number, string][] = [
    ['cpu', m?.cpu, '%', 100, t('Procesador del PC', 'Processor')],
    ['gpu', m?.gpu, '%', 100, t('Gráfica del PC', 'Graphics card')],
    ['tmp', m?.temp, '°', 90, t('Temperatura de la gráfica', 'Graphics card temperature')],
  ];
  const vram = m?.model_vram_gb, ram = m?.model_ram_gb;
  const used = typeof vram === 'number' ? vram : null;
  const modelTip = used !== null || typeof ram === 'number'
    ? t('Modelo BAXY · vídeo ', 'BAXY model · VRAM ') + (fixed(vram, 1) ?? '—') + ' GB · RAM ' + (fixed(ram, 1) ?? '—') + t(' GB · límite 4 GB', ' GB · 4 GB limit')
    : t('Modelo BAXY · aún no se puede leer', 'BAXY model · can’t be read yet');
  return (
    <div className="bx-left">
      <div className="left-header">
        <div className="row">
          <span className="name">baxy</span>
          <button className="bx-ib plain bx-gear" onClick={() => onPanel('settings')} title={t('Ajustes', 'Settings')} aria-label={t('Ajustes', 'Settings')}><Icon name="settings" size={15} /></button>
        </div>
        <div className={'bx-priv' + (net || api ? ' out' : '')} title={api ? t('Lo que le pases a BAXY sale hacia la API de ', 'What you give BAXY goes out to the API of ') + api : net ? t('Salió a internet: ', 'Went online: ') + net : t('El modelo y tus datos se quedan en este PC', 'The model and your data stay on this PC')}>
          {api ? <><Globe s={10} /><span>{t('Modelo por API', 'Model by API')}</span></> : net ? <><Globe s={10} /><span>{t('Salió a internet', 'Went online')}</span></> : <><i></i><span>{t('Todo local', 'All local')}</span></>}
        </div>
      </div>
      <button className={'power-row' + (powered ? ' on' : ' off')} onClick={onPower} title={powered ? t('Poner en reposo', 'Put to sleep') : t('Activar', 'Wake up')}
        aria-label={state === 'booting' ? t('BAXY arrancando', 'BAXY starting') : powered ? t('BAXY activo · poner en reposo', 'BAXY active · put to sleep') : t('BAXY en reposo · activar', 'BAXY asleep · wake up')}>
        <span className="power-ic"><Icon name="power" size={15} /></span>
        <span className="power-lbl">{state === 'booting' ? t('Arrancando', 'Starting') : powered ? t('Activo', 'Active') : t('En reposo', 'Asleep')}</span>
        <span className="power-dot"></span>
      </button>
      <div className="min-block">
        <div className="sec-head"><span>{t('confirmación', 'confirmation')}</span></div>
        <button className={'bx-modebtn ' + (bypass ? 'bypass' : 'normal')} onClick={onMode} role="switch" aria-checked={bypass}
          aria-label={bypass ? t('Confirmación en Bypass: hace todo sin preguntar', 'Confirmation in Bypass: does everything without asking') : t('Confirmación Normal: pregunta antes de lo arriesgado · activar Bypass', 'Normal confirmation: asks before risky things · turn on Bypass')}
          title={bypass ? t('Bypass: hace todo sin preguntar · pulsa para volver a Normal', 'Bypass: does everything without asking · press to go back to Normal') : t('Normal: pregunta antes de lo arriesgado · pulsa para Bypass', 'Normal: asks before risky things · press for Bypass')}>
          <span className="ic"><Icon name={bypass ? 'bolt' : 'check'} size={14} /></span>
          <span className="tx"><span className="n">{bypass ? 'Bypass' : 'Normal'}</span><span className="s">{bypass ? t('Sin frenos', 'No brakes') : t('Si hay riesgo', 'When risky')}</span></span>
          <span className="sw"><i></i></span>
        </button>
      </div>
      <div className="min-block">
        <div className="sec-head"><span>{t('sistema', 'system')}</span></div>
        <div className="bx-gauges">
          {gauges.map(([k, v, u, mx, tip]) => {
            const t = fixed(v, 0);
            return <Gauge key={k} k={k} v={t ?? '—'} unit={t ? u : ''} norm={t ? Math.min(1, (v as number) / mx) : 0} hot={k === 'tmp' && t !== null && (v as number) > 76} tip={tip} />;
          })}
          <Gauge k="mdl" v={fixed(used, 1) ?? '—'} unit={used !== null ? 'gb' : ''} norm={used !== null ? used / 4 : 0} hot={used !== null && used / 4 > 0.92} tip={modelTip} />
        </div>
      </div>
      <div className="min-block bx-modblock">
        <div className="sec-head"><span>{t('paneles', 'panels')}</span></div>
        <div className="bx-mods">
          {MODS.map(([id, l, g]) => (
            <button key={id} className="bx-mod" onClick={() => onPanel(id)}>
              <span className="ic"><svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round">{g}</svg></span>
              <span className="l">{t.w(l)}</span>
              <span className={'n' + (id === 'proposals' && quiet ? ' q' : '')}>
                {id === 'proposals' ? (quiet ? t('Silencio', 'Muted') : t('Activas', 'Active')) : counts[id] ?? '—'}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className="bx-foot">
        <div className="sec-head"><span>{t('accesibilidad', 'accessibility')}</span></div>
        <div className="bx-profiles">
          {PROFILES.map(([id, ic, words, ready]) => {
            const tip = t.w(words);
            return <button key={id} className={'bx-pchip' + (profile === id ? ' on' : '') + (ready ? '' : ' soon')} data-tip={tip} title={tip}
              aria-label={tip} aria-pressed={profile === id} aria-disabled={!ready} onClick={() => { if (ready) onProfile(id); }}><Icon name={ic} size={14} /></button>;
          })}
        </div>
      </div>
    </div>
  );
}

export const Rail = memo(RailView);
