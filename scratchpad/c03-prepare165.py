from pathlib import Path
import hashlib
import json
import os
from datetime import datetime, timezone

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
for suffix in ('', '-entry'):
    source=root/f'scratchpad/c03-sidecar161{suffix}.py'
    target=root/f'scratchpad/c03-sidecar165{suffix}.py'
    text=source.read_text(encoding='utf-8').replace('161','165')
    text=text.replace('Full original sidecar module with actual current Core catalog169', 'Product source164 with main prepare_resampler, no diagnostic preimport. Actual current Core catalog169')
    with target.open('x',encoding='utf-8') as f:
        f.write(text)
snapshot=base/'astra-source164-snapshot'
snapshot.mkdir(exist_ok=False)
paths=['src/baxy_mind/__main__.py','src/baxy_mind/voice_aec.py','tests/test_sidecar_lifecycle.py']
index=[]
for rel in paths:
    p=root/rel
    target=snapshot/p.name
    data=p.read_bytes()
    target.write_bytes(data)
    index.append({'source':rel,'copy':str(target.relative_to(root)),'sha256':hashlib.sha256(data).hexdigest()})
for name in ('c03-source164-red.log','c03-source164-owner.log'):
    p=Path(os.environ['TEMP'])/name
    data=p.read_bytes()
    (snapshot/name).write_bytes(data)
    index.append({'source':str(p),'copy':str((snapshot/name).relative_to(root)),'sha256':hashlib.sha256(data).hexdigest()})
(snapshot/'INDEX.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
note='''# C03 — inicialización del remuestreador antes del lector JSONL

Fuente164: VoiceEngine y DSP147 conservados. main llama prepare_resampler antes
de _run_control_plane. El helper usa el remuestreador existente con 48 muestras
vacías a48kHz; no abre dispositivos, cambia DSP, umbrales ni plazos. Warmup de
LoopbackReference se conserva para clientes nativos sin el entrypoint JSONL.

161 agotaba voice.start60s en carga _fblas con el lock de voz retenido.
162 sólo preimporta scipy.signal antes de runpy: precarga2,000s,
voice.start4,438s, ready/listening/ttsReady/AEC true, cierre18,656s exit0 y stderr
vacío. Es diagnóstico sin volumen audible/UI y con wake no aprobado heredado.

163 reduce a subprocess con numpy y stdin abierto: isatty responde tanto con
os.read como ReadFile; import SciPy bloquea10s con ambos. Se rechaza que baste
cambiar el lector o que os.isatty por sí solo explique el bloqueo. No se afirma
stack C gfortran específico; sólo inicialización nativa y lectura concurrente.
La documentación OpenBLAS describe bloqueo gfortran/pipes en otro host Java:
https://github.com/OpenMathLib/OpenBLAS#considerations-for-using-the-library-from-java
Sirvió como hipótesis, no como evidencia exacta del mecanismo de BAXY.
Biblioteca consultada por índice/inventario: sin título específico SciPy/BLAS/stdin.

Regresión real en proceso frío: el main/lector originales reciben probe con stdin
abierto y ejecutan SciPy; sin164 falla tras10s (1failed11,03s), con164 responde.
Suites dueñas lifecycle/protocol + siete de voz:191pass,0skips,19,14s.
Se conserva main y la lectura originales en la prueba; sólo el dispatcher del
modelo se sustituye por la operación de DSP. No simula SciPy ni cierra stdin.
No es aprobación integrada. Siguiente165 mismo sidecar161 con fuente164 y sin
precarga experimental; después Fast y producto real si cumplen.
'''
(base/'ASTRA-TRAMO-162_165.md').write_text(note,encoding='utf-8')
for name in ('CHECKPOINT.md','HANDOFF.md'):
    p=base/name
    intro='# Último: fuente164 — precarga DSP antes del lector;165 siguiente\n\nFuente164191pass/0skips/19,14s; regresión fría antes fallaba10s.162preimport corrige voz4,438s.163ReadFile también bloquea: no cambiar protocolo. ASTRA-TRAMO-162_165.md manda.165 listo; no procesos propios activos antes del arranque. Sin Full/UI todavía.\n\n'
    p.write_text(intro+p.read_text(encoding='utf-8'),encoding='utf-8')
p=base/'RELEVO_ACTIVO.json'
d=json.loads(p.read_text(encoding='utf-8'))
d.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='Fuente164 prepara DSP antes del lector.191pass/0skips19,14s; regresión red/green demostrada.',continuation='Ejecutar sidecar165 sin precarga experimental; Fast y UI/audio físico si verdes. No Full durante reparación; corte148 y reserva100 siguen abiertos.')
p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
