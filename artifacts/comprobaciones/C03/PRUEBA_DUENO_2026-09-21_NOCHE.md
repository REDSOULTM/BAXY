# Prueba del dueño 2026-09-21 23:46–00:06 (perfil dev-mente-v2, build Release de baec1159b) — auditoría

Fuente: registro privado `%LOCALAPPDATA%\BAXY\dev-mente-v2\conversation\conversation.v1.jsonl`, turnos 111–231
(copiado al paquete de traspaso como `private-logs/conversation.v1.jsonl`; el fichero NO va a git). 60 turnos del
dueño: **22 bien, 38 mal o flojos.** Lo que el dueño dejó dicho en la propia conversación (turno 164), y que manda:
«BAXY debe funcionar de forma generalizada, no sólo para los 742 casos: esos son ejemplos de los cuales se debe
generalizar para que BAXY siempre entienda cuando cualquier persona le hable de lo que sea».

## Hallazgo principal: la lectura se midió turno a turno; en conversación se rompe

Las tandas y las cien miden literales aislados (un perfil por caso) o charla sin efectos. En una conversación real
el fallo dominante es **de contexto**: BAXY pregunta algo, el dueño contesta, y BAXY no une la respuesta con el
pedido anterior (o vuelve a preguntar lo mismo). Ocho de los 38 fallos son exactamente eso; nueve más son la guarda
«En eso no encuentro un pedido para mí» disparándose sobre frases de charla o sobre respuestas a sus propias
preguntas. Ninguna tanda actual lo detectaría porque ninguna encadena turnos dependientes.

## Tabla (turno = línea del registro; clase: C contexto · L lectura · A adaptador/estado · P presentación/compositor · M motor · K conocimiento)

| Turno | Dueño dijo (forma) | BAXY hizo | Debía | Clase | Quién lo arregla |
|---|---|---|---|---|---|
| 116–117 | frase de charla terminada en «, como tu» | «El mensaje me llegó cortado en “, como tu”» | seguir la charla | L (detector de mensaje cortado) | Fase 3.5 |
| 118–121 | la misma frase sin coma; luego «no era un pedido, sólo charla» | dos veces «En eso no encuentro un pedido para mí; ¿necesitás algo?» | seguir la charla (el modelo lo hace bien en 123–139) | L (guarda de «sin pedido» sobre charla) | Fase 3.5 |
| 140 | «hablando de amor, pon una canción de amor en YouTube» | preguntó qué tono de canción | media.play.youtube con búsqueda «canción de amor» | L | Fase 3.5 |
| 142–145 | «Quiero una canción de amor» → BAXY «¿en Spotify?» → «No, en YouTube» | preguntó otra vez qué canción | unir la respuesta con el pedido de 140: YouTube ya estaba dicho | **C** | Fase 3.5 (contexto) |
| 146–147 | «Pon una canción de amor en YouTube» | reprodujo (título citado) | ok | — | — |
| 148–149 | «para la canción» | «No estoy escuchando nada en este momento» | detener lo que acababa de reproducir (estado de reproducción del turno anterior) | **A/C** (estado de media no persistido) | Notebook |
| 150–153 | «cierra edge» → confirmación → «confirmo» | cerró; pero preguntó «¿confirmar o cancelar **la cerrado** de Edge?» | texto de confirmación bien formado («el cierre de Edge») | P | Notebook |
| 154–155 | «¿sabés qué peli estoy viendo en PotPlayer?» | «No sé… no pude entender bien la pregunta» | leer el título de la ventana de PotPlayer (window.resolve) y contestar | L | Fase 3.5 |
| 156–163 | «estoy viendo Colony, la de zombies; investigala, quiero saber qué piensa la gente» → «Investigala» → «te dije que investigues, eso debería ir a web search» | cuatro veces «no encuentro un pedido» | web.search «Colony película reseñas/opiniones» y resumen; «investigala» = anáfora al tema | L + **C** | Fase 3.5 |
| 164–167 | dos párrafos dirigidos «al agente que lea esto» | «No pude entender» / «no encuentro un pedido» | charla (acusar recibo) | L (guarda) | Fase 3.5 |
| 168–173 | «Dime algo» / «Di la palabra “algo”» / «muy bien» | curiosidad del Titanic / «Algo.» / «Gracias, ¿qué necesitas?» | ok | — | — |
| 174–181 | qué es un zombie / qué hacen / primera iteración / primer libro | contestó; en 181 inventó «*The Zombie* de George A. Romero, 1968» | para hechos verificables, web.search antes de afirmar; no inventar títulos | K | Fase 3.5 (regla: hechos datados → búsqueda) |
| 182–183 | «abre Steam y ve a la biblioteca» | abrió y pulsó BIBLIOTECA, verificado | ok | — | — |
| 186–187 | «ahora en Steam apretá en Counter-Strike 2» | leyó la biblioteca: «ya está instalado, puedes abrirlo» | pulsar la entrada de la biblioteca (motor de computer use) | M | Fase 4/5 |
| 188–189 | «pero quiero que le hagas click» | **«Claro, ya le hice click.» sin ninguna operación** | nunca afirmar un efecto que no ocurrió: límite honesto | **P (efecto inventado, gravísimo)** | Notebook (veto en el compositor) + Fase 3.5 |
| 190–193 | «no lo hiciste, no lo vi» / «dímelo tú, te mandé la misión a ti» | «¿Podrías explicarme qué hiciste exactamente…?» / «no pude entender» | reconocer que no se hizo nada y decir por qué | P + C | Notebook + Fase 3.5 |
| 194–195 | «en Steam ve a Crash Bandicoot» | 45 s y «No pude armar una respuesta (no_response; retry_exhausted)» | motor; y mientras no exista, límite honesto inmediato, no 45 s de fallo del compositor | M + P | Notebook (tiempo/fallback) · Fase 4/5 |
| 198–199 | «mutea mi micrófono» | «No entendí “mutea”, “microfono”» | audio.microphone.mute (mutear/desmutear son verbos normales; «microfono» sin tilde no es palabra desconocida) | L | Fase 3.5 |
| 200–201 | «silencia mi micrófono» | silenció | ok | — | — |
| 202–203 | «activalo» | «No entendí “activalo”» | anáfora: reactivar el micrófono recién silenciado | **C** + L | Fase 3.5 |
| 204–205 | «activa mi micrófono» | «No pude activar… no pude observar el efecto» | la operación de reactivar debe verificarse (post-lectura del estado del micrófono) | A | Notebook |
| 206–207 | «desmutea mi micrófono en Discord» | «No puedo desmutear tu micrófono en Discord» | control dentro de Discord = motor (H0128 y familia); límite honesto correcto hoy | M | Fase 4/5 |
| 208–209 | comentario sobre el motor | «no encuentro un pedido» | charla | L (guarda) | Fase 3.5 |
| 210–213 | «BAXY, cierra BAXY» (dos veces) | «la aplicación no tiene ventana abierta» | cerrarse a sí misma (o decir con verdad que no se cierra sola y cómo hacerlo) | A | Notebook |
| 214–219 | «baja el volumen» → «¿cuánto?» → «20» → «¿quieres que ajuste el volumen?» → «sí» → «no pude entender» | la cantidad no completó el pedido pendiente; el «sí» tampoco | «20» tras «¿cuánto?» = bajar 20; nunca preguntar lo ya contestado | **C** | Fase 3.5 (contexto) |
| 220–221 | «pon el volumen a 20» | puso 20 | ok | — | — |
| 222–225 | «ahora súbelo a 100» → «¿a qué cosa?» → «al volumen» | recién a la segunda | «lo» = el volumen del turno anterior | **C** | Fase 3.5 (contexto) |
| 226–227 | «¿la nueva peli de Resident Evil es buena?» | «no tengo información actualizada» | web.search y resumen de reseñas | L | Fase 3.5 |
| 228–231 | «pues investigala, dime si tiene buenas o malas reseñas» → «¿sobre qué producto?» → «te lo dije hace 2 mensajes» | preguntó el tema que estaba dos turnos atrás; luego «no encuentro un pedido» | anáfora al tema anterior | **C** | Fase 3.5 (contexto) |

## Reparto

- **Notebook (adaptador/estado/presentación, antes de su cierre):** 148 (estado de reproducción → «para la
  canción» detiene lo último reproducido), 151 (texto de confirmación de cierre), 189/191 (veto duro: un final
  nunca afirma un efecto sin operación completada; si no hubo operación, límite honesto), 195 (fallo del compositor
  en 45 s → respuesta de límite inmediata), 205 (post-lectura de reactivar micrófono), 211 (cerrar BAXY a sí misma o
  respuesta veraz). Cada uno con test, Fast verde, cien, y una tanda de re-medición si toca una lectura acreditada.
- **Fase 3.5 (Fable, lectura y contexto):** todo lo marcado L y C. El harness de replay DEBE correr conversaciones
  enteras con historial (no literales sueltos), y esta sesión entera es un caso de regresión: cada turno con su
  «debía».
- **Fase 4/5 (motor):** 187, 195, 207.

## Medida contextual nueva (la pide el dueño)

Los 742 literales se midieron uno a uno. A partir de ahora, además:
1. `artifacts/comprobaciones/C03/contexto/dueno-2026-09-21.turns.jsonl`: esta conversación como guion del conductor
   (`scripts/run_baxy_conductor.ps1`, mismo mecanismo que las cien) con la tabla de arriba como esperado por turno.
   Se corre en el notebook antes y después de sus arreglos y en la Fase 3.5 antes y después de la migración; la
   cifra es «turnos bien / 60». Los efectos son los del dueño (YouTube, cerrar Edge, Steam, micrófono, volumen) y
   corren de verdad con preset/restore de volumen y micrófono.
2. **Bancos contextuales del registro:** el notebook agrupa los 742 literales por categoría en guiones de 15–25
   turnos con dependencias reales (pedido → pregunta de BAXY → respuesta corta; pedido → «ahora lo mismo en X»;
   pedido → «para/cierra/deshazlo»), en `contexto/<categoria>.turns.jsonl`, y los corre como cien contextuales
   (`cien-ctx-NN`) con captura; se puntúa cada turno como bien/mal/pregunta-repetida. Sólo turnos sin efecto o con
   efectos reversibles (volumen, brillo, ventanas propias, notas del perfil); los de efecto irreversible se dejan
   como pedidos que deben producir la confirmación correcta y se cancelan.
3. La regla de generalización del dueño (turno 164) va a `documentacion/SEMANTICA.md` como principio de diseño.
