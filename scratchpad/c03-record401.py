from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / 'artifacts/comprobaciones/C03/astra-required-fact401'
rows = [json.loads(line) for line in (folder / 'replies.jsonl').open(encoding='utf-8')]
assert len(rows) == 16
resources = json.loads((folder / 'resources.json').read_text())
assert resources['completed'] and not resources['violations']
report = '''#401 — valor observado retenido por el contrato existente

Ocho casos fijados, dos reales393b y seis controles sintéticos; compositor Python
real con guardas/reintentos, no App/UI/voz/efectos. Primeros payloads baseline
idénticos a393b, comprobados offline y durante inferencia. Sólo requiredFacts
añade el valor único, corto y ya proyectado; vacío/redactado quedan idénticos.

3/8 útiles baseline →5/8 con valor retenido. Mejoran las dos consultasEN de nombre,
sin regresiones en este panel. NombresES siguen mal atribuidos a BAXY y dato
redactado sigue agotando composición hasta cadena vacía en ambos brazos.
No llamar a esto cierre de memoria ni cambiar esa adjudicación por conservar
el literal. Se justifica transportar el dato mediante el contrato compartido,
con prueba dueña de privacidad y ausencia de efecto; sujeto y redacción pendientes.

| Caso | Baseline | Valor retenido | Adjudicación |
|---|---|---|---|
'''
reasons = {'stored-en': 'fallo→útil: deja de negar lectura', 'stored-es': 'fallo→fallo: sujeto BAXY',
           'new-name-en': 'fallo→útil: deja de negar lectura', 'new-name-es': 'fallo→fallo: sujeto BAXY',
           'preference-en': 'útil→útil', 'preference-es': 'útil→útil', 'empty-en': 'útil→útil',
           'redacted-es': 'fallo→fallo: final vacío, no fuga'}
for index in range(0, len(rows), 2):
    a, b = rows[index:index+2]
    report += f"| {a['id']} | {a['answer'] or '[vacío]'} | {b['answer'] or '[vacío]'} | {reasons[a['id']]} |\n"
report += f"\nRecursos: GPU{resources['gpu_peak_mib']}MiB, RAM{resources['ram_peak_mib']}MiB; {resources['seconds']}s. Telemetría disponible, sin infracciones, manifiesto intacto. No aceptación conjunta.\n"
assert not (folder / 'RESULT.md').exists()
(folder / 'RESULT.md').write_text(report, encoding='utf-8')
paths = [folder / name for name in ['PREREG.json', 'replies.jsonl', 'resources.json', 'command.json', 'RESULT.md']]
paths += [root / 'scratchpad/c03-required-fact401.py']
pins = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
(folder / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
source = root / 'artifacts/comprobaciones/C03/astra-required-fact402'
source.mkdir(exist_ok=False)
(source / 'PREREG.json').write_text(json.dumps({
    'utc': datetime.now(timezone.utc).isoformat(),
    'hypothesis': 'Reuse RequiredLiteralFacts for one short nonredacted projected memory read value. Actual401 changed only this fact transport:3/8->5/8 with no new failure, leaving Spanish subjects and redaction unresolved.',
    'scope': 'UserMessagePolicy.CollectStructuredLiterals and owner MemoryAppFlowTests. Only verified successful memory.recall/list records; no generic subject extraction, cache, new prompt, parser or runtime change. Single short value avoids unrelated multi-fact mission scaffold; large/multi/empty/redacted data remain observations without imposing a copied full response.',
    'validation': 'Add owner tests first and record failing baseline. Focal owner then MemoryAppFlow/MemoryOperationProtection/PlannerAppBoundary owners; Fast. No Full until complete C03. Final actual product measurement must use source402, not retain-value injection.',
    'prior_source_sha256': hashlib.sha256((root / 'src/Baxy.App/UserMessagePolicy.cs').read_bytes()).hexdigest()
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
