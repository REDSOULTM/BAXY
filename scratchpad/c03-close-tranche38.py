import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
lines = ['# C03 — pruebas literales del tramo 38', '',
         'Fecha: 2026-09-06. Desarrollo consumido; ninguna entrada cuenta como reserva de los cien turnos.', '',
         'Tres consultas en el producto registrado y quince llamadas de diagnóstico al chat de BAXY. '
         'Las sondas conservan instrucciones, idioma y guardas de BAXY: no son el LLM solo. '
         'No se adoptó ninguna variante de prompt de estas sondas.', '',
         '## Producto: nombre de la salida de audio', '',
         'Fuente: [paired.json](astra-audio-endpoint-name3/paired.json), '
         '[prerregistro](astra-audio-endpoint-name3/PREREG.json), '
         '[resultado](astra-audio-endpoint-name3/RESULT.json). '
         'Endpoint predeterminado Multimedia: Altavoces (Realtek(R) Audio), nivel 100, muted=false. '
         'No demuestra qué endpoint usa cada aplicación. Tres respuestas útiles; la gramática menor no invalida la primera.', '']
for i, row in enumerate(json.loads((base / 'astra-audio-endpoint-name3/paired.json').read_text(encoding='utf-8')), 1):
    lines += [f'### Producto {i}', '', '**Entrada literal**', '```text', row['request'], '```', '',
              '**Respuesta literal**', '```text', row['final'], '```', '',
              '**APROBADO en desarrollo:** conserva los hechos necesarios para la consulta.', '']

for folder, title in [('astra-knowledge-brief-policy', 'Conocimiento: política actual frente a brevedad flexible'),
                      ('astra-knowledge-one-sentence', 'Conocimiento: una frase con excepción para detalle')]:
    lines += [f'## {title}', '', f'Fuentes: [payloads y respuestas brutas]({folder}/posts.jsonl), '
              f'[respuestas del wrapper]({folder}/replies.jsonl), [resultado]({folder}/RESULT.json). '
              'Mismo modelo registrado, temperatura 0, historial vacío y máximo 128 tokens. '
              'Agua, aire y Steam son entradas históricas ya consumidas. SSID y explicación detallada son controles sintéticos, no uso humano acreditado.', '']
    posts = [json.loads(x) for x in (base / folder / 'posts.jsonl').read_text(encoding='utf-8').splitlines()]
    rows = [json.loads(x) for x in (base / folder / 'replies.jsonl').read_text(encoding='utf-8').splitlines()]
    for i, row in enumerate(rows, 1):
        matching = [p for p in posts if p['stage'] == row['stage'] and p['case'] == row['id']]
        finishes = [c.get('finish_reason') for p in matching for c in p['response'].get('choices', [])]
        answer = row.get('answer') or ''
        if row['id'] == 'synthetic-detail-control':
            verdict = 'NO APROBADO: salida cortada al alcanzar 128 tokens (finish_reason=length); no completa el detalle solicitado. La brevedad no resuelve este límite.'
        elif row['id'] == 'synthetic-en-definition' and 'password' in answer:
            verdict = 'NO APROBADO: la comparación con una contraseña confunde el nombre de red con autenticación.'
        elif row['text'] == 'El aire es h20?' and row['stage'] == 'current':
            verdict = 'PENDIENTE DE CALIDAD: distingue aire de agua, pero añade una generalización innecesaria sobre ausencia de agua líquida. No usar como aceptación del caso integrado anterior.'
        else:
            verdict = 'ÚTIL en esta sonda: responde a la cuestión con explicación sencilla. No acredita comportamiento en producto con historial.'
        lines += [f"### Sonda {i} — {row['stage']}", '', '**Entrada literal**', '```text', row['text'], '```', '',
                  '**Respuesta literal**', '```text', answer, '```', '', verdict, '',
                  f'finish_reason de las llamadas asociadas: {finishes}.', '']
lines += ['## Decisión y límites', '',
          'La lectura nativa del nombre sí está integrada y verificada. Las variantes de prosa no se promovieron: '
          'la segunda mejora las definiciones breves, pero el control detallado sigue cortado. '
          'La siguiente hipótesis debe tratar el presupuesto efectivo de salida y comprobar calidad, latencia y producto; '
          'no encadenar una tercera variante de redacción.', '',
          'Validación: 138 pruebas de proveedor y 131 de integración pasan, cero skips. Core NativeAOT publicado localmente; '
          'Fast verde, cero errores y avisos de compilación. La corrida de audio terminó con código 0, 58,06 s, '
          '3497,56 MiB de VRAM y 4608,77 MiB de RAM. No hay Full final ni nueva prueba de UI con voz.', '']
(base / 'PRUEBAS_IDENTIDAD_AUDIO_Y_CONOCIMIENTO_C03.md').write_text('\n'.join(lines), encoding='utf-8')

checkpoint = base / 'CHECKPOINT.md'
old = checkpoint.read_text(encoding='utf-8')
rest = old[old.index('### Registro conservado37'):]
current = '''# C03 — CHECKPOINT — 2026-09-06, tramo 38

## Estado vigente: identidad del audio reparada; C03 EN_CURSO

La aclaración sobre herencia Y estado del arte está en el goal activo y en
C03_ASTRA_AUTORIDAD.md, apartado «Herencia contrastada con el estado del arte actual».
El resumen antiguo del goal conserva una referencia al tramo32: reanudar desde
este checkpoint, no repetir ese tramo. Sin bloqueo externo.

Tramo38 añade nombre nullable del endpoint predeterminado Multimedia a audio.status.
Herencia/documentación/implementación contrastadas en INVESTIGACION_IDENTIDAD_AUDIO_C03.md.
No modifica mutaciones ni expone ID físico. Sin nuevo código Python ni modelo/sampler.
Core NativeAOT normal actualizado; astra-audio-endpoint-name3: 3/3 consultas conocidas
útiles, nombre real Altavoces (Realtek(R) Audio), volumen100, muted=false.
58,06s; GPU3497,56MiB; RAM4608,77MiB; registro intacto; exitCode0 (34603 cerrado).
No equivale a dispositivos activos por aplicación ni a reserva/UI con voz.

138 proveedor pass,0skip;131 integración pass,0skip. Handles29997/23252/92587/28321
terminales0. Fast verde, build0errores/avisos. Logs scratchpad/c03-endpoint-*.log.
Pruebas Python vigentes: las2804 del tramo37; no se repitieron sin cambios Python.
No Full final, UI actual, commit/push ni integración en main.

PRUEBAS_IDENTIDAD_AUDIO_Y_CONOCIMIENTO_C03.md conserva18 entradas/respuestas literales:
3producto+15sondas. astra-knowledge-brief-policy:10llamadas,16,36s; una definición
de SSID añade analogía falsa con contraseña; detalle se trunca a128tokens.
astra-knowledge-one-sentence:5llamadas,9,45s; agua/aire/Steam/SSID útiles en sonda,
pero detalle termina finish_reason=length,128tokens. No se promovió ninguna variante.
Esta última corrida terminó: RESULT/replies/posts/log completos y no hay proceso
Python de ese script; se perdió el handle al compactar, no afirmar exitCode leído.
GPU3497,56MiB en ambas; registro intacto. No son «modelo solo»: llevan wrapper BAXY.

Siguiente: comprobar presupuesto de salida de conocimiento en src/baxy_mind/llm.py
y su efecto al pedir detalle, partiendo de estas capturas. No tercera variante de
redacción ni adoptar la política breve sin prueba integrada con historial.
Después negación social seguida de petición positiva y cierre de desarrollo.
Faltan reserva100/procedencia/autoría/exposición, ocho rutas, averías/recuperación,
UI/recursos finales, contratos posteriores afectados, Full y publicación propia.

'''
checkpoint.write_text(current + rest, encoding='utf-8')

(base / 'ASTRA-TRAMO-38.md').write_text('''# C03 — tramo 38, 2026-09-06

Reparada la identidad de salida de audio: el dato faltaba antes del compositor.
WindowsCoreAudioPlatform lee PKEY_Device_FriendlyName del mismo IMMDevice;
AudioStatusReceipt → AudioStatusResult → compositor conserva EndpointName.
No se añaden operaciones, respuestas fijas ni consultas de nombre a las mutaciones.
Herencia y contraste: INVESTIGACION_IDENTIDAD_AUDIO_C03.md.

Pruebas literales y dictámenes: PRUEBAS_IDENTIDAD_AUDIO_Y_CONOCIMIENTO_C03.md.
Producto registrado: tres consultas conocidas, tres útiles; 3497,56MiB de VRAM.
138 pruebas de proveedor y131 integración pasan sin skips; Fast verde,0errores/avisos.
Core NativeAOT publicado localmente antes de medir. No Full final ni nueva UI.

Dos sondas comparables de prosa de conocimiento: diez y cinco llamadas. La variante
de una frase mejora definiciones breves, pero pedir detalle sigue truncándose por
max_tokens128. No se promovieron variantes. Siguiente hipótesis: presupuesto de
salida efectivo, no más redacción a ciegas. Véase checkpoint para reanudar.

Goal-c03; main/modelo/registro intactos. C03 EN_CURSO, sin bloqueo externo.
No hay reserva de100aceptada ni publicación propia todavía.
''', encoding='utf-8')

(base / 'HANDOFF.md').write_text('''# Handoff — C03 — 2026-09-06 — tramo 38

Objetivo: cierre de C03 conforme a C03_ASTRA_AUTORIDAD.md y C03_RESPUESTA_VERAZ.md.
Estado: EN_CURSO/ACTIVE, sin bloqueo externo. Goal-c03, HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49.
Cambios acumulados sin commit/push; main y cambios ajenos conservados. Sin subagentes.
El goal activo referencia históricamente tramo32: manda CHECKPOINT.md vigente38.

## Hecho y decisiones
audio.status conserva nombre del endpoint predeterminado Multimedia del mismo
IMMDevice: Altavoces (Realtek(R) Audio). Tres consultas conocidas útiles en producto
registrado, sin mutaciones. GPU3497,56MiB; RAM4608,77MiB;58,06s; exitCode0.
Core NativeAOT normal actualizado. INVESTIGACION_IDENTIDAD_AUDIO_C03.md registra
herencia, Microsoft y WebRTC. PRUEBAS_IDENTIDAD_AUDIO_Y_CONOCIMIENTO_C03.md:18literales.

Dos variantes de brevedad diagnosticadas, ninguna promovida. Una frase mejora
definiciones breves, pero detalle se corta: finish_reason=length/max_tokens128.
No repetir tercera variante de redacción. El wrapper persiste en estas sondas;
no presentarlas como modelo aislado ni como producto con historial.

## Validación
dotnet test tests/Baxy.Providers.Windows.Tests -c Release --nologo -v:minimal
con filtro WindowsAudioControlProviderTests|ExternalAdaptersTests:138pass,0skip.
dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal con filtro
AudioStatusHandlerTests|AudioVolumeHandlerTests|AudioMuteHandlerTests|C03FactPreservationTests:
131pass,0skip. scripts/test_source_quality.ps1:Fast verde, build0errores/avisos.
Logs scratchpad/c03-endpoint-*.log. Python sin cambios38:2804pass del tramo37 vigentes.
No Full final ni UI actual. Procesos conocidos cerrados; última sonda sin handle
recuperable, pero RESULT/posts/replies completos y proceso ausente; no reiniciarla.

## Siguiente acción
src/baxy_mind/llm.py: comprobar presupuesto de salida de conocimiento al pedir
detalle y calidad integrada con historial; heredar capturas de las dos sondas.
Queda negación social seguida de acción positiva; desarrollo completo; reserva100
literal con autoría/exposición/contexto comprobados; ocho rutas; averías y recuperación;
UI real/recursos finales; contratos afectados; Full verde y publicación fuera main.

## Runtime
Qwen3-4B-Instruct-2507 Q4_K_M base; llama.cpp b9980; KVq8,4096×3slots; total≤4096MiB.
LOCALAPPDATA/BAXYRuntime/mind-runtime-v1.json SHA
13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed intacto.
Python: LOCALAPPDATA/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.
''', encoding='utf-8')
print('Tramo38: 18 literales, investigación, checkpoint e informe de reanudación actualizados.')
