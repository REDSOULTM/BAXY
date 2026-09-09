from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
ui = root / 'src/Baxy.FieldUi'
excluded = {'.gitignore', 'ORIGIN.md', 'README.md', 'tsconfig.node.json', 'vite.config.ts'}
files = []
for folder, dirs, names in os.walk(ui):
    dirs[:] = [name for name in dirs if name != 'node_modules']
    for name in names:
        path = Path(folder) / name
        if path.relative_to(ui).as_posix() not in excluded:
            files.append(path)
files.sort(key=lambda p: p.relative_to(ui).as_posix())
assert len(files) == 38, len(files)
digest = hashlib.sha256()
for path in files:
    digest.update(path.relative_to(ui).as_posix().encode() + b'\0' + path.read_bytes() + b'\0')
seal = digest.hexdigest().upper()
test = root / 'tests/Baxy.Integration.Tests/MainWindowShellContractTests.cs'
old = '5396C5B4C33FAA3603CED416017EED5D44E0B03949A8C82D920C43F25BAF3687'
text = test.read_text(encoding='utf-8-sig')
assert text.count(old) == 1
test.write_text(text.replace(old, seal), encoding='utf-8', newline='\n')
with (ui / 'ORIGIN.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n## Reapertura de error de composición de 2026-09-07\n\n'
        'C03 UI107 muestra composition_failed con Idle tras avería real. Fuente108\n'
        'añade error al estado consumido por el lector existente: grafo Error y\n'
        'etiqueta Response error en una región alert persistente, sin prosa de\n'
        'respuesta ni movimiento de foco. La App conserva diagnóstico tipado y\n'
        'proyecta la cola pendiente como thinking. ADR-0008 reabierto; pnpm build\n'
        'deliberado con las mismas dependencias. Pruebas en ASTRA-TRAMO-108.md.\n\n')
    for path in files:
        if path.is_relative_to(ui / 'dist'):
            stream.write(f'- `{path.relative_to(ui).as_posix()}`: `{hashlib.sha256(path.read_bytes()).hexdigest().upper()}`\n')
    stream.write(f'- sello conjunto source + payload: `{seal}`\n')
print(json.dumps({'files':len(files), 'seal':seal}))
