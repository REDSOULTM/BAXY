"""Persist product337 adjudication and current owner-directed consolidation."""
from pathlib import Path
import hashlib
import json
import os
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-memory-product337-private'
prereg = json.loads((out / 'astra-memory-product337/PREREG.json').read_text(encoding='utf-8'))
events = [json.loads(s) for s in (private / 'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
terminals = [r for r in events if r.get('type') == 'terminal']
assert len(terminals) == 6
reasons = [
    'Fallo: silencio por composition_failed. Las preguntas nativas válidas se rechazan con missing_name al exigir vocabulario de capacidades ajenas a la aclaración.',
    'Fallo: la reacción se convierte en incomprensión, sin recuperar el pedido pendiente.',
    'Parcial, no útil completo: causa memory_disabled verdadera; omite el saludo y no orienta la activación. No certifica guardado.',
    'Fallo: vuelve a pedir el nombre ya declarado.',
    'Fallo: refiere la cuenta de Windows en lugar del nombre declarado en contexto.',
    'Fallo: pregunta si debe contestar lo que ya se le pidió.',
]
lines = ['# Producto337 — 0/6 completos, un silencio', '',
    'Seis terminales, exit0 del conductor; no confundir fin del proceso con utilidad. '
    'Regresión frente a334 (2/6, cero silencios). Desarrollo, no aceptación fresca, UI gráfica ni voz física. '
    'Perfil nuevo deshabilitado por defecto, sin override ni activación inyectada.', '']
for idx, request, terminal, reason in zip([99,101,103,105,107,109], prereg['cases'], terminals, reasons, strict=True):
    lines.extend([f'## {idx}', '', request, '', '> ' + terminal['final'], '', reason, ''])
journal = private.parent / 'C03-memory-profile337/journal/missions.jsonl'
operations = []
for line in journal.read_text(encoding='utf-8-sig').splitlines():
    row = json.loads(line)['payload']
    operations.append({k: row.get(k) for k in ('phase', 'operation', 'response')})
lines.extend(['## Diagnóstico y siguiente comparación', '',
    'Primera transformación incorrecta: _compose_situation_payload agrega can a una '
    'clarificación por el texto de capacidades del pedido original. _payload_fact_defect '
    'exige vocabulario de esa lista y descarta las tres preguntas válidas. '
    'Fuente338 acota capacidades/límites conversacionales al tipo conversation, '
    'sin debilitar el validador de hechos. Después queda resolver activación guiada '
    'y continuidad de identidad con sus confirmaciones existentes.', ''])
(out / 'astra-memory-product337/RESULT.md').write_text('\n'.join(lines), encoding='utf-8')
pins = {}
for path in [private/'capture/events.jsonl', private/'compose-audit.jsonl', private/'http-posts.jsonl', journal]:
    with path.open('rb') as stream:
        pins[str(path)] = hashlib.file_digest(stream, 'sha256').hexdigest()
(out/'astra-memory-product337/PINS.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8')
checkpoint = out/'CHECKPOINT.md'
current = '''# C03 — checkpoint338 — EN_CURSO

Petición directa del dueño incorporada: 16 mensajes propios recuperados hasta el
inicio de esta tarea, originales y síntesis en INSTRUCCIONES_CONSOLIDADAS_2026-09-08.md
y MENSAJES_DUENO_2026-09-08.json. Excluir instrucciones llegadas de ChatGPT/otra tarea;
conservar hallazgos sólo como evidencia contrastada. AutoridadC03 actualizada.
No nuevo goal ni reinicio. AGENTS/identidad vigentes. BAXY cerrado para uso manual.
Encuesta final revisión1248 intacta; 742 requisitos/generalización ya trazados336.

336: 1908pass0skip y prueba disabled separada1pass0skip; Fastverde20,12s.
Persistencia sólo comprobada con habilitación/confirmación explícitas en perfil
temporal. Producto337 terminó exit0:0/6 completos y un silencio (regresión frente
a3342/6). RESULT/PINS escritos; no aceptación integrada de memoria.

338: primera causa337: payload can ajeno a aclaración => veto missing_name de
preguntas nativas válidas. Fuente sólo acota can/beyond a kind conversation.
Baselinefinal14fail1pass; dueñas composición/política1023pass0skip5,24s.
Fast en curso; siguiente recoger, repetir seis literales de337 sin overrides.
Durante creación de tests: dos Python sin pytest; fixture request reservado;
corregidos sin cambiar producto. Una variante inglesa además dispara knowledge_question;
el test inglés338 mide sólo el payload. El otro veto queda pendiente explícito,
no presentar soporte integrado inglés de esa variante como resuelto.

SIGUIENTE: producto339 tras Fast338; activación guiada y continuidad contextual
de memoria; mantener privados/confimación exacta/default. No Full en reparación.
Sin subagentes, commit/push ni cambios a main. No bloqueo externo.
Pendiente C03 completo: otras conductas264/todasrutas,100humanosfrescos,averías,
UIreal/vozfísica/ASR/recursos,runtime/instalación,contratosC04–C09,Full/publicación.
Auditoría335 dejó204 por auditar; no reserva certificada ni congelada.

## Contexto anterior (histórico; este encabezado manda)

'''
checkpoint.write_text(current + checkpoint.read_text(encoding='utf-8'), encoding='utf-8')
(out/'HANDOFF.md').write_text(current, encoding='utf-8')
state_path = out/'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='338: all16 direct owner messages consolidated; cross-task instructions excluded. 337 finished0/6 one silence; 338 owner tests1023pass, Fast running.',
    continuation='Collect Fast338 then product339 same six turns. Fix activation/context and the separate English knowledge-question veto; BAXY closed. C03 active, no Full during repair.')
state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'terminals':len(terminals),'operations':operations},ensure_ascii=True))
