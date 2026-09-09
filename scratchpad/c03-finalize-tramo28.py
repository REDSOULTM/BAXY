from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
assert 'source_quality_gate_passed: mode=Fast' in (root/'scratchpad/c03-unified-final-fast.log').read_text(encoding='utf-8-sig')
assert '1171 passed' in (root/'scratchpad/c03-unified-final-tests.log').read_text(encoding='utf-8-sig')
rows=json.loads((base/'astra-clarification-unified-qwen/paired.json').read_text(encoding='utf-8'))
assert len(rows)==12 and all(r['terminal']=='published_final' for r in rows)
text='''# C03 — CHECKPOINT — 2026-09-06

EN_CURSO, sin bloqueo externo. Goal-c03, HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49.
Main/stash ajeno intactos. Cambios acumulados sin commit/push. Sin procesos propios
pendientes ni subagentes. AGENTS/identidad/C03_ASTRA_AUTORIDAD mandan; VRAM≤4096MiB.

## Último avance (tramo28)

Investigación por capas hecha: Granite falla desnudo; BAXY también degrada por
selección de presentación, historial y guardas. DIAGNOSTICO_POR_CAPAS_C03.md
conserva315observaciones iniciales; PRUEBAS_CONTINUIDAD_C03.md amplía los literales.
No son aceptación fresca. Prefijo idiomático, saludo social, puntuación de
confirmaciones y nombres propios derivados de verbos: corregidos previamente.
Qwenbase sin LoRA:21/21útiles de desarrollo en astra-presentation-product-qwen.

Límite de identidad del catálogo ahora usa compositor de errores existente:
astra-boundary-composer-qwen-base9/9 útiles; astra-boundary-product-qwen12/12
publicados, caso inglés de inexistencia inventada resuelto. La pregunta mixta
tenía aún problema de continuidad, conservado como fallo en ADJUDICACION.

Continuación real reparada: astra-clarification-unified-qwen,12/12publicados,
73,19s,GPU3499,56MiB. Aplicó80%,60%,40%; lecturas posteriores coinciden y restauró
100% con lectura final. t8 pregunta amplia sobre dispositivo, podría pedir el
nivel más directamente; conserva objetivo y entiende40%. Datos/PREREG/hashes/
RESPUESTAS/ADJUDICACION completos. Desarrollo conocido, NO100reservados.

Correcciones causales:
- _truncated_fact_word sólo valores hoja; volume no es un corte de volumePercent.
- Proyección conserva effect:applied sólo si verified+succeeded+observed.applied;
  eleva estado final de audio; rechaza número equivocado y efecto no verificado.
- App comparte AddMindClarification entre decisión, plan y argumentos: rewording
  no pierde objetivo ni cambia tipo a conversación. Retirada duplicación.
- _volume_domain conserva modificadores existentes tras coma/punto y coma;
  no confunde volumen de ventas/datos/enciclopedia con audio.

Intentos anteriores permanecen: continuation-qwen11/12, repaired-qwen12/12pero
40%noaplicado, grounded-qwen11/12con t9filtered. No sumar como aprobados.
Prompt/guarda causal de tramo27 retirados, no reintroducir ni ampliar por frases.

## Validación actual

Fast7741 TERMINAL0,0errores/0advertencias: scratchpad/c03-unified-final-fast.log.
Python19363:1171pass+115subtests,8,80s,0skip (turn_policy, c03_request_preservation,
compose_contract, planner, goal06_voice). test_effect_intent57502:1477pass,40,51s.
.NET17277:3pass/0skip,16s, rejected-clarification por decisión/plan/argumentos.
Familia aclaraciones anterior65172:7pass/0skip,45s. Fixture de argumentos inicial
faltaba operation/ok; corregido y los3casos pasan. No era fallo del producto.
Ruff/format/diff-check verdes. Sellos refrescados. Full final pendiente.

## Runtime y próximo paso

Registro permanece Granite, SHA428b6248eeb8f78bb94082eec5b59bc127a669d9c609e24251591dbcb5743181.
Qwen3-4B-Instruct-2507-Q4_K_M.gguf candidato base sin LoRA, ubicado en
D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/.
KVq8 es ahora default del producto. QwenKVq4 medido:19/21publicados, audio invertido,
reunión inventada,2confirmaciones agotadas (astra-product-default-kv-qwen); rechazado.
No promover con q4 ni mezclar ese resultado con q8. q8 real confirmado en
astra-clarification-grounded-qwen/SERVER_COMMAND.json:ctk/ctv=q8_0,ngl99,ctx12288.
Los últimos probes usan sólo overrideGGUF y observador, no overrideKV ni sampling.

Siguiente: fijar runtime Qwen reproducible registrado, conservando backup y activos
STT/TTS/wake; validar resto de rutas/desarrollo y consumo junto a voz/wake.
Preparar100NUEVOS sólo tras desarrollo verde, con8rutas/3idiomas/contexto; adjudicar
cada respuesta. Averías aparte en MISMA sesión (ProductConductorHost:inject con
mode reject/timeout/exhaust y restore ya existen). UIreal py main.py, Full final,
publicación propia fuera main y contratos posteriores afectados hasta12.3.
No redefinir cierre ni declarar éxito por estos paneles. No bloqueo externo.
LoRApiloto4 pausado; no repetir entrenamiento/escala ni invalidadaablationV1.
'''
for filename in ['CHECKPOINT.md','HANDOFF.md']:
    (base/filename).write_text(text.replace('CHECKPOINT',filename[:-3],1),encoding='utf-8')
tramo=base/'ASTRA-TRAMO-28.md'
with tramo.open('a',encoding='utf-8') as f:
    f.write('''\n## Resultado final del tramo

64415 terminó0:11/12publicados; dominio reparado pasó a plan, pero el plan
retenía el mismo fallo de pérdida de aclaración. Se retiraron las tres
implementaciones duplicadas y se reutiliza AddMindClarification en decisión,
plan y argumentos.3pruebas de frontera .NET pasan (17277,16s,0skip).
66482 terminó0: astra-clarification-unified-qwen12/12publicados,73,19s,
GPU3499,56MiB.80/60/40aplicados y leídos; restauración100comprobada. El script
c03-export-continuation.py comprueba los4efectos verified+succeeded+applied.
Fast7741 verde0errores/0advertencias; Python19363:1171pass+115subtests,8,80s.
Todos los procesos terminales. Registro Granite intacto, defaultKVq8 consolidado.
CHECKPOINT tiene siguiente paso: runtime registrado,100reservados/averías/UI/Full.
''')
report=base/'PRUEBAS_CONTINUIDAD_C03.md'
with report.open('a',encoding='utf-8') as f:
    f.write('''\n\n## Estado comprobado al cerrar esta tanda

La última secuencia tiene12respuestas finales. Los cambios80%,60%,40% y la
restauración100% tienen verified+succeeded+applied y lectura posterior coincidente.
La pregunta mixta sobre dispositivo puede ser más directa al pedir el nivel;
ahora conserva contexto y la respuesta40% se aplica. Es desarrollo conocido.
Fast verde,1171pruebas Python+115subtests;1477pruebas del dominio;3pruebas.NET
para conservar aclaración en decisión, plan y argumentos. Full/100/UI pendientes.
''')
(base/'PRUEBAS_CONTINUIDAD_C03.manifest.json').write_text(json.dumps({
    'reportSha256':hashlib.sha256(report.read_bytes()).hexdigest(),'acceptance':False,
    'finalTurnCount':12,'allFinalsPublished':True,
    'sourceHashes':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [
        'src/baxy_mind/llm.py','src/baxy_mind/__main__.py',
        'src/baxy_mind/effect_intent.py','src/Baxy.App/MainWindowViewModel.cs']}
},indent=2),encoding='utf-8')
print('Tramo28, CHECKPOINT, HANDOFF y reporte final actualizados. Ningún proceso pendiente.')
