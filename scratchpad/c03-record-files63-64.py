from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
report = base / 'PRUEBAS_ARCHIVOS63_64.md'
assert not report.exists()
lines = ['# C03 — límite de consulta y fallo de recuperación63–64', '',
         'Ambos paneles:2/5 útiles. Controles técnicos consumidos, no humanos reservados ni UI/audio. '
         '63 conserva la causa real del primer pedido, pero las lecturas siguientes se rechazan. '
         '64 reproduce con captura HTTP de sólo observación. No aprobación integral del cambio.', '']
paths = ['src/Baxy.Providers.Windows/Filesystem/LocalFilesystemProvider.cs',
         'tests/Baxy.Providers.Windows.Tests/LocalFilesystemProviderTests.cs',
         'tests/Baxy.Integration.Tests/MvpLocalStatefulHandlerMatrixTests.cs']
for name in ('files63-absolute', 'files64-wire'):
    directory = base / ('astra-' + name)
    lines += [f'## {name}', '', (directory / 'RESULT.json').read_text(encoding='utf-8'), '']
    for turn in json.loads((directory / 'paired.json').read_text(encoding='utf-8')):
        lines += [f"### {turn['turnId']}", '', f"Entrada: {turn['request']}", '',
                  f"Final ({turn['terminal']}): {turn['final']}", '',
                  ('Útil: causa específica verificada, sin afirmar inexistencia del archivo.' if turn['turnId'] == 't1'
                   else 'Útil: hora verificada, sesión disponible.' if turn['turnId'] == 't5'
                   else 'No útil: negativa sin causa específica ante lectura del catálogo o pérdida del límite conocido.'), '']
    lines += [f'[Hechos, borradores, vetos y estado posterior](astra-{name}/paired.json).', '']
    paths += [f'artifacts/comprobaciones/C03/astra-{name}/{f}' for f in ('RESULT.json', 'PREREG.json', 'paired.json')]
paths += ['artifacts/comprobaciones/C03/astra-files64-wire/wire-29264.jsonl']
lines += ['El selector elige search para leer en t2/t3; domain_grounding rechaza esa operación insuficiente. '
          'T4 no propone operación. El catálogo conserva read.text. La causa del selector se compara en65 '
          'con los mismos cuatro payloads nativos; t5 usa ruta determinista y no tiene paquete AUTO.', '',
          'Proveedor:8 pass/0 skips/119ms; integración:152 pass/0 skips/8s. Core AOT publicado6368exit0, '
          'hash fe2c1cfc351abf78bd4d5080fd651eaec2e5915f83b82a30613a57df40e48fed. '
          'Modelo/registro sin cambios. Fast63/Full pendientes; Full no corresponde durante reparación.', '']
report.write_text('\n'.join(lines), encoding='utf-8')
paths.append(str(report.relative_to(root)).replace('\\', '/'))
(base / 'TRAMO63_64_PINS.json').write_text(json.dumps({'scope': 'Provider63 candidate and failing product captures, not acceptance',
    'files': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}}, indent=2), encoding='utf-8')
print('Recorded63–64')
