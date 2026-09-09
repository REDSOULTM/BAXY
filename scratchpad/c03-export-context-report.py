"""Export the two existing context diagnostics without running inference."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
notes = {
    ('full', 't8'): 'Explicación básica pertinente; mezcla de idiomas mínima (Encryption).',
    ('user_only', 't8'): 'Responde en español; sustituye cifrado por el concepto más amplio de criptografía y alarga la explicación.',
    ('full', 't9'): 'Explica correctamente la finalidad de la copia; spanglish limitado a backup.',
    ('user_only', 't9'): 'La finalidad es reconocible, pero «siempre» en un lugar seguro no está garantizado. Mezcla mínima.',
    ('full', 't10'): 'Analogía imprecisa: gravedad no equivale a pegarse y la explicación de los planetas es insuficiente.',
    ('user_only', 't10'): 'Falla el tema: responde sobre copias de seguridad a una pregunta sobre gravedad.',
    ('full', 't13'): 'Explicación pertinente en inglés y en dos oraciones.',
    ('user_only', 't13'): 'El contenido básico es pertinente, pero cambia al español.',
    ('full', 't14'): 'Identifica la menor densidad; «más ligero» necesita la comparación a igual volumen.',
    ('user_only', 't14'): 'Explica correctamente la menor densidad y aclara peso por volumen.',
    ('full', 't15'): 'Definición inicial circular y omisión de la petición explícita de spanglish.',
    ('user_only', 't15'): 'Definición inicial circular y omisión de la petición explícita de spanglish.',
    ('isolated', 't8'): 'Contenido básico pertinente, pero sólo inglés y extensión excesiva frente a las instrucciones de la prueba.',
    ('isolated', 't9'): 'Finalidad pertinente; mezcla mínima limitada a backup, sin mejora clara de naturalidad.',
    ('isolated', 't10'): 'Explicación física imprecisa y analogía final sin sentido; no respeta la mezcla de idiomas.',
    ('isolated', 't13'): 'Explicación pertinente en inglés y en dos oraciones.',
    ('isolated', 't14'): 'La densidad está bien explicada, pero añade una afirmación falsa de exclusividad en la naturaleza.',
    ('isolated', 't15'): 'Circular, sólo español pese a pedir spanglish, y afirma una restricción universal injustificada sobre guardar archivos.',
}

def fence(value):
    marks = '`' * max(3, max((len(m) + 1 for m in re.findall(r'`+', value)), default=3))
    return f'{marks}text\n{value}\n{marks}'

body = [
    '# C03: preguntas y respuestas del diagnóstico de contexto\n',
    '**18 respuestas directas del modelo local; no son turnos de aceptación ni ejecuciones completas de BAXY.** '
    'Se exportan registros existentes sin ejecutar nuevas pruebas.\n',
    'Se comparó el historial completo acotado (full), el historial con sólo mensajes del usuario (user_only), '
    'y la pregunta actual sin historial (isolated). Se conservaron las instrucciones de sistema. '
    'Los payloads de la primera comparación fueron reconstruidos a partir de corpus-warm usando el límite '
    'de 12 mensajes de la interfaz y el método chat del producto; no son una captura HTTP original.\n',
    'Se utilizó Qwen3-4B-Instruct-2507 Q4_K_M, seed 0. Los PREREG enlazados conservan los payloads internos '
    'y las huellas de fuente/modelo. Las evaluaciones siguientes son revisión individual del asistente, '
    'posterior a la ejecución, sin convertir publicación en acierto.\n',
    '**Decisión:** no adoptar ninguna poda del historial. Quitar mensajes no resuelve de forma consistente '
    'idioma o fidelidad y llega a cambiar el tema solicitado. No se modificó el historial del producto.\n',
]
manifest = {'sources': [], 'responses': 0}
checks = []
for folder_name, expected in [('astra-history-ablation-ready', 12), ('astra-history-isolated', 6)]:
    folder = BASE / folder_name
    source = folder / 'replies.jsonl'
    rows = [json.loads(line) for line in source.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    assert len(rows) == expected
    result = json.loads((folder / 'RESULT.json').read_text(encoding='utf-8-sig'))
    body += [f'## {folder_name}\n',
             f"Duración: {result['elapsedSeconds']} s. Pico GPU registrado: {result['gpuPeakMiB']:.2f} MiB.\n",
             ' · '.join(f'[{name}](<{(folder/name).as_posix()}>)' for name in ['PREREG.json', 'replies.jsonl', 'RESULT.json']) + '\n']
    for row in rows:
        request = row['request']
        reply = row['response']['choices'][0]['message']['content']
        body += [f"### {row['turnId']} · {row['variant']}\n", '**Entrada literal**\n', fence(request),
                 '\n**Respuesta literal del modelo**\n', fence(reply),
                 '\n**Evaluación:** ' + notes[(row['variant'], row['turnId'])] + '\n']
        checks.extend([fence(request), fence(reply)])
    manifest['sources'].append({'path': source.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'responses': len(rows)})
    manifest['responses'] += len(rows)
report = BASE / 'PRUEBAS_CONTEXTO_C03.md'
text = '\n'.join(body) + '\n'
assert manifest['responses'] == 18 and all(value in text for value in checks)
report.write_text(text, encoding='utf-8')
assert report.read_text(encoding='utf-8') == text
manifest['reportSha256'] = hashlib.sha256(report.read_bytes()).hexdigest()
report.with_suffix('.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'responses': 18, 'verbatimChecked': True, 'path': str(report)}, ensure_ascii=False))
