from pathlib import Path
import hashlib
import json
import datetime

root = Path(__file__).resolve().parents[1]
ui = root / 'src/Baxy.FieldUi'
excluded = {'.gitignore', 'ORIGIN.md', 'README.md', 'tsconfig.node.json', 'vite.config.ts'}
files = sorted((p for p in ui.rglob('*') if p.is_file()
    and p.relative_to(ui).as_posix() not in excluded
    and 'node_modules' not in p.relative_to(ui).parts), key=lambda p: p.relative_to(ui).as_posix())
assert len(files) == 38, [(p.relative_to(ui).as_posix()) for p in files]
digest = hashlib.sha256()
for p in files:
    digest.update(p.relative_to(ui).as_posix().encode() + b'\0' + p.read_bytes() + b'\0')
seal = digest.hexdigest().upper()
test = root / 'tests/Baxy.Integration.Tests/MainWindowShellContractTests.cs'
text = test.read_text(encoding='utf-8')
old = '0F6DCDA5DCF7DFA8A89C64763EF4E75067967977C5673121197825F8EB0E1C71'
assert text.count(old) == 1
test.write_text(text.replace(old, seal), encoding='utf-8', newline='\n')
with (ui / 'ORIGIN.md').open('a', encoding='utf-8') as stream:
    stream.write('\n## Reapertura de progreso de 2026-09-07\n\n'
        'C03 UI102 localiza una etiqueta de progreso oculta por el borrador del input.\n'
        'FieldCenter usa una región role=status existente antes de recibir la etiqueta;\n'
        'retira su uso como placeholder y conserva el lector y su borrado terminal.\n'
        'Bridge, autoridades y grafo de dependencias conservados. Build deliberado\n'
        'pnpm build; evidencia antes/después en C03/PRUEBAS_UI102.md y ASTRA-TRAMO-103.md.\n\n')
    for p in files:
        if p.is_relative_to(ui / 'dist'):
            stream.write(f'- `{p.relative_to(ui).as_posix()}`: `{hashlib.sha256(p.read_bytes()).hexdigest().upper()}`\n')
    stream.write(f'- sello conjunto source + payload: `{seal}`\n')
base = root / 'artifacts/comprobaciones/C03'
checkpoint = base / 'CHECKPOINT.md'
text = checkpoint.read_text(encoding='utf-8')
start, end = text.index('## Estado actual'), text.index('## Decisiones y pruebas')
current = '''## Estado actual y siguiente acción

UI102 terminado: ocho finales técnicos útiles/fieles, bienvenida también.
PRUEBAS_UI102.md conserva literales y capturas. Monitor4385exit0:787,91s,
GPU3493,98828125MiB,RAM5737,51953125MiB; arranque excluido. App16164 terminado
con ruta verificada, sin procesos propios activos. Sin audio ni cierre grácil.

101 sí compone temprano antes del final, pero cinco cuadros intermedios UI102
caso5 muestran sólo Thinking y el draft. Primera pérdida en FieldCenter:
bootStage.label se usaba sólo como placeholder mientras /turn conserva draft.
Fuente103 mueve la etiqueta al status encima del input y retira el placeholder
de progreso, con el mismo lector y limpieza. No otra capa/bridge/modelo/prompt.
ADR-0008 reabierto; source/dist regenerados deliberadamente y sellados en ORIGIN.
ASTRA-TRAMO-103.md: herencia, contraste MDN, hipótesis y criterio previo.

101 validado:1179pytest pass/0skips;233integración pass/0skips;Fast verde.
103: pnpm build exit0; pendientes pruebas dueñas, Fast y UI104 con los mismos
ocho casos. No Full durante reparación. Monitor y launcher UI102 finalizados.
Sky201388 ya no sirve; obtener ventana nueva sólo tras py main.py. Qwen3.5
override/wake0, sin promoción. Reserva humana100/audio/runtime siguen pendientes.

'''
text = text[:start] + current + text[end:]
text = text.replace('fuente101; UI100 finales8/8; progreso integrado por verificar',
    'fuente103; UI102 finales8/8; progreso visible por verificar')
tail = text.find('\nUI102 ACTIVO:')
if tail >= 0:
    text = text[:tail] + '\n'
checkpoint.write_text(text, encoding='utf-8')
with (base / 'HANDOFF.md').open('a', encoding='utf-8') as stream:
    stream.write('\n## Relevo más reciente —103\n\n' + current.split('\n\n', 1)[1])
relay_path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(relay_path.read_text(encoding='utf-8-sig'))
relay.update(checkpoint='Fuente103 presentación de progreso; UI102 ocho finales útiles; C03 EN_CURSO',
    continuation='Sin procesos propios activos. Build UI103 exit0 y sello actualizado. Pruebas dueñas/Fast/UI104 pendientes; no Full.',
    confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
relay_path.write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'files': len(files), 'seal': seal}))
