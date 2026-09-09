"""Seal the completed diagnostic desktop run; preserve prior evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import psutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-ui194'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-ui194-private'

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

process = json.loads((out / 'PROCESS.json').read_text(encoding='utf-8'))
if psutil.pid_exists(process['app']):
    assert psutil.Process(process['app']).create_time() != process['appCreateTime']
resources = json.loads((out / 'RESOURCES.json').read_text(encoding='utf-8'))
assert resources['reason'] == 'operator_finished' and resources['cleanupExit'] == 0
prereg = json.loads((out / 'PREREG.json').read_text(encoding='utf-8'))
assert all(sha(root / p) == h for p, h in prereg['sourceFiles'].items())
assert sha(Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json') == prereg['registrationSha256']
old = json.loads((base / 'TRAMO191_193_PINS.json').read_text(encoding='utf-8'))
assert all(sha(root / row['path']) == row['sha256'] for row in old['public'])
ui = (out / 'UI-supersede.txt').read_text(encoding='utf-8')
assert ui.count('Estoy listo para ayudarte con lo que necesites.') == 1
assert ui.count('¿Podrías repetir lo que dijiste?') == 1
assert ui.count('Son las 13:05.') == 1 and '5 entries' in ui
report = '''# C03 — publicación real de avisos de voz — 194

Tres casos diagnósticos en la aplicación de escritorio, iniciada con `py main.py`.
Fuente192 sin cambios; modelo Qwen3.5 con override, registro intacto. Un hook
externo emite eventos de diagnóstico; no inyecta respuestas redactadas.

| Caso | Salida visible | Evaluación |
|---|---|---|
| Evento wake | Estoy listo para ayudarte con lo que necesites. | Acuse útil sin afirmar ejecución. |
| Transcripción dudosa | ¿Podrías repetir lo que dijiste? | Pide repetir sin inventar lo escuchado. |
| Nueva pregunta durante composición del acuse | Son las 13:05. | Nuevo resultado fiel; el segundo acuse queda descartado. |

La tercera prueba entrega «¿Qué hora es?» mientras el compositor redacta un
acuse, con pausa diagnóstica de 0,5 s en esa invocación. El historial final tiene
cinco entradas: bienvenida, primer acuse, aclaración, pregunta y hora. La marca
published del audit del compositor describe su etapa, no acredita publicación
posterior en UI. UI-supersede.txt demuestra ausencia del segundo acuse.

Core: utc `2026-09-07T16:05:01.2546992+00:00`, localUtcOffsetMinutes `-180`.
El resultado local 13:05 coincide con la respuesta visible. Los textos se
inspeccionaron en la ventana real mediante Computer Use y quedaron conservados.

Monitor51134 recogido exit0. Fin mediante STOP_APP del propio lanzador;
cleanupExit0 y launcherExit0. Duración540,41s; GPU3480,15234375MiB,
RAM5326,40625MiB. No promoción ni cambio de AEC: el producto conserva Speex.

Estos son tres casos técnicos, no entrada humana ni reserva. La activación usa
la costura de wake aún no aprobada. No hubo captura acústica ni ajuste de volumen;
no se acredita audio físico ni ocho rutas completas. Fallo183 y mezcla129 siguen
abiertos. Las pruebas113Python/16.NET/Fast corresponden a fuente192/193.

Siguiente: incorporar controles humanos públicos con transcripción conocida al
diagnóstico de conservación del habla, antes de otra sustitución de AEC. Separados
de la reserva Carter→BAXY. C03 íntegro EN_CURSO, sin Full final ni publicación.
'''
(base / 'PRUEBAS_UI194.md').write_text(report, encoding='utf-8')
names = ['PREREG.json', 'PROCESS.json', 'RESOURCES.json', 'UI-wake.txt', 'UI-uncertain.txt', 'UI-supersede.txt', 'compose-audit.jsonl', 'shell-trace.jsonl', 'turn-audit.jsonl', 'raw-replies.jsonl', 'launch.log', 'STOP_APP']
public = [base / 'PRUEBAS_UI194.md'] + [out / name for name in names if (out / name).is_file()]
public += [root / 'scratchpad' / name for name in ['c03-prepare194.py', 'c03-launch194.py', 'c03-ui194-hook/sitecustomize.py', 'c03-finish194.py']]
private_files = [private / name for name in ['command.json', 'events.jsonl'] if (private / name).is_file()]
save(base / 'TRAMO194_PINS.json', {
    'public': [{'path': str(p.relative_to(root)), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in public],
    'private': [{'privatePath': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in private_files],
})
state_path = base / 'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state.update(goalStatus='active', confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='194: tres casos UI correctos, acuse obsoleto descartado, hora Core verificada. GPU3480MiB; sin aceptación acústica. Fuente192 intacta. Evidencia fijada.', continuation='Controles humanos públicos de conservación del habla sobre eco grabado; fallo183 abierto. No procesos propios activos; no Full durante reparación.')
save(state_path, state)
(base / 'HANDOFF.md').write_text((base / 'CHECKPOINT.md').read_text(encoding='utf-8'), encoding='utf-8')
print(json.dumps({'publicPins': len(public), 'privatePins': len(private_files), 'priorPinsVerified': True, 'sourceUnchanged': True}))
