import { useEffect, useState } from 'react';
import { Icon, type IconName } from './Icon';
import type { BaxyState, MicMode } from '../types';

/* The input bar (design parts.jsx BxInput): the voice button with its three modes, the text field and the send button.
   The design's attach button is not here: attaching files waits for a typed contract on the host (README: «adjuntos sin
   contrato tipado» are blocked), and a button that does nothing is a dead end (owner, 2026-10-17). */

// The owner's rule (2026-10-18): only text is ready today; voice input is shown «en pruebas · próximamente disponible»,
// never as ready, and it stays usable (taking it away is the owner's decision).
const MIC: { id: MicMode; icon: IconName; label: string; sub: string }[] = [
  { id: 'off', icon: 'mic-off', label: 'Apagado', sub: 'Solo texto' },
  { id: 'always', icon: 'mic', label: 'Siempre activo', sub: 'Responde a «BAXY» · en pruebas, próximamente disponible' },
  { id: 'ptt', icon: 'wave', label: 'Mantener para hablar', sub: 'O la barra espaciadora · en pruebas, próximamente disponible' },
];

// the host refuses a longer request (MissionInput.MaximumCharacters, the WPF composer's MaxLength)
const MAX_CHARS = 4096;

interface Props {
  mic: MicMode;
  micAvailable: boolean;
  onMic: (m: MicMode) => void;
  onPttStart: () => void;
  onPttEnd: () => void;
  /** sends the request; false when the host did not take it */
  onSubmit: (text: string) => Promise<boolean>;
  state: BaxyState;
  canSend: boolean;
}

export function VoiceInput({ mic, micAvailable, onMic, onPttStart, onPttEnd, onSubmit, state, canSend }: Props) {
  const [draft, setDraft] = useState('');
  const [menu, setMenu] = useState(false);
  const cur = MIC.find((m) => m.id === mic) ?? MIC[1];
  const talking = mic === 'ptt' && state === 'listening';
  const armed = draft.trim().length > 0 && canSend;
  useEffect(() => {
    if (!menu) return;
    const close = (e: PointerEvent) => { if (!(e.target as Element | null)?.closest('.bx-micwrap')) setMenu(false); };
    // Esc closes the open menu and goes no further (it is also a card's No)
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); e.preventDefault(); setMenu(false); } };
    window.addEventListener('pointerdown', close);
    window.addEventListener('keydown', esc, true);
    return () => { window.removeEventListener('pointerdown', close); window.removeEventListener('keydown', esc, true); };
  }, [menu]);
  // a request the host did not take comes back to the box (unless the person already wrote something else)
  const send = async () => {
    if (!armed) return;
    const text = draft.trim();
    setDraft('');
    if (!(await onSubmit(text))) setDraft((d) => d || text);
  };
  const ph = state === 'booting' ? 'Cargando el modelo…'
    : state === 'confirm' ? '↵ sí · esc no'
      : mic === 'ptt' ? 'Escribe o mantén espacio'
        : mic === 'off' ? 'Escribe a BAXY'
          : 'Escribe o di «BAXY»';
  return (
    <div className="bx-line">
      <div className="bx-micwrap">
        {menu ? (
          <div className="bx-micmenu">
            {MIC.map((m) => {
              const blocked = m.id !== 'off' && !micAvailable;
              return (
                <button key={m.id} className={m.id === mic ? 'on' : ''} disabled={blocked}
                  title={blocked ? 'No hay micrófono disponible' : undefined}
                  onClick={() => { onMic(m.id); setMenu(false); }}>
                  <Icon name={m.icon} size={14} />
                  <span className="l"><span>{m.label}</span><span className="s">{blocked ? 'No hay micrófono' : m.sub}</span></span>
                  {m.id === mic ? <Icon name="check" size={12} /> : null}
                </button>
              );
            })}
          </div>
        ) : null}
        <button
          className={'bx-mic' + (mic !== 'off' ? ' on' : '') + (mic === 'always' && state === 'idle' ? ' breath' : '') + (talking ? ' talking' : '')}
          onClick={() => { if (mic !== 'ptt') setMenu(!menu); }}
          onPointerDown={(e) => { if (mic === 'ptt') { e.preventDefault(); e.currentTarget.setPointerCapture(e.pointerId); onPttStart(); } }}
          onPointerUp={() => { if (mic === 'ptt') onPttEnd(); }}
          /* a press the system takes away (a touch turned into a scroll, the pen leaving) never sends its pointerup */
          onPointerCancel={() => { if (mic === 'ptt') onPttEnd(); }}
          title={mic === 'ptt' ? 'Mantén para hablar' : cur.label}
        ><Icon name={cur.icon} size={15} /></button>
        <button className={'bx-caret' + (menu ? ' open' : '')} onClick={() => setMenu(!menu)} title="Modo de micrófono" aria-expanded={menu}>
          <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1.3"><path d="M1.5 5 L4 2.5 L6.5 5"></path></svg>
        </button>
      </div>
      <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={ph} spellCheck={false} autoFocus maxLength={MAX_CHARS}
        aria-label="Escribe a BAXY" data-ready={canSend ? 'true' : 'false'}
        onKeyDown={(e) => { if (e.key === 'Enter' && armed) { e.preventDefault(); e.stopPropagation(); void send(); } }} />
      <button className={'bx-send' + (armed ? '' : ' hide')} onClick={() => void send()} title="Enviar"><Icon name="send" size={14} /></button>
    </div>
  );
}
