"""Export captured answers and explicit manual judgements; no inference is run."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'

def literal(value):
    fence = '`' * max(3, max((len(x) + 1 for x in re.findall(r'`+', value)), default=3))
    return f'{fence}text\n{value}\n{fence}\n'

def link(path, label):
    return f'[{label}](<{path.as_posix()}>)'

def save(report, body, sources, count):
    text = '\n'.join(body) + '\n'
    report.write_text(text, encoding='utf-8')
    manifest = {'responses': count, 'verbatimChecked': True,
                'reportSha256': hashlib.sha256(report.read_bytes()).hexdigest(),
                'sources': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    report.with_suffix('.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(report), 'responses': count, 'verbatimChecked': True}, ensure_ascii=False))

folder = BASE / 'astra-lora-pilot2-evaluation'
source = folder / 'replies.jsonl'
rows = [json.loads(x) for x in source.read_text(encoding='utf-8').splitlines()]
assert len(rows) == 54
old_manifest = json.loads((BASE / 'PRUEBAS_AJUSTE_C03.manifest.json').read_text(encoding='utf-8'))
base_pass = set(old_manifest['passed']['base']) | {'compound-heldout-0-es', 'compound-heldout-1-es', 'compound-heldout-1-en'}
pilot_fail = {
    'heat-metal-en': 'Añade transferencia a una mano sin que se indique contacto y no explica la conducción del metal.',
    'heat-metal-mixed': 'Cambia la cuchara preguntada por un cuchillo.',
    'audio-holdout-1-mixed': 'Conserva los hechos, pero responde sólo en español.',
    'previous-t8': 'Responde sólo en español pese a la petición mixta.',
    'previous-t10': 'Explicación pertinente, pero sólo en español.',
    'previous-t15': 'Sólo español y definición poco informativa de archivo como un dato.',
}
base_new_fail = {
    'compound-heldout-0-en': 'Datos conservados, pero redacción como campos técnicos; no cumple la naturalidad exigida por C03.',
    'compound-heldout-0-mixed': 'Sólo español; el préstamo muteado no constituye frases en ambos idiomas.',
    'compound-heldout-1-mixed': 'Sólo español; el préstamo muteado no constituye frases en ambos idiomas.',
}
old_notes = {}
for line in (BASE / 'astra-lora-pilot-evaluation/ADJUDICACION.md').read_text(encoding='utf-8').splitlines():
    cells = [x.strip() for x in line.split('|')]
    if len(cells) == 6 and cells[1] == 'base': old_notes[cells[2]] = cells[4]
body = ['# C03 — segundo ajuste: preguntas y respuestas literales\n',
        '**54 respuestas: 27 casos con base y 27 con adaptador v2. Diagnóstico, no aceptación.**\n',
        'Adjudicación manual: base 10/27; adaptador 21/27. En los 18 casos reservados de desarrollo: '
        '8/18 y 15/18. No es un porcentaje de completitud del goal. Los datos de entrenamiento son '
        'sintéticos; las respuestas de abajo proceden del modelo local y no se han corregido.\n',
        'Mejoran los resultados compuestos, pero persisten fallos de idioma y precisión. '
        '**Adaptador no promovido**: el recorrido integrado posterior sigue fallando.\n',
        ' · '.join(link(folder / name, name) for name in ['PREREG.json', 'RESULT.json', 'replies.jsonl']) + '\n']
adj = ['# Adjudicación individual — segundo piloto\n',
       'Manual, posterior a la captura. Diagnóstico directo; no son nuevas observaciones del PC.\n',
       '| Variante | Caso | Resultado | Motivo |\n|---|---|---|---|']
counts = {'base': 0, 'pilot_lora': 0}
for row in rows:
    variant, identifier = row['variant'], row['id']
    ok = identifier in base_pass if variant == 'base' else identifier not in pilot_fail
    note = ('Responde de forma útil y fiel, en el idioma solicitado.' if ok else
            (base_new_fail.get(identifier) or old_notes[identifier]) if variant == 'base' else pilot_fail[identifier])
    verdict = 'APROBADO' if ok else 'NO APROBADO'
    counts[variant] += ok
    answer = row['response']['choices'][0]['message']['content']
    body += [f'## {variant} · {identifier}\n', '**Entrada literal**\n', literal(row['request']),
             '**Respuesta literal**\n', literal(answer), f'**{verdict}:** {note}\n']
    adj.append(f'| {variant} | {identifier} | {verdict} | {note} |')
assert counts == {'base': 10, 'pilot_lora': 21}, counts
(folder / 'ADJUDICACION.md').write_text('\n'.join(adj) + '\n', encoding='utf-8')
save(BASE / 'PRUEBAS_AJUSTE_2_C03.md', body, [source], 54)

folder = BASE / 'astra-lora-pilot2-product'
source = folder / 'paired.json'
rows = json.loads(source.read_text(encoding='utf-8-sig'))
assert len(rows) == 21
fail = {
    't5': 'Hora contradictoria: tres y veintitrés no corresponde a 13:23. El verificador se corrigió después de esta captura; este fallo histórico sigue siendo fallo.',
    't6': 'Conserva hora y audio, pero responde sólo en español a una petición mixta.',
    't7': 'Saluda, pero duplica la bienvenida en ambos idiomas; no cumple la naturalidad sin traducción repetida.',
    't8': 'Explica el concepto más amplio de criptografía y presenta sólo autorizados como garantía, sin explicar la transformación con clave.',
    't9': 'Reduce una copia de seguridad a un archivo; puede contener múltiples archivos u otros datos.',
    't10': 'Redacción española incorrecta: mantiene que objetos caigan.',
    't13': 'Se pidieron dos oraciones; entrega una sola, unida con punto y coma.',
    't15': 'Archivo como objeto no explica la diferencia; una carpeta puede estar vacía.',
}
notes = {
    't1': 'Hora fiel al reloj observado.', 't2': 'Conserva hora, volumen y audio no silenciado.',
    't3': 'Hora fiel y respuesta en inglés.', 't4': 'Hora y audio correctos en inglés.',
    't11': 'Respeta la petición negativa; no anuncia ni propone abrir Paint.',
    't12': 'Capital correcta.', 't14': 'Explicación correcta de la menor densidad del hielo.',
    't16': 'Fiel a la lectura: tasks=[], count=0 en el perfil de prueba; no se extrapola a otras cuentas o perfiles.',
    't17': 'Identifica el cierre solicitado y ofrece confirmar o cancelar.',
    't18': 'Describe la cancelación; el cierre no se ejecuta.',
    't19': 'Nueva solicitud y nueva confirmación ligada a la ventana resuelta.',
    't20': 'Cierre real verificado: app.close, windowClosed=true; la fixture no necesitó limpieza externa.',
    't21': 'Nueva lectura correcta tras finalizar la acción, en el mismo recorrido.',
}
# Explicit owner adjudication supersedes our overly strict interpretation.
for identifier in ['t6','t7','t8','t9']:
    fail.pop(identifier)
    notes[identifier] = 'APROBADO expresamente por el dueño: respuesta útil y suficientemente sencilla; ver ACLARACION_DUENO_2026-09-06.md.'
body = ['# C03 — las pruebas más recientes, sin corregir las respuestas\n',
        '**C03 sigue EN_CURSO. Esta captura publicó 21 respuestas: 17 aprobadas y 4 no aprobadas según revisión manual.** '
        'Son pruebas de desarrollo repetidas, no los 100 turnos nuevos de aceptación.\n',
        'Se ejecutó el recorrido integrado con Qwen3-4B y un adaptador experimental v2, '
        'mediante conductor y una ventana vacía propia. No equivale a verificar toda la interfaz con `py main.py`. '
        'El modelo registrado del producto sigue intacto. Pico de VRAM: 3519,56 MiB, dentro del techo de 4096 MiB.\n',
        'Cada entrada es el mensaje enviado y cada respuesta es el final capturado, incluyendo errores. '
        'Los prompts internos, hechos y borradores rechazados están en la auditoría enlazada.\n',
        ' · '.join(link(folder / name, name) for name in ['paired.json', 'compose-audit.jsonl', 'RESULT.json']) + '\n',
        link(BASE/'ACLARACION_DUENO_2026-09-06.md', 'Aclaración del dueño: cuatro aprobaciones que corrigen la rúbrica anterior')+'\n', '## Conversación integrada\n']
adj = ['# Adjudicación — recorrido integrado del segundo piloto\n',
       '21 publicados; 17 aprobados y 4 no aprobados tras aclaración del dueño. Antes: 13/21; no es una mejora del modelo. Desarrollo, no aceptación.\n',
       '| Turno | Resultado | Motivo |\n|---|---|---|']
for row in rows:
    identifier = row['turnId']
    note = fail.get(identifier) or notes[identifier]
    verdict = 'NO APROBADO' if identifier in fail else 'APROBADO'
    body += [f'### {identifier}\n', '**Entrada literal**\n', literal(row['request']),
             '**Respuesta literal**\n', literal(row['final']), f'**{verdict}:** {note}\n']
    adj.append(f'| {identifier} | {verdict} | {note} |')
(folder / 'ADJUDICACION.md').write_text('\n'.join(adj) + '\n', encoding='utf-8')

replay = BASE / 'astra-word-clock-replay/replies.jsonl'
body += ['## Reproducción del fallo de hora tras corregir el verificador\n',
         'Se reutilizaron hechos históricos de las 13:23. En el primer caso se inyectó el borrador '
         'contradictorio de t5: fue rechazado con `reversed_result`; el reintento sí lo generó el modelo local. '
         'Los otros tres casos fueron generaciones locales normales, sin efectos sobre el PC.\n',
         link(replay.parent / 'compose-audit.jsonl', 'Auditoría de rechazo y reintento') + '\n']
for line in replay.read_text(encoding='utf-8').splitlines():
    row = json.loads(line)
    note = {'injected-contradiction': 'Hora corregida, pero repetida y sólo en español: no aprobado.',
            'es': 'Hora correcta en español: aprobado.', 'en': 'Hora correcta en inglés: aprobado.',
            'mixed': 'Hora correcta, pero repite la traducción completa: no aprobado.'}[row['case']]
    body += [f"### Reproducción · {row['case']}\n", '**Entrada literal**\n', literal(row['request']),
             '**Respuesta literal**\n', literal(row['response']), note + '\n']
body += ['## Pruebas automáticas y pendientes\n',
         '| Comprobación | Resultado | Evidencia |\n|---|---|---|',
         f"| `pytest tests/test_c03_request_preservation.py tests/test_compose_contract.py -q` | 125 pass | {link(ROOT/'scratchpad/c03-word-clock-owner-final.log', 'log')} |",
         f"| `scripts/test_source_quality.ps1 -Mode Fast` | Verde; compilación sin errores ni advertencias | {link(ROOT/'scratchpad/c03-word-clock-fast.log', 'log')} |",
         '| Full final | Pendiente | El candidato todavía falla en conducta visible |\n',
         'Faltan calidad consistente de desarrollo, los 100 turnos nuevos adjudicados, los ocho recorridos '
         'completos, recuperación final, UI real, runtime reproducible registrado y Full verde final. '
         'No se certifican los goals posteriores con esta captura.\n',
         '## Más evidencia y contexto\n',
         '\n'.join('- ' + link(BASE / name, label) for name, label in [
             ('PRUEBAS_C03_PARA_EMMAN.md', 'Archivo completo de conversaciones registradas'),
             ('PRUEBAS_AJUSTE_2_C03.md', '54 respuestas comparadas del segundo ajuste'),
             ('PRUEBAS_AJUSTE_3_C03.md', '78 respuestas posteriores de formato: mejora parcial y regresiones de contenido; no promovido'),
             ('PRUEBAS_ESCALA_C03.md', '27 respuestas de la escala descartada'),
             ('CHECKPOINT.md', 'Estado y siguiente acción para reanudar')])]
save(BASE / 'PRUEBAS_RECIENTES_C03.md', body, [source, replay], 25)
