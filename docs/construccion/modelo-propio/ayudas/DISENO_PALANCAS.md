# Diseño de las palancas 5 y 7-9, y del schema futuro

Escrito el 2026-10-19 por la sesión del PC, antes del objetivo «ayudas al modelo». Nada de esto está implementado. Los
tokens se midieron con el tokenizer de Qwen3.5-4B (`D:/BAXYft/hf/Qwen3.5-4B`, transformers 5.20.1). Los números de
palanca siguen `PROMPT_OBJETIVO_AYUDAS_MODELO.md`.

## Palanca 5: hechos del turno antes de la respuesta final (sin prefijo)

**Lo que hay hoy** (`src/baxy_mind/mind.py:520-555`): cada resultado de herramienta termina con
`[En este turno: op → resultado; …]`. Ahí van todas las llamadas del turno con su estado, que sale de `_outcome`
(`mind.py:113-136`): `completado y verificado en {fullPath}`, `completado sin verificar` o `falló (error)`. Cuando la
App cierra el turno se añade `[Este turno no admite más herramientas: …]`.

**Por qué no basta:** en el holdout del ajuste fino, FH141 dijo «Cerré Paint» con `app_close → falló
(window_not_found)` en esa misma línea. En falsedades, F013 dijo que el Bloc de notas «ya no estaba» y F015 contestó
«Sí» a «¿ya lo cerraste?». La línea mezcla lo hecho y lo fallido en un orden cronológico, y el modelo de 4B no separa
qué puede contar como hecho.

**Diseño, en dos variantes que se miden por separado:**

- **5a. Hechos partidos.** Antes del último paso, en el último resultado y solo cuando hay al menos una llamada
  fallida o sin verificar, la línea se parte en dos: `[Hecho en este turno: …. No hecho: … → falló (…).]` Usa los
  mismos nombres y estados que ya produce `_outcome`, sin interpretar a la persona.
  - **Coste:** unos 36 tokens en el sufijo (medido sobre un caso de dos llamadas). No toca el prefijo.
  - **Riesgo para el ajuste fino:** bajo. Cambia el formato de una línea que sí aparece en todas las muestras de
    entrenamiento con llamadas, así que es una presentación nueva, pero en el sufijo.
  - **Evidencia:** CRITIC (ICLR 2024, https://doi.org/10.48550/arXiv.2305.11738) y Kamoi et al. (TACL 2024, https://doi.org/10.48550/arXiv.2406.01297): la
    corrección funciona con señal externa fiable. Es un artículo revisado por pares, pero no está medido en un 4B
    ajustado: el efecto aquí es **inferencia**.
- **5b. Segunda oportunidad con los hechos.** Después de que el modelo escribe su respuesta final, un verificador
  compara los verbos de acción de la respuesta (abrí/cerré/guardé/borré/escribí… y sus pares en inglés) con las
  operaciones de ese turno: si la respuesta dice «cerré X» y la única llamada a `app_close` falló, se le devuelve al
  modelo una sola vez `[Tu respuesta dice que cerraste X, pero app_close falló (window_not_found). Responde otra vez
  con lo que muestran los resultados.]` y se usa la respuesta nueva, que sigue siendo suya.
  - **Lo que lee:** las palabras del modelo, no las de la persona. No decide: pide revisar con un hecho.
  - **Coste:** una generación extra solo en los turnos señalados, de 1 a 3 s en este hardware (**inferencia**).
  - **Riesgo:** los falsos positivos del verificador, que se miden en las corridas de falsedades limpias.
  - **Evidencia:** Huang et al. (ICLR 2024, https://doi.org/10.48550/arXiv.2310.01798): autocorregirse sin señal externa empeora. Aquí la
    señal es el recibo, que es externo.

**Medida:**
- falsedades s0-2: la cifra principal, con la lectura a mano;
- e2e s0-2 pareado contra el producto de partida;
- la familia F_falsedad del holdout nuevo, solo al final;
- latencia p50 y p90 de la primera respuesta.

decision2 y escenas no ven observaciones, salvo el latido si se le aplica (no se aplica al latido). Se queda solo si
baja las falsedades sin bajar el e2e.

## Palancas 7-9: con prefijo (texto exacto y plan de base)

Cada una cambia el prefijo cacheado, así que hay que medir otra vez la base (c2-e1.0 con la presentación nueva) en
decision2 s0-2 y escenas ×4 antes de compararla. El presupuesto total es de ≤ +1.000 tokens sobre el prefijo de
partida (p0 42.734, p1 42.675), medido con `prompt_n` en el calentamiento.

**Palanca 7. Modos, en la descripción de `system.settings.set`** (td:141, se añade al final). 75 tokens:

> BAXY's accessible mode only changes BAXY's own window (larger text, more contrast, wider buttons). BAXY has no
> blind or screen-reader mode and no hands-free or full voice-control mode yet: if the person asks for one, say it is
> not available yet and will come later; do not turn on the accessible mode in its place.

- **Ataca:** la sonda de modos (0/34 hoy) cuando el modelo responde sin llamar, y que active el modo accesible por
  error (17 de 22 casos).
- **Fuente:** la decisión de diseño de los tres modos, y el código (`PresentationModeStore.cs:3-7`, `Rail.tsx:45-49`).
- **Medida:** la sonda de modos, decision2 s0-2, escenas ×4, e2e s0-2 y falsedades.
- **Riesgo:** medio. Del ciclo 8 sabemos que enseñar esto con datos movió conductas de rutas; con texto no se sabe.

**Palanca 8. Carpeta de la persona, en la descripción de `filesystem.known.trash.named`** (td:62, se añade al final).
50 tokens:

> A folder the person names, in their home or anywhere else, is theirs even if its name contains BAXY or bench:
> delete from it like from any other folder (BAXY's own work folder is only the one filesystem_list shows).

- **Ataca:** E027 s0 y s2 (el modelo se niega diciendo que es su carpeta privada).
- **Lo que se espera:** poco, porque td:63 (`filesystem.list`) ya lo dice y aun así falla.
- **Medida:** la misma que la palanca 7, más los casos de rutas de la familia R del holdout al final.

**Palanca 9. Pocos ejemplos dinámicos.**
- **Qué se recupera:** 1-3 trazas propias que salieron bien, del conjunto de ajuste y de los sintéticos de v2, nunca
  de los bancos que miden, con la comprobación de fuga.
- **Cómo:** por similitud de embeddings con el pedido actual. El candidato es el MiniLM multilingüe que ya usa
  `fuga_emb.py`, a medir en RAM. Va dentro del último mensaje de la persona como contexto (`[Pedidos parecidos que
  salieron bien: …]`), no como mensajes aparte, para que el historial siga cacheado.
- **Coste:** 150-450 tokens de sufijo por turno; el embedder, unos 100-500 MB de RAM (**inferencia**: medir con
  `measure_resources`; el producto está en 1.787 MiB de RAM, con margen hasta 4 GB). Latencia: un embedding por
  turno, menos de 50 ms en CPU (**inferencia**).
- **Fuentes:** LangChain, few-shot para tool calling (blog del proveedor): 11 % → 75 % en Claude 3 Haiku con 3
  ejemplos, y efecto nulo en otros modelos. ToolBench con demostraciones recuperadas (https://doi.org/10.48550/arXiv.2305.16504, preprint).
  No hay evidencia en un 4B ya ajustado.
- **Riesgo:** medio. Es la palanca que más se acerca a «decidir por el modelo», porque el código elige qué ejemplos ve.
  Se mide la última y solo si 5-8 dejan fallos.
- **Medida:** decision2 s0-2 (sí la ve, porque va en el mensaje), escenas ×4 (el latido no la recibe), e2e s0-2,
  falsedades y RAM.

## Rediseño del schema: un objetivo futuro con reentrenamiento

**Un solo argumento `path` en `file.write`, `file.find`, `file.read`, `file.edit` y `filesystem.known.trash.named`,**
con la ruta tal como la dijo la persona. La resuelve el proveedor como ya hace `RootFor` (`LocalFilesystemProvider.cs
:227-269`); `folder` y `relativePath` desaparecen.

- **Ataca:** E006, E017, E020, E024 y E027. Hoy el modelo parte la ruta en dos argumentos y pierde un tramo.
- **Fuente:** guía oficial de function calling de OpenAI, «use enums and object structure to prevent invalid
  states» (https://developers.openai.com/api/docs/guides/function-calling). Anthropic, «Building effective
  agents»: con rutas absolutas el modelo dejó de equivocarse (https://www.anthropic.com/engineering/building-effective-agents).
- **Coste:** reentrenar. Los datos v2 se vuelven a renderizar con el schema nuevo, la base se mide con la
  presentación nueva y hace falta un holdout nuevo. Cambia el prefijo (las descripciones de 5 herramientas) y las
  pruebas de los proveedores.
- **Plan:** cuando el autor reabra el ajuste fino. Antes, comprobar con el modelo base, sin reentrenar, cuánto cambia
  decision2 con el schema nuevo: si el base ya mejora en rutas, es una señal fuerte.
