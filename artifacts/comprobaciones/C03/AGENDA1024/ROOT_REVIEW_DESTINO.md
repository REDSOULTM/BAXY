# Revisión raíz de la propuesta 1024 en el PC destino — sin integrar

Revisión estática hecha en `ed305c38` contra el fichero base, **antes** de tener el parche a la vista.
El diff real (`repair.patch` `b45ff88467f3ea281fb59520687a59bc7b96ad8e5f0f6f507807aa92ea4dd493`)
viaja en el ZIP privado y no está en esta máquina, así que esto revisa **el diseño descrito en
`AGENDA1024/DIAGNOSIS.md`**, no sus bytes. No hay integración, medición ni adopción.

## Lo que sí se puede verificar aquí

- `src/baxy_mind/effect_intent.py` en `ed305c38` tiene SHA256
  `3bb83dc8f0c8736c86d402d0faf656915044a9089b8b27b9b9a430b36365cade`, **exactamente la base**
  declarada por 1024. El fichero no cambió desde `d97670db`: su último commit es `20dab7ed`, la
  fuente de producto de la entrega. La propuesta sigue aplicándose sobre la base correcta.
- `_time_only_reminder_request` ya existe (línea 2235) y `_reminder_has_actionable_due` (línea 2259)
  contiene inline el patrón de duración que 1024 quiere extraer a `_REMINDER_RELATIVE_DURATION`.
  `_REMINDER_RELATIVE_DURATION` no existe todavía. La refactorización descrita es exacta.
- El diagnóstico de fondo se sostiene leyendo el código. `_time_only_reminder_request` exige hoy el
  sustantivo literal `recordatorio|reminder` seguido de `para|for` y una hora. «Avísame en 30
  minutos» no lo satisface, y por eso H0121/H0343 nunca llegan a pedir `title`.

## El punto que el diagnóstico deja corto

La puerta real no es `_time_only_reminder_request`, es el `if` que la envuelve (líneas 3170–3182):

```python
if (
    "reminder.create" in available
    and _has(folded, r"\b(?:recordatorio|reminder)\b")
    and _head_is(_request_head(folded), r"(?:pon|ponme|pone|crea|crear|set|create)")
):
    if not _reminder_has_actionable_due(folded):
        return ClarificationIntent(("reminder.create",), ("due_time",))
    if _time_only_reminder_request(folded):
        return ClarificationIntent(("reminder.create",), ("title",))
```

Para «avísame en 30 minutos» ese guard falla en las dos condiciones: no hay sustantivo
`recordatorio` y `avisame` no está entre las cabezas de creación. El bloque entero se salta. Por eso
ampliar sólo la función interna no cambiaría nada, y el diagnóstico lo reconoce de pasada («el
caller añade esas cabezas»). Esa ampliación del guard es la parte arriesgada del parche, no la
refactorización:

1. **Riesgo de arrastre a `due_time`.** Si el guard admite `_SCHEDULING_BY_ITSELF` de forma
   independiente del cuerpo, entonces peticiones con `avisame`/`despiertame` y **sin** plazo
   accionable caerían en la primera rama y empezarían a preguntar `due_time` donde antes el bloque
   se saltaba. El diagnóstico afirma que las cabezas se añaden «únicamente cuando el cuerpo completo
   demuestra que sólo se proporcionó tiempo», lo cual evitaría el arrastre, pero eso es precisamente
   lo que hay que comprobar en el diff y medir con controles: un literal de aviso sin plazo y un
   literal de aviso con título ya dado.

2. **Efecto colateral no mencionado: la ruta de efecto.** `_time_only_reminder_request` tiene un
   segundo uso, en la línea 13842:

   ```python
   if "reminder.create" in available and _time_only_reminder_request(folded):
       return None
   ```

   Es una **abstención**: el reconocedor determinista renuncia a producir el efecto. Ensanchar la
   función ensancha también esa abstención, así que «avísame en 30 minutos» dejaría de producir
   `EffectIntent` por esta vía aunque hoy lo produjera por otra rama. `AGENDA1024/DIAGNOSIS.md`
   sólo analiza el caller de aclaración (3178–3182) y no menciona 13842. Puede ser correcto —
   coherente, incluso: si falta el título, abstenerse y pedirlo es lo que se busca — pero **no está
   revisado**, y es el tipo de cambio que se cuela como regresión silenciosa en recordatorios que
   sí traen contenido inferible.

3. **Lo que la revisión estática no puede demostrar**, y el diagnóstico ya lo admite: que tras
   recibir el título la continuación conserve el plazo. La aclaración pide `title` y no entrega
   argumentos ejecutables; que los 30 minutos sobrevivan al segundo turno es conducta de producto,
   no propiedad del regex.

## Veredicto de esta revisión

**No integrar todavía.** El diseño es el más simple que resuelve H0121/H0343 —reutiliza gramática
existente, reutiliza `ClarificationIntent(("reminder.create",), ("title",))`, no añade prompts,
reglas por literal ni respuestas fijas, y no toca `__main__.py`, `llm.py` ni el catálogo— y por eso
merece medirse. Pero le faltan tres cosas antes de adoptarse:

- ver el diff real, para confirmar que la ampliación del guard está condicionada al cuerpo completo;
- decidir explícitamente qué pasa en 13842;
- medir el subconjunto pertinente: los literales H0121/H0343, sus pares, y **controles** de aviso
  sin plazo, de aviso con título ya dado y de continuación con el título en el segundo turno.

Ese subconjunto no puede sellarse en este PC: los literales exactos de H0121/H0343 sólo están en el
registro privado de la encuesta. Queda como el primer trabajo de agenda en cuanto llegue el paquete.

## Alcance

Fuera: H0011, H0043 y el fallback transversal de `llm`. Sin pruebas, imports, AST, builds, GPU, HTTP
ni efectos. Cero adjudicación y cero crédito. No se ha modificado ningún fichero de fuente.
