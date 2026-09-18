# H0060 — el motor público sí responde; lo que estaba roto era su canal RSS — 2026-09-18 (Fable, REDPC)

Diagnóstico y reparación de la condición «el buscador público devuelve resultados no
relacionados a preguntas de varias palabras» (WEB1831, CONDICIONES §Web, H0060).
Medido con el conductor sin ventana (`scripts/run_baxy_conductor.ps1`) sobre el candidato
compilado en Release de esta rama, runtime registrado Qwen3-4B-Instruct-2507 Q4_K_M, sin
override. **No es una tanda sellada ni adjudica nada**: el registro privado vigente no está
en este PC (ver HANDOFF). El literal privado no se publica; los finales se identifican por
SHA-256.

## Causa medida (no la puerta de pertinencia: el canal)

Sondas de sólo lectura al mismo endpoint que usa el proveedor
(`https://www.bing.com/search?format=rss&q=…`) con la pregunta del literal y con formas de
palabras clave («whatsapp falla causas», «whatsapp suele fallar»): el RSS devolvió Gmail, las
portadas de WhatsApp y, con `cc=AR`, feeds ajenos. Ningún ítem compartía una palabra con la
consulta: la puerta de pertinencia rechazaba con razón. La misma consulta en la **página HTML
del mismo motor** (`/search?q=…&setlang=es&cc=AR`), con el User-Agent propio del producto
(`BAXY/1.0 structured-search`), devolvió diez resultados orgánicos (`<li class="b_algo">`)
todos sobre fallos de WhatsApp. DuckDuckGo lite también los daba, pero bloqueó la IP con su
página de desafío tras una docena de consultas: no sirve como motor del producto.

## Reparación (fuente de esta rama, HEAD posterior a fe64b80c)

1. `WebBrowserAdapter.SearchAsync`: lee la página HTML del motor en vez del RSS; decodifica
   el redirect (`/ck/a?…&u=a1<base64url>`) al destino real; descarta enlaces del propio
   motor; distingue «página de resultados sin ítems» de «página de bloqueo o error»
   (`web_search_engine_unavailable`, antes del efecto). Autoridad `bing_html_https`.
2. Puerta de pertinencia informada por la página: una palabra de la consulta que ningún
   resultado repite (errata «porqeu», «suele», «mucho») no cuenta contra ningún resultado;
   un resultado es pertinente si repite al menos la mitad de las palabras verificables, con
   tolerancia a flexión («fallar» ~ «fallas», raíz de ≥4 letras); cero palabras compartidas
   sigue rechazando. Palabras interrogativas y auxiliares pasan a la lista de parada.
3. Lente de fallo (mente `llm.py` y App `UserMessagePolicy.ReversesSuccessfulResult`): en
   una `web.search` verificada, las palabras que traen la consulta, los títulos y los
   fragmentos son datos observados y se enmascaran palabra a palabra antes de buscar una
   afirmación de fallo; «no pude» y los demás marcadores propios se conservan. Sin esto el
   borrador fiel «se han encontrado páginas que mencionan fallos…» se vetaba como
   `asserted_failure` en las tres etapas y el turno terminaba `composition_failed`
   (`no_response;recovery:no_response;retry_exhausted`).
4. Instrucción de composición de resultados de búsqueda: además de temperatura y pronóstico,
   prohíbe causas, explicaciones y consejos que ningún resultado contenga, «aunque lo sepas»,
   y pide decir qué página afirma cada dato. Sin esto el primer final publicado añadía
   «problemas de conexión», «fallos en el servidor» y «reiniciar el dispositivo», que ningún
   fragmento decía.

## Corridas (mismo literal, un turno cada una, perfil fresco)

| Sonda | Fuente | Terminal | SHA-256 del final (16) | Lectura |
|---|---|---|---|---|
| 1 | HEAD fe64b80c + DDG lite | published_final | 1c88efbd4a6edcf3 | «no puedo investigar porque el motor no está disponible» (DDG bloqueó la IP): honesto, no útil |
| 2 | HTML del motor, puerta 2/3 | published_final | 090cb73ebc41eec6 | «resultados irrelevantes»: la puerta exigía 4 de 6 palabras con errata y verbos |
| 3 | HTML + puerta informada | composition_failed | b2b148f30140319b | web.search verificada con 5 resultados; los tres borradores vetados `asserted_failure`/`extra_claim` (audit opt-in) |
| 5 | + lente de datos observados | published_final | e6818ad134e8e485 | útil pero con causas y consejos que ningún fragmento contenía |
| 6 | + instrucción de fidelidad | published_final | f08e92b8be7a19e3 | útil y fiel: fallos de envío/inicio, papelera, cortes; todo rastreable a los fragmentos |

Compilación: `dotnet build src/Baxy.App -c Release` y `dotnet publish src/Baxy.Core -c Release
-r win-x64` (0 errores); `tests/Baxy.Providers.Windows.Tests` compila (0 errores, 0 avisos);
`py_compile` de `llm.py` correcto. **Sin tests ejecutados, por orden del dueño.**

## Qué queda

- Medir H0060 en tanda sellada (literal + 2 variantes + límites) cuando llegue el registro
  privado; sólo entonces se acredita.
- Revalidar con el mismo candidato dos literales ya acreditados de «Información web actual»
  (noticias de hoy, clima) como regresión de la puerta nueva antes de adjudicar.
