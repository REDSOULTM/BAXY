"""Close actual compound577 and native CPU repair578–580 before source adoption."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

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


private = local / 'C03-compound-product577-private'
out = base / 'astra-compound-product577'
panel = read(private / 'panel.json')
finals = [r for r in rows(private / 'capture/events.jsonl') if r.get('type') == 'terminal']
posts = rows(private / 'http-posts.jsonl')
assert len(finals) == len(panel) == 9 and read(out / 'EXIT.json')['exitCode'] == 0
adjudication = [{**case, 'terminal': finals[i], 'ordinal': i + 1, 'adjudication': 'Correcto. Conserva hora03:16 y sonido no silenciado/volumen100 en el orden pedido.' if i < 6 else 'Control correcto de estado de audio o conectividad.'} for i, case in enumerate(panel)]
write(private / 'adjudication.json', adjudication)
lines = ['# Producto577 — composición de hora y silencio', '']
for row in adjudication:
    lines += [f'## {row["ordinal"]}', '', row['text'], '', row['terminal']['final'], '', row['adjudication'], '']
lines += ['## Capturas nativas', '', '```json', json.dumps(posts, ensure_ascii=False, indent=2), '```']
(private / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
compound_note = '''# Producto577 — hora y silencio verificados

Fuente576 publicada022416a0. Nueve finales correctos/sin cortes. Las seis compuestas ES/EN conservan hora03:16 y no silenciado/volumen100, con inversión de orden y verbo explícito/heredado. Native2/4/6: hora→audio;8/10/12: audio→hora. Controles de pregunta indirecta, audio y red correctos. El control inglés de audio hace dos lecturas audio.status: redundancia observada, sin atribuirle ahorro mínimo definitivo.

GPU3497,559MiB/RAM1859,543MiB,28,766s. Conductor compartido sin ventana ni voz; no consumo conjunto final. Encuesta12 cubiertos/730 abiertos/0NA, sin crédito automático por variantes de desarrollo. Fuente576 verificada en el producto.
'''
(out / 'RESULT.md').write_text(compound_note, encoding='utf-8', newline='\n')
write(out / 'RESULT.json', {'finals': 9, 'correct': 9, 'source576_verified': True, 'new_survey_credit': False, 'private_report_sha256': sha(private / 'RESULT.md'), 'adjudication_sha256': sha(private / 'adjudication.json'), 'resources': read(out / 'resources.json')})

native_specs = [
    ('cpu-dialogue-repair578', 8, 'Dar al modelo su borrador real y feedback de sujeto corrige los dos actores. Greedy genera Esto computadora en el uso ES: gramática defectuosa, no adoptar ese perfil. EN conserva hechos e idioma. La instrucción genérica First person del tercer reintento no estaba en los primeros prompts543/575; no atribuirle la causa inicial.'),
    ('cpu-dialogue-sampling579', 8, 'Mismo feedback y borradores; perfil oficial Qwen0,7/0,8/20/0, presence0/repeat1. Seed0 corrige sujeto y gramática en los cuatro casos. Seed17 omite sujeto explícito en Está usando, ambiguo; los otros tres se conservan. Perfil candidato seed0 exclusivamente para reparación detectada, no muestreo global. Fuente oficial comprobada:https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507#best-practices.'),
    ('cpu-repair-generalization580', 12, 'Seis fixtures sintéticos cambian pregunta/idioma, porcentaje, conteos físicos/lógicos y nombre de procesador. Primero se genera el borrador real y después su corrección. Los tres borradores con primera persona indebida (2/3/5, ordinales cero) pasan a Este equipo/computador y conservan19%,6núcleos/modeloR3 y4físicos/8lógicos. Los controlesEN1/4 permanecen correctos. El controlES0 ya decía Estás usando y corregirlo innecesariamente da Está usando: la adopción debe detectar primera persona indebida y dejar el correcto intacto; no corregir todas las respuestas. Doce EOS, saltos de línea efectivos verificados, no literales escapados. No observaciones reales ni aceptación humana en estos fixtures.'),
]
all_folders = ['astra-compound-product577']
for name, count, conclusion in native_specs:
    private = local / ('C03-' + name + '-private')
    out = base / ('astra-' + name)
    responses = rows(private / 'responses.jsonl')
    requests = rows(private / 'requests.jsonl')
    assert len(responses) == len(requests) == count
    assert all(r['response']['choices'][0]['finish_reason'] == 'stop' for r in responses)
    lines = ['# ' + name, '', conclusion, '']
    for request, response in zip(requests, responses, strict=True):
        assert request['case'] == response['case'] and request['profile'] == response['profile']
        lines += [f'## {response["case"]} / {response["profile"]}', '', response['response']['choices'][0]['message']['content'], '', '```json', json.dumps(request['payload'], ensure_ascii=False, indent=2), '```', '']
    (private / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    (out / 'RESULT.md').write_text('# ' + name + '\n\n' + conclusion + '\n\nSólo nativo. Sin fuente/runtime/encuesta modificados; recursos enRESOURCES.json, informe íntegro privado sellado.\n', encoding='utf-8', newline='\n')
    write(out / 'RESULT.json', {'native_finals': count, 'production_adoption': False, 'conclusion': conclusion, 'private_report_sha256': sha(private / 'RESULT.md'), 'resources': read(out / 'RESOURCES.json')})
    all_folders.append('astra-' + name)
for name in all_folders:
    out = base / name
    write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
    with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(f'/artifacts/comprobaciones/C03/{name}/** -text\n')
note = '# Handoff C03 — evidencia580, fuente581 pendiente\n\n' + compound_note.split('\n', 1)[1] + '''
578 feedback con borrador corrige actor pero greedy rompe gramática;579 perfil oficial seed0 corrige los cuatro originales;580 extiende a seis fixtures sintéticos, corrige tres primeras personas y preserva controlesEN. Corregir el controlES ya correcto degrada el trato: activar sólo ante primera persona indebida demostrada por hechos CPU. Sin código de reparación adoptado todavía. Próximo581: ampliar guarda de composición acotada a observación CPU, reusar reintento existente con borrador rechazado y feedback, perfil cualificado Qwen2507 seed0; mantener máximo de intentos y todas las guardas de hechos. El tercer reintento genérico obliga First person: el caso CPU debe conservar feedback y nunca recibir esa orden contraria. No nueva ruta visible ni plantilla. Probar controles que no deben reintentarse, otros modelos, hechos incorrectos y agotamiento honesto; después producto real.

Fuente vigente022416a0 (576) publicada y verificada577. Guardas actuales wrong_actor sólo cubren capacidades/conectividad; no reutilizar su hint online para CPU. Datos físicos574 publicadosad6d9a1a, reales8/16; H0007 continúa abierto por sujeto en575. Encuesta12/730/0,742/rev1248 intactos; BAXY manual cerrado; ninguna decisión pendiente del dueño. Main5f572ee1b48cb5e2543ee5e06510e51057c9c845 intacto. Fuente576:2651pass+121subtests/0skip,1632pass/1STTskip ambiental,Fast verde11,36s. Árbol Python9b75b8a888b69ddffdd90bd07d3acd3ea5fed2add9ef513fde1a57453ecfbeb7/403.

Recursos nativos578–580 GPU3497,559MiB, RAM720,598/720,195/725,414MiB,5,547/5,625/7,140s; sin nueva promoción de modelo. Pendientes otros defectos CPU/GPU/unidades/memoria/progreso/curiosidades, encuesta y ocho rutas, UI real, loopback íntegro/AEC como supresión, consumo conjunto, aceptación y Full final. Full526 original rojo reparado en dueñas528–531, nunca presentar como Full verde. C08 humano sólo evidencia. No procesos pendientes de577–580.
'''
(base / 'HANDOFF.md').write_text(note, encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
state = read(base / 'RELEVO_ACTIVO.json')
state.update(checkpoint='580: product577 nine correct; native CPU draft repair promising only after first-person defect. Source581 not yet implemented; survey12/730/0.', continuation='Implement scoped CPU actor guard + existing bounded draft-aware retry with qualified sampling; test and verify actual product. C03 remains active.', publishedSourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(), confirmedAtUtc=datetime.now(timezone.utc).isoformat())
write(base / 'RELEVO_ACTIVO.json', state)
print('577–580 adjudicated; source581 pending, survey12/730/0.')
