# Sonda del motor de búsqueda — WEB1291 (2026-09-14, raíz)

Consultas directas desde este PC con PowerShell (`Invoke-WebRequest`, UA de navegador), independientes del producto.

| Consulta | Fuente | Primeros títulos devueltos |
|---|---|---|
| Transformers | Bing RSS (`search?format=rss`) | AeroFarms - The Vertical Farming Company; Empowering Vertical Farming Automation through AI and IOT; Vertical Farming: How Automation Transforms the Future |
| Transformers | Bing RSS + `mkt=es-CL` | How to Become a Dental Assistant in Wyoming (2026); How to Become a Dental Assistant (10 Essential Steps); Dental Assistant - LCCC |
| Transformers | Bing RSS + `cc=CL&setlang=es` | 10 Financial Management Strategies; Financial Management Techniques; How To Manage Your Money |
| marvel rivals steam | Bing RSS | Marvel.com; Marvel Movies (MCU); Universo cinematográfico de Marvel - Wikipedia |
| "marvel rivals" steam | Bing RSS | Marvel.com; Marvel Movies (MCU); Universo cinematográfico de Marvel - Wikipedia |
| marvel rivals steam | Bing HTML (`search?q=`, 10 `b_algo`) | Marvel.com; Marvel Movies (MCU); Universo cinematográfico de Marvel; Marvel Comics - Wikipedia (enlaces `bing.com/ck/a` redirigidos) |
| recetas de pizza | Bing RSS | Recetas \| Gourmet; Cocina Fácil: más de 10.000 Recetas de cocina; Recetas de cocina +20.000 recetas fáciles (ninguno con «pizza») |
| Transformers | DuckDuckGo HTML (`html.duckduckgo.com/html/`) | Buy as 01 transformers (AliExpress); Transformers (film series) - Wikipedia; Transformers - Wikipedia — **pero la segunda y siguientes peticiones devuelven 202 (desafío anti-bot), sin resultados** |
| marvel rivals steam / recetas de pizza / que es el h2o | DuckDuckGo HTML y lite | 202, 0 resultados |

Conclusión: desde este PC, Bing (RSS y HTML) devuelve resultados ajenos al tema para consultas genéricas y no incluye la página de Steam de Marvel Rivals; el filtro de pertinencia del producto (todos los términos en título/host/ruta/fragmento) los rechaza con razón (`web_search_results_irrelevant`). DuckDuckGo bloquea peticiones automatizadas tras la primera. Las noticias en español (WEB1271) sí funcionaron porque el RSS de Bing indexa noticias. Condición de motor, no de lector ni de compositor: los finales de WEB1291 dicen con honestidad que no hubo resultados pertinentes.
