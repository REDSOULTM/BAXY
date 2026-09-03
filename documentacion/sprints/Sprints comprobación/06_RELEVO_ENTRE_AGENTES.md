# Relevo del mismo goal a un agente nuevo

Este procedimiento permite continuar un Cxx con Grok 4.6 High y contexto de 500K
sin la conversación anterior. También sirve si el dueño cambia de cuenta: no
depende de transferir sesiones, credenciales ni memoria entre cuentas.
Forma parte del [protocolo común](02_PROTOCOLO_GROK_46_500K.md).

## Qué hace el dueño

1. Deja de ejecutar el agente anterior sobre esta carpeta. Una prueba que lanzó
   puede seguir activa; el nuevo agente debe comprobarla antes de repetirla.
2. Abre el nuevo agente en la misma carpeta BAXY Definitivo, rama main, con
   Grok 4.6 y esfuerzo High. Conserva el árbol actual, incluidos archivos nuevos,
   cambios sin commit y evidencia. Cambiar de cuenta no exige clonar otra vez.
3. Mira el Cxx activo en [Estado y continuación](05_ESTADO_Y_CONTINUACION.md).
   Si aún no comenzó ninguno, corresponde C01. Un corte durante C01 no habilita C02.
4. Como objetivo persistente, pega el **Cxx completo precedido por el bloque de
   relevo de abajo**, en un solo envío. El bloque complementa el objetivo y no
   reemplaza sus criterios. El protocolo común ya exige recuperar el estado al
   empezar una sesión nueva, aunque sólo se haya pegado el Cxx completo.

Si cambias también de máquina o carpeta, un clon del último commit puede no
contener lo pendiente. Conserva explícitamente los cambios sin publicar, archivos
nuevos y evidencia necesarios. Los procesos y efectos sobre el PC no se trasladan
con Git: el nuevo entorno debe volver a verificarse.

## Bloque de relevo para anteponer al Cxx completo

```text
RELEVO DE AGENTE — CONTINUAR EL MISMO GOAL

Trabaja en BAXY Definitivo, rama main, con Grok 4.6 High y contexto de 500K.
Eres un agente nuevo y no puedes depender de la conversación anterior. El goal
íntegro que sigue a este bloque es tu único objetivo; sus criterios siguen vigentes.

Antes de implementar o lanzar pruebas, lee AGENTS.md, la identidad del producto,
el contrato y el protocolo común referenciados por el goal, y estos archivos:
- documentacion/sprints/Sprints comprobación/05_ESTADO_Y_CONTINUACION.md
- documentacion/sprints/Sprints comprobación/06_RELEVO_ENTRE_AGENTES.md

Recupera el estado mediante el procedimiento de relevo. Verifica el repositorio,
goal activo, cambios, evidencia y procesos. No asumas que el último checkpoint
refleja todo lo ocurrido después. Distingue cambios heredados del mismo goal de
cambios ajenos; preserva ambos mientras estableces su procedencia. Comprueba si
hay otro agente escribiendo antes de empezar a modificar este árbol.

Conserva resultados que sigan demostrados para la versión y entorno actuales.
Completa ediciones parciales y valida lo pendiente. Antes de repetir un intento
con efectos inciertos, observa su resultado real. No descartes trabajo por no
haberlo escrito tú, no declares pass a partir de una intención o un log incompleto,
y no avances al siguiente goal porque la sesión anterior se cortó.

Actualiza el checkpoint con tu punto de partida y la próxima acción concreta.
Explica brevemente qué retomas y continúa ejecutando el goal; no te limites a
entregar otro plan. Guarda avances durante el trabajo, sin esperar al cierre.

A CONTINUACIÓN SE INCLUYE EL CXX ÍNTEGRO:
```

## Procedimiento de recuperación del agente

1. **Identifica el trabajo.** Contrasta el objetivo recibido con el archivo de
   estado, sus criterios y predecesores. Si todo está PENDIENTE y se recibió C01,
   empieza C01. Si hay una discrepancia, revisa primero la evidencia; no elijas
   otro goal silenciosamente. Consulta al dueño sólo si sigue sin poder resolverse.
2. **Reconcilia el árbol.** Comprueba raíz, rama y commit; examina status, stat y
   diff acotado, incluyendo los archivos sin rastrear pertinentes. Un checkpoint
   anterior al último cambio puede estar desactualizado. Registra qué cambios
   pertenecen al goal y cuáles son ajenos. No uses reset, clean, restauración de
   snapshot ni eliminación de archivos para simular un comienzo limpio.
3. **Reconcilia lo que estaba ejecutándose.** Para cada intento registrado,
   contrasta PID, ejecutable y hora de inicio, comando, log, salida y recursos
   usados. Si sigue vivo, recoge su resultado sin lanzar otra copia. Un log vacío
   o la ausencia del PID no demuestra el resultado de una operación.
4. **Comprueba los efectos.** Si hubo una operación con resultado incierto,
   observa el recurso real antes de repetirla. No conviertas una orden registrada
   en evidencia de ejecución. Las pruebas de aceptación siguen usando la misma
   entrada del usuario y los observadores exigidos por el contrato común.
5. **Determina qué sigue válido.** Reutiliza evidencia sólo si corresponde al
   código, runtime, entorno y caso actuales. Un cambio invalida los criterios
   afectados; una nueva sesión por sí sola no obliga a repetir toda la campaña.
   Si no puede acreditarse una prueba, déjala pendiente y vuelve a medirla cuando
   sea seguro hacerlo. Si el goal ya estaba completamente demostrado, reconcilia
   su cierre; no empieces el siguiente sin recibir su objetivo.
6. **Continúa y deja relevo.** Guarda fecha, sesión responsable si está disponible,
   cambios heredados, intento activo, resultados comprobados, validación pendiente
   y próxima acción. Avanza desde ese punto y actualiza el estado después de cada
   unidad pequeña o resultado material, y antes de una operación larga.

## Qué garantiza el procedimiento y qué no

Deja una base verificable para retomar trabajo guardado sin el chat anterior.
No garantiza conservar razonamiento que nunca se escribió, una edición interrumpida
ni el resultado de una prueba cuyo log no llegó a guardarse. Esos casos se
reconstruyen a partir del árbol y del estado real; no se presentan como completados.

El corte de cuota no cumple un criterio ni cierra el goal. Este procedimiento no
recarga cuota, no inicia sesiones por sí solo y no cambia el límite de contexto.
El dueño inicia el relevo; el agente reconstruye lo persistido y continúa.
