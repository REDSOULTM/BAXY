"""Update owner-facing progress while the owned503 suites run."""
from datetime import datetime, timezone
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
report = '''# Avance de BAXY y C03 — 8 de septiembre de 2026

C03 sigue activo. Ya hay correcciones verificadas y ahorros de memoria, pero falta la aceptación completa del producto. Una tanda aprobada no equivale a un porcentaje del goal.

Se reunieron tus 20 mensajes directos y las 742 respuestas de la encuesta, conservando autoría y expectativas. Las instrucciones automáticas de otras tareas quedaron separadas. Esa base orienta las conductas generales junto con AGENTS.md y la identidad de BAXY.

Se corrigieron pérdidas de contexto y de hechos: distinguir la cuenta de Windows del nombre conversacional o guardado, evitar reutilizar un guardado anterior al presentarse alguien nuevo, preguntar por una aplicación que falta y conservar el destino y la posibilidad de sincronización en las confirmaciones de exportación. Algunas confirmaciones aún omiten consecuencias o explican mal la autorización; siguen pendientes.

En el audio, se corrigieron la segunda acción tras pero/but, las negaciones independientes, los clíticos de desmutear y ponle, las peticiones de volumen sin nivel y la respuesta numérica a una aclaración. El texto citado sigue siendo contenido.

La prueba real de la mente 502 comprobó tu secuencia «Ponle volumen al pc» → «Al 100, pero desmutealo»: pide el nivel cuando falta y después genera volumen 100 y silencio desactivado, con ambos argumentos correctos. El segundo pedido pasó de fallar en 6,188 segundos a preparar su interpretación y plan en unos 0,484 segundos. En esa tanda hubo 12 propuestas/aclaraciones correctas de 14 y 10 bindings correctos de 10. No se ejecutó audio físico ni la interfaz de escritorio.

El caso «perfecto, necesito lo dessilencies pls» ya pasa las pruebas focales de la siguiente corrección, 503, que está en validación. La respuesta que define desmutear aún contiene prosa interna y una oferta de control del micrófono que esa respuesta no acredita.

La fuente 501 pasó siete suites: 3377 pruebas y 121 subpruebas aprobadas, cero skips, en 48,89 segundos. Fast y compilación Release también pasaron, sin advertencias ni errores. La compuerta Full final sigue pendiente; durante la reparación se ejecutan las pruebas dueñas y Fast.

## Recursos medidos

| Medición | RAM máxima | VRAM máxima | Qué incluye |
|---|---:|---:|---|
| Producto antes del ajuste 422 | 5,18 GiB | 3,10 GiB | Se detuvo por falta de RAM libre |
| Producto Qwen3.5, 437 | 2,75 GiB | 3,10 GiB | Conductor de producto; 7/8 respuestas útiles |
| Producto Gemma E2B, 464 | 2,59 GiB | 1,65 GiB | Conductor de producto; 7/8 respuestas útiles |
| Compositor Gemma E2B, 462 | 0,98 GiB | 1,65 GiB | Servidor y compositor; no toda la aplicación |
| Gemma E2B original, 497 | 1,01 GiB | 1,64 GiB | Prueba nativa de selección; calidad incompleta |
| Mente y planes actuales, 502 | 1,73 GiB | 3,42 GiB | Qwen registrado, recursos semánticos y conductor; sin UI/voz |

El ajuste de caché y mapeo redujo RAM del producto; la carga bajo demanda de Gemma mantuvo sus respuestas y redujo RAM del compositor. Sigue habiendo uso de RAM y disco. No se ha conseguido ni demostrado que todo BAXY resida sólo en VRAM. Tampoco está medido un mínimo universal. El techo de 4 GiB corresponde al conjunto y aún falta verificar el candidato final con interfaz, micrófono, reconocimiento y activación por voz.

## Comparación de modelos

Tu criterio está escrito en AGENTS.md: investigar papers, documentación y reproducciones de usuarios; comprobar modelo, cuantización, versión de llama.cpp, plantilla y parámetros efectivos; medir calidad, tiempo, RAM y VRAM. Los defaults no bastan para descartar un modelo y una receta documentada tampoco prueba que sea el óptimo.

Se contrastaron llama.cpp b9980, estable b10809 y posterior b10865, con las correcciones aplicables a cada familia. Actualizar el backend por sí solo no corrigió la semántica. Qwen Q8 y Qwen3.5-9B se probaron con perfiles documentados, pero no resolvieron todos los fallos de confirmación/memoria y no se promovieron.

El Gemma original evitó las repeticiones de llamadas del checkpoint publicado en la comparación 497, pero siguió invirtiendo el silencio en tres respuestas contextuales y violando la interfaz sin argumentos en cuatro. Tampoco se promovió. Las reparaciones 498–501 corrigen pérdidas demostradas del código y mantienen el runtime registrado.

## Qué falta para cerrar

- Resolver las respuestas y confirmaciones restantes de las ocho rutas y los incidentes de la sesión manual, incluidos aplicaciones, reproducción, capacidades y cierre de BAXY.
- Certificar y congelar 100 turnos humanos frescos, separados del desarrollo, y obtener 100/100 respuestas útiles y fieles en español, inglés y mezcla natural. Hay 204 candidatos potenciales; todavía ninguno certificado ni ejecutado para aceptación. Faltan comprobaciones de contexto, entrenamiento y exposición.
- Verificar recuperación ante averías, interfaz real, voz y audio físico, ASR/wake y recursos del conjunto.
- Verificar runtime e instalación, continuidad C04–C09, Full final íntegramente verde y publicación fuera de main.

BAXY permanece cerrado para uso manual. La encuesta terminada se conserva. El estado técnico exacto y las sesiones activas están en CHECKPOINT.md; los resultados y fallos intermedios siguen guardados por tramo.
'''
(base / 'ESTADO_PARA_DUENO_2026-09-08.md').write_text(report, encoding='utf-8')
research = base / 'INVESTIGACION_MODELO_C03.md'
text = research.read_text(encoding='utf-8')
start = text.index('## Avance485–490')
text = text[:start] + '''## Cierre de las pruebas nativas 491–497

Los contratos completos y la polaridad explícita de audio.mute (491/492) mejoraron unas respuestas y empeoraron otras. El campo de entrada real es state: true silencia y false reactiva; muted pertenece a observaciones. No se adoptaron las variantes.

Gemma E2B publicado, con perfil Google y thinking/lazy-on/b10809 (493), repitió operaciones. 494 comparó generación cruda y llamadas parseadas: eran iguales, por lo que el parser no insertó esas llamadas. 495 falló HTTP antes de generar; no es un resultado del modelo. 496 cambió únicamente gramática, grammar_lazy y disparadores en cuatro pares con parámetros efectivos iguales: quitarla eliminó extras, pero introdujo una operación no declarada y prosa de éxito previa a ejecución. No se adoptó.

497 comparó el Gemma E2B-it original Q4 (SHA740185...) con el publicado, ambos bajo gramática nativa y perfil Google T1/top_p.95/k64/min0, thinking y lazy-on. Tres prompts renderizados coincidían exactamente con494. El original evitó extras en14 respuestas, pero invirtió el silencio en3 respuestas contextuales y violó la interfaz sin argumentos en4. RAM1030,965/GPU1681,988MiB,62,719s; sólo nativo. No promoción ni conclusión global sobre toda una familia.

Fuentes primarias del mecanismo: documentación específica de Gemma4 sobre function calling y formato de prompts (https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4 y https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4); fuente llama.cpp5266f24da archivada en privado494/495. Los reportes de usuarios21375 y22786 tienen otras versiones/condiciones y no prueban por sí solos la causa de BAXY. RESULT, ADJUDICATION y PINS de491–497 conservan perfiles, fallos y límites.

## Reparación del producto y comprobación 502

498 protege las cláusulas con pero/but y el texto citado;500 comparte ponle entre lectura y delimitación;501 conserva una respuesta numérica sólo frente a un pedido previo del usuario con contrato de nivel incompleto, y prueba nivel/polaridad en la materialización. No cambia modelo ni sampler. Siete suites:3377 pass y121 subtests,0skips; Fast verde.

502, con runtime registrado, entrega12/14 propuestas/aclaraciones correctas y10/10 bindings correctos. Owner51 pasa de error6,188s a turno0,484s y plan con level100/statefalse. RAM1773,180/GPU3497,559MiB,45,297s; mente y conductor, sin UI/voz/efectos. Persisten owner46 y definición defectuosa. Es comparación de regresión del código, no una clasificación de capacidad de modelos a partir de defaults. 503 trabaja sobre la pérdida del marco de petición y la familia desilenciar; aún en validación. CHECKPOINT.md manda para el estado vigente.
'''
research.write_text(text, encoding='utf-8')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = base / name
    text = path.read_text(encoding='utf-8')
    text = text.replace('No hay runtime, build ni prueba activos.',
                        'Pruebas dueñas503 activas en sesión26227; no runtime de producto ni build activo. No editar fuente hasta recogerla.')
    text = text.replace('503 preregistrado', '503 en validación')
    text += '\n503: baseline13fallos/12pass; primera intervención9fallos/16pass (sólo cabeza, lectores anclados aún veían necesito); segunda1fallo/24pass (pls no era cierre elíptico). Fallos preservados. Se comparte el marco de deseo entre normalización y cabeza; familia desilenciar/desmutees y cierres pls/plz/porfa. Focal31pass/2822deselected,2,05s, incluidos argumentos false y señales opuestas. Owners26227 pendientes; fuente effect_intent503 y tests en validación.\n'
    path.write_text(text, encoding='utf-8')
record = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
              checkpoint='Fuente503 en validación:31 focales pasan; owner46 ya se reconoce y liga state=false en pruebas.',
              continuation='Recoger dueñas26227; después Fast y repetición real502 como504. No editar fuente durante pruebas. C03 íntegro activo.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Owner report, model research and active503 state updated.')
