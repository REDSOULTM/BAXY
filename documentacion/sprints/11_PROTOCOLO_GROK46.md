# Protocolo de las sesiones 11.x — Grok 4.6 High

Lanza una sesión limpia en Grok 4.6 High con `/goal` y pega cada `11.x` **una sola
vez**. Lee
`AGENTS.md`, `00_INDICE.md`, `../00_IDENTIDAD.md`, `11_VALIDACION.md`, este
protocolo, la cola 11.1 y el handoff anterior. Aplican las cinco leyes, los seis
invariantes y la disciplina de contexto de `10_PROTOCOLO_GROK46.md`.
Lee además `../herencia/00_MAPA.md` y la decisión 09.5 del owner: una corrección
histórica aceptada se reutiliza antes de diseñar otra. Sólo ES/EN/spanglish son
alcance; nombres ingleses de apps dentro de español cuentan como spanglish.

## Qué cambia respecto del 10

Aquí sí se persigue lo hipotético asignado, pero sólo dentro del owner y slice de
la sesión. Cada contrato o aplazado termina en una de estas salidas:

- `pass`: conducta probada con el oráculo apropiado;
- `descartado`: medición demuestra que el riesgo no existe o no pertenece al
  producto;
- `fuera_de_alcance_vigente`: lo excluye explícitamente el documento de alcance y
  no se afirma como producto terminado;
- `FALLO_DE_AMBIENTE`: falta preparación del PC para una misión in-scope; receta,
  cursor y pausa de la misma meta hasta readiness, sin relanzar el prompt;
- `fail`: defecto de BAXY que debe corregirse antes de cerrar la sesión.

`review`, `unresolved`, skip, “cubierto por otro goal” sin enlace exacto o
“ambiental” genérico no son terminales.

## Oráculos por clase

- `user_mission` y `conversation_question`: runtime real y postcondición.
- `product_requirement`: test, inspección trazable y evidencia viva cuando aplique;
  nunca se envía como prompt al producto.
- `engineering_instruction`: restricción verificable del árbol y proceso.
- `feedback_failure`: reproducción o test de regresión de la causa.
- `no_action_constraint`: prueba de que no ocurre el efecto negado.
- `preference`: memoria/configuración y conducta observable.
- `safety_instruction`: autorización, confirmación y terminal bajo riesgo.

## Presupuesto y cierre

Máximo 500k por ventana: 350k trabajo, 150k verificación. No abras otro slice.
Salidas grandes van a artefacto; al chat sólo conteos, causas, hashes y rutas.
Actualiza handoff y commit antes de compactar y continúa la misma meta desde el
cursor. Todo `fail` corregible se repara en su owner mínimo y se revalida aquí; no
se vuelve a un goal anterior. Test dueño dos veces por cambio; validación de slice;
commit/push; siguiente fichero distinto.

Si falta ambiente, detén antes de tocar producto y escribe
`artifacts/goal11/environment/<goal>.md`: contratos afectados, requisito, pasos
manuales exactos, prueba de readiness y orden de reanudación. El siguiente goal
queda bloqueado hasta que esta misma meta reanude y cierre verde. Nunca pidas al
dueño volver a pegar el fichero.
