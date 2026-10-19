import { useEffect, useState, type ReactNode } from 'react';
import { Icon, Globe } from '../Icon';
import { Seg, Toggle } from '../Panel';
import { getJson } from '../../api';
import { spoken } from '../../duration';
import type { GeneralSettings, Metrics, MicMode, NetEntry } from '../../types';

/* Settings (design settings.jsx BxSettings). The theme, text size and contrast are this view's own presentation; the
   rest is the host's (GET/PUT /settings/general, /confirmation, /accessibility) and changes what BAXY does. */

const TABS: [Tab, string][] = [
  ['general', 'General'], ['confirmacion', 'Confirmación'], ['voz', 'Voz'], ['accesibilidad', 'Accesibilidad'], ['privacidad', 'Privacidad'], ['modelo', 'Modelo'],
];
type Tab = 'general' | 'confirmacion' | 'voz' | 'accesibilidad' | 'privacidad' | 'modelo';

export interface A11y { on: boolean; size: 'm' | 'l' | 'xl'; contrast: boolean }

function Row({ label, hint, children, ro }: { label: string; hint?: string; children?: ReactNode; ro?: boolean }) {
  return (
    <div className="bxs-row">
      <div className="bxs-l"><span>{label}{ro ? <em className="ro">solo lectura</em> : null}</span>{hint ? <span className="h">{hint}</span> : null}</div>
      <div className="bxs-c">{children}</div>
    </div>
  );
}

function Bar({ label, v, max, unit }: { label: string; v: number | null | undefined; max: number; unit: string }) {
  const known = typeof v === 'number' && Number.isFinite(v);
  return (
    <div className="bx-res">
      <div className="h"><span className="k">{label}</span><span className="v">{known ? v.toFixed(1) : '—'}<span className="u"> / {max} {unit}</span></span></div>
      <div className={'b' + (known && v / max > 0.9 ? ' hot' : '')}><span style={{ width: known ? Math.min(100, (v / max) * 100) + '%' : '0%' }}></span></div>
    </div>
  );
}

interface Props {
  onClose: () => void;
  theme: 'dark' | 'light';
  onTheme: (t: 'dark' | 'light') => void;
  bypass: boolean;
  onBypass: (v: boolean) => void;
  mic: MicMode;
  micAvailable: boolean;
  onMic: (m: MicMode) => void;
  a11y: A11y;
  onA11y: (a: A11y) => void;
  general: GeneralSettings | null;
  onGeneral: (patch: Partial<GeneralSettings>) => void;
  metrics: Metrics | null;
  netLog: NetEntry[];
  /** how long the engine's confirmation waits (the host's), null while unknown */
  confirmSeconds: number | null;
  onMemory: () => void;
}

export function SettingsPanel({ onClose, theme, onTheme, bypass, onBypass, mic, micAvailable, onMic, a11y, onA11y, general, onGeneral, metrics, netLog, confirmSeconds, onMemory }: Props) {
  const [tab, setTab] = useState<Tab>('general');
  const [voice, setVoice] = useState<{ tts?: { name?: string; downloaded?: boolean }; wake?: { downloaded?: boolean } } | null>(null);
  const [model, setModel] = useState<{ modelAlias?: string } | null>(null);
  useEffect(() => {
    void getJson<typeof voice>('/voice/inventory').then(setVoice);
    void getJson<{ modelAlias?: string }>('/settings').then(setModel);
  }, []);
  const g = general;
  const lock = g === null;
  const tts = voice?.tts?.name ? 'Supertonic · ' + voice.tts.name + (voice.tts.downloaded ? '' : ' · no está en disco') : '—';
  return (
    <div className="panel-shroud" onClick={onClose}>
      <div className="panel settings-panel bxs" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Ajustes">
        <div className="panel-head">
          <span className="panel-title">Ajustes</span>
          <button className="bx-ib plain" onClick={onClose} title="Cerrar"><Icon name="x" size={14} /></button>
        </div>
        <div className="settings-tabs">
          {TABS.map(([id, l]) => <button key={id} className={'settings-tab' + (tab === id ? ' on' : '')} onClick={() => setTab(id)}>{l}</button>)}
        </div>
        <div className="panel-body settings-body">
          {tab === 'general' ? (<>
            <Row label="Tema"><Seg value={theme} onChange={onTheme} options={[['dark', 'Oscuro'], ['light', 'Claro']]} /></Row>
            <Row label="Arrancar con Windows" hint={g?.autostartBlocked === 'not_this_copy' ? 'Esta copia de desarrollo no arranca con Windows: se abre con run_renew.cmd'
              : g?.autostart === null ? 'No se pudo leer el inicio de Windows' : 'Se queda en la bandeja del sistema'}>
              <Toggle on={!!g?.autostart} label="Arrancar con Windows" locked={lock || g?.autostart === null} onChange={(v) => onGeneral({ autostart: v })} />
            </Row>
            <Row label="Al cerrar la ventana" hint={g?.closeToTray ? 'Sigue escuchando desde la bandeja' : 'BAXY se cierra del todo'}>
              <Toggle on={!!g?.closeToTray} label="Al cerrar la ventana, seguir en la bandeja" locked={lock} onChange={(v) => onGeneral({ closeToTray: v })} />
            </Row>
          </>) : null}
          {tab === 'confirmacion' ? (<>
            <Row label="Nivel de confirmación" hint="Lo mismo que el interruptor del panel: Normal o Bypass">
              <Seg value={bypass ? 'never' : 'risk'} onChange={(v) => onBypass(v === 'never')} options={[['risk', 'Lo arriesgado'], ['never', 'Nada']]} />
            </Row>
            <div className="st-tip">Con <b className="bone">lo arriesgado</b>, BAXY pregunta antes de: borrar o perder trabajo sin guardar, enviar un mensaje o un correo, crear un evento en tu calendario, instalar, y un comando o un clic que cambia algo que no se puede deshacer. Con <b className="bone">nada</b> (bypass), lo hace sin preguntar y la conversación lo dice. La tarjeta aparece en la conversación, nunca encima de tu ventana, y espera tu respuesta {spoken(confirmSeconds)}; si no contestas, no se hace nada.</div>
          </>) : null}
          {tab === 'voz' ? (<>
            <Row label="Palabra de activación" ro hint={voice?.wake?.downloaded === false ? 'El modelo de activación no está en disco' : 'En pruebas · próximamente disponible'}><span className="bxs-fixed">BAXY</span></Row>
            <Row label="Voz de BAXY" ro><span className="bxs-fixed">{tts}</span></Row>
            <Row label="Micrófono" hint={micAvailable ? 'Entrada por voz: en pruebas · próximamente disponible' : 'No hay micrófono disponible'}>
              <Seg value={mic} onChange={(m) => (m === 'off' || micAvailable) && onMic(m)} options={[['always', 'Siempre'], ['ptt', 'Al pulsar'], ['off', 'Apagado']]} />
            </Row>
            <Row label="Sonido al despertar"><Toggle on={!!g?.wakeSound} label="Sonido al despertar" locked={lock} onChange={(v) => onGeneral({ wakeSound: v })} /></Row>
            <Row label="Silenciar su voz" hint="Seguirá respondiendo por escrito"><Toggle on={!!g?.voiceMuted} label="Silenciar su voz" locked={lock} onChange={(v) => onGeneral({ voiceMuted: v })} /></Row>
          </>) : null}
          {tab === 'accesibilidad' ? (<>
            <Row label="Modo accesible" hint="Texto más grande, más contraste y botones más amplios"><Toggle on={a11y.on} label="Modo accesible" onChange={(v) => onA11y({ ...a11y, on: v })} /></Row>
            <Row label="Tamaño del texto"><Seg value={a11y.size} onChange={(v) => onA11y({ ...a11y, size: v })} options={[['m', 'Normal'], ['l', 'Grande'], ['xl', 'Muy grande']]} /></Row>
            <Row label="Alto contraste"><Toggle on={a11y.contrast} label="Alto contraste" onChange={(v) => onA11y({ ...a11y, contrast: v })} /></Row>
            <div className="st-tip">Todo lo que hace BAXY se puede pedir y escuchar por voz. El modo cambia cómo se ve, no lo que puede hacer.</div>
          </>) : null}
          {tab === 'privacidad' ? (<>
            <Row label="El modelo corre en este PC" ro hint="Nada de lo tuyo sale sin que lo pidas"><Toggle on locked label="El modelo corre en este PC" /></Row>
            <Row label="Búsqueda web" hint="Sale la búsqueda, nunca tus archivos ni la conversación"><Toggle on={!!g?.web} label="Búsqueda web" locked={lock} onChange={(v) => onGeneral({ web: v })} /></Row>
            <Row label="Clima" hint="Sale solo el nombre de la ciudad"><Toggle on={!!g?.weather} label="Clima" locked={lock} onChange={(v) => onGeneral({ weather: v })} /></Row>
            <Row label="Mirar la pantalla" hint="Solo la ventana que necesita, y lo dice en el paso"><Toggle on={!!g?.screen} label="Mirar la pantalla" locked={lock} onChange={(v) => onGeneral({ screen: v })} /></Row>
            <Row label="Memoria"><button className="panel-btn ghost" onClick={onMemory}>Ver y editar</button></Row>
            <div className="panel-sec-head" style={{ marginTop: 16 }}>Salidas a internet de esta sesión</div>
            {netLog.length
              ? netLog.map((n, i) => <div key={i} className="bxs-log"><Globe s={10} /><span>{n.what}</span><span className="ts">{n.ts}</span></div>)
              : <div className="bxs-log empty">Ninguna. Todo se ha quedado en este PC.</div>}
          </>) : null}
          {tab === 'modelo' ? (<>
            <Row label="Modelo" ro><span className="bxs-fixed">{model?.modelAlias ?? '—'}</span></Row>
            <Row label="Límite de memoria" ro hint="Lo máximo que puede ocupar el modelo"><span className="bxs-fixed">4 GB</span></Row>
            <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
              <Bar label="Memoria de vídeo" v={metrics?.model_vram_gb} max={4} unit="GB" />
              <Bar label="RAM" v={metrics?.model_ram_gb} max={4} unit="GB" />
            </div>
            <div className="st-tip">Si un dato no se puede leer, se muestra «—», nunca 0.</div>
          </>) : null}
        </div>
        <div className="settings-footer"><span className="bxs-foot">Los cambios se guardan al momento</span><button className="panel-btn" onClick={onClose}>Listo</button></div>
      </div>
    </div>
  );
}
