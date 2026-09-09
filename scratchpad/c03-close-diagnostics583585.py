"""Seal unsuccessful native alternatives without counting cleanup as model failures."""
from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def rows(p):
    return [json.loads(s) for s in p.read_text(encoding='utf-8-sig').splitlines()]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


for number, name, notes in [
    (583, 'qwen9b-bounded', '''# Nativo583 — razonamiento limitado9B no adoptado

Qwen3.5-9B Q4_K_M/b10865, perfil general oficialT1/p0,95/k20/min0/presence1,5/repeat1/seed0, NGL19, un contexto8192, q8KV, FA. Frente a567 se limita razonamiento256 y salida total768, conservando los prompts de desarrollo. Siete respuestas recibidas: seis EOS y una cortada. Confirmación, progreso, hora y distinción de memoria desactivada son utilizables; el guardado inventa el apelativo Bax y la recuperación dice «Mi nombre guardado es Jordan», atribuyéndolo a BAXY. La séptima llama físicos a16 procesadores lógicos, expone deliberación en inglés y acaba por length tras127,1s. Es una respuesta fallida, no una prueba de incapacidad con presupuesto suficiente. El razonamiento aparece separado al principio y luego sigue deliberando en el contenido final después del límite.

Se detuvo sólo el servidor identificado en PROCESS tras esos fallos, sin promoverlo. La siguiente petición recibió ConnectionReset y ocho posteriores ConnectionRefused: nueve errores inducidos por el cierre, no nueve fallos semánticos. El complete:true del conductor sólo significa que recorrió su bucle; la campaña semántica quedó parcial con siete respuestas. No se evaluaron las cuatro capturasCPU recientes582. No extrapolar a todo9B ni repetir este perfil sin cambiar estrategia.

GPU3428,148MiB/RAM3039,039MiB,478,094s; los seis EOS tardaron44,1–50,1s. Las pruebas Python584 se solaparon brevemente: no es un benchmark limpio de latencia. Ningún cambio del manifiesto, UI, voz, ejecución de efectos ni cobertura de encuesta. Fuentes oficiales consultadas2026-09-09: fichaQwen3.5-9B y llama.cpp discusión21445 sobre presupuesto; PR25961 sigue experimental, no se atribuyó como implementada en b10865.
'''),
    (585, 'tool-result-envelope', '''# Nativo585 — separar evidencia con roles no corrige el sujeto

Ocho capturasCPU recientes582 por dos representaciones,16 EOS. La variante mueve la línea situation intacta a role:tool, precedida por una representación estructural sintética de la lectura ya observada; no es un tool_call producido en aquel turno. Identidad, pregunta, hechos, instrucciones, muestreo greedy/seed0 y límites permanecen iguales. El template efectivo contiene tool_call/tool_response conforme al template oficial exactoQwen2507. No se ejecutan herramientas ni se introduce un borrador de prosa escrito a mano.

Ambos formatos conservan cuatro respuestas correctas (conteos4/9 y usos14/23), pero ambos fallan en los sujetos10/12/20/21. El formato tool sigue diciendo Estoy/I'm/Tengo al describir la CPU total. No hay mejora que justifique incorporarlo; no se modifica el producto. Esta comparación a muestreo constante aísla la representación, no clasifica modelos ni afirma que greedy sea su óptimo general.

GPU3497,559MiB/RAM721,680MiB,8,829s. Fuentes consultadas2026-09-09: tokenizer_config oficialQwen3-4B-Instruct-2507 y documentaciónQwen3 de function calling. Sin UI/voz ni consumo conjunto final. Encuesta13 cubiertos/729 abiertos/0NA intacta.
'''),
]:
    private = local / f'C03-{name}{number}-private'
    out = base / f'astra-{name}{number}'
    replies = rows(private / 'responses.jsonl')
    cases = {c['case']: c for c in read(private / 'cases.json')}
    adjudications = []
    for i, r in enumerate(replies):
        if number == 583:
            verdict = 'induced_transport_error_after_owned_stop' if 'error' in r else 'failed' if r['case'] in ('save-result', 'stored-name-es', 'C03-survey-readonly541-private:26') else 'correct'
        else:
            verdict = 'correct' if r['case'] in ('582:4', '582:9', '582:14', '582:23') else 'wrong_machine_actor'
        adjudications.append({'ordinal': i + 1, 'case': r['case'], 'profile': r['profile'], 'verdict': verdict, 'response': r})
    write(private / 'adjudication.json', adjudications)
    lines = [notes, '\n## Entradas y respuestas literales privadas\n']
    for row in adjudications:
        lines += [f'### {row["ordinal"]} · {row["case"]} · {row["profile"]}', '', '```json', json.dumps(cases[row['case']]['payload'], ensure_ascii=False, indent=2), '```', '', '```json', json.dumps(row['response'], ensure_ascii=False, indent=2), '```', '', row['verdict'], '']
    (private / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    (out / 'RESULT.md').write_text(notes, encoding='utf-8', newline='\n')
    result = {'adopted': False, 'resources': read(out / 'RESOURCES.json'), 'private_report_sha256': sha(private / 'RESULT.md'), 'private_adjudication_sha256': sha(private / 'adjudication.json'), 'survey': {'covered': 13, 'open': 729, 'not_applicable': 0}, 'source_unchanged_by_experiment': True}
    if number == 583:
        assert len(replies) == 16 and sum('error' in r for r in replies) == 9
        result.update(received_responses=7, eos=6, length=1, correct=4, failed_received=3, induced_transport_errors=9, campaign_complete=False)
    else:
        assert len(replies) == 16 and all(r['response']['choices'][0]['finish_reason'] == 'stop' for r in replies)
        templates = {p.name: read(p) for p in (private / 'template-registered-user-envelope.json', private / 'template-native-tool-envelope.json')}
        assert '<tool_response>' in json.dumps(templates['template-native-tool-envelope.json'])
        result.update(received_responses=16, correct_per_profile=4, wrong_actor_per_profile=4, template_sha256={name: sha(private / name) for name in templates})
    write(out / 'RESULT.json', result)
    write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
    with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(f'/artifacts/comprobaciones/C03/astra-{name}{number}/** -text\n')
    with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write('\n\n' + notes)
print('583 partial and585 complete adjudicated; neither adopted.')
