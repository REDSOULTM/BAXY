"""Verbatim export and individual adjudication of the completed Gemma diagnostics."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/comprobaciones/C03'
common = {
    't8': 'No respeta la mezcla de idiomas: contesta sólo en inglés.',
    't9': 'No respeta la petición explícita de spanglish: contesta sólo en inglés.',
    't10': 'No respeta la mezcla de idiomas: contesta sólo en inglés.',
    't13': 'Explicación pertinente en inglés, en dos oraciones.',
    't14': 'Explica la menor densidad del hielo en español; la comparación de peso debe entenderse a igual volumen.',
    't15': 'Distingue archivo y carpeta, pero ignora la petición explícita de spanglish.',
    't2': 'Conserva hora, volumen y ausencia de silencio; no afirma haberlos cambiado.',
    't4': 'Conserva la hora y el volumen solicitados, en inglés.',
    't6': 'Conserva los datos, pero responde sólo en español; no satisface spanglish.',
}
overrides = {
    ('standard_base','t8'): 'Sólo inglés; además generaliza el uso de la misma clave, que no cubre el cifrado asimétrico.',
    ('inherited_lora','t2'): 'Omite si el audio está silenciado: sólo comunica hora y volumen.',
    ('inherited_lora','t6'): 'Omite el estado de silencio y no produce spanglish natural; «Es las» es incorrecto.',
    ('standard_base_thinking','t8'): 'Sólo inglés; además presenta el cifrado con garantías excesivas de seguridad.',
    ('standard_base_thinking','t9'): 'La mezcla «A backup, es when» es forzada y no logra la naturalidad exigida.',
    ('standard_base_thinking','t10'): 'Sí mezcla idiomas, pero equipara tamaño con intensidad de atracción sin aclarar masa o distancia. No se acepta la precisión conceptual.',
    ('standard_base_thinking','t6'): 'Datos conservados; «muteado» aislado no satisface el contrato de combinar frases de ambos idiomas.',
    ('published_baxy','t9'): 'Sólo inglés y termina con una garantía excesiva: «It keeps everything safe».',
    ('published_baxy','t6'): 'Copia una intención de redacción en vez de contestar: omite hora, volumen y estado del audio.',
}
passes = {
    'standard_base': {'t13','t14','t2','t4'},
    'inherited_lora': {'t13','t14','t4'},
    'standard_base_thinking': {'t13','t14','t2','t4'},
    'published_baxy': {'t13','t14','t2','t4'},
}
def literal(value):
    marks = '`' * max(3, max((len(m)+1 for m in re.findall(r'`+',value)),default=3))
    return f'{marks}text\n{value}\n{marks}\n'

body = ['# C03 — pruebas literales de los modelos Gemma heredados\n',
        '**36 respuestas directas del modelo; ninguna de estas corridas acredita aceptación del producto.** '
        'Las nueve preguntas se repiten para comparar configuraciones. Los hechos de estado provienen de '
        'una captura verificada anterior; no son nuevas lecturas del PC.\n',
        'Las evaluaciones son adjudicación individual del asistente, realizada después de leer las respuestas. '
        'Criterios: utilidad, fidelidad, idioma solicitado y naturalidad. Un final generado no equivale a aprobado. '
        'No se ha promovido ninguno de estos candidatos.\n',
        '| Configuración | Aprobadas en este diagnóstico |\n|---|---|',
        *[f'| {variant} | {len(ids)}/9 |' for variant,ids in passes.items()],
        '\nEl control conserva los mismos payloads y sampler. La variante thinking permite hasta 1024 tokens '
        'totales y activa razonamiento nativo; las otras lo desactivan. Los payloads completos y las huellas '
        'están en PREREG.json. Aquí se muestra sólo el contenido final del modelo, no su canal interno.\n']
manifest = {'responses': 0, 'sources': []}
checks = []
for name, expected in [('astra-gemma-inherited-ready',18),('astra-gemma-standard-thinking',9),('astra-gemma-published',9)]:
    folder = BASE/name
    source = folder/'replies.jsonl'
    rows = [json.loads(line) for line in source.read_text(encoding='utf-8').splitlines()]
    assert len(rows) == expected
    body += [f'## {name}\n', ' · '.join(f'[{n}](<{(folder/n).as_posix()}>)' for n in ['PREREG.json','RESULT.json','replies.jsonl'])+'\n']
    adjudication = ['# Adjudicación individual — '+name+'\n',
                    'Diagnóstico directo, no aceptación C03. Evaluación manual del asistente; hechos históricos.\n',
                    '| Variante | Turno | Resultado | Motivo |\n|---|---|---|---|']
    for row in rows:
        variant, turn = row['variant'], row['turnId']
        verdict = 'APROBADO' if turn in passes[variant] else 'NO APROBADO'
        note = overrides.get((variant,turn), common[turn])
        request = row['request']
        response = row['response']['choices'][0]['message']['content']
        body += [f'### {variant} · {turn}\n','**Entrada literal**\n',literal(request),
                 '**Respuesta literal**\n',literal(response),f'**{verdict}:** {note}\n']
        adjudication.append(f'| {variant} | {turn} | {verdict} | {note} |')
        checks += [literal(request),literal(response)]
    (folder/'ADJUDICACION.md').write_text('\n'.join(adjudication)+'\n',encoding='utf-8')
    manifest['responses'] += len(rows)
    manifest['sources'].append({'path':source.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
report = BASE/'PRUEBAS_GEMMA_C03.md'
text = '\n'.join(body)+'\n'
assert manifest['responses'] == 36 and all(value in text for value in checks)
report.write_text(text,encoding='utf-8')
assert report.read_text(encoding='utf-8') == text
manifest['reportSha256'] = hashlib.sha256(report.read_bytes()).hexdigest()
report.with_suffix('.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'responses':36,'verbatimChecked':True,'report':str(report)},ensure_ascii=False))
