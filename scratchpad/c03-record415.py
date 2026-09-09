from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-os-caption415'
resources = json.loads((out / 'resources.json').read_text())
assert resources['completed'] and not resources['violations'] and resources['manifest_unchanged']
rows = [json.loads(x) for x in (out / 'replies.jsonl').open(encoding='utf-8')]
assert len(rows) == 8
report = '''# 415 — transportar el nombre observado de Windows: 1/4 → 4/4 útiles

La primera petición y su payload nativo igualan el T5 de producto411, comprobados
offline y durante la ejecución. La única diferencia es observed.os.caption.
El baseline repite Windows 10 para Windows 11 y Server 2022; con Caption distingue
los cuatro sistemas y conserva sus ediciones. Las respuestas ES llaman «versión»+al número de compilación, una imprecisión terminológica; no cambian el número
observado. Ningún silencio, error o violación de recursos. Los controles de
Windows 10 y Server son sintéticos, no observaciones de este PC ni aceptación.

GPU propia máxima: 3171,5625 MiB. RAM del árbol: 3623,171875 MiB. Duración 8,641 s.
Esto mide composición aislada con sus guardas, no voz física ni VRAM conjunta.
Modelo diagnóstico Qwen3.5-4B Q4_K_M; no se promovió el runtime. Modelos cerrados.

Se implementará una lectura CIM local, acotada y cancelable mediante el runner
ya existente. Sustituye la lectura numérica RtlGetVersion por los datos de
Win32_OperatingSystem (Caption, Version, ProductType), con arquitectura del runtime.
No se deduce el nombre comercial desde umbrales de build; no se añade una respuesta
fija ni una nueva operación. Caption forma parte del contrato y del resultado
verificado. Si falla la observación, queda un fallo explícito del scope OS.

Herencia: biblioteca/carter/carter_v5/microagents/windows_commands.md:23–32 no
resuelve este nombre; el runner y CIM ya existen en Providers.Windows/External.
Microsoft documenta Windows 10 y 11 con NT 10.0 y Caption como descripción local:
[OSVERSIONINFOEXW](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/ns-wdm-_osversioninfoexw),
[Win32_OperatingSystem](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-operatingsystem).
Fuentes comprobadas el 2026-09-08; prueba y respuestas completas en replies.jsonl.
'''.replace('\\+','')
(out / 'RESULT.md').write_text(report, encoding='utf-8')
prereg = json.loads((out / 'PREREG.json').read_text(encoding='utf-8'))
private = Path(prereg['private'])
paths = [out / n for n in ['PREREG.json', 'RESULT.md', 'replies.jsonl', 'resources.json', 'command.json']]
paths += [private / n for n in ['posts.jsonl', 'compose-audit.jsonl']]
(out / 'PINS.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2) + '\n')
old = (base / 'CHECKPOINT.md').read_text(encoding='utf-8')
(base / 'CHECKPOINT_413_ANTES_416.md').write_text(old, encoding='utf-8')
state = '''# C03 — 415 completado; implementación OS416 pendiente — EN_CURSO

Goal completo activo. Goal-c03 / HEAD 2bf3d4c. Preservar WIP, main y evidencia.
Sin agentes, commit/push ni Full durante reparación. BAXY manual cerrado; sólo
la encuesta permanece (PID 101140, padre 29800). No hay modelo/producto activo.
Mensajes directos 16 y encuesta 742/rev1248 consolidados; automáticos excluidos.

Fuente última adoptada 410: alcance cuenta/recursos y descripción del catálogo.
12 focales, 2260 Python +121 subtests, Kernel 140; Fast verde; turn_policy 967
pass/0 skips (4,68 s). Benchmark explícito omitido por Kernel no cuenta como pass.
Memoria fuente 402/404 conservada. Evidencia en astra-account-catalog410.

Producto411: 4/6 útiles; cuenta EN fría sí funciona. T3 vuelve a pedir permiso
para leer cuenta; T5 confunde Windows 11 con Windows 10. Modelos cerrados.
412 no reproduce por omitir bienvenida. 413 sí reproduce (payload por PID):
recuperar lectura antes de guardas mejora 13/15→14/15, pero recita cuenta en warm.
414 filtra read_only antes del top4: 14/15→14/15, corrige warm y rompe cold.
Ambos rechazados para adopción; no duplicar pases ni combinar por frío/caliente.
Ver astra-read-recovery413 y astra-read-candidates414/RESULT.md. Historia para
reproducir siempre desde HTTP nativo: activity omite bienvenida automática.

415 composición iguala payload real411. Sólo observed.os.caption mejora 1/4→4/4
casos útiles (Windows 11 ES/EN, Windows 10, Server 2022). RESULT/PINS completos.
GPU 3171,56 MiB/RAM 3623,17 MiB, sólo composición; no acredita voz conjunta.
Siguiente: sustituir lectura OS Rtl por CIM local con runner existente, timeout
y cancelación; transportar Caption tipado hasta resultado. Ver scratchpad/
c03-os-caption415.py, SystemStatusProbe/Provider/Contracts y SystemStatusHandler.
Probar proveedor, handler y producto real; no tocar modelo, sampler ni prosa.

Pendiente: account T3, memoria ES/redactada, falsa persistencia al presentarse,
precedencia aclaración MainWindow671, ocho rutas y encuesta/fallos264. Cero
requisitos finales certificados y 0/100 frescos de aceptación. Quedan averías,
UI real/voz física/ASR/wake/≤4 GB conjunto, runtime/instalación/contratos C04–C09,
Full final verde y publicación. Sin bloqueo externo; no porcentaje ni ETA.
'''
(base / 'CHECKPOINT.md').write_text(state, encoding='utf-8')
(base / 'HANDOFF.md').write_text(state.replace('# C03 —', '# Handoff C03 —', 1), encoding='utf-8')
p = base / 'RELEVO_ACTIVO.json'
relay = json.loads(p.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='415 completed 1/4 to 4/4; source410 last validated; models closed.', continuation='Implement observed OS caption through existing bounded CIM runner and typed result, then owner tests and product. Full C03 active.')
p.write_text(json.dumps(relay, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('415 recorded; checkpoint current')
