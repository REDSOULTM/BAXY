"""Adjudicate341/342, including verified private operations and lost narration facts."""
from pathlib import Path
import os
import json
import hashlib

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03'
base = Path(os.environ['LOCALAPPDATA'])/'BAXY'
reviews = {
    '341': ('1/6 completo, cero silencios', [
        'Útil: pide el dato que falta.',
        'Fallo: reacción convertida en incomprensión.',
        'Parcial: saluda y pide confirmar, pero no dice que se autoriza activar la memoria; no permite una decisión informada.',
        'Fallo: repite confirmar/cancelar ante referencia de identidad, sin explicar acción ni atender el contexto.',
        'Fallo: repite confirmar/cancelar ante pregunta de identidad.',
        'Fallo: repite confirmar/cancelar ante pregunta de ambas identidades.',
    ]),
    '342': ('2/7 completos; identidad conjunta parcial; cero silencios', [
        'Útil: pide el nombre faltante.',
        'Parcial: saludo y elección sin explicar qué se confirma.',
        'Útil para el recorrido: el journal verifica enable y un nuevo save, y se entrega el saludo pendiente. Las narraciones intermedias Confirmado/Guardé son pobres y se revisan abajo.',
        'Fallo: invierte el referente y responde con otra pregunta.',
        'Fallo: pide desambiguar una identidad ya declarada; dos preguntas innecesarias.',
        'Parcial: identifica BAXY y Emmanuel, pero añade la confusa atribución de que el usuario está hablando consigo mismo. No presentar como respuesta natural plenamente validada.',
        'Fallo demostrado: niega conocer el nombre después de memory.recall verificado con un registro name=emmanuel.',
    ]),
}
for number, (headline, reasons) in reviews.items():
    private = base/f'C03-memory-product{number}-private'
    prereg = json.loads((out/f'astra-memory-product{number}/PREREG.json').read_text(encoding='utf-8'))
    events = [json.loads(l) for l in (private/'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
    terminals = [r for r in events if r.get('type') == 'terminal']
    assert len(terminals) == len(reasons) == len(prereg['cases'])
    lines = [f'# Producto{number} — {headline}', '',
        'Exit0, admisiones200 y ningún timeout. Runtime registrado sin override. '
        '341 conserva seis literales humanos;342 agrega confirmar y cómo me llamo '
        'como controles sintéticos explícitamente declarados, no uso humano ni reserva fresca. '
        'El conductor no prueba escritorio ni voz física.', '']
    for index, (request, terminal, reason) in enumerate(zip(prereg['cases'],terminals,reasons,strict=True),1):
        lines.extend([f'## Turno {index}', '', request, '', '> '+terminal['final'], '', reason, ''])
    lines.extend(['## Diagnóstico compartido', '',
        '341: memoria no se habilita sin confirmar.340 añade correctamente el paso '
        'privado; la explicación de la confirmación recibe sólo cause=memory_enable, '
        'sin pendingAction. El borrador nativo omite qué se autoriza y el guard lo deja pasar.', '',
        '342: tras confirmar, journal registra memory.enable completado y memory.save '
        'completado con nueva invocationId frente al save fallido por memory_disabled. '
        'La continuación pública sí saluda. Al recordar, la App emite status/cause '
        'memory_records con shown1,total1,records[{label:name,value:emmanuel}], pero '
        'Python lo reduce a kindstatus/outcomecompleted/state listed memories: elimina '
        'los registros. El modelo ya no recibe el nombre y publica No sé cómo te llamas. '
        'Enable/save también llegan como prosa fija al compositor, con payload vacío; '
        'éste publica Confirmado y Guardé. Primera transformación incorrecta localizada.', '',
        'Decisión: reparar el contrato de proyección privada de resultado/confirmación, '
        'no introducir otro nombre en prompts o filtro de frases. Preservar los valores '
        'permitidos por MemoryOperationResponseProjection y sus reglas de secretos. '
        'La referencia conversacional105/107 también sigue pendiente.340 no cierra '
        'la memoria integrada sólo por los1911tests. C03 EN_CURSO.', ''])
    (out/f'astra-memory-product{number}/RESULT.md').write_text('\n'.join(lines),encoding='utf-8')
    paths = [private/'capture/events.jsonl', private/'compose-audit.jsonl', private/'http-posts.jsonl',
        base/f'C03-memory-profile{number}/journal/missions.jsonl']
    pins = {}
    for path in paths:
        with path.open('rb') as stream:
            pins[str(path)] = hashlib.file_digest(stream,'sha256').hexdigest()
    (out/f'astra-memory-product{number}/PINS.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'341':'1/6','342':'2/7 complete, one partial identity','silence':0,'next':'private result/confirmation projection'}))
