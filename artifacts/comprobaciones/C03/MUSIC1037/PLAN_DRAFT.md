# Música1037 — selección pendiente de raíz

Snapshot privado `1a7ec3d381e4d972cb0bbdf9c55ed632216618e932614e31d2ea602a74a3eae6`: los39miembros exactos de Música846 siguen abiertos. El registro154 de raíz está pendiente de consolidación; refrescar filas antes de sellar. `panel.draft.json` conserva los39literales, marcas y owner_review completos, sin adjudicar. READS1035 tiene H0224/H0543: quedan fuera de esta ejecución y de sus pares.

Propuesta concreta: **8literales +10variantes originales +5límites =23casos**, no10literales ficticios ni tanda30–40. Son las cinco acciones de `media.control` sobre una sesión real ya cargada. No hay evidencia dueña de ≥80% de éxito para música ni para esta familia que justifique una tanda masiva. No hay diez literales homogéneos de control: existen exactamente ocho. H0333 es un noveno candidato de prohibición sin efecto, reservado como conducta distinta y sin apropiarse de los pares de control.

## Partición exhaustiva y primera condición pendiente

| Grupo | IDs exactos | Operación existente / condición |
|---|---|---|
| Control de sesión,8 | H0046,H0110,H0311,H0351,H0567,H0580,H0637,H0686 | media.control; seleccionados, fixture y ejecución pendientes. Ninguno tiene recibos vinculados en el registro consultado; no llamarlos fallados ni garantizar que nunca se hayan ejecutado fuera de la evidencia enlazada. |
| Estado,2 | H0224,H0543 | media.status; READS1035, no duplicar. Heredar991 sin rehacer la campaña970/989. |
| Prohibición,1 | H0333 | Conversación sin efecto. Literal original «no pongas música», marca positive del dueño preservada; no convertirlo en boundary. Reserva sin dos variantes propias. |
| Pausa condicional Spotify,1 | H0421 | media.status y media.control con sourceApp existente; debe observarse condición e identidad. No asumir Spotify abierto ni controlar la sesión incierta962. |
| Contenido/artista/estilo,12 | H0068,H0163,H0213,H0237,H0250,H0282,H0388,H0454,H0548,H0552,H0579,H0598 | media.play.query, o exact sólo si corresponde al pedido; Spotify es política actual. Bloqueo común del provider por resolver, no aliases nuevos. |
| Música genérica,5 | H0009,H0066,H0405,H0526,H0601 | media.play.query necesita contenido; media.control(play) sólo si realmente se pide reanudar una sesión conocida. No inventar query ni dar crédito de reproducción a una aclaración. |
| Spotify genérico,4 | H0022,H0178,H0215,H0300 | Mismo problema de contenido/estado, además provider explícito. No sustituir reproducción por app.open. |
| Comentario y música genérica,2 | H0656,H0740 | Conservar ambas partes y resolver contenido sin convertir comentario en negativa. Sin ejecución vinculada; no afirmar que1024 u otros arreglos de agenda lo reparen. |
| Chrome y música,1 | H0352 | app.open más reproducción musical, conservación de ambos efectos y contenido pendiente. No llenar cuota con un compuesto aún no demostrado. |
| YouTube,3 | H0129,H0560,H0614 | media.play.youtube existente; H0129 además genérico/compuesto. Los otros2son reservas separadas de búsqueda/reproducción pertinente, no Spotify. Necesitan elección de efecto/confirmación y evidencia real de identidad musical por raíz; no cuentan como control SMTC. |

## Qué se heredó realmente

MUSIC_PANEL958: H0009 falló por selección streaming/unsupported; H0066 produjo aclaración útil pero no reproducción. H0068 sobreaclaró;961 corrigió el reconocimiento y MUSIC_TAIL962 llegó a media.play.query confirmado con query daft punk. El provider falló `spotify_exact_result_not_found`, verifiedfalse/resultnull/effectMayHaveOccurredtrue, inv88672a39-9448-4096-accb-10d3f48873f8. Los17casos restantes962 están demostrados no ejecutados por el guardstop; no son17fallos funcionales. Las variantes958 siguen material no pasado, no pares utilizables por antigüedad.

No repetir962, abrir/cerrar Spotify ni consultar otra canción para esquivar ese bloqueo. Reanudación Spotify exige reconciliar la invocación y una hipótesis nueva de selección/postlectura UIA existente. La ausencia de token descrita en PLAN958 es histórica, no lectura actual de credenciales. No se leyó ni imprimió token alguno.

Herencia991 demuestra una pérdida de conservación de lectura única para la variante EN de estado; eso no demuestra un fallo de las acciones SMTC que se proponen aquí. Los dos literales de estado no se adjudican de nuevo en1037.

## Qué acredita el mecanismo, y qué no

ProductCatalog.cs657–712: media.control es LowReversible, action∈next/pause/play/previous/stop/toggle, sourceApp opcional; media.status es ReadOnly. No se inventan operaciones ni se introducen proveedores. WindowsMediaSessionAdapter.cs63–88 elige sesión actual y permite sourceApp; un nombre de app no debe sustituir una identidad observada al construir argumentos. StatusAsync519–542 devuelve sourceAppUserModelId, título, artista y playbackStatus de ESA sesión, no silencio global.

ControlAsync403–508 manda el método SMTC de la acción y relee: pause→paused, play→playing, stop→stopped/closed; next/previous exige diferencia en título/artista. Este último predicado no demuestra por sí solo dirección correcta o cuál era el elemento esperado: antes de esos casos raíz necesita una cola propia/controlada y observada con entradas distintas. Una sesión vacía, sin controles o el reinicio de la pista actual no acreditan siguiente/anterior. El estado previo ya satisfecho debe narrarse como tal; el panel propone baseline que obligue al cambio para evitar un éxito meramente idempotente.

Spotify query utiliza API autenticada si hay token; sin token, el adaptador leído devuelve authentication_required y la ruta UIA documentada958/962 sigue pendiente. No trasladar esos fallos automáticamente a SMTC control: es otro mecanismo, pero tampoco usar el estado incierto de Spotify como fixture de control.

YouTube (WebBrowserAdapter.cs283–328,1066–1145) construye search_query directamente, toma el primer videoRenderer y verifica página watch/embed, readyState y playing. No utiliza el RSS Bing de1010/1017; no se propone repetir esas búsquedas. El predicado leído no compara la identidad musical observada con la consulta. Por ello reproducir cualquier video o devolver query en un campo no basta para H0560/H0614. Quedan como reserva para que raíz elija cómo acreditar relevancia usando las observaciones existentes, sin aflojar el criterio ni afirmar un fallo remoto no medido.

## Pares y ejecución futura

Cinco pares ES/EN originales en JSON: pause dev01/02→H0046/H0637; play dev03/04→H0110; next dev05/06→H0351/H0567; previous dev07/08→H0311; stop dev09/10→H0580/H0686. Ninguno está pasado. No intercambiar next con previous ni usar pausa para acreditar stop. H0333 necesitaría su propio par; los cinco límites no son variantes acreditables.

Las frases literales permanecen exactas. Los criterios de1037 exigen efecto solicitado, postcondición real y respuesta útil/factual; los argumentos esperados son sólo comparación futura, nunca valores a inyectar. El borrador no elige contenido musical, cola, app o preferencias del usuario. Cada caso necesita sesión conversacional independiente, pero session.new NO resetea SMTC: raíz debe observar/restablecer baseline de forma explícita antes de cada efecto y conservar los IDs/estados necesarios. Si sólo existe la sesión incierta962, no ejecutar estos controles hasta reconciliarla o seleccionar otra sesión segura mediante mecanismos actuales.

Límites originales: prohibición, explicación conceptual, traducción citada, condición futura y narración pasada; cero control/reproducción o lectura personal no solicitada. No reetiquetan H0333. Cleanup y restauración de playback son efectos que raíz debe escoger sobre identidad exacta; este borrador no los ejecuta ni ordena reintentos automáticos.

Potencial dirigido máximo8créditos, condicionado a fixture válido, literales y sus pares; no8garantizados ni39desbloqueados. Nueve candidatos estáticos si se añade la reserva de prohibición, pero sólo ocho comparten este mecanismo/selección; los demás tienen dependencias distintas documentadas arriba. Si raíz prefiere ampliar con YouTube o prohibición, debe revisar criterios y pares antes de sellar, no rellenar cuota después de ejecutar.

## Entrega y autoridad

Sólo PLAN_DRAFT.md y panel.draft.json externos. Sin sello, wire, runner, GPU, imports, tests, build, HTTP, reproducción, procesos, código ni registro modificados. Candidato null. Root decide efectos y registro vigente antes de la corrida. Los pins de las fuentes y evidencias exactas usadas están en source_pins del JSON; el material se preparó con evidencia-baxy, no con una campaña nueva.
