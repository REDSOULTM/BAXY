from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-progress-pipeline99'
finals = [json.loads(s) for s in (out / 'finals.jsonl').read_text(encoding='utf-8').splitlines()]
lines = ['# C03 — progreso en el compositor completo98/99', '',
    'Ocho finales compatibles con las fases suministradas; entre0,344 y0,969s por '
    'composición. No efectos inventados y posición2/3 conservada. Fuente98 usa '
    'FieldBridge para fase real y descarta avisos obsoletos;99 ejercita Python con '
    'fixtures de esas fases, no observa su publicación en una ventana.63123exit0; '
    '16,75s;GPU3173,5625MiB;RAM3258,35546875MiB;registro intacto.', '',
    '1155pytest pass/0skips/5,66s;203integración pass/0skips/15s. Fast49118exit0, '
    'Release16,90s,0 avisos/errores. ASTRA-TRAMO-98.md describe cambios y correcciones '
    'halladas por tests. Modelo/sampler/instrucción originales, Qwen3.5 override.', '',
    'El primer borrador inglés de paso2/3 es verdadero pero el guard exige forma '
    'progresiva en la primera oración; se rechaza y recompone en0,969s total. No se '
    'cambia ese guard porque la recuperación cumple sin agotar el turno. En acting '
    'inglés se conserva el recorte previo de la segunda oración, sin pérdida de hechos. '
    'La evidencia de UI/voz/audio/reserva100 sigue pendiente.', '']
for row in finals:
    lines += [f'## {row["case"]} — compatible', '', 'Entrada: ' + row['request'], '',
        'Hechos de fase: ' + json.dumps(row['facts'], ensure_ascii=False), '',
        'Final del compositor: ' + row.get('final', row.get('error', '')), '',
        f'Tiempo: {row["seconds"]}s.', '']
report = base / 'PRUEBAS_PROGRESO98_99.md'
report.write_text('\n'.join(lines), encoding='utf-8')
files = [report, base / 'ASTRA-TRAMO-98.md', out / 'PREREG.json', out / 'RESULT.json',
    out / 'finals.jsonl', out / 'posts.jsonl', out / 'compose-audit.jsonl']
(base / 'TRAMO98_99_PINS.json').write_text(json.dumps({'scope': 'Source98 Python pipeline99; real UI still pending',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2), encoding='utf-8')
path = base / 'CHECKPOINT.md'
text = path.read_text(encoding='utf-8').replace('fuente92; recuperación4/4; progreso pendiente', 'fuente98; recuperación4/4; compositor de progreso8/8')
start = text.index('Sin procesos/modelos propios activos.93 timeout')
end = text.index('\n## Decisiones y pruebas', start)
text = text[:start] + '''98 adoptado localmente: fase del FieldBridge y posición válida al compositor,
sin el objetivo futuro en su prompt; el pedido original conserva idioma y validación.
La composición se descarta si cambió turno/estado; cambiar fase retira label viejo.
1155pytest pass/0skips/5,66s;203integración pass/0skips/15s. Fast49118exit0,
Release16,90s,0 avisos/errores. ASTRA-TRAMO-98.md registra correcciones de los tests.
99 compositor real con8fixtures de fase/idioma:8finales compatibles;0,344–0,969s
por composición.63123exit0,16,75s,GPU3173,56MiB,RAM3258,36MiB,registro intacto.
Paso inglés2/3 necesitó reintento por guard de primera oración; final fiel.
PRUEBAS_PROGRESO98_99.md/TRAMO98_99_PINS.json. Sin procesos/modelos propios activos.
93 timeout por límite19s;94 razonó2048tokens sin final;95 sampler oficial no fiable.
NO adoptar perfiles.96/97 datos de actividad demostraron la vía incorporada en98.

Siguiente: UI real por py main.py y Computer Use; todavía NO lanzada.
Skill computer-use leída completa junto a guidance/confirmations. Tool disponible:
mcp__node_repl__js; globalThis.sky importado desde @oai/sky; apps inventariadas,
no hay ventana BAXY. No usar CUA de navegador ni PowerShell UIA en este turno.
El script run_baxy.ps1 fuerza perfil dev-mente-v2; --profile sólo es conductor.
--ui-capture permite registrar ventana sin --ui-probe. Preparar prueba técnica
local con override Qwen3.5 y captura, preservando ese perfil y sus archivos.
No ejecutar modelo/build paralelo. No Full hasta cierre integral.
''' + text[end:]
text = text.replace('App Release92.', 'App Release98.')
path.write_text(text, encoding='utf-8')
path = base / 'HANDOFF.md'
text = path.read_text(encoding='utf-8')
text += '''
Actualización98/99:1155pytest pass/0skips;203integración pass/0skips;Fast49118exit0,
Release16,90s. Compositor99 devuelve8/8compatibles,0,344–0,969s por caso, sin UI
observada aún. PRUEBAS_PROGRESO98_99.md/pins. Sin procesos propios activos.
Siguiente UI por py main.py. Computer Use inicializado en mcp__node_repl__js,
globalThis.sky; no BAXY en apps. Skill/guidance/confirmations leídas completas.
run_baxy.ps1 usa dev-mente-v2; --profile sólo conductor. Preparar captura técnica
sin pisar archivos/perfil. No PowerShell UIA, no navegador ni modelos paralelos.
'''
path.write_text(text, encoding='utf-8')
path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(path.read_text(encoding='utf-8'))
relay.update(checkpoint='Fuente98:1155pytest/203integración pass,Fast verde; compositor99 ocho finales compatibles; C03 EN_CURSO',
    continuation='Sin procesos activos. UI por py main.py aún no lanzada. Computer Use sky inicializado en node_repl. Perfil dev-mente-v2, preservar archivos; modelo override. No Full.')
path.write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8')
