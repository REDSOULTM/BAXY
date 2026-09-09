"""Seal completed decoder diagnostics without rewriting prior evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))
def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
prior = read(base/'TRAMO195_199_PINS.json')
assert all(sha(root/r['path']) == r['sha256'] for r in prior['public'])
assert all(sha(Path(r['privatePath'])) == r['sha256'] for r in prior['private'])
folders = ['astra-wave200', 'astra-segment201', 'astra-segment201-retry',
    'astra-decode202', 'astra-greedy203', 'astra-decoder-cost204']
for folder in folders:
    if folder != 'astra-segment201':
        assert (base/folder/'COMPLETE.json').is_file()
assert len(read(base/'astra-greedy203/RESULTS.json')) == 47
private = []
for row in read(base/'astra-segment201-retry/RESULTS.json'):
    path = Path(row['privateOutput'])
    assert sha(path) == row['sha256']
    private.append(path)
report = '''# C03 — diagnóstico de decodificación 200–204

No hay cambio de producto ni promoción de runtime/AEC. Fuente192 sigue vigente.
200 conserva comparación de onda sobre las24 señales198. 201 usa la segmentación
real del producto/Silero:42 segmentos, cada uno idéntico a un rango de entrada.
El primer intento201 falla en el arnés antes de ingerir frames; se conserva.
202 completa42 lecturas con helper real y modified_beam_search, CPU6/paths8.
203 cambia sólo a greedy_search:42 segmentos +4 originales +silencio =47 lecturas.
Tres segmentos humanos vacíos (casos15,21,23) recuperan contenido, y caso3 pasa
de «Hola.» a la frase humana. Existen omisiones menores y texto procedente del
eco; no son47 pases. Silencio puro vacío. No acredita reparación acústica183.

204 mide el coste de dos reconocedores CPU: greedy751,99MiB incrementales,
6,453s de construcción; beam adicional729,19MiB y6,204s. RSS conjunto1525,50MiB.
El mismo segmento23 con beam y aliases wake sigue vacío; greedy lo recupera.
El primer lanzamiento204 falló por import incorrecto antes de crear outputs;
reintento completo, proceso79058 recogido exit0. No segundo modelo adoptado.

Decisión: probar reparación nativa acotada antes de aceptar dos copias del modelo.
En curso205: fuente sherpa-onnx v1.13.4 commit142807252687d81b40d6315f23470a1512a00de3,
compilación aislada Windows. PR3657 abierta, head867762892495a6bf1a2b031699906aaa73217e90.
La fuente1.13.4 ya avanza al menos un frame en blank: el cambio efectivo propuesto
es puntuación de duración/límite de símbolos. No atribuirlo a añadir ese guard.
Se comparará primero compilación sin parche, después mismo build con parche,
sobre los controles congelados. No modifica el registro ni instala en el runtime.
SetConfig de Nemo no reconstruye el decoder; no usarlo para fingir cambio dinámico.

Fuentes: [reporte3267](https://github.com/k2-fsa/sherpa-onnx/issues/3267),
[propuesta3657](https://github.com/k2-fsa/sherpa-onnx/pull/3657), herencia en
biblioteca/gemma4-agent/documentacion/03_voz_stt/research/parakeet_v3_uso_correcto_2026-06-10.md.
Todos los controles200–204 terminados;205 es trabajo posterior sin resultado aún.
C03 EN_CURSO: se mantienen íntegros los pendientes de CHECKPOINT.md.
'''
(base/'PRUEBAS_DECODER200_204.md').write_text(report, encoding='utf-8')
public = [base/'PRUEBAS_DECODER200_204.md']
for folder in folders:
    public.extend(p for p in (base/folder).iterdir() if p.is_file())
public.extend(root/'scratchpad'/name for name in ['c03-wave200.py',
    'c03-segment201.py','c03-decode202.py','c03-greedy203.py',
    'c03-decoder-cost204.py','c03-seal204.py'])
save(base/'TRAMO200_204_PINS.json', {
    'public': [{'path': p.relative_to(root).as_posix(), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in public],
    'private': [{'privatePath': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in private],
})
relevo = read(base/'RELEVO_ACTIVO.json')
relevo.update({'confirmedAtUtc': datetime.now(timezone.utc).isoformat(),
    'checkpoint': '203 actualizado:200–204 sellados. Decoder greedy recupera voz; dos contextos cuestan729MiB/6.2s extra.205 compilación aislada en curso.',
    'continuation': 'Conservar registros. Recoger configure205 sesión11110; construir baseline nativo antes de parche3657. Goal completo activo.'})
save(base/'RELEVO_ACTIVO.json', relevo)
print(json.dumps({'public': len(public), 'private': len(private)}))
