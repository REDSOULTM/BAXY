---
name: research-and-summarize
description: Research a topic from the web with multi-source extraction, optionally ingest results to local knowledge base, and write an honest summary citing sources. Use when user asks to "investigate", "research", "summarize from the web".
priority: medium
---

# Research and summarize

**Tools used**: `web`, `document`, `knowledge`, `memory`.
**Honesty-critical**: yes — never invent source URLs or quotes; report what
the tool returned, including failures.

## Cuándo usar este skill

El usuario dice algo como:
- "investigá X y resumime"
- "buscá info sobre X en internet"
- "compará Y vs Z según fuentes"
- "armame un resumen de noticias sobre W"
- "qué dicen los reviews de <producto>"

NO usar para preguntas de conocimiento general que el LLM puede responder
directamente ("quién es Batman", "qué es Python"). Este skill es para
**información actual** que requiere fetch externo.

## Steps

### 1. Multi-source research

```
web(action="research", query="<topic>", search_limit=6, read_limit=3, per_page_chars=4500)
```

Esto hace search → extract content de top-3 results. Devuelve:
- `sources`: lista con `title`, `url`, `excerpt`, `status_code`.
- `failures`: URLs que no se pudieron leer (con error).
- `source_count`: cuántas se leyeron exitosamente.

**Si `source_count == 0`**: NO inventar. Reportar: "No pude leer ninguna
fuente para '<topic>'. ¿Querés que pruebe con otros términos?"

### 2. (Opcional) Ingest a knowledge base local

Si el usuario quiere que el contenido quede disponible para futuras
consultas:

```
knowledge(action="ingest", text="<excerpt>", source="<url>", title="<page title>")
```

Una llamada por source. Después se puede consultar via
`knowledge(action="search", query=...)` sin re-fetch.

### 3. Escribir resumen honesto

Reglas para el resumen:
- **Citar fuentes**: cada afirmación debe tener URL asociada
  (e.g. "Según <url>, X").
- **No promediar** opiniones contradictorias como si fueran consenso.
  Si 2 sources dicen A y 1 source dice B, reportar ambos.
- **Reconocer incertidumbre**: si las sources discrepan, decirlo.
- **No extrapolar** más allá de lo que las fuentes dicen.

### 4. (Opcional) Guardar nota en memoria

Si el usuario lo pide o si es un fact que vale la pena recordar:

```
memory(action="save", key="<topic>", value="<conclusion en 1-2 frases + fecha>")
```

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
