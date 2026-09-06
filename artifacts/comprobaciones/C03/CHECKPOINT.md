# C03 — checkpoint 2026-09-06, traspaso a otro PC

**Punto único de reanudación.** El trabajo está publicado en la rama `Goal-c03`
de `origin` (`main` intacto en `5f572ee`): el dueño sigue en otro PC. Ese PC
**no tiene Granite descargado** — el GGUF no viaja por git ni lo encuentra
`bootstrap.ps1`; hay que copiarlo y registrarlo a mano. La tabla con rutas,
tamaños, hashes y el comando de registro está al final del handoff.

Se puede trabajar sin Granite: pytest, .NET y el censo no lo necesitan. Lo que
**no** se puede hacer sin él es panel, tramo D ni cierre.

## Reparado en esta sesión (2026-09-06)

La prueba roja que dejó la sesión anterior está en verde. El veto era
`ContainsInternalCode` en `UserMessagePolicy.cs`, entrada literal «keep talking»:
miraba la respuesta y nunca el pedido, así que «I will keep talking without
launching anything» —que es exactamente la respuesta correcta a «keep talking
without launching anything»— moría por acertar. La mente ya tenía esa exención
(`llm.py`, `prompt_echo`); el shell la ignoraba. Ahora las nueve frases de
encargo y el prefijo `name the ` sólo vetan cuando la persona no las escribió, y
una prueba nueva exige que sigan vetadas cuando nadie las pidió. Detalle y
fingerprints en el handoff. **Falta medirla en panel.**

## Siguiente clase, diagnosticada y sin reparar

El saludo mal formado («Good afternoon» → «Hello hi!», `panel-opus-13/001`,
`/003`, `/004`). Es determinista, no es generación de C05/C06: el payload fija
`greeting` al literal «hi»/«hola» sin mirar con qué saludó la persona, y el veto
`welcome_question` perdona el «?» sólo si pedido y respuesta empiezan por
`hola|hi|hey|hello|buenas`, lista que no incluye «good afternoon». El buen
borrador se tira y el reintento pega el literal. El mecanismo, con las líneas y
la hipótesis a probar, está en el handoff.

## Estado

**EN_CURSO.** No hay 100/100 y no se declara nada cumplido. Cambiar de PC no
cumple el goal.

**El relevo está en [`HANDOFF_OPUS_METODO.md`](HANDOFF_OPUS_METODO.md)**: ahí
viven el candidato con sus fingerprints, lo comprobado, lo provisional, las
hipótesis descartadas, la validación recogida, los procesos, los activos que no
viajan y la siguiente acción. Este checkpoint no repite esa lista para no tener
dos que se contradigan.

## Sesión anterior (2026-09-05/06), resumida — el detalle está en el handoff

Causa que la gobernó: todo turno conversacional degradado llegaba al compositor
con `{"kind":"conversation","polarity":"success"}` y nada más, así que un
seguimiento elíptico sólo podía salir vacío. Evidencia en
[`SEGUIMIENTOS.md`](SEGUIMIENTOS.md).

Reparado allí: censo de prosa visible a 0 (salta docstrings vía `ast`); elipsis
leída donde se lee el pedido, con `priorRequests` desde el shell (de 0 de 9
seguimientos en tema a 7–9 de 9); capacidades y límites leídos por forma y nunca
convertidos en aclaración (`limites-22/`: 8 de 9); eco del encargo derivado de lo
enviado; `compose-audit.jsonl` v2 con `situation` y `followup_subject`.

Retiradas y no repetir: prohibir la definición en un seguimiento
(`seguimiento-12` contra `-11`: de 9 en tema a 6); turno anterior como contexto;
muestreo 0.2/0.9; forzar la ruta contextual. Regresión propia encontrada y
corregida: `panel-opus-13/051`, «this» tomado por anáfora.

Sigue aplazado y **no** marcado reparado: el seguimiento en tema que repite la
definición, la persona impersonal y los agotamientos; los que tocan generación
conversacional siguen apuntando a C05/C06. El saludo mal formado deja de estar
sólo aplazado: arriba queda su mecanismo.

## Siguiente acción

La del handoff: reparar el saludo por owner y fijarlo (no necesita Granite);
después `panel-opus-14` sobre la misma población de `panel-opus-13`, que sí lo
necesita, para medir juntas la exención de encargo copiado y el saludo; y sólo
con el panel fiel congelar la población v19 y correr el tramo D.
