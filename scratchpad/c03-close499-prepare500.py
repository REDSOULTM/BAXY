"""Close the completed mind repeat and freeze the reproduced volume morphology defect."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-audio-mind499'
def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
rows = [json.loads(s) for s in (out / 'replies.jsonl').open(encoding='utf-8-sig')]
assert len(rows) == 10
resources = json.loads((out / 'RESOURCES.json').read_text(encoding='utf-8-sig'))
adjudications = []
lines = ['# Mente completa 499', '',
         'Fuente 498, runtime registrado: comparación de regresión, no ranking de capacidad entre modelos. Sólo decisiones, sin ejecutar audio ni interfaz. Los argumentos anotados son expectativas y no resultados de esta fase.', '',
         '| Caso | Respuesta literal | Evaluación |', '|---|---|---|']
for row in rows:
    reply = row['reply']
    context_failure = row['id'] in {'owner46', 'owner51', 'owner51-resumed'}
    knowledge = row['id'] == 'word-meaning'
    status = ('Falla: error de análisis, aclaración distorsionada o incapacidad no probada' if context_failure else
              'Definición parcialmente correcta; prosa interna y ofrece control de micrófono no acreditado' if knowledge else
              'Conserva selección y orden; argumentos y ejecución pendientes')
    adjudications.append({'id': row['id'], 'selection_correct': not context_failure and not knowledge,
                          'knowledge_control': knowledge, 'assessment': status, 'reply': reply})
    literal = reply.get('question') or reply.get('reply') or json.dumps(reply.get('effectOperations'), ensure_ascii=False)
    lines.append(f"| {row['id']} | {literal.replace('|', '/')} | {status} |")
lines += ['', 'El caso owner51-resumed contiene exactamente el formato de MindClarificationPolicy.ResumeObjective. No demuestra que la interfaz alcance esa rama: aún maneja RecoveryFailureCode antes de la reanudación.', '',
          'Primera frontera del caso reanudado: Ponle no figura en _SET_VOLUME_VERB. La comparación pura con Pon conserva ambas operaciones; con Ponle queda la primera cláusula sin resolver y el producto declara unsupported. El selector nativo también formula una incapacidad falsa. Las respuestas estructuradas posteriores terminan por longitud y el fallback inventa que el sistema no respondió; no se ejecutó ningún efecto.', '',
          f"RAM {resources['ram_peak_mib']:.3f} MiB, VRAM {resources['gpu_peak_mib']:.3f} MiB, {resources['seconds']} s. Manifiesto intacto. Seis selecciones correctas, tres fallos contextuales y una respuesta de conocimiento defectuosa; no aceptación de C03.", '']
(out / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8')
write(out / 'ADJUDICATION.json', adjudications)
write(out / 'RESULT.json', {'utc': datetime.now(timezone.utc).isoformat(), 'session': 19054, 'exit': 0,
                           'correct_operation_selections': 6, 'contextual_failures': 3,
                           'knowledge_response_defects': 1, 'resources': resources,
                           'adopted_runtime': False, 'next': 'Source500 volume-setting clitic and incomplete local-device target; preserve guards and real context problem.'})
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
new = base / 'astra-volume-clitic500'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-volume-clitic500-private'
new.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
for name, relative in [('effect_intent-before.py', 'src/baxy_mind/effect_intent.py'),
                       ('test_effect_intent-before.py', 'tests/test_effect_intent.py')]:
    shutil.copy2(root / relative, private / name)
write(new / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'source_before_sha256': sha(root / 'src/baxy_mind/effect_intent.py'),
    'cause': 'Actual resumed owner51 string fails with Ponle, while the same literal with Pon resolves volume and mute. _SET_VOLUME_VERB lacks the valid dative clitic. The no-level clarification grammar also lacks explicit local PC/computer target modifiers.',
    'intervention': 'Extend shared volume-setting head to ponle and preserve missing level for explicit local PC/computer targets. No general history concatenation, compatibility bypass, prompt or runtime changes.',
    'tests': 'Record baseline for new clitic actions, actual resumed string, missing-level local devices, other-device/negative/quoted controls and absent catalog. Then owner suites and Fast after focal green.',
    'limits': 'Does not fix C# pre-resumption failure or contextual typo by itself. No reserve, physical audio, UI or final acceptance.'
})
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = base / name
    text = path.read_text(encoding='utf-8')
    start = text.index('Siguiente:')
    end = text.index('\n\n', start)
    text = text[:start] + ('499 cerrado, sesión 19054 exit 0: seis selecciones correctas, tres fallos contextuales y una definición con prosa interna/alcance de micrófono no acreditado. RAM 1770,824 MiB / VRAM 3497,559 MiB, 56,609 s, sólo mente. Siguiente: fuente 500. Se aisló que la cadena real reanudada reconoce Pon pero pierde Ponle; también falta aclaración de nivel con objeto local pc/computer. PREREG congelado en astra-volume-clitic500. No runtime ni prueba activa.') + text[end:]
    path.write_text(text, encoding='utf-8')
record = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
              checkpoint='Fuente498 validada; mente499 cerrada. Fuente500 preregistrada por clítico Ponle y nivel faltante.',
              continuation='Baseline focal500 antes de editar la fuente; luego dueñas/Fast. Ningún proceso de producto activo. C03 íntegro activo.')
write(base / 'RELEVO_ACTIVO.json', record)
print('499 closed;500 preregistered with before-source and before-tests copies.')
