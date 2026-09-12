# 1015 — consulta efectiva y rechazos RSS

Alcance: lectura de WebBrowserAdapter.cs actual y los cuatro registros privados de 1010; herencia exacta de DIAGNOSIS1001 conforme evidencia-baxy. Sin HTTP, producto, pruebas, build ni cambios de fuente. HEAD comunicado por raíz: 437e4183; no se atribuye éxito funcional.

## Primera discrepancia demostrada

| Consulta efectiva capturada | Observación anterior al filtro | Conclusión limitada |
|---|---|---|
| `marvel rivals en steam` | 7 items de Marvel general; todos carecen de `rivals` y `steam` | La consulta conserva sus palabras, pero la colección no satisface su objeto completo. |
| `la NASA` | 10 items ajenos, entre ellos WhatsApp/Lowyat y Microsoft Community; todos carecen de `nasa` | Incluso el único término significativo falta; no es un falso rechazo por exigir demasiados términos. |
| `Navegá hasta la página de Blender para su descarga oficial.` | La consulta conserva toda la orden; 10 items estructuralmente válidos rechazados | Hay además una pérdida independiente de delimitación del operando, anterior al HTTP. No basta corregirla para demostrar resultados pertinentes. |
| `the official Python website` | 10 items estructuralmente válidos rechazados | El resultado no supera el criterio actual; no se demuestra una causa distinta por este registro. |

Los cuatro registros declaran `verified:false` y `omittedItems:0`. No son hechos públicos verificados. Para Marvel, aparecen marvel.com, sus películas, Wikipedia del universo/comics y YouTube de Marvel; ninguno demuestra el juego en Steam. NASA contradice una explicación universal de «sólo se busca el primer término»: los items tampoco identifican NASA y no se capturó cómo el servidor interpretó `la`.

## Construcción exacta en el código

Owner: `src/Baxy.Providers.Windows/External/WebBrowserAdapter.cs`, SearchAsync:331–400; constructor:30–31; IsSearchResultRelevant:530–550.
`RequiredString(arguments,"query").Trim()` conserva el query; `SearchTokens(query)` sirve al filtro y no sustituye el valor enviado. Línea343 construye `https://www.bing.com/search?format=rss&q=` + `Uri.EscapeDataString(query)`; línea344 usa `_http.GetStreamAsync`. Cliente: timeout20s y User-Agent `BAXY/1.0 structured-search`.
URIs inferidas del código y consultas capturadas, NO capturadas en el transporte:
- `https://www.bing.com/search?format=rss&q=marvel%20rivals%20en%20steam`
- `https://www.bing.com/search?format=rss&q=la%20NASA`
No hay truncamiento local de esas consultas en esta construcción. El lector XML recoge title/link/description de los items, luego compara todos los términos significativos con título, URL y descripción. `queryTokens.All(observed.Contains)` protege correctamente estos dos casos. Cero coincidencias con items válidos termina `web_search_results_irrelevant`, antes de entregar resultados como verificados.

La captura no conserva RequestUri efectivo/final, redirecciones, headers ni cuerpo RSS original. Demuestra contenido ajeno en los items parseados, pero no identifica si la causa es interpretación RSS del query, intermediación o respuesta de servidor. No se atribuye proxy/caché ni se propone aflojar el filtro. `%20` es la representación que construye el código; esta lectura no demuestra que cambiarla por `+` repare nada.

## Siguiente experimento acotado, pendiente de autorización/ejecución raíz

Comparar sólo las dos consultas públicas anteriores, máximo seis GET, mismo cliente/UA/timeout y sin navegación ni reintentos automáticos:
1. A: URI actual `?format=rss&q=...` con espacios `%20`.
2. B: `?q=...&format=rss`, conservando `%20`; cambia únicamente el orden de parámetros.
3. C: mismo orden B, espacios `+`; cambia únicamente esa representación del valor q, conservando el escape del resto de caracteres.
Retener localmente URI preparada y URI final de respuesta, status/content-type, headers de caché/redirección disponibles, hash del cuerpo RSS, título/enlace de channel y los mismos items/términos faltantes. No introducir esos datos como resultados verificados. Comparar A→B y B→C por separado; un cambio de pertinencia orienta una reparación de construcción, pero una sola respuesta distinta no demuestra causalidad estable. Si las tres formas siguen ajenas, detener sin adoptar cambio ni bajar requisitos de relevancia.

## Masa y reanudación

La frontera es web.search existente y sus planes posteriores de navegación simbólica. En estos cuatro registros, el literal directamente identificado es H0723 y los otros tres son variantes NASA/Blender/Python; no son cuatro créditos históricos. La reparación podría volver acreditables pares de navegación pendientes para los cinco literales que raíz mantiene con literal pasado, y beneficiar otros abiertos de web36, únicamente tras ejecución pertinente. No se demuestra que desbloquee esos cinco ni toda la categoría. Mantener separado el binding de Blender; esperar esta comparación antes de modificar HTTP o resultados.

## Evidencia retenida — SHA256

- `C:/Users/usuario/AppData/Local/BAXY/C03-web-diagnostic1010-profile/captures/web-search-rejections.jsonl`: `6dd961c258a8be4d59307f27d0bfeb4169e60353ffc5bb44c0c012bd0463a546` (cuatro registros).
- `D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/src/Baxy.Providers.Windows/External/WebBrowserAdapter.cs`: `0f78170466bde65883904dfd7ef717a67ba7cf96ffa5b53f9cae818b4f411afb`.
- `C:/Users/usuario/AppData/Local/BAXY/C03-web-search1001-proposal/DIAGNOSIS.md`: `82bf11ba20ec5f0695ce866b185f3473f9032028062371f02b3ea1d904aacfb5`.
- Líneas JSON originales, UTF8 sin terminador: Marvel `73f7e17ae36cd4898011638d9194b3ad4d08a1c5f2606f0a6d719669096955b3`; NASA `024d9a1414782b67e7dddbf977f6029eaad15a2df6ee36b2cd12aa3220fd34f5`.

No parche; cero créditos adjudicados. Pruebas y reproducciones omitidas por instrucción explícita del dueño.
