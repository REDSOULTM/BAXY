"""Keep the owner-facing report current without confusing diagnostics with acceptance."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
report = base / 'ESTADO_PARA_DUENO_2026-09-08.md'
backup = base / 'astra-memory-configuration516/OWNER_STATUS.before.md'
assert not backup.exists()
backup.write_bytes(report.read_bytes())
report.write_text('''# Estado de BAXY y cierre C03

C03 continúa activo. La encuesta completa (742 respuestas) y tus instrucciones están incorporadas como base de conducta. BAXY sigue cerrado para uso manual. Las pruebas se hacen en perfiles aislados cuando necesitan efectos de memoria.

## Lo que ya cambió y se comprobó

- Se reparó la comprensión de órdenes de audio, incluidas las variantes de desmutear de tu sesión, niveles dados como continuación y pedidos compuestos. El plan conserva el orden y el argumento correcto de silenciar o reactivar.
- Se retiró el atajo que publicaba como respuesta la prosa interna del selector de operaciones. La conversación pasa por su generador propio; no se añadieron respuestas visibles fijas.
- Se corrigió cómo el generador recibe el historial para preguntas de conocimiento: conserva el texto y quién lo escribió, y distingue tus declaraciones de una respuesta anterior equivocada de BAXY. También puede contestar qué había dicho él, sin convertirlo en un dato tuyo.
- La fuente512 pasó siete suites de Python: 3406 pruebas y 121 subpruebas aprobadas, cero skips, en 53,88 s. Fast y compilación Release pasaron sin advertencias ni errores. Después, el protocolo real superó 24/24 casos de desarrollo y 11/11 comprobaciones de operaciones y argumentos, con el runtime registrado y sin tratamiento privado.
- La memoria del producto habilita, guarda y recupera el nombre sintético del perfil aislado. Distingue el nombre persistido del usado en la conversación. Sin embargo, algunas narraciones de resultados y progreso siguen usando lenguaje interno; eso aún impide dar esas rutas por cerradas.
- La prueba515 de retirar metadatos del redactor no resolvió ese problema y no se adoptó. También reveló que «desactiva la memoria privada» no llegaba a una operación que sí existe. La fuente516 sustituye alias de configuración por una gramática acotada. Sus 36 controles focales pasan; las pruebas completas de memoria están en marcha. Se preparó517 para comprobar el efecto real después de validarlas.

## Recursos medidos

| Sesión y carga | RAM máxima | VRAM máxima | Alcance |
|---|---:|---:|---|
| Producto antes del ajuste422 | 5,18 GiB | 3,10 GiB | Se detuvo por falta de RAM libre |
| Producto Qwen3.5,437 | 2,75 GiB | 3,10 GiB | Conductor, 7/8 respuestas útiles |
| Producto Gemma E2B,464 | 2,59 GiB | 1,65 GiB | Conductor, 7/8 respuestas útiles |
| Compositor Gemma E2B,462 | 0,98 GiB | 1,65 GiB | Servidor y compositor; no toda la aplicación |
| Mente y planes Qwen registrado,513 | 1,75 GiB | 3,42 GiB | 24/24 casos de desarrollo; sin UI/voz |
| Producto Qwen registrado,515 base | 1,54 GiB | 3,42 GiB | Perfil aislado, 7/9 finales útiles; sin UI/voz |
| Producto Qwen registrado,515 vista | 1,82 GiB | 3,42 GiB | Mismos casos, 7/9 finales útiles; filtro rechazado |

Se redujo RAM mediante ajustes de caché y mapeo; la carga bajo demanda de Gemma redujo RAM del compositor sin alterar sus respuestas en esa comparación. Las distintas filas no son una comparación justa entre modelos: cambian la carga y el alcance medido. BAXY sigue usando RAM y disco. No se ha demostrado que todo resida en VRAM ni un mínimo universal. Falta medir el candidato final con interfaz, micrófono, reconocimiento y activación por voz dentro del techo conjunto de 4 GiB.

## Cómo se comparan los modelos

Tu regla está incorporada en AGENTS.md y en la autoridad C03: investigar papers, documentación y reproducciones de usuarios; fijar modelo, cuantización, llama.cpp, plantilla y parámetros efectivos; medir calidad, tiempo, RAM y VRAM. Una prueba con defaults no basta para descartar un modelo. Tampoco se presume que una receta recomendada sea el óptimo.

Se contrastaron llama.cpp b9980, estable b10809 y posterior b10865, junto con las correcciones aplicables a cada familia. Actualizar el backend por sí solo no arregló los fallos semánticos medidos. Qwen Q8 y Qwen3.5-9B se evaluaron con perfiles documentados, pero no resolvieron todas las confirmaciones y lecturas de memoria; no se promovieron. Se compararon también checkpoints de Gemma, distinguiendo sus errores de generación de los del protocolo.

En conversación, el perfil registrado y el recomendado de Qwen2507 empataron en los dos grupos de semillas (5/7 y 6/7 tras revisión semántica). El fallo de historial exigió corregir su representación. Con los contenidos conservados como datos, el ensayo510 corrigió el nombre pero mostró una respuesta con comentarios internos;511 aisló temperatura0 en 22 payloads emparejados y consiguió22/22 útiles. La adopción512 y la prueba real513 confirmaron la mejora con la configuración registrada. Estas cifras son desarrollo, nunca los cien turnos frescos de aceptación.

## Qué falta para terminar

1. Cerrar las ocho rutas de respuesta y los incidentes de tu sesión manual, incluyendo aplicaciones, reproducción, capacidades y cierre de BAXY; completar narración de resultados, confirmaciones y progreso.
2. Certificar y congelar 100 turnos humanos frescos, separados del desarrollo, y obtener100/100 respuestas útiles y fieles en español, inglés y mezcla natural. Hay204 candidatos potenciales; ninguno certificado ni ejecutado para aceptación. Faltan contexto, entrenamiento y actualización de exposición.
3. Verificar averías y recuperación, interfaz real de escritorio, voz y audio físico, ASR/wake y recursos del conjunto.
4. Comprobar runtime e instalación, continuidad C04–C09, Full final íntegramente verde y publicación fuera de main.

No hay un porcentaje de cierre ni un plazo fiable todavía. Las mejoras anteriores están verificadas en su alcance; las comprobaciones pendientes no se cuentan como realizadas. CHECKPOINT.md y HANDOFF.md conservan el siguiente paso y los registros de cada prueba.
''', encoding='utf-8')
print('Owner report updated through516 focal validation; remaining work explicit.')
