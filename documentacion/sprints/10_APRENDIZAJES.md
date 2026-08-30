# Evidencia para rehacer el Goal 10

Este documento es **evidencia, no un árbol que deba restaurarse**. El punto de
partida de producto es `8c57747`, cierre del Goal 09. Los commits posteriores del
intento de Goal 10 explican mecanismos y errores, pero su código no se hereda por
defecto.

## Las dos versiones que hay que reconciliar

En `8c57747`, `10_USO_DIARIO.md` exigía uso normal: 200 turnos reales en tres o
más sesiones, cinco peticiones ×20, modos, narración, memoria, consumo en reposo
y compuerta final. Su propósito era que BAXY se ganara permanecer instalado.

El intento posterior convirtió el 10 en validación integral: proyectó 1.947
turnos reales observados, 808 misiones accionables, 2.036 contratos históricos,
Identidad completa, latencia, caminos de error y limpieza. Entre `77537bf` y
`2a1a311` consumió 195 commits y llegó a la corrida r132 sin cerrar: 1.590 pass y
142 fail in-scope. El corte tardío 10.1–10.10 seguía poniendo campañas completas
en sesiones nominalmente cortas.

La sesión principal de Grok 4.6 High confirma el problema de tamaño: 927 mensajes
de chat, 5.065 eventos y dos rondas de `/goal`; terminó pausada sin cerrar 808,
2.036, identidad, latencia ni Full. La lección es cortar por resultado y ownership,
no por títulos breves.

Al restaurar `8c57747`, Full descubrió además una precondición que el cierre del 09
no había cobrado: Contracts 60/60, Kernel 137/137, Providers 451/451 y Setup
477/477 pasan, pero Integration queda en **2.742 pass, 85 fail y 1 skip**. El
patrón dominante de los fallos mostrados espera frases fijas mientras
`OperationOutcomeNarration` entrega el contrato JSON estructurado que Goal 6
necesita para que el modelo formule la prosa. `10.0_BASE_VERDE.md` clasifica los 85
y resuelve esa costura antes de construir corpus; no se restaura la prosa fija ni
se relaja la suite.

La conclusión no es abandonar ninguna obligación. Es separar:

- Goal 10: uso real + aceptación de los mensajes reales observados;
- Goal 11: contratos históricos adicionales + deuda + errores + cierre.

## Datos recuperables

El builder del intento produjo, desde las autoridades privadas congeladas:

- Nivel 1: **1.947 ocurrencias**, 626 textos únicos; 1.078 conversaciones o
  preguntas, 808 misiones, 56 restricciones, 3 preferencias y 2 reportes de fallo.
- Nivel 2: **808 misiones**, 281 textos únicos, 32 familias y 74 posibles cadenas.
- Anillo histórico: **2.036 contratos `product_1_0`**. No son 2.036 mensajes de
  usuario: incluyen 1.421 requisitos de producto, 290 instrucciones de ingeniería,
  218 misiones, 79 reportes de fallo y otras clases. Cada clase necesita su oráculo.

Por eso los 2.036 pasan al Goal 11 y está prohibido ejecutarlos a ciegas como
prompts. Los requisitos se prueban o trazan; las misiones sí cruzan runtime; las
restricciones demuestran no-acción.

## Lecciones operativas

- Nunca perder el journal ni aplicar un overlay de un shard incompleto.
- Una fila fuera de español/inglés/spanglish puede quedar fuera de alcance por
  idioma con procedencia. Una fila in-scope jamás se omite por ambiente: si falta
  una app, cuenta, serie, contenido, permiso o dispositivo, el goal falla y dice
  exactamente cómo preparar el PC para repetirlo.
- Probar el dueño dos veces antes de una remake completa. Una remake no sustituye
  una prueba focal.
- Cero reglas de runtime dependientes de literales del corpus. El holdout decide
  si una corrección generaliza.
- Los hechos dinámicos se contrastan en el mismo turno; una hora plausible no es
  una hora correcta.
- `tools_executed: 0` no aprueba una misión cuyo contrato exige un efecto.
- En automatización se impide apagar/reiniciar el host. Las transiciones de energía
  se prueban con fixture y contrato, nunca poniendo en riesgo la sesión.
- Los intentos r122, r123 y r130 quedaron VOID; un reinicio de host invalida una
  campaña que dependa de identidad de arranque.
- No hay soak/24 h. El dueño lo sustituyó por escenarios acotados y reproducibles.

Mecanismos concretos que merecen prueba, no copia: identidad de ventanas Explorer
por `CabinetWClass`; `WindowHandle > 0`; nombres y prefijos de catálogo; hechos
implícitos que no deben persistirse; trivia que no debe producir prosa de efecto;
y postlectura obligatoria antes de afirmar que una app o estado cambió.

## Regla de herencia

Antes de implementar una corrección, se puede inspeccionar el commit histórico que
la intentó. Se hereda únicamente si el test dueño demuestra que resuelve la causa
en el árbol nuevo sin reintroducir capas, literales de examen ni dependencias
caducadas. El commit es una pista; el test sobre el nuevo árbol es la autoridad.
