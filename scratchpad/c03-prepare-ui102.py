from pathlib import Path
import datetime
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-ui102'
out.mkdir(exist_ok=False)
previous = json.loads((base / 'astra-ui100/PREREG.json').read_text(encoding='utf-8'))
for name, expected in previous['fixtures'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected
assert not (Path(previous['profile']) / 'filesystem-sandbox/c03-ui100-ausente.txt').exists()
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
assert hashlib.sha256(reg.read_bytes()).hexdigest() == previous['registrationSha256']
with Path(previous['model']).open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == previous['modelSha256']
prereg = {**previous,
    'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'method': 'Repeat the same eight UI100 technical cases in the same order through '
        'py main.py and Computer Use sky, source101. Existing uniquely named fixtures '
        'are hash-verified and reused unchanged. Capture early progress in the real '
        'window before terminal replies. No fresh human reserve, no promotion, no '
        'audio acceptance; wake disabled, Qwen3.5 override. No concurrent builds/models.',
    'files': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in (
        'src/baxy_mind/llm.py', 'src/baxy_mind/__main__.py',
        'src/Baxy.App/MainWindowViewModel.cs', 'src/Baxy.App/MindSidecarClient.cs',
        'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll')},
}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
monitor = (root / 'scratchpad/c03-ui100-resources.py').read_text(encoding='utf-8')
assert monitor.count('astra-ui100') == 1
(root / 'scratchpad/c03-ui102-resources.py').write_text(monitor.replace('astra-ui100', 'astra-ui102'), encoding='utf-8')
with (base / 'ASTRA-TRAMO-101.md').open('a', encoding='utf-8') as stream:
    stream.write('\nFast80125 exit0, Release19,24s, cero avisos/errores. UI102 preparado; no lanzado aún.\n')
files = [base / 'ASTRA-TRAMO-101.md', base / 'PRUEBAS_UI100.md', out / 'PREREG.json',
    base / 'astra-ui100/PREREG.json', base / 'astra-ui100/RESOURCES.json']
(base / 'TRAMO100_101_PINS.json').write_text(json.dumps({
    'scope': 'UI100 terminal replies; source101 validated, UI102 still pending',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
}, indent=2), encoding='utf-8')
checkpoint = base / 'CHECKPOINT.md'
text = checkpoint.read_text(encoding='utf-8')
start = text.index('## Estado actual y siguiente acción')
end = text.index('## Decisiones y pruebas', start)
current = '''## Estado actual y siguiente acción

Fuente101 adoptada localmente sobre98. UI100: ocho finales técnicos útiles y fieles
en ventana real; bienvenida también. Progreso no acreditado: temporizador espera
la cola ocupada y termina solicitando el aviso después del final. PRUEBAS_UI100.md.
Monitor27634exit0:987,44s,GPU3504,640625MiB,RAM5959,11328125MiB; arranque excluido.
Cerrar ventana oculta en bandeja por diseño; se terminó sólo el árbol propio25164
con ruta verificada. No aceptación de cierre grácil ni audio (muted/volumen0).

101 extiende la señal temprana existente antes de decisión/planificación por modelo;
fase y trace; timeout2,5s compartido entre POST/reintentos, sin reiniciar el deadline
principal. El fallo opcional no falla el pedido. Conversación reconocida/ruta rápida
se conservan. App cuenta sólo intentos iniciables y descarta señales de peticiones
retiradas o turnos/fases anteriores. Sin otra cola, hilo, modelo, prompt ni muestreo.
Se actualiza expectativa de progreso anterior a98; excepción de conocimiento de78
ya no admite una negativa vacía. Explicaciones reales de ambos errores conservadas.
1179pytest pass/0skips/6,63s;233integración pass/0skips/2m10s;Fast80125exit0,
Release19,24s,cero avisos/errores. Logs TEMP/c03-progress101-*. No Full.
ASTRA-TRAMO-101.md,TRAMO100_101_PINS.json. Sin procesos propios activos.

Siguiente: UI102 preparado, NO lanzado. astra-ui102/PREREG.json fija los mismos
ocho casos de UI100 en orden y verifica hashes de las dos fixtures existentes.
Usar py main.py con override Qwen3.5, wake0, dev-mente-v2; monitor preparado en
scratchpad/c03-ui102-resources.py. Computer Use sky inicializado; la antigua ventana
4395546 no sirve, obtener nueva por inventario. Capturar sólo BAXY tras inspección;
el helper puede devolver la ventana oclusora. No UIA PowerShell ni navegador.
No builds/modelos paralelos. Reserva100/voz/runtime/continuidad/Full siguen pendientes.

'''
text = text[:start] + current + text[end:]
tail = text.find('\nUI100 preparado, no lanzado:')
if tail >= 0:
    text = text[:tail] + '\n'
text = text.replace('fuente98; recuperación4/4; compositor de progreso8/8', 'fuente101; UI100 finales8/8; progreso integrado por verificar')
text = text.replace('Core AOT63 SHAfe2c1cfc351abf78bd4d5080fd651eaec2e5915f83b82a30613a57df40e48fed.',
    'Core AOT de UI100 SHA9bc4b041ab4741a54a930dc7387498b9d263de9d1f3ed8ef45858dbf94bf6632.')
text = text.replace('App Release98.', 'App Release101.')
checkpoint.write_text(text, encoding='utf-8')
relay_path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(relay_path.read_text(encoding='utf-8-sig'))
relay.update(checkpoint='Fuente101:1179pytest y233integración pass;Fast verde. UI100 ocho finales útiles; C03 EN_CURSO',
    continuation='UI102 preparado sin lanzar, repetir ochoUI100 con Sky. Sin procesos activos. Monitor script preparado; no Full.')
relay_path.write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8')
print('UI102 prepared; fixtures/model/registration verified; no launch yet.')
