import { Panel, Seg, Toggle } from '../Panel';
import type { ProposalSettings, QuietSpan } from '../../types';
import { spoken } from '../../duration';

/* Proposals (design panels4.jsx BxProposals): what the heartbeat may suggest on its own. «No me interrumpas durante…»
   keeps BAXY from speaking in those moments (a proposal then arrives as a Windows notification); silencing stops the
   heartbeat until the chosen time (Heartbeat, ProposalSettingsStore). */

const OPTS: [QuietSpan, string][] = [['30m', '30 min'], ['1h', '1 hora'], ['tomorrow', 'Hasta mañana']];

export function ProposalsPanel({ value, proposalSeconds, onChange, onClose }: { value: ProposalSettings | null; proposalSeconds: number | null; onChange: (v: Partial<ProposalSettings>) => void; onClose: () => void }) {
  const ctx = value?.ctx ?? { game: true, call: true, video: true };
  const quiet = value?.quiet ?? null;
  const until = value?.quietUntil ? new Date(value.quietUntil).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }) : null;
  return (
    <Panel title="Propuestas · lo que BAXY sugiere por su cuenta" onClose={onClose} width={480}>
      {value === null ? <div className="bx-mem-empty">No se pudieron leer los ajustes de propuestas.</div> : null}
      <div className="bxs-row"><div className="bxs-l"><span>No me interrumpas durante…</span><span className="h">BAXY no habla en estas situaciones. Si algo no puede esperar, te llega como notificación de Windows.</span></div></div>
      {([['game', 'Juegos'], ['call', 'Llamadas'], ['video', 'Vídeo a pantalla completa']] as const).map(([k, l]) => (
        <div key={k} className="bxs-row sm">
          <div className="bxs-l"><span>{l}</span></div>
          <div className="bxs-c"><Toggle on={ctx[k]} label={l} locked={value === null} onChange={(v) => onChange({ ctx: { ...ctx, [k]: v } })} /></div>
        </div>
      ))}
      <div className="bxs-row">
        <div className="bxs-l"><span>Silenciar todas las propuestas</span><span className="h">{quiet ? 'En silencio' + (until ? ' hasta las ' + until : '') : 'Activas'}</span></div>
        <div className="bxs-c">
          <Seg<QuietSpan | ''> value={quiet ?? ''} options={OPTS} onChange={(v) => onChange({ quiet: v === quiet ? null : (v || null) })} />
        </div>
      </div>
      <div className="st-tip">Las propuestas usan la misma tarjeta Sí / No que las confirmaciones y esperan tu respuesta {spoken(proposalSeconds)}; si no contestas, no se hace nada.</div>
    </Panel>
  );
}
