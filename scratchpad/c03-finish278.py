"""Persist rejected retrieval strategies and the next distinct experiment."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import psutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-priority278'
previous = (base / 'CHECKPOINT.md').read_text(encoding='utf-8')
(out / 'CHECKPOINT273.md').write_text(previous, encoding='utf-8')
rows = json.loads((out / 'RESULT.json').read_text(encoding='utf-8'))
assert len(rows) == 34
pair = [row for row in rows if row['case_id'] == 'win-07']
assert pair[0]['decision']['effect_operations'] == ['window.application.status']
assert pair[1]['decision']['effect_operations'] == ['app.installed']
live = {}
for pid in (84328, 89232, 101140):
    try:
        process = psutil.Process(pid)
        live[str(pid)] = {'name': process.name(), 'createTime': process.create_time()}
    except psutil.NoSuchProcess:
        live[str(pid)] = None
summary = '''# C03 — checkpoint278 — EN_CURSO

Última tanda: SELECCION274_278.md, sin adopción ni fuente de producto modificada.
274 corrige omisión diagnóstica271 del sufijo nativo app.open. Con28sigue sin
seleccionar; con sólo app.open selecciona frase larga y simple.275 mueve sólo
app.open al principio de las mismas28: elige apertura correctamente.
276 sustituir span de app autenticada por tipo sólo en queryE5 mejora rango
116→7,15→4,26→4.277 con esas shortlists reales sólo1/3correcto; no adoptar.
278 prioridad app.open ante cualquier nombre local:34comparaciones sobre
14controles conocidos+3dueño. Recupera frase larga pero pierde win-07
window.application.status→app.installed y cambia med-04query→exact. Descartado.
win-07 no tiene bypass explícito (resolve_explicit_effects=None). No esconder
regresión con capas posteriores. Procesos de ensayo15831/23984 terminaron exit0.

SIGUIENTE cambio de estrategia: heredar investigación formato/argumentos y
comparar contrato nativo con schemas reales frente a tools vacías actuales;
casos que distingan abrir/instalado/estado/música. No otra heurística de posición,
historial, frase Steam o template repetido. Grounding de frase larga sigueNone;
separar identidad de petición sólo con pruebas que conserven autorización.
Nada de lo anterior arregla aún publicación veraz.269 ya mostró que fuente267
cambia efecto inventado por estado no leído. Los validadores siguen aceptándolo.

Dueño terminó prueba264 y autorizó revisar/controlar PC. Logs preservados y
revisión parcial privada C03-owner264-snapshot268/REVIEW273.md. Faltan entradas
completas/UI. Instancia84328 preservada oculta a bandeja; no reiniciar antes de
recuperar conversación en memoria.397256 ya no disponible. Sky no expone
bandeja y algunas capturas no coinciden con objetivo; no clics inciertos.
No volver a pedir permiso. Backend existente89232/57485 usado para pruebas
nativas, cada petición con /slots sin actividad; no efectos/UI ni medición
integral. Live state exacto guardado en TRAMO274_278_PINS.json.

Cuestionario742: http://127.0.0.1:63179/ PID101140, SIN cierre automático.
%LOCALAPPDATA%/BAXY/C03-owner-questionnaire-20260907/answers.json pertenece al
dueño, que está marcando: NO sobrescribir/borrar/rellenar/congelar mientras
revisa. Autoría y capacidad separadas; no atribuir duplicados ni frescura por
una marca. Tres ingleses admitidos antes siguen vigentes. QA65100 cerrado.

Última fuente266:2597pass0skip/ruff;267:999pass0skip/ruff. Modelo/UI/Fast
integrados aún pendientes; últimoFast262. No Full durante reparación.
Capacidades263 aún falla catálogo incompleto/length/timeout/extra_claim.
Registro13b971… intacto, overrideQwen3.5 no promovido. Goal-c03/HEAD2bf3d4c,
preservar WIP/main. Recursos2603516,66MiBGPU/4822,60MiBRAM con captura/AEC/Piper,
sin ASR humano; wake sin certificar. Ocho rutas,100/100humanos frescos aún sin
congelar, averías/recuperación, UI/voz/ASR/recursos finales, runtime/instalación,
continuidadC04–C09, Full y publicación fuera main pendientes. Sin bloqueo externo.
'''
for name in ('CHECKPOINT.md', 'HANDOFF.md'):
    (base / name).write_text(summary, encoding='utf-8')
now = datetime.now(timezone.utc).isoformat()
path = base / 'RELEVO_ACTIVO.json'
relevo = json.loads(path.read_text(encoding='utf-8'))
relevo.update(confirmedAtUtc=now, checkpoint='278: typed entity and app-priority retrieval rejected by native controls; no product source adoption.',
    continuation='Change strategy: inherit native argument-schema evidence, then bounded full-schema vs empty-tool comparison; preserve owner UI and questionnaire.')
path.write_text(json.dumps(relevo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
names = ['scratchpad/c03-selector274.py', 'scratchpad/c03-order275.py', 'scratchpad/c03-entity276.py',
    'scratchpad/c03-native277.py', 'scratchpad/c03-priority278.py', 'scratchpad/c03-finish278.py',
    'artifacts/comprobaciones/C03/SELECCION274_278.md']
for directory in ('astra-selector274', 'astra-order275', 'astra-entity276', 'astra-native277', 'astra-priority278'):
    names.extend(f'artifacts/comprobaciones/C03/{directory}/{name}' for name in ('PREREG.json', 'RESULT.json'))
pins = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}
(base / 'TRAMO274_278_PINS.json').write_text(json.dumps({'utc': now, 'publicFiles': pins,
    'liveProcesses': live, 'productSourceChanged': False, 'goalStatus': 'active'}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'pins': len(pins), 'checkpoint': 278, 'live': live, 'goal': 'active'}))
