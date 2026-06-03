---
name: research-and-summarize
description: Research a topic from the web with multi-source extraction, optionally ingest results to local knowledge base, and write an honest summary citing sources. Use when user asks to "investigate", "research", "summarize from the web".
priority: medium
metadata:
  examples:
    - "investigá sobre este tema en internet"
    - "averiguá qué es esto y resumime"
    - "buscá información sobre esto y hacé un resumen"
    - "investigá a fondo y citame las fuentes"
    - "investigá qué pasó con este tema y contame"
    - "averiguá qué es esto y explicámelo"
    - "research this topic online and summarize it"
    - "pesquise sobre isso na internet e resuma"
  when_to_use:
    - "el usuario quiere que busques información nueva en internet sobre un tema"
    - "averiguar sobre algo desconocido consultando fuentes en la web"
  limitations:
    - "resumir todo lo anterior de la charla o de esta conversación"
    - "no es para resumir un texto que el usuario ya te dio"
    - "hacer un resumen de los mensajes previos sin buscar en internet"
    - "not for summarizing the previous conversation or a text already given"
---

# Research and summarize

Tools: `web`, `document`, `knowledge`, `memory`. Honesty-critical: SÍ — nunca inventar URLs ni quotes; reportar lo que la tool devolvió, incluidas las fallas.

Usar cuando: "investigá X y resumime", "buscá info sobre X en internet", "compará Y vs Z según fuentes", "armame un resumen de noticias sobre W", "qué dicen los reviews de <producto>". NO usar para conocimiento general que el LLM responde directo ("quién es Batman", "qué es Python"). Este skill es para **información actual** que requiere fetch externo.

## Steps

1. **Multi-source research.** `web(action="research", query="<topic>", search_limit=6, read_limit=3, per_page_chars=4500)`. Hace search → extract de top-3. Devuelve: `sources` (title/url/excerpt/status_code), `failures` (URLs no leídas + error), `source_count`. **Si `source_count == 0`**: NO inventar. Reportar: "No pude leer ninguna fuente para '<topic>'. ¿Pruebo con otros términos?"
2. **(Opcional) Ingest a knowledge base local.** Si el usuario quiere que quede para futuras consultas: `knowledge(action="ingest", text="<excerpt>", source="<url>", title="<page title>")` — una llamada por source. Luego se consulta vía `knowledge(action="search", query=...)` sin re-fetch.
3. **Escribir resumen honesto.** Reglas: **citar fuentes** (cada afirmación con su URL, ej. "Según <url>, X"); **no promediar** opiniones contradictorias como consenso (si 2 dicen A y 1 dice B, reportar ambos); **reconocer incertidumbre** si discrepan; **no extrapolar** más allá de lo que las fuentes dicen.
4. **(Opcional) Guardar nota en memoria.** Si lo pide o vale la pena recordar: `memory(action="save", key="<topic>", value="<conclusión en 1-2 frases + fecha>")`.

## Outcomes honestos

| Estado | Cómo reportar |
|---|---|
| 3 sources leídas exitosamente | "Según [n] fuentes: ... [resumen + citas]" |
| 2 OK + 1 failure | "Encontré 2 fuentes útiles ([url1], [url2]). La 3ra falló por <error>. Según estas:" |
| 0 sources leídas | "No pude leer ninguna fuente sobre '<topic>'. ¿Probás con otros términos?" |
| Sources contradictorias | "Las fuentes no coinciden: [url1] dice A, [url2] dice B. No tengo evidencia para decidir cuál es correcta." |
| Topic muy genérico | "Tu pregunta es muy amplia. ¿Querés enfocar en algún aspecto? (e.g. precio, reviews, specs, fechas)" |

## Anti-patterns

- ❌ Inventar URLs que no estaban en `sources`.
- ❌ Combinar quotes de fuentes distintas como si fueran una sola.
- ❌ Decir "según mi investigación X" cuando NO ejecutaste `web.research`.
- ❌ Promediar precios/datos numéricos de fuentes incompatibles.
- ❌ Resumen sin citar al menos `source_count` URLs.
