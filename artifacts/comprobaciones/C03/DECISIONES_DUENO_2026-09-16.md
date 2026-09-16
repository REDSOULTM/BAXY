# Decisiones del dueño — 2026-09-16 (límites acreditados que son capacidades)

Registro de la decisión del dueño transmitida por su agente de seguimiento (sesión Claude Code
`baxy-definitivo-7e`) a las 03:20 -03:00, tras revisar las tandas LIMITS1665, LIMITS1667, LIMITS1677,
UI1663 y AGENDA1669 del bloque nocturno (606/742). Texto del dueño entre comillas; lectura operativa debajo.

## Decisión

«Resumir un PDF, minimizar todo, ir a un canal dentro de Discord: son cosas que debería hacer.»
Y sobre el resto de casos acreditados como «límite conocido» en esas tandas: «la encuesta de por sí ya
responde todo eso, pero sí debería hacer lo de Spotify y cerrar».

Lectura: los siguientes case_id **no son límites**. Su acreditación como «cero operaciones y un final
que dice llanamente que no puede» no cumple la expectativa del dueño y debe **reabrirse** (`open`, con
causa «acreditado como límite; el dueño lo declara capacidad esperada 2026-09-16»), para medirse después
con el mecanismo que corresponda:

| Capacidad esperada | case_id | Literal |
|---|---|---|
| Resumir un PDF | H0666 | resumime informe.pdf |
| Minimizar todas las ventanas | H0238, H0529, H0658 | minimiza todas las ventanas · minimizá todas las ventanas · minimizá todo |
| Cerrar todas las ventanas / todo | H0467, H0484 | cerrame todo · cerrá todas las ventanas |
| Cerrar todas las pestañas de Chrome | H0444 | cerrá todas las pestañas de chrome |
| Navegar a un canal dentro de Discord | H0290, H0636 | ve a Cotele en Discord · ve a cotele en discord |
| Volumen de una app concreta (Spotify) | H0652 | subí el volumen de spotify |

Total: 10 casos que vuelven a `open`. Las variantes y límites de esas tandas que dependían de estos
literales pierden su valor de crédito; la evidencia de las tandas se conserva como medición.

## Lo que el dueño NO reabre (siguen como están)

Los demás casos acreditados como límite en esas tandas quedan como el dueño los dejó («la encuesta ya
responde todo eso»): ejecutar comandos (H0245 `ejecuta ls`, H0048 `ejecuta pytest`), fondo de pantalla
(H0459), presentación PowerPoint (H0188), guardar contactos (H0306, H0138).

## Notas operativas para raíz

- Minimizar/cerrar todas las ventanas y cerrar todas las pestañas: mismo marco que el punto 4 del
  2026-09-13 (permisos totales sobre el PC; no perder documentos sin guardar ni cancelar tareas ajenas).
  Si el mecanismo exige infraestructura nueva, cuenta como autorizada por el dueño en este documento; si
  desbloquea menos de 10 abiertos, se declara igual porque la orden es explícita.
- Resumir PDF: la lectura de páginas web ya se acreditó (categoría cerrada); el dueño espera lo análogo
  sobre un PDF local. Sin OCR: texto extraíble del PDF.
- Canal dentro de Discord y volumen de Spotify: requieren el cliente presente. Si la sesión/cliente no
  está en el perfil del producto, aplica el punto 7 del 2026-09-13 (aplazado, ni fallo ni cubierto), no
  «límite».
- Fable sigue siendo el único escritor del registro; este fichero sólo registra la decisión. Al aplicar
  la reapertura, publicar el nuevo conteo (606 − 10 = 596 si no hubo altas intermedias) y anotar la
  causa en el checkpoint.

Órdenes vigentes no revocadas: sin tests/dueñas/Fast/Full; sin mensajes reales a terceros; guardas de
RAM/GPU/tiempo intactas; escritor único; sin respuestas visibles fijas; no publicar textos privados.
