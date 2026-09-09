from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
checkpoint = base / 'CHECKPOINT.md'
text = checkpoint.read_text(encoding='utf-8-sig')
start, end = text.index('## Estado actual'), text.index('## Decisiones y pruebas')
current = '''## Estado actual y siguiente acción

Fuente103 adoptada. UI104 demuestra progreso real antes del final en español e
inglés, con draft aún escrito, dos líneas legibles y retirada al cambiar fase o
finalizar. Los ocho finales técnicos y bienvenida siguen útiles/fieles.
PRUEBAS_UI104.md y PRUEBAS_UI102.md: comparación antes/después, literales y capturas.
No son cien humanos ni ocho rutas completas; no audio físico ni promoción.

103 modifica el dueño FieldCenter: la etiqueta recibida pasa del placeholder a
un role=status. Mismo lector/limpieza, sin nuevo bridge/prompt/generador. ADR-0008
reabierto, source/dist regenerados deliberadamente con pnpm build exit0.
Sello38archivos5396C5B4C33FAA3603CED416017EED5D44E0B03949A8C82D920C43F25BAF3687.
97pruebas shell/progreso/entrada pass/0skips/12s;13098exit0. Fast73364exit0,
Release18,95s,0avisos/errores. No repetir sin nuevo cambio/fallo. No Full.
Errores corregidos: Python312 sin Ruff al forzar QualityPython; CRLF del script
de sellado en el test C# restituido a LF. Logs TEMP/c03-ui103-*. Ver ASTRA-TRAMO-103.

UI104 launcher72826exit0; monitor21463exit0:388,12s,GPU3519,48046875MiB,
RAM5946,796875MiB; atribución disponible, arranque previo excluido. App35420
terminado con ruta verificada tras guardar ocho finales. Sin procesos propios.
Sky11538408 obsoleto. CoreSHA176FE1BF667F1A80B5792603A73E417429D88824F40869693FAA86C513BBC6DE.
Qwen3.5 override, wake0, registro conservado. No audio ni cierre grácil acreditados.

Siguiente: recuperar las comprobaciones faltantes de confirmación/restauración
del recurso y voz; luego reserva100, promoción y cierre completo. Índices/rutas
heredados primero; no otra colección de prompts ni repetir paneles verdes.
105 sólo preview de reserva: scratchpad/c03-preview-reserve105.py lee auditoría45
privada sin inferencia; vistos candidatos0–69, no selección ni congelación.
239 no refutados no equivalen a239 humanos certificados; tres ingleses confirmados
por el dueño ya registrados. No volver a preguntar esos tres ni extender a742.

'''
text = text[:start] + current + text[end:]
text = text.replace('fuente103; UI102 finales8/8; progreso visible por verificar',
    'fuente103; UI104 progreso visible y finales8/8')
tail = text.find('\nUI104 ACTIVO:')
if tail >= 0:
    text = text[:tail] + '\n'
checkpoint.write_text(text, encoding='utf-8', newline='\n')
handoff = base / 'HANDOFF.md'
archive = base / 'HANDOFF_HISTORICO_HASTA103.md'
with archive.open('x', encoding='utf-8', newline='\n') as stream:
    stream.write(handoff.read_text(encoding='utf-8-sig'))
handoff.write_text('''# Handoff C03 — fuente103/UI104 — 2026-09-07

Goal activo, tarea01a07974-2a33-7ed3-ba87-2436944e8115. Goal-c03,
HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. WIP ajeno/evidencia conservados;
sin commit/push ni main. CHECKPOINT manda. No Full durante reparación.

''' + current.split('\n\n', 1)[1] + '''
Cierre íntegro pendiente: ocho rutas,100humanos frescos/literales congelados y
100/100adjudicados, averías y recuperación aparte, UI/voz/audio físico y4GB,
runtime registrado sin override, continuidadC04–C09,Full verde y publicación.
Python312 para pytest; resolvedor predeterminado para calidad; py main.py GUI.
No usar py313 para pytest. No subagentes, modelos/builds paralelos ni UI por shell.
Computer Use sky/node_repl inicializado; helper saveBaxyEvidence apunta aUI104.
CapturasJPEG; inspeccionar oclusiones antes de guardar, no automatizar Codex.
''', encoding='utf-8', newline='\n')
relay_path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(relay_path.read_text(encoding='utf-8-sig'))
relay.update(checkpoint='Fuente103/UI104: progreso visible ES/EN y ocho finales útiles,97tests/Fast verdes; C03 EN_CURSO',
    continuation='Sin procesos activos. Completar confirmación/restauración/voz y reserva humana. No repetir UI104 ni Full durante reparación.',
    confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
relay_path.write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
paths = [base / 'PRUEBAS_UI102.md', base / 'PRUEBAS_UI104.md', base / 'ASTRA-TRAMO-103.md',
    base / 'astra-ui104/PREREG.json', base / 'astra-ui104/RESOURCES.json',
    root / 'src/Baxy.FieldUi/ORIGIN.md']
(base / 'TRAMO103_104_PINS.json').write_text(json.dumps({
    'scope': 'Source103 sealed UI, 97 owner tests and Fast green; UI104 technical finals8/8 and progress ES/EN visible; not C03 acceptance',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}, indent=2), encoding='utf-8', newline='\n')
print('UI104 evidence pinned; checkpoint and one-page handoff updated; C03 remains active.')
