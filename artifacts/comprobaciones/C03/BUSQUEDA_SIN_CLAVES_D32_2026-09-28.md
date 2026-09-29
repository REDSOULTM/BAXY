# Búsqueda sin claves (D32) — fuentes de `web.search`, 2026-09-28

Paso 2 del goal v3. Decisión del dueño en `DECISIONES_COMPRENSION_2026-09-25.md` §D32; estudio previo R6
(fuentes comparadas, APIs retiradas, BYOK descartado por el dueño).

## M51 (2026-09-28, tras la revisión de v3a-final): pertinencia y una fuente por tipo de consulta

La revisión independiente de la corrida en la app real (`%LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3a-final`,
conjunto de desarrollo) encontró 30 fallos de búsqueda. Tres familias: artículos de Wikipedia que sólo compartían
una palabra con la consulta, publicados como respuesta («any new status updates» → HTTP 301; «gas stations in
Buford» → un pueblo fantasma de Wyoming; «números ganadores del loto» → Baloto; «trains to Manchester on Wednesday»
→ la inauguración de 1830); datos inventados a partir de ellos («el artículo más leído es…», «no hay números
ganadores porque…», «hay aparcamiento subterráneo» cuando la fuente decía que un partido lo *plantea*); y preguntas
de actualidad, lugares o divisas sin fuente (dólar blue, nafta, taquerías cerca, 500 CAD en USD).

Lo que cambió (sustituye al orden de fuentes de la sección siguiente, que queda como historia):

1. **Compuerta de pertinencia** (`SearchPertinence.cs`), para Wikipedia y para las noticias. Un resultado vuelve
   sólo si trata de lo preguntado: los nombres propios de la consulta (palabras con mayúscula que no abren la frase)
   están todos en el título o el extracto, o, sin nombre propio, alguna palabra de contenido está en el título; y
   título más extracto repiten las palabras de contenido (todas si son una o dos, mayoría estricta si son más). No
   cuentan como contenido los verbos de pedir («muestra», «show me»), los de relación («quién escribió», «who
   wrote»), «internet/wikipedia» ni las palabras de actualidad y precio. Si nada pasa, esa fuente **no respondió**.
   Wikipedia recibe sólo las palabras de contenido y, si nada es pertinente, una vez los nombres propios solos (en el
   idioma de la consulta).
2. **Una fuente por tipo de consulta** (`WebBrowserAdapter.SearchAsync`), en este orden:
   - dos divisas nombradas → **Frankfurter** (`FrankfurterRateSource.cs`, `api.frankfurter.dev/v2/rates`); el
     recibo trae la cantidad ya convertida («500 CAD = 353.87 USD») y el tipo de referencia con su fecha. El
     «dólar blue» no es un tipo de referencia y no se pregunta ahí;
   - una clase de sitio (aparcamiento, gasolinera, farmacia, taquería…) en un lugar nombrado («en/in/cerca de/near
     <Nombre>») o cerca de este PC (`nearby`) → **OpenStreetMap Nominatim** (`OpenStreetMapPlaceSource.cs`): el
     lugar se geocodifica (vale el candidato cuya dirección lleva el nombre; «La Puntilla, El Puerto» daba un bar
     de Ceuta), y la clase se busca dentro de su recuadro, del sitio más cercano al más lejano. De este PC sólo sale
     el nombre de la ciudad, como antes;
   - actualidad, precio, horario, sorteo («hoy», «precio», «noticias», «horario», «loto», «sale»…) → **RSS de
     búsqueda de Google News** (`news.google.com/rss/search?q=…`, edición es-419/CL o en-US según el idioma), con la
     misma URL y el mismo lector que `GoogleNewsHeadlinesAdapter`; cada titular con su medio y su hora;
   - lo enciclopédico → **Wikipedia**, como en D32;
   - **DuckDuckGo lite**, último intento para todo, con su compuerta de siempre.
   Recibo sin cambio de forma; `authority` nuevos: `frankfurter_reference_rates`, `openstreetmap_nominatim`,
   `google_news_rss_search`. Sin fuente que conteste: `web_search_unavailable`.
3. **La mente** (`llm._payload_fact_defect`): un borrador que afirma algo cuando ningún resultado trata de la
   consulta (misma regla que la compuerta) cae en `search_report_off_subject` y se reintenta con «no lo encontré»;
   uno que da por existente lo que el único resultado que lo nombra *propone o planea* cae en
   `search_report_proposal_as_fact`. Probado con los borradores reales de F-s026, F-s037 y F-p05-t1.

Prueba real, 2026-09-28 (a través del proveedor, sin mente):

| Consulta | Fuente | ms | Primer resultado |
|---|---|---|---|
| euro to usd rate for 100 eur in usd | frankfurter_reference_rates | 641 | 100 EUR = 114 USD (1 EUR = 1.14 USD, 2026-09-28) |
| cuántos pesos chilenos son 50 dólares | frankfurter_reference_rates | 529 | 50 USD = 48196 CLP |
| pharmacies near Puerta del Sol, Madrid | openstreetmap_nominatim | 2015 | Vilar, Calle de Espoz y Mina, Sol, Madrid |
| aparcamiento en Plaza Mayor, Madrid | openstreetmap_nominatim | 3070 | parking, Calle de la Concepción Jerónima, Sol, Madrid |
| noticias de la bolsa de valores hoy | google_news_rss_search | 665 | «La Bolsa de Valores de Mascate registra un aumento del 0,62 %» |
| latest news about the Mars rover | google_news_rss_search | 492 | «SA pupils build a Mars rover and beat university students…» |
| capital de Australia | wikipedia_es_api | 473 | Territorio de la Capital Australiana |
| who wrote Dracula | wikipedia_en_api | 517 | Dracula («…novel by Irish author Bram Stoker») |

Nominatim tarda 2–3 s porque son dos peticiones separadas por al menos 1,1 s (política de uso); lo leído queda en
caché un día.

Los 30 fallos de búsqueda de v3a-final, releídos con las consultas que mandó la mente (RUN.jsonl y
turn-audit.jsonl) y, donde no hacía falta la ubicación de este PC, pasados otra vez por el proveedor el 2026-09-28.
No hay corrida nueva en la app: es un análisis.

| Resultado | Casos |
|---|---|
| Contesta ahora (la fuente trae la respuesta) | s030 (gasolineras en Buford, Georgia), s090 (500 CAD = 353.87 USD), p05-t1 (aparcamientos junto a la Plaza del Polvorista), p09-t1 (Give Me Liberty), p01-t2 (aparcamientos en la ciudad de este PC; no probado, usa la ubicación) |
| Deja de inventar: sin fuente pertinente dice que no lo encontró o que no pudo buscar | s016, s026, s037 (titulares del sorteo sin los números), s076, p09-t2 (el extracto no trae el reparto), w12-t4 y w13-t1 (titulares del día sin la cifra) |
| Sin cambio | s012 (la reescritura «Tell me about any new status updates» encuentra la película «Status Update»), p08-t3 (Noah's Event Venue pasa la compuerta), w10-t3 (otro Luis Miguel), w01-t4 (precio en una tienda: ninguna fuente abierta), p05-t3 («La Puntilla» sin más se geocodifica en Catamarca), w11-t2 (taquerías en la ciudad de este PC, sin dato de reparto a domicilio) |
| Fuera de la búsqueda (comprensión o clima) | s014, s034, s048 (datos propios), p01-t1, p08-t4, p09-t3, p12-t1, p12-t2 (el contexto se pierde), p10-t1, p07-t1, p07-t2, w13-t4 (geocodificación del clima) |

### Términos de uso de las fuentes nuevas (consultados el 2026-09-28)

**OpenStreetMap Nominatim** — política de uso (operations.osmfoundation.org/policies/nominatim):
- «No heavy uses (an absolute maximum of 1 request per second).» → un turno global por proceso, 1,1 s entre
  peticiones, como mucho tres por búsqueda.
- «Provide a valid HTTP Referer or User-Agent identifying the application (stock User-Agents as set by http
  libraries will not do).» → `BAXY/<versión> (https://github.com/REDSOULTM/baxy-assistant)`.
- «Results must be cached on your side. Clients sending repeatedly the same query may be classified as faulty and
  blocked.» → caché en memoria de 24 h.
- Prohibidas las «Systematic queries» y el «Auto-complete search»: BAXY pregunta una vez por pregunta de la persona.
- «Clearly display attribution as suitable for your medium.» (datos ODbL, «© OpenStreetMap contributors») →
  **pendiente**: el recibo lleva el enlace a openstreetmap.org de cada sitio, pero la App todavía no muestra la
  atribución cuando `authority` es `openstreetmap_nominatim`.
- «Applications and services whose primary function is related to geocoding must run their own service.» BAXY no
  es un servicio de geocodificación. `nominatim.openstreetmap.org/robots.txt` pone `Disallow: /search` para
  rastreadores; la política de uso es la que regula el uso por aplicaciones.

**Frankfurter** (frankfurter.dev): «You don't need an API key.» «There are no quotas. Requests are rate-limited to
prevent abuse, but there are no monthly or daily caps.» Sobre uso comercial: «Yes. The rates themselves fall under
each provider's terms.» La API v1 está «deprecated in favor of v2, but remains available indefinitely»; se usa v2.

**Google News RSS.** Google no documenta el RSS como API. El propio canal dice: «This XML feed is made available
solely for the purpose of rendering Google News results within a personal feed reader for personal, non-commercial
use. Any other use of the feed is expressly prohibited.» Los términos de Google News añaden: «You may only display
the content of the Service for your own personal use (i.e., non-commercial use)» y prohíben «take the results from
the Service and reformat and display them» y «use any robot, spider, other device or manual process to monitor or
copy any content from the Service». `news.google.com/robots.txt` pone `Disallow: /` para `User-agent: *` salvo
portada, temas y publicaciones (el RSS queda fuera). Lectura: BAXY lee el canal para la persona que pregunta, en su
PC, sin uso comercial (D32 «no comercial por ahora»), que es lo más cercano a un lector personal; pero relata los
titulares con su voz, y eso roza «reformat and display». **Zona gris, igual que DuckDuckGo, y pendiente del dueño.**
Si el producto pasa a ser comercial, esta fuente (y `web.news.headlines`, que ya la usaba) se retira.

## Qué quedó en el código

`src/Baxy.Providers.Windows/External/WebBrowserAdapter.cs` (`SearchAsync`) y
`src/Baxy.Providers.Windows/External/WikipediaSearchSource.cs`. La operación `web.search` y sus argumentos
(`query`, `limit`, `nearby`) no cambian.

Orden de fuentes. Responde la primera cuyos resultados pasan la compuerta de pertinencia, que es la misma para
todas:

1. **Wikipedia, API Action abierta** (`/w/api.php?action=query&generator=search&prop=extracts|info|pageprops`).
   Es una petición por idioma, en serie. Va primero la Wikipedia del idioma de la consulta (marcadores es/en y
   tildes; si empatan, decide la cultura de la persona y, en su defecto, el español), y la otra hace de respaldo.
   Sale sólo la consulta, reducida a sus palabras de contenido y sin «internet», «google» ni «wikipedia». El
   User-Agent es `BAXY/<versión> (https://github.com/REDSOULTM/baxy-assistant)`, según la política de
   User-Agent de Wikimedia: con él el límite es de 200 peticiones por minuto, y sin identificarse, de 10. Las
   desambiguaciones y los enlaces que no son de esa Wikipedia se descartan. El extracto (3 frases de la entradilla,
   en texto plano) es el `snippet`.
   No se pregunta a Wikipedia cuando la consulta nombra el momento, un precio, un horario, una noticia o un marcador
   («hoy», «precio», «noticias», «horario», «today», «news»…; lista en `TimeBoundWords`), ni cuando es `nearby`.
2. **DuckDuckGo lite** (POST a `lite.duckduckgo.com/lite/`): último intento, para lo que no es de enciclopedia.
   Queda **hasta que el dueño decida** (ver §Términos).
3. **Bing HTML: retirado** (ver §Términos).

Contrato del recibo (sin cambios de forma): `result = {version, query, near?, count, results[{title,url,snippet}],
authority}`. Lo nuevo son los valores de `authority`: `wikipedia_es_api`, `wikipedia_en_api` o
`duckduckgo_lite_https`; `bing_html_https` desaparece. La mente sigue leyendo sólo `results`.

Fallos tipados:
- `web_search_unavailable` (**nuevo**; sustituye a `web_search_engine_unavailable`, que la mente no conocía y
  redactaba como «web search engine unavailable»): ninguna fuente buscó. Pasa cuando Wikipedia no contestó o no
  aplicaba y el buscador general dio error, desafío o bloqueo. En `llm._CAUSE_FACT`: «it could not be looked up
  right now; say only that, briefly, and offer to open it in the person's web browser». Probado contra los vetos de
  informe de búsqueda: «No pude consultarlo ahora. ¿Quieres que lo abra en tu navegador?» pasa.
- `web_search_results_irrelevant` (sin cambios): el buscador general devolvió una página de resultados y ninguno era
  pertinente.
- `web_search_place_unavailable` (sin cambios).

Prueba real, 2026-09-28, sólo con hosts de Wikipedia permitidos:

| Consulta | Fuente | ms | Primer resultado |
|---|---|---|---|
| primer libro de zombies | wikipedia_es_api | 1467 | Zombi (el extracto no dice cuál fue el primer libro) |
| capital de Australia | wikipedia_es_api | 581 | Territorio de la Capital Australiana («…contiene la capital nacional, Camberra») |
| who wrote Dracula | wikipedia_en_api | 488 | Dracula («…novel by Irish author Bram Stoker») |

## Términos de uso (consultados el 2026-09-28)

**Bing.** El Microsoft Services Agreement lo dice así:
- §14.f.i: «The articles, text, photos, maps, videos, video players, and third-party material available on Bing
  and MSN, including through Microsoft bots, applications and programs, are for your noncommercial, personal use
  only … downloading, copying, or redistributing these materials, or using these materials or products to build
  your own products, are permitted only to the extent specifically authorized by Microsoft.»
- §3.a.vi: «Don't circumvent any restrictions on access to, usage, or availability of the Services (e.g.,
  attempting to "jailbreak" an AI system or impermissible scraping).»
- Además, `bing.com/robots.txt` declara `User-agent: *` / `Disallow: /search`. La API oficial de Bing se retiró el
  11-08-2025 (R6).

Leer los resultados de Bing para redactar las respuestas de un producto es usarlos para construir un producto sin
autorización. Da igual que se lean por HTTP o por un navegador automatizado. Por eso **se retira**.

**DuckDuckGo.** Ni los términos (duckduckgo.com/terms) ni la política de uso aceptable (duckduckgo.com/acceptable-use)
tienen una cláusula sobre acceso automatizado. La política sólo prohíbe «Attempt to access, interfere with, or
connect to the services and/or any computer without authorization» y se reserva suspender a quien viole «the
spirit of these conditions». En `robots.txt`, `duckduckgo.com` pone `Disallow: /lite` y `Disallow: /html`, mientras
que `lite.duckduckgo.com` y `html.duckduckgo.com` ponen `Allow: /` («Ensure all paths are crawled so their noindex
tags/headers are respected»). DuckDuckGo no ofrece API de resultados: la Instant Answer API no devuelve resultados
web. En la práctica limita el tráfico automatizado, y desde el 26-09 esta red recibe desafíos. No hay prohibición
expresa, pero tampoco permiso, y D32 prefiere no hacer peticiones HTTP sueltas a buscadores. **Queda como último
intento, pendiente del dueño.** Retirarlo es borrar `ReadGeneralSearchAsync`, `ParseDuckDuckGoLitePage` y
`IsDuckDuckGoResultsPage`, y con ello `nearby` y las consultas de actualidad pasan a `web_search_unavailable`.

## La vía del navegador (CDP): estudiada, no activada

La idea era cargar la página de resultados en el Edge del perfil del producto (`CdpBrowserSession`), a ritmo
humano y sin robar el foco, y leer los resultados del DOM. No se activa por tres razones:

1. **Términos.** Para Bing no cambia nada: §14.f.i trata el material y no el medio («including through Microsoft
   bots, applications and programs»), y un navegador conducido por el programa sigue siendo extracción
   automatizada para un producto. Con DuckDuckGo la zona gris es la misma que por HTTP.
2. **Foco.** `CdpBrowserSession.EnsureEndpointAsync` arranca Edge con `UseShellExecute` y `about:blank`, con
   ventana, así que si el perfil del producto no está abierto la búsqueda abre una ventana y se lleva el foco.
   `ResolveTargetAsync` reutiliza la **primera pestaña** del perfil, y buscar ahí navegaría la pestaña que la
   persona tiene delante: YouTube, Netflix o la página que abrió. No roban foco dos variantes:
   - `Target.createTarget` con `background: true`. Sólo sirve si Edge ya está abierto.
   - Un Edge `--headless=new` con un perfil aparte. Ya no es «el navegador del usuario», sino un navegador sin
     ventana: justo el perfil que los buscadores clasifican como robot.
3. **Bloqueo.** Los desafíos del 26-09 son por red. Un navegador real en la misma red recibe el mismo desafío, y
   resolverlo sería eludir una restricción (§3.a.vi).

Lo que sí es legítimo, y es lo que el dueño eligió como salida: **abrir la búsqueda en el navegador de la persona
para que la mire ella** (BAXY no lee esa página). La redacción la ofrece con `web_search_unavailable`.

## M53 (paso 6 del goal v3, D35): recetas y argumentos se consultan antes de afirmar

Estudio R8 (`research/R8_conocimiento_honesto.md`, recomendación A + B) y decisión D35 del dueño (la respuesta no
nombra la fuente; enlace discreto «fuente» bajo el mensaje, que la voz no lee; sin fuente, se responde de memoria y
se avisa en corto).

**Elección: la fuente vive en el proveedor de `web.search`; el decisor (su LoRA) no cambia.** La mente no hace
peticiones HTTP (invariante 1: la mente propone, el proveedor ejecuta). Cuando el decisor dice «talk» y un lector
general de `semantic/knowledge.py` lee en las palabras de la persona una receta de un plato con nombre (con una
palabra de cocina: receta, ingredientes, cocina, hornear, recipe, cook…) o el argumento de una obra con nombre
(resumen/argumento/de qué trata + libro/película/serie… o un título con mayúsculas), el turno pasa a `web.search`
con la consulta que escribe ese lector: la palabra de clase y el referente («receta pastel de choclo», «resumen
libro hobbit»). El paso de argumentos lee la misma consulta del mismo pedido (como el lector de noticias pone
«noticias»). Una pregunta sobre la historia justo después del resumen de una obra, que no nombra otra obra ni pide
imaginar, consulta la misma obra (F-p11-t2). Lo abierto («una receta vegetariana»), el código y las explicaciones
siguen en charla (paso 5).

El proveedor (`WikimediaReferenceSource.cs`), antes de Wikipedia genérica:

| clase | fuente | lectura | peticiones |
|---|---|---|---|
| receta | es.wikibooks «Artes culinarias/Recetas/…» (búsqueda con `prefix:`) y en.wikibooks «Cookbook:» (espacio 102) | wikitexto de la página: plantilla «Datos de receta» (es) o secciones Ingredients/Procedure con lista o tabla (en); comentarios, `{{ing}}`, `{{coc}}`, enlaces y citas fuera; el pie de la foto dice la variante | 1 (búsqueda + contenido); si el recetario español no lo tiene, el nombre inglés del artículo de es.wikipedia (`langlinks`, en paralelo) y 1 más al Cookbook |
| argumento | Wikipedia es/en | texto plano con cabeceras (`exsectionformat=wiki`) de la primera página, si su título lleva el nombre de la obra; sección Argumento/Sinopsis/Trama/Plot…, o la introducción; ≤ 1 500 caracteres cortados en frase | 1 |

El proyecto que se pregunta primero es el del idioma de la palabra de clase. Plazo de 2,5 s por petición. El recibo
es el de siempre (`results[].title/url/snippet`) con `reference` (`recipe`/`plot`) y, si la página lo dice,
`servings`. Si ninguna página sirve, la consulta sigue como cualquier otra (Wikipedia genérica…).

Redacción (`llm._compose_consulted_answer`): la receta con su forma (qué es, «Ingredientes:» uno por línea,
«Preparación:» numerada), desde la evidencia y sin nombrarla; el escalado de porciones es un cálculo declarado por
BAXY (`servings` de la página frente a las pedidas, «multiplica por 1,5»); toda cifra de la respuesta sale de la
página, del pedido o de ese cálculo (diseño B), si no se reescribe. Si la consulta no respondió
(`web_search_unavailable`/`web_search_results_irrelevant`) y era una de estas, se responde de memoria empezando por
el aviso («No pude comprobarlo; de memoria, puede no ser exacto»). En charla, las cifras derivadas de las cantidades
de la persona las calcula `semantic/quantities.py` (evaluador cerrado sobre `ast` con `Fraction` y unidades; las
duraciones se leen enteras: 1 h 10 min = 70 min) y se entregan al redactor; una velocidad, ritmo o total que no
coincide, o un promedio sin datos, se vetan y se reescriben.

La App (`ConsultedSource.cs`) pone la dirección de la página en el mensaje publicado sólo si hubo una consulta real
a Wikimedia (web.search verificado con autoridad `wikipedia_*`/`wikibooks_*`) y la redacción no fue un último
recurso; la vista la muestra como «fuente» y la abre, a petición, en el navegador de la persona
(`POST /source/open`, sólo direcciones que el canal publicó).

**Términos de Wikilibros** (igual que Wikipedia): texto CC BY-SA 4.0 (pie de cada página), API de MediaWiki sin clave
con User-Agent identificado (D32), límites de Wikimedia (sin paralelismo agresivo: como mucho dos peticiones a la
vez). La atribución es el enlace a la página. Los recetarios los escribe cualquiera y la cobertura en español es
desigual (R8 R2): el pastel de choclo de es.wikibooks es la variante dulce peruana, y su foto lo dice.

Medido en vivo el 2026-09-28 desde esta red (fuente sola, sin mente): «receta sopaipillas» 560–594 ms, «recipe
chicken alfredo» 528 ms, «receta pan de banana» 663 ms (vía «Banana bread»), «receta pastel de choclo» 247 ms,
«resumen libro hobbit» 602–758 ms, «summary novel Frankenstein» 1 701 ms (artículo largo).

## Qué falta

- Que el «sí» a la oferta de abrir el navegador en el turno siguiente se resuelva como `browser.navigate` a la
  búsqueda. Es de la mente (estado de diálogo) y no se tocó.
- Fuentes abiertas por dominio de R6/D32: Frankfurter, Nominatim y el RSS de noticias quedaron cableados en M51;
  Wikibooks y el argumento de Wikipedia en M53; falta Wikidata (dato puntual: edad, población) y las listas con
  cifras (rankings: F-s020, tablas de «List of…»).
- Atribución de OpenStreetMap en la App cuando responde Nominatim (M51).
- Decisión del dueño sobre el RSS de Google News (zona gris, M51).
- Decisión del dueño sobre DuckDuckGo lite: mantenerlo como último intento o retirarlo.
- La medida de búsqueda (D32: «va aparte hasta que la fuente funcione») queda por correr en la app real.
