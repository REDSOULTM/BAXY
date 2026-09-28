# Búsqueda sin claves (D32) — fuentes de `web.search`, 2026-09-28

Paso 2 del goal v3. Decisión del dueño en `DECISIONES_COMPRENSION_2026-09-25.md` §D32; estudio previo R6
(fuentes comparadas, APIs retiradas, BYOK descartado por el dueño).

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

## Qué falta

- Que el «sí» a la oferta de abrir el navegador en el turno siguiente se resuelva como `browser.navigate` a la
  búsqueda. Es de la mente (estado de diálogo) y no se tocó.
- Fuentes abiertas por dominio de R6/D32 aún sin cablear: Wikidata (dato puntual), Frankfurter (divisas), RSS o GDELT
  (noticias). Hoy esas preguntas caen en DuckDuckGo lite o en `web_search_unavailable`.
- Decisión del dueño sobre DuckDuckGo lite: mantenerlo como último intento o retirarlo.
- La medida de búsqueda (D32: «va aparte hasta que la fuente funcione») queda por correr en la app real.
