import { Panel, Seg, Toggle } from '../Panel';
import type { ProposalSettings, QuietSpan } from '../../types';
import { spoken } from '../../duration';
import { useT, type Words } from '../../i18n';

/* Proposals (design panels4.jsx BxProposals): what the heartbeat may suggest on its own. «No me interrumpas durante…»
   keeps BAXY from speaking in those moments (a proposal then arrives as a Windows notification); silencing stops the
   heartbeat until the chosen time (Heartbeat, ProposalSettingsStore). */

const OPTS: [QuietSpan, Words][] = [['30m', { es: '30 min', en: '30 min' }], ['1h', { es: '1 hora', en: '1 hour' }], ['tomorrow', { es: 'Hasta mañana', en: 'Until tomorrow' }]];

export function ProposalsPanel({ value, proposalSeconds, onChange, onClose }: { value: ProposalSettings | null; proposalSeconds: number | null; onChange: (v: Partial<ProposalSettings>) => void; onClose: () => void }) {
  const t = useT();
  const ctx = value?.ctx ?? { game: true, call: true, video: true };
  const quiet = value?.quiet ?? null;
  const until = value?.quietUntil ? new Date(value.quietUntil).toLocaleTimeString(t.locale, { hour: '2-digit', minute: '2-digit' }) : null;
  return (
    <Panel title={t('Propuestas · lo que BAXY sugiere por su cuenta', 'Proposals · what BAXY suggests on its own')} onClose={onClose} width={480}>
      {value === null ? <div className="bx-mem-empty">{t('No se pudieron leer los ajustes de propuestas.', 'Couldn’t read the proposal settings.')}</div> : null}
      <div className="bxs-row"><div className="bxs-l"><span>{t('No me interrumpas durante…', 'Don’t interrupt me during…')}</span><span className="h">{t('BAXY no habla en estas situaciones. Si algo no puede esperar, te llega como notificación de Windows.', 'BAXY stays quiet in these moments. If something can’t wait, it reaches you as a Windows notification.')}</span></div></div>
      {([['game', t('Juegos', 'Games')], ['call', t('Llamadas', 'Calls')], ['video', t('Vídeo a pantalla completa', 'Full-screen video')]] as const).map(([k, l]) => (
        <div key={k} className="bxs-row sm">
          <div className="bxs-l"><span>{l}</span></div>
          <div className="bxs-c"><Toggle on={ctx[k]} label={l} locked={value === null} onChange={(v) => onChange({ ctx: { ...ctx, [k]: v } })} /></div>
        </div>
      ))}
      <div className="bxs-row">
        <div className="bxs-l"><span>{t('Silenciar todas las propuestas', 'Mute all proposals')}</span><span className="h">{quiet ? t('En silencio', 'Muted') + (until ? t(' hasta las ', ' until ') + until : '') : t('Activas', 'Active')}</span></div>
        <div className="bxs-c">
          <Seg<QuietSpan | ''> value={quiet ?? ''} options={OPTS.map(([v, l]) => [v, t.w(l)] as [QuietSpan, string])} onChange={(v) => onChange({ quiet: v === quiet ? null : (v || null) })} />
        </div>
      </div>
      <div className="st-tip">{t('Las propuestas usan la misma tarjeta Sí / No que las confirmaciones y esperan tu respuesta ', 'Proposals use the same Yes / No card as confirmations and wait ')}{spoken(proposalSeconds, t)}{t('; si no contestas, no se hace nada.', ' for your answer; if you don’t answer, nothing is done.')}</div>
    </Panel>
  );
}
