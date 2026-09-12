# MUSIC1078 — elegibilidad de la cola restante

Base: 6929b5ff388bc1410213380a14f3a965458053eb. Registro f1105d75a2c69ed30e8fff733e1311fa2515bc0296fe8e093d59cef7252bc1e9. Clasificación heredada de1037, contrastada con las filas actuales; lectura únicamente, sin ejecución, crédito ni sello de panel.

**39 miembros: 2 cubiertos (H0046/H0637), 37 abiertos, 6 ya en1077, 31 restantes.** Se excluyen de próxima selección H0110/H0311/H0351/H0567/H0580/H0686 mientras raíz adjudica1077. ROWS.json conserva los39 literales exactos, marcas, notas del dueño, causas y referencias actuales; la tabla siguiente contiene sólo los31 restantes.

**Ruta de mayor masa: 12 consultas musicales concretas, por el proveedor Spotify existente.** No recomiendo repetir962 ni una tanda genérica de controles: primero reconciliar su única invocación incierta documentada y resolver la selección/postlectura existente. Después, esos12 constituyen la siguiente selección homogénea condicional, con pares distintos para artista, título y género/ambiente (no dos variantes universales). Hay consultas en español y menciones explícitas/implícitas del proveedor; ninguna autoriza sustituir artista o pista por los WAV propios.

No se demostró necesidad de infraestructura nueva para ningún literal. Tampoco se demostraron10 restantes listos para ejecución inmediata: ausencia de recibo vinculado no significa fallo ni nunca ejecutado. H0333 es un literal positivo de abstención elegible sin efecto, pero sólo uno. Los restantes dependen de reparar un fallo conocido o acreditar selección, condición o contexto real; no se rellenará una tanda con aclaraciones cuando el criterio requiere reproducir.

## Matriz de31 abiertos fuera de1077

La columna grupo remite a causa y reanudación precisas de la sección posterior y de ROWS.json. «Sin vínculo» significa sin resultado individual enlazado actualmente; no certifica ausencia de ejecución histórica.

| ID | Literal intacto | Grupo | Causa actual |
|---|---|---|---|
| H0224 | qué está sonando | reads1035 | 965/970/989/1035: composición, lectura existente |
| H0543 | qué canción está sonando | reads1035 | 965/970/989/1035: composición, lectura existente |
| H0333 | no pongas música | prohibition | Sin vínculo individual |
| H0421 | si tengo spotify abierto pausalo | spotify_conditional | Sin vínculo individual |
| H0068 | pon música de daft punk | spotify_specific | 962: spotify_exact_result_not_found; efecto incierto |
| H0163 | reproducí la sinfonía 9 de Beethoven en Spotify | spotify_specific | Sin vínculo individual |
| H0213 | pon una cancion de michael jackson | spotify_specific | Sin vínculo individual |
| H0237 | pon michael jackson en spotify | spotify_specific | Sin vínculo individual |
| H0250 | Pon una cancion de michael jackson | spotify_specific | Sin vínculo individual |
| H0282 | Pon una cancion de michael jackson en spotify | spotify_specific | Sin vínculo individual |
| H0388 | Pon bad de michael jackson | spotify_specific | Sin vínculo individual |
| H0454 | pon Bad Bunny en Spotify | spotify_specific | Sin vínculo individual |
| H0548 | pon Bohemian Rhapsody en Spotify | spotify_specific | Sin vínculo individual |
| H0552 | poné rock en spotify | spotify_specific | Sin vínculo individual |
| H0579 | pon una cancion de michael jackson en spotify | spotify_specific | Sin vínculo individual |
| H0598 | poneme algo de música tranqui | spotify_specific | Sin vínculo individual |
| H0009 | poneme una canción | generic | 958: selección streaming→veto→incapacidad |
| H0066 | pon música | generic | 958: aclaración sin reproducción |
| H0405 | poné una canción | generic | Sin vínculo individual |
| H0526 | poné música | generic | Sin vínculo individual |
| H0601 | ponme musika | generic | Sin vínculo individual |
| H0022 | pon música en spotify | spotify_generic | Sin vínculo individual |
| H0178 | tocá una canción en Spotify | spotify_generic | Sin vínculo individual |
| H0215 | pon una cancion en spotify | spotify_generic | Sin vínculo individual |
| H0300 | pon musica en spotify | spotify_generic | Sin vínculo individual |
| H0656 | no me molesta, poné música | conversation_and_music | Sin vínculo individual |
| H0740 | tengo hambre poné música | conversation_and_music | Sin vínculo individual |
| H0352 | abrí chrome y poné música | browser_and_music | Sin vínculo individual |
| H0129 | Pon youtube y pon musica | youtube | Sin vínculo individual |
| H0560 | pon una cancion de michael jackson en youtube | youtube | Sin vínculo individual |
| H0614 | pon un video de lofi en youtube | youtube | Sin vínculo individual |

### spotify_specific — 12

Operación existente: media.play.query. Contenido expreso: grupo común de 12. H0068 tiene fallo UIA y efecto incierto 962; otros 11 no tienen ese recibo ni fallo individual vinculado.

Reanudación: Reconciliar invocación H0068 sin retry/cierre ciego; corregir o demostrar cambio pertinente en selección/postlectura Spotify existente; observar cliente, cuenta/sesión autorizada y reproducción pertinente. Después seleccionar los 12 con pares por artista, título y estilo, sin sustituir consultas.

### generic — 5

Operación existente: media.play.query / aclaración existente. H0009 falsa incapacidad; H0066 aclaración útil sin reproducción. Los otros tres no tienen resultado individual vinculado. Falta contenido o política de selección legitimada.

Reanudación: Resolver petición genérica conservando criterio de reproducción; observar contexto/cola real si autoriza selección. No inventar query ni acreditar aclaración sola. H0009 requiere selección musical pertinente antes de repetir.

### spotify_generic — 4

Operación existente: media.play.query / media.control según intención y estado. Cliente nombrado pero contenido ausente; no hay efecto individual registrado. Abrir Spotify no acredita reproducir.

Reanudación: Observar Spotify actual y autoridad para selección/reanudación; conservar diferencia entre reproducir una canción y reanudar. Resolver contenido mediante mecanismo existente antes de tanda.

### conversation_and_music — 2

Operación existente: media.play.query / aclaración existente. Comentario más petición genérica positiva; falta contenido o selección legitimada. No consta fallo individual vinculado.

Reanudación: Separar comentario de petición sin perder autoridad positiva; misma precondición del grupo genérico. No usar comentario como artista ni rechazar por negación fuera de alcance.

### browser_and_music — 1

Operación existente: app.open + media.play.query. Dos efectos explícitos, segundo sin contenido. No consta resultado individual vinculado.

Reanudación: Conservar ambos efectos y sus verificaciones, destino Chrome inequívoco y reproducción legitimada. Un app.open útil no acredita toda la petición.

### youtube — 3

Operación existente: media.play.youtube. Dos consultas concretas y una orden compuesta/genérica; proveedor existente independiente del RSS fallido. Seleccionar primer videoRenderer no acredita pertinencia por sí solo.

Reanudación: H0560/H0614: observar consulta, identidad/contenido pertinente y reproducción real autorizada en navegador propio. H0129 además conserva apertura+selección genérica, sin rellenar query. No repetir RSS1010/1017.

### reads1035 — 2

Operación existente: media.status. Lecturas verificadas históricas pero respuesta final fallida; READS1035 también fail. No es falta de SMTC demostrada.

Reanudación: Vincular rechazo concreto anterior con cambio pertinente de composición antes de reejecutar ambos y sus pares; no asumir que la reparación morfológica de play elimina todos los vetos de lectura.

### prohibition — 1

Operación existente: conversación sin efecto. Literal positivo de encuesta que solicita abstención; sin fallo individual vinculado en registro.

Reanudación: Elegible sin efectos con dos variantes pertinentes de prohibición, respuesta fiel y cero reproducción. No reetiquetar H0333 como límite sin crédito.

### spotify_conditional — 1

Operación existente: lectura actual + media.control pause condicional. Condición sobre Spotify, no sobre cualquier sesión SMTC. No consta fallo individual vinculado.

Reanudación: Verificar condición e identidad actual Spotify y estado antes del único efecto autorizado; ninguna sustitución por ZuneMusic. Si no puede acreditarse la condición, abstenerse/aclarar sin afirmar ausencia.
## Recibos, límites y propietarios

- H0068, MUSIC_TAIL962: inv88672a39-9448-4096-accb-10d3f48873f8; media.play.query Spotify/daft punk; verified=false, result=null, effectMayHaveOccurred=true. ROOT_ADJUDICATION registra1 caso admitido,1 confirmación y17 no ejecutados. Sólo H0068 es un efecto incierto observado; no trasladar ese estado a los otros11 candidatos. No leer credenciales, reintentar ni cerrar Spotify para resolverlo.
- Catálogo actual ProductCatalog.cs:657–712 conserva media.control, media.play.query(provider=spotify,query), media.play.youtube(query) y media.status. Cambios posteriores de control no acreditan resolución de consultas Spotify.
- SpotifyDesktopAdapter.cs:77–110 conserva el resultado UIA y autoridad spotify_windows_uia_postread; SpotifyDesktopAutomation.ps1:201–207 devuelve spotify_exact_result_not_found cuando no hay candidato. Es el propietario existente a reanudar, no un proveedor nuevo. Esta lectura no demuestra la causa UIA exacta de962 ni una reparación ya efectiva.
- WindowsMediaSessionAdapter.cs:403–550: control y lectura SMTC existentes; estado y título/artista son observados, next/previous verifica cambio de metadatos, no el vecino correcto de una cola. Los WAV/cola propios sólo prueban controles y lecturas, no consultas de autores reales ni Spotify.
- WebBrowserAdapter.cs:289–304 construye búsqueda YouTube con query literal codificada y extrae un videoRenderer. Esta ruta no es Bing RSS. H0560/H0614 requieren corroborar pertinencia además de playing; H0129 aún tiene selección genérica/compuesto.
- H0224/H0543 ya tienen evidencia fallida enlazada de READS1035: no volver a presentar como nuevos, ni atribuir reparación a1070 sin relacionar el primer rechazo concreto. El grupo es2, separado de las12 consultas.

Fuentes exactas y SHA actuales en IDENTITY.json. No hay panel ejecutable ni propuesta de código. Próximo paso recomendado a raíz: priorizar el propietario de selección/postlectura Spotify y reconciliación H0068 para habilitar una tanda potencial de12; si no es viable, las otras31 no contienen hoy una tanda de10 inmediata demostrada por esta herencia. Esta conclusión no autoriza saltar categoría ni concede cobertura.
