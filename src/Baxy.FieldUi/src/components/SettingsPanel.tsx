/* SettingsPanel — read-only local diagnostics: what the host reports of the
   model (GET /settings) and of the voice models (GET /voice/inventory). The
   host manages both; nothing here is written back. The chrome is the shared
   panel (.panel-shroud > .panel.settings-panel) with .settings-tabs header,
   .settings-body section and .settings-footer. */

import { useEffect, useState, type PropsWithChildren } from 'react';
import { Icon } from './Icon';

const SETTINGS_TABS = [
  { id: 'model', label: 'model' },
  { id: 'voice', label: 'voice' },
  { id: 'about', label: 'about' },
] as const;
type TabId = typeof SETTINGS_TABS[number]['id'];

/** GET /settings — only what the host reports. */
interface HostSettings {
  modelAlias?: string;
  ggufPath?: string;
  ctxSize?: number;
  wakeWordEnabled?: boolean;
  voiceEnabled?: boolean;
}

interface VoiceModel { name?: string; downloaded?: boolean; }

/** GET /voice/inventory — the launcher's voice models, as found on disk. */
interface VoiceInventory {
  stt?: VoiceModel;
  tts?: VoiceModel;
  wake?: VoiceModel;
}

function useHostJson<T>(path: string): { data: T | null; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(path);
        if (cancelled) return;
        if (!r.ok) { setError(`server error ${r.status}`); return; }
        setData((await r.json()) as T);
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [path]);
  return { data, error };
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="kv-row"><span className="k">{k}</span><span className="v">{v}</span></div>
  );
}

function STSection({ children }: PropsWithChildren) {
  return <div className="st-section">{children}</div>;
}

function Pending({ error }: { error: string | null }) {
  return <div className="muted" style={{ padding: 24 }}>{error ? `error · ${error}` : 'loading…'}</div>;
}

function onOff(value: boolean | undefined): string {
  return value === undefined ? '—' : value ? 'on' : 'off';
}

function modelText(model: VoiceModel | undefined): string {
  if (!model?.name) return '—';
  return `${model.name} · ${model.downloaded ? 'en disco' : 'no está en disco'}`;
}

function ModelTab() {
  const { data, error } = useHostJson<HostSettings>('/settings');
  if (!data) return <Pending error={error} />;
  return (
    <STSection>
      <div className="kv">
        <Row k="model" v={data.modelAlias || '—'} />
        <Row k="gguf" v={data.ggufPath || '—'} />
        <Row k="context (tokens)" v={data.ctxSize ? data.ctxSize.toLocaleString() : '—'} />
      </div>
    </STSection>
  );
}

function VoiceTab() {
  const settings = useHostJson<HostSettings>('/settings');
  const inventory = useHostJson<VoiceInventory>('/voice/inventory');
  if (!settings.data || !inventory.data) return <Pending error={settings.error ?? inventory.error} />;
  return (
    <STSection>
      <div className="kv">
        <Row k="stt" v={modelText(inventory.data.stt)} />
        <Row k="tts" v={modelText(inventory.data.tts)} />
        <Row k="wake" v={modelText(inventory.data.wake)} />
        <Row k="microphone" v={onOff(settings.data.voiceEnabled)} />
        <Row k="wake listening" v={onOff(settings.data.wakeWordEnabled)} />
      </div>
    </STSection>
  );
}

function AboutTab() {
  return (
    <STSection>
      <div className="st-about-title">BAXY · desktop</div>
      <div className="st-about-sub">asistente local · modelo administrado por BAXY</div>
      <div className="hair" style={{ margin: '16px 0' }} />
      <div className="kv">
        <Row k="host" v="Baxy.App · .NET 10" />
        <Row k="mind" v="baxy_mind" />
        <Row k="runtime" v="llama.cpp · local" />
      </div>
    </STSection>
  );
}

interface Props {
  onClose: () => void;
}

export function SettingsPanel({ onClose }: Props) {
  const [tab, setTab] = useState<TabId>('model');

  return (
    <div className="panel-shroud" onClick={onClose} role="presentation">
      <div
        className="panel settings-panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="settings"
      >
        <div className="panel-head">
          <div className="panel-head-left">
            <span className="panel-title">configuration</span>
            <span className="muted">·</span>
            <span className="panel-subtitle">diagnóstico local</span>
          </div>
          <button className="ibtn" onClick={onClose} data-tip="close" aria-label="close">
            <Icon name="x" />
          </button>
        </div>

        <div className="settings-tabs" role="tablist">
          {SETTINGS_TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              className={`settings-tab${tab === t.id ? ' on' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="settings-body">
          {tab === 'model' && <ModelTab />}
          {tab === 'voice' && <VoiceTab />}
          {tab === 'about' && <AboutTab />}
        </div>

        <div className="settings-footer">
          <div className="footer-right">
            <button type="button" className="panel-btn ghost" onClick={onClose}>cerrar</button>
          </div>
        </div>
      </div>
    </div>
  );
}
