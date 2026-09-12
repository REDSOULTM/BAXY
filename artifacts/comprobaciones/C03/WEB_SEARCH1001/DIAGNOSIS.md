# 1001 — búsqueda pública en WEB_TAIL1000

Fuente declarada por capture/meta: `04ae6daa2c28cf711eaca78b77affd7126bcd67e`. Lectura estática y registros existentes; ningún HTTP, ejecución, test, build ni cambio de fuente.

## Primera pérdida comprobada

Hay **cinco invocaciones web.search: una correcta (Wikipedia) y cuatro failed/verified=false/result=null**, todas con `web_search_results_irrelevant`. No hay cinco búsquedas fallidas.

| Caso | Shell / mente | Invocación | Resultado |
|---|---|---|---|
| H0692 Wikipedia | t1 / request8 | c7f44926-1533-475b-9272-796cf74b7932 | verified, query observada `wikipedia`, cinco resultados. |
| H0723 Marvel Rivals en Steam | t3 / request19 | 51282039-4ef6-48af-9756-c69a9b9fa72a | irrelevant; journal secuencias7–8. |
| web-named993-dev-01 NASA | t5 / request34 | 41db7efc-1455-4afb-a7bd-6fd727305dc1 | irrelevant; secuencias11–12. |
| web-named993-dev-02 Prado | t6 / request42 | 7a2e0166-8048-4bef-bdea-f22121f9f5f0 | irrelevant; secuencias13–14. |
| web-named993-dev-04 Blender | t8 / request55 | 29d07bd2-1406-44bc-9ac4-172dacfdb6b8 | irrelevant; secuencias15–16. |

Los cuatro planes conservan `web.search→browser.navigate` en las etapas del audit. Shell registra llamadas web.search en secuencias83,140,172,223. Compose recibe ya `mission_failed`, steps vacío y error del proveedor: no produce el error original ni elimina resultados correctos.

Owner exacto: `src/Baxy.Providers.Windows/External/WebBrowserAdapter.cs`, `SearchAsync:328–415`, `SearchTokens:417–449`, `IsSearchResultRelevant:452–472`.
`SearchAsync:340` construye `https://www.bing.com/search?format=rss&q=` + `Uri.EscapeDataString(query)` completo. No hay truncamiento al primer término en este código. Esa URI es construcción inferida de fuente, NO una captura de request HTTP.
El XML se carga completo; cada item se lee por sus hijos title/link/description (:353–376). La condición :390–393 sólo devuelve este error si **al menos un item es estructuralmente válido y ninguno supera relevancia**. Por tanto, para estos cuatro casos se llegó al filtro después de recibir y parsear RSS. No son timeout, cero respuesta HTTP o error de binding/schema.
El filtro compara tokens sin acentos y en minúscula, descarta stopwords y exige `queryTokens.All(observed.Contains)`, donde observed reúne título, host, ruta y snippet. Es coincidencia de **todos** los términos, no parcial; no verifica semánticamente que una página sea oficial. No se debe volver al filtro parcial que admitió recetas sin pizza y películas para novelas.

## Consulta aplicada: límite preciso de la captura

Las fases disponibles de missions.jsonl son started/completed, sin objeto de argumentos. Shell-trace contiene operación en core.call.start y detail=null en arguments.start/end; **no contiene query ni fase requested con argumentos**. Turn-audit conserva identidad/efectos, no argumentos del plan. Compose sólo conserva fallo sin resultados. Capture/events aporta textos de petición y terminales, no request HTTP ni items rechazados. Sólo Wikipedia conserva query en su resultado verificado.

En consecuencia, no atribuyo a los otros cuatro una query aplicada que estos archivos no prueban. Lectura estática de `effect_intent._symbolic_web_destination:11196` y `__main__._explicit_arguments_from_evidence:4450` predice, si se usa ese binding con el texto original:

- H0723: `marvel rivals en steam`; identidad/contenedor permanecen, stopword en no exige coincidencia.
- NASA: `la NASA`; la se descarta en el filtro, quedaría nasa como término significativo. Esto no permite explicar el rechazo por exceso de términos sin observar query real/RSS.
- Prado: `del Museo del Prado`; del se descarta y quedan museo/prado. No demuestra que los items contuvieran ambos.
- Blender: el lector positivo no acepta `Navegá hasta...`; el fallback de :4497–4510 sólo retira abre/abrir/open y puede conservar la orden completa `Navegá hasta la página de Blender para su descarga oficial.`. Tokens como navega/hasta/pagina/su podrían exigir vocabulario del mandato en cada resultado. Es discrepancia estática concreta, **no query aplicada capturada**.

Se distinguen dos hipótesis todavía abiertas: resultados remotos sin identidad pertinente frente a resultados pertinentes rechazados por términos o morfología que el filtro exige literalmente. Los títulos/snippets rechazados no están retenidos; no se inventan para escoger una causa.

## Reparación mínima justificable y alcance

No está demostrado un cambio seguro del filtro que desbloquee a los cuatro: reducir All o aceptar primer resultado repetiría el defecto de relevancia anterior. Antes de tocar esa condición hace falta conservar, en el diagnóstico existente del proveedor, query efectiva y términos faltantes por item estructuralmente válido (sin nueva consulta, sin aceptar esos items ni cambiar la autoridad de resultados). Con los registros presentes no se puede reconstruir retroactivamente.

La discrepancia de binding Blender sí delimita una propuesta futura pequeña: compartir el reconocimiento ya positivo de navegación con la extracción de operando, incluyendo flexión de verbo y preposición de destino, conservando propósito oficial/descarga y nombre original. No añadir nombres de sitios, traducciones, scores ni ampliar consultas privadas. Sólo dev-04 muestra aquí ese candidato sintáctico; no lo transfiero a NASA/Prado/H0723 ni prometo créditos históricos.
Alcance empírico de este error: **un literal abierto H0723 + tres variantes**. H0360 y otros históricos parecidos requieren evidencia propia para atribuirles esta misma causa. Número de IDs acreditables por una reparación demostrada con estos recibos: **aún indeterminado; cero acreditados**.

## Project Gutenberg dev-05: pérdida distinta

Shell t9 enlaza turn.decide request63; raw y final son **action browser.tabs.list**, no plan de búsqueda/navegación. Seq256 llama browser.tabs.list; seq258 compone confirmation. Capture publica pregunta de confirmación, después el conductor devuelve `review_pending_not_supported` 409, final sintético sin admisión real de confirmación (case-observations, index7). No hubo web.search para Gutenberg en journal.
El fallo de selección antecede al guard del conductor. No se debe explicar como búsqueda irrelevante ni sustituir el plan real por el esperado; el material esperaba navegación, pero el audit muestra tabs.list. No se amplía el harness para aprobar esa operación distinta.

## SHA256 retenidos

- `C03-web-tail1000-profile/journal/missions.jsonl`: c3f4ba4e1858498a660b2ed539d30947079c76b813f5f668ec240fdef6af9bb3.
- `C03-web-tail1000-private/run/capture/events.jsonl`: dedef8f0a7bb3ca060624c7fd446246d9e23e48d99e94ff3950a26afc642466c.
- `C03-web-tail1000-private/run/turn-audit.jsonl`: 820a15bc927f815698efdc928e7256daa1694ad8cf7c1888a544428c5b1a673d.
- `C03-web-tail1000-private/run/shell-trace.jsonl`: 854e9302b7ef2403ca85e074ed7de1a4ad103f53d777762a1cb6b03c67d82542.
- `C03-web-tail1000-private/run/compose-audit.jsonl`: 9e6a15d1f02c1b33117339d1d3c615c446c7022908dec1bdcb30578fad27d614.
- `WebBrowserAdapter.cs`: 2b6df728cc3f79a8097d2795e7978ebf7b8ebd5fa7a40d06d7371d57db6f4a0f.
