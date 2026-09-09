"""Checkpoint validated scoped CPU actor and quantity checks before product582."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-cpu-actor581'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


for part in ('stt', 'fast'):
    (out / (part + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-actor581-{part}.log').read_bytes())
assert '12 passed, 1 skipped' in (out / 'stt.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
note = '''# Handoff C03 — fuente581 validada

Se adopta guarda de primera persona indebida al informar observaciones CPU, con distinción frente a actividad de lectura o medidas de un proceso. Reutiliza los dos reintentos existentes con el borrador realmente rechazado y feedback de sujeto; no pide First person en esa reparación. Qwen3-4B-Instruct-2507 usa sólo en esa corrección el perfil oficial cualificado0,7/0,8/20/min0/presence0/repeat1/seed0; otros modelos mantienen su muestreo. Una respuesta correcta conserva el primer intento sin cambio de perfil. Tres rechazos devuelven vacío mediante el contrato existente, nunca el texto rechazado. No ruta ni plantilla visible nueva.

Un probe de la corrección mostró que el validador anterior aceptaba99% con observado23,75. Se añadió guarda de cifras sólo cuando el conjunto observado es CPU: porcentaje con redondeo a la precisión presentada y conteos físicos/lógicos. No atribuye porcentajes de audio/RAM a CPU en observaciones mixtas; no afirmar validación numérica universal. Comprobado que cifra cambiada en el reintento se rechaza y conserva el último intento acotado.

Baseline final39casos contra el llm anterior guardado:25fallos/14pass,0,70s, cargado sólo en memoria de subprocess con rutas de módulo originales, sin sobrescribir fuente. Focal39pass,0,61s. Dueñas1993pass+121subtests/0skip,9,52s; contratos/transporte156pass/0skip,1,27s. STT12pass/1skip ambiental,1,20s (archivos de campaña ciega ausentes). Fast verde completo, Release21,11s,0advertencias/errores. Árbol Python96be318f220b53ed56b75e3b21502388405670b479a05373eb8090be1284d816/403, sellos históricos intactos. SóloPython en581; Full final pendiente.

578 feedback con borrador corrige actor pero greedy rompe gramática;579 seed0 corrige cuatro originales;580 corrige tres primeras personas en fixtures con medidas/modelos/ES-EN distintos, conserva controlesEN. Corregir el controlES que ya decía Estás usando empeora el trato: por eso se activa sólo ante defecto, cubierto en pruebas. Nativos578–580GPU3497,559MiB/RAM720,598/720,195/725,414MiB; no UI/voz ni consumo conjunto final.

Fuente576 publicada022416a0 y verificada577:9finales correctos, seis variantes hora/silencio y tres controles. GPU3497,559MiB/RAM1859,543MiB,28,766s. CPU física574 publicadaad6d9a1a, reales8/16;575 conserva datos pero falla sujeto en una variante, H0007 continúa abierto. Encuesta12 cubiertos/730 abiertos/0NA,742/rev1248 intactos. BAXY manual cerrado, nada pendiente del dueño, goal activo. Main5f572ee1b48cb5e2543ee5e06510e51057c9c845 intacto.

Publicar581 y ejecutar582 (17turnos): H0007 seis variantes, H0065 cuatro, H0350 tres, nombres/identidad y hora-audio/red de control. Verificar primer rechazo y reparación reales, todos los valores y sujeto; adjudicar por case_id sin crédito por mero parentesco. Después quedan otros fallos CPU/GPU/unidades/memoria/progreso/curiosidades, encuesta y ocho rutas, UI real, loopback íntegro/AEC como supresión, recursos conjuntos, aceptación y Full final. Full526 rojo reparado por dueñas528–531, nunca presentar como Full verde; C08 humano sólo evidencia/reanudación. Ningún proceso de578–580 pendiente; Fast581 terminado.
'''
(out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out / 'RESULT.json', {'adopted': True, 'baseline_final_population': {'failed': 25, 'passed': 14, 'seconds': .70}, 'focal': {'passed': 39, 'seconds': .61}, 'owners': {'passed': 1993, 'subtests': 121, 'skipped': 0, 'seconds': 9.52}, 'contracts_transport': {'passed': 156, 'skipped': 0, 'seconds': 1.27}, 'stt': {'passed': 12, 'environmental_skips': 1, 'seconds': 1.20}, 'fast': 'passed', 'release_seconds': 21.11, 'product': 'pending582', 'survey': {'covered': 12, 'open': 730, 'not_applicable': 0}})
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('/artifacts/comprobaciones/C03/astra-cpu-actor581/** -text\n')
(base / 'HANDOFF.md').write_text(note, encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
state = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
state.update(checkpoint='581: scoped CPU actor repair and CPU-only numeric guards;2149pass+121subtests,STT12pass/1skip,Fast green. Survey12/730/0; product582 pending.', continuation='Publish581 and run582; adjudicate actual CPU generalization and controls. All remaining C03 obligations stay open.', confirmedAtUtc=datetime.now(timezone.utc).isoformat())
write(base / 'RELEVO_ACTIVO.json', state)
print('581 owner-validated, ready to publish; product582 pending.')
