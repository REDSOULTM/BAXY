# Protocolo de las sesiones 10.x — Grok 4.6 High

## Lanzamiento

Sesión nueva y limpia, modelo **Grok 4.6**, esfuerzo **High**, modo `/goal`. Pega
un solo fichero `10.x` entero. Grok Build ya carga `AGENTS.md`; el prompt no lo
duplica, pero sí ordena leer los documentos concretos que gobiernan el tramo.

El objetivo de `/goal` es el objetivo único escrito en el fichero, no «avanza»,
«continúa» ni «cierra rápido». El intento anterior perdió frontera cuando el goal
activo quedó reducido a una frase de ese tipo.

## Contrato de ejecución

Antes de actuar, lee `AGENTS.md`, `00_INDICE.md`, `../00_IDENTIDAD.md`,
`10_APRENDIZAJES.md`, este protocolo, `../herencia/00_MAPA.md`, la decisión 09.5
del subsistema y el handoff del tramo anterior. Después:

1. crea un checklist corto basado sólo en los criterios de cierre;
2. ejecuta el preflight de ambiente de la partición;
3. localiza primero la pieza histórica aceptada, luego dueño y prueba con búsquedas acotadas;
4. mide antes de editar;
5. corrige la causa mínima;
6. ejecuta test dueño dos veces, medición del tramo y validación proporcional;
7. escribe evidencia y handoff, revisa el diff, commitea y publica.

No pauses para pedir aprobación de un plan. Pregunta sólo ante daño irreversible a
datos personales o a otro proyecto. No trabajes en el siguiente `10.x`.

## Las cinco leyes

1. Hereda primero desde el ledger 09.5, estado del arte después, construye al final.
2. Mínimo código; una capa nueva retira en el mismo goal la que sustituye.
3. Sólo arregla lo que bloquea este tramo. Lo demás va en `APLAZADOS.md`.
4. Gana lo más ligero que cumpla; 4 GB de VRAM es techo, no objetivo.
5. Una responsabilidad por pieza, dependencias hacia dentro y cero código muerto.

Los seis invariantes siguen vigentes: catálogo tipado único; mente propone,
kernel autoriza y provider ejecuta; nada se afirma sin verificar; terminales
honestos; confirmación ligada a la invocación exacta; cero prosa visible fija; y
modelo local sin salida de contenido del usuario.

## Presupuesto de contexto

La sesión tiene un máximo operativo de **500k tokens**, aunque el modelo admita más.
Reserva aproximadamente 350k para diagnóstico/implementación y 150k para
verificación/cierre. Consulta `/context` al arrancar, después de cada campaña y
antes de Full.

- Abre sólo los archivos dueño y la partición asignada.
- Nunca vuelques JSONL ni salidas completas al chat: guarda artefactos y trae
  conteos, causas, hashes y rutas.
- Si dos lecturas seguidas no cambian la próxima acción, sobra la tercera.
- No reejecutes tramos cerrados salvo regresión demostrada por un test dueño.
- Actualiza el handoff después de cada medición material y antes de compactar. La
  compactación ayuda al modelo, pero el estado durable vive en el repositorio.
- Sin subagentes salvo exploración de sólo lectura cuyo resultado quepa en rutas,
  rangos y conclusión.

## Método de aceptación

Cada `message_id` conserva prompt, salida visible, operación/plan, hechos
contemporáneos, postcondición, terminal y veredicto. `review`, `unresolved`, timeout
oculto, skip o exclusión automática no son pass. Las repeticiones se contabilizan;
los textos únicos sólo sirven para diagnosticar.

Las acciones seguras y reversibles se prueban físicamente. Compras, mensajes a
terceros, borrados personales, energía y otros efectos peligrosos usan ámbito
desechable o fixture fiel y se publican como no físicos. Nunca se toca un dato
personal para aprobar una fila.

Sólo español, inglés y spanglish son alcance de producto. Un nombre inglés de app
dentro de una petición española es spanglish. Otro idioma puede cerrarse fuera de
alcance con procedencia, nunca como fallo ambiental ni como capacidad pendiente.

## Ambiente: fallo, no excepción

Antes de ejecutar la campaña, deriva de sus contratos una lista comprobable de
aplicaciones, cuentas, contenido, ventanas, permisos, dispositivos y estado inicial.
El preflight deja evidencia de cada requisito.

Si una petición in-scope no puede ejecutarse porque el PC no está preparado:

1. no la omitas, no la conviertas a conversación y no uses fixture para fingir el
   efecto físico;
2. no continúes una campaña parcial que vaya a ocultar el bloqueo;
3. termina la sesión como **`FALLO_DE_AMBIENTE`**, por lo que el goal no está
   cumplido y el siguiente no puede empezar;
4. escribe `artifacts/goal10/environment/<goal>.md` con requisito ausente, filas
   afectadas, por qué BAXY no puede resolverlo solo, preparación manual exacta,
   comprobación de que quedó listo y comando para reanudar;
5. después de que el dueño prepare el PC, repite **el mismo fichero 10.x** en una
   sesión limpia.

«Pon la serie X» sin servicio, cuenta o contenido disponible es un fallo de
ambiente de esa sesión, no una limitación aceptada del producto. Sólo idioma fuera
del compromiso ES/EN/spanglish o efecto explícitamente fuera del producto puede
quedar fuera de alcance; el manifiesto lo justifica fila por fila.

## Prohibiciones específicas

No soak, no espera de 24 h, no enseñar el examen al runtime, no regex por fallo, no
overlay parcial, no remake con tests rojos, no convertir ambiente/idioma en pass,
no avanzar después de `FALLO_DE_AMBIENTE`, no saltarse el ledger 09.5 y no usar el
código del intento fallido como autoridad.

## Forma del cierre

El goal sólo termina `cumplido` o `inalcanzable demostrado`. Entrega: criterios
marcados, comandos y resultados exactos, artefactos/hashes, defectos corregidos,
limitaciones reales, diff sin restos, commit publicado y el nombre exacto del
siguiente prompt. Un resumen optimista no sustituye ninguno de esos puntos.
