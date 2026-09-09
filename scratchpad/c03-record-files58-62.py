from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
report = base / 'PRUEBAS_ARCHIVOS56_62.md'
assert not report.exists()
lines = ['# C03 — lectura y causas: tramos56–62', '',
         'Desarrollo técnico consumido. No reserva humana, UI ni audio físico.', '',
         '56 copia la identidad única verificada;57 conserva error de operación;58 acepta modales negativos sin exigir primera persona. '
         'Producto58:3/5 útiles, no cierre de C03.166 integración pass/0 skips/14s;3140 pytest pass/121 subtests/0 skips/45,45s;Fast58 verde, Release16,80s,0 avisos/errores.', '']
paths = ['src/Baxy.App/PlannerExecutionSupport.cs', 'src/Baxy.App/UserMessagePolicy.cs',
         'src/baxy_mind/__main__.py', 'src/baxy_mind/llm.py']
for name, useful in [('files56-identity', {'t2', 't5'}), ('files57-cause', {'t2', 't5'}),
                     ('files58-modal', {'t2', 't3', 't5'})]:
    directory = base / ('astra-' + name)
    result = json.loads((directory / 'RESULT.json').read_text(encoding='utf-8'))
    lines += [f'## {name}', '', f'Resultado: {json.dumps(result, ensure_ascii=False)}', '']
    for turn in json.loads((directory / 'paired.json').read_text(encoding='utf-8')):
        labels = list(dict.fromkeys(e['label'] for e in turn['publicEvents']
                                   if e.get('type') == 'boot_stage' and e.get('label')))
        lines += [f"### {turn['turnId']}", '', f"Entrada: {turn['request']}", '',
                  f"Final ({turn['terminal']}): {turn['final']}", '',
                  f"Útil: {'sí' if turn['turnId'] in useful else 'no'}. Progreso visible: {json.dumps(labels, ensure_ascii=False)}", '']
    lines += [f'[Payloads, borradores y vetos](astra-{name}/paired.json).', '']
    paths += [f'artifacts/comprobaciones/C03/astra-{name}/{f}' for f in ('RESULT.json', 'PREREG.json', 'paired.json')]
lines += ['## Comparaciones nativas59–62', '',
          'Conservan identidad, instrucciones, template y límites de BAXY; se toma la primera respuesta HTTP sin validadores/reintentos. '
          'No son modelo sin wrapper.59 añade scope=sandbox;60 cambia la causa a no matches in the searched scope;61 especifica filesystem sandbox. '
          '62 cambia la hipótesis: fallo tipado antes de buscar una ruta absoluta no admitida por el contrato de búsqueda por nombres. '
          'Es una simulación causal, aún no conducta medida del proveedor.', '']
for name in ('files-scope59', 'files-empty60', 'files-sandbox61', 'files-path62'):
    directory = base / ('astra-' + name)
    lines += [f'### {name}', '', (directory / 'RESULT.json').read_text(encoding='utf-8'), '']
    for raw in (directory / 'posts.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(raw)
        lines += [f"{row.get('turn')} / {row.get('variant', name)}: {row['response']['choices'][0]['message']['content']}", '']
    paths += [f'artifacts/comprobaciones/C03/astra-{name}/{f}' for f in ('RESULT.json', 'PREREG.json', 'posts.jsonl')]
lines += ['Decisión:59 no mejora;60 elimina indisponibilidad inventada pero omite el alcance concreto;61 sólo lo concreta en uno de dos casos. '
          '62 explica la limitación real en ambos casos. Procede validar el error en el proveedor y repetir el producto, sin ampliar acceso ni sustituir rutas por nombres.', '',
          'Contraste actual consultado2026-09-07: [Path.IsPathFullyQualified, .NET10](https://learn.microsoft.com/en-us/dotnet/api/system.io.path.ispathfullyqualified?view=net-10.0) '
          'distingue rutas absolutas de las rooted dependientes del directorio/unidad actual. Se reutiliza esa API, sin parser de rutas propio. '
          'El catálogo actual ya define búsqueda por nombres confinada al sandbox; se conserva ese alcance.', '',
          'Pendientes: progreso que infirió UTF8 del nombre en55, causas de búsquedas vacías normales, validación completa de C03. Ausencia de avisos en58 no demuestra reparación del progreso.', '']
report.write_text('\n'.join(lines), encoding='utf-8')
paths.append(str(report.relative_to(root)).replace('\\', '/'))
(base / 'TRAMO58_62_PINS.json').write_text(json.dumps({'scope': 'Source58 and native59–62 evidence, before provider change; not C03 acceptance',
    'files': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}}, indent=2), encoding='utf-8')
print('Recorded source58 and native59–62')
