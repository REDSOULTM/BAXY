# BAXY Renew al máximo: plan de palancas (fase A cerrada, 2026-10-22)

## En corto, para el autor

1. Investigamos toda la aplicación con 13 áreas (7 en el PC, 6 en el notebook) y revisamos el código en 11 piezas.
   Salieron ~80 palancas y ~60 defectos; cada palanca de más de 2 puntos la revisó la otra máquina.
2. Tu decisión de hoy: **CU rápido ya está dentro** (fusión de `pc-cu`, suites en verde).
3. **Lo más urgente no son palancas, son agujeros de seguridad** que encontró la revisión: el modelo podía encender el
   modo sin frenos escribiendo un archivo; un clic «a ciegas» y un Enter sin destino no preguntaban; «Laya corrige»
   podía ejecutar con un dato inventado; las sesiones guardaban en claro lo que la memoria cifra. Se están arreglando
   con su prueba.
4. **Muchas promesas de «más acierto» no resistieron la verificación cruzada**: tocar el texto que el modelo ya
   aprendió suele empeorar. Lo que queda con evidencia es sobre todo **recursos, velocidad y recibos más honestos**.
5. Recursos: con System One, la tarjeta gráfica está a 5 MiB del techo de 4 GB porque Laya usa la GPU sin querer; una
   línea lo arregla (−189 MiB). Otra deja ~1 GB menos de RAM en sesiones largas.
6. Velocidad: los turnos dudosos tardan el doble (1,9 s frente a 0,9 s) por pasos de más; el historial se relee
   entero a cada turno en sesiones largas; la voz junta frases y tarda en empezar a hablar.
7. Honestidad: los recibos dirán «ya estaba así», «el lugar no se comprobó» y «la app sí se abrió aunque el lugar no»,
   en vez de dejar que el modelo adivine.
8. Línea base: decision2 233/268 con System One (231 sin él); tras fusionar CU, 229 (dentro del ruido).
9. El holdout nuevo (720 decisiones, 90 escenas, 72 e2e, 36 falsedades) lo escriben y sellan dos agentes aislados;
   nadie lo abre hasta el final.
10. Te preguntaremos sólo lo que es tuyo: la calidad de la voz más rápida y unas pocas reglas de confirmación.

## Línea base (medida)

| Banco | `pc-system-one` S1 apagado | S1 encendido | `renew-maximo` c1177101d (con pc-cu), S1 encendido |
|---|---|---|---|
| decision2 (268) | 231 | 233 | **229** (8 cambian: −6/+2, n.s.) |
| decision2 sin los 9 ids que están en los datos de Laya (B-MED, 259) | 223 | 225 | 220 |
| acciones equivocadas | 25 | 19 | 20 |
| p50 / p90 decisión | 0,94 / 1,56 s | 0,88 / 1,80 s | 0,98 / 2,01 s |
| escenas de práctica (39) | 32 | 32 | 34 (+2, dentro de ±2) |
| VRAM / RAM del producto (portátil) | 3 902 / 2 438 MiB | **4 091** / 2 719 MiB | — |
| suites | — | — | Kernel 603, Contracts 69, Setup 477, pytest 85 (verde) |

Notas de medición (del portátil, verificadas): la semilla está fija (una corrida = una muestra; `BAXY_RENEW_SEED` en
camino); P251/P252 del banco esperan una ventana sin `window.resolve` (−2 fijo por corrida); los umbrales 0,4/0,6 se
fijaron en decision2, así que la ganancia de S1 en decision2 está algo inflada; S1 no actúa en el latido (escenas
on/off = ruido); el AUROC de la duda sobre sólo acciones es 0,837 (no 0,902) y bajo 0,4 se retiene el 2,6 % de las
acciones buenas (no el 0,65 %).

## Tabla de palancas, ordenada por ganancia sobre costo

Fuentes, evidencia completa y descartes de cada una: `PALANCAS-pc.md` y `PALANCAS-nb.md`. Verificación cruzada:
`VERIFICACION-pc-de-nb.md` y la del portátil sobre las del PC (canal de mensajes 2026-10-22 14:41). «Esperada» = sin medir aún.

| # | Palanca | Área | Evidencia | Fuente | Ganancia esperada | Banco | VRAM / RAM / latencia | Riesgo | Esfuerzo | Medida o esperada | Máquina |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Fusionar `pc-cu` | 7 | `PALANCAS-nb.md` §0 | CU_CASOS.md | CU 18/18 con variantes; 2 arreglos de seguridad | CU, decision2 | +5 descripciones | prefijo | bajo | **medida**: d2 229 (n.s.), suites verdes | hecho (autor) |
| R | Arreglos de seguridad e invariantes de la revisión (B-SYS-1, K-1, K-2, K-3, B-MED-1, A-1, A-3, M-1, textos fijos) | B | `PALANCAS-pc.md` «Defectos», `REVISION-nb.md` | OS-Harm, CaMeL | cierra agujeros, no puntos | pruebas + decision2 S1 | 0 | ninguno | medio | arreglos en curso | ambas |
| 3.1 | Laya con `--device none` | 3 | `system_one.py:73-75`; VRAM S1 on 4 091 | llama.cpp README | −189 MiB VRAM | recursos; decisiones de S1 idénticas | −189 / 0 / Laya algo más lenta | ninguno | trivial | VRAM medida | portátil |
| 3.3 | `-ctxcp 10` **con** `-cram 0` (no bajar `-cms`) | 3 | verificado en `server-context.cpp` (VERIFICACION-pc-de-nb) | llama.cpp b11609 | −~1 GB de pico de RAM en sesiones largas | recursos en sesión larga; decision2 | 0 / −1 GB / 0 | perder el checkpoint del prefijo (vigilar el log) | trivial | esperada | PC |
| 4.1 | Candidatos de duda por los nombres del catálogo, sin rollout (= portátil 3.5) | 4 | turnos con S1 1,9 s p50 frente a 0,9 s | Apple 2604.22985 | −0,8 s en turnos dudosos, mismos aciertos | decision2 S1 (latencia, decisiones idénticas) | 0 | nulo | bajo | esperada | PC |
| 1.4 | Recortar el historial con histéresis + precalentar en ocioso (= portátil 3.2) | 1, 3, 9 | 28 % de `turn.decide` releen >500 tokens | PR #24176 | −0,5 s p50 en ~19 % de turnos; −1,5-3,6 s en sesiones largas | sesión de 20 turnos | 0 | menos turnos a ratos | bajo | esperada | PC |
| 9.3 | Primera frase sintetizada sola | 9 | `JOIN_CHARS=120` junta el 84 % | Pipecat | −0,3-0,7 s en respuestas de dos frases | `sound_ms` | 0 | prosodia | trivial | esperada | PC |
| 9.5 | `top_logprobs` sólo en `turn.decide` | 9 | `mind.py:859` | server-common.cpp | −20-100 ms por continuación | latencia | 0 | nulo | trivial | esperada | PC |
| 8.2 | `verification` tipado desde el kernel; retira la heurística de `_outcome`; «ya estaba así» y «lugar sin comprobar» bien dichos (absorbe C-5) | 8 | `mind.py:106-146`; `ExternalCapabilityHandlers.cs:334-345` | Tool Receipts 2603.10060 | F004, F013, lugar sin mirar | falsedades ×6, sonda | 0 | nulo | medio | esperada | PC |
| 6.2/6.3 | `placeWindowChanged` y pistas de recuperación (`launchIssued`, candidatos, «sin red» aparte) | 6 | verificado (VERIFICACION-pc-de-nb) | Anthropic, writing tools | F001, F006, F016, E015 | falsedades, e2e | tokens sólo en fallo | nulo | medio | esperada | portátil |
| 7.7 | La repetición compara el contenido del resultado | 7 | `TurnClosing.cs:37-42` | — | no cortar esperas legítimas | prueba, CU | 0 | nulo | bajo | esperada | PC |
| 6.1, 6.4-6.7 | media de todas las sesiones; `game.launch` ya abierto; apps empaquetadas por ActivateApplication; catálogo vencido en segundo plano; presupuesto de YouTube | 6 | `PALANCAS-nb.md` | MS docs | latencia y verdad en casos concretos | vivo, pruebas | 0 | bajo-medio | bajo-medio | esperada | portátil |
| 2.2 | Defectos de descripciones (message_send, 1/0, placeValue, newDocument, scroll, browser_navigate) | 2 | `PALANCAS-pc.md` P2.2 | Anthropic | filas concretas | decision2 ×3 | relee el prefijo 1 vez | prefijo entrenado | bajo | esperada | PC |
| 2.3/2.6 | Constantes del esquema; `null` fuera de enums; −0,6k tokens de apps de ayuda y `{app_places}` doble | 2, 5 | `mind.py:408-422,524,544` | PA-Tool; Less is More | menos argumentos inválidos; más historial | decision2 | −0,75k tokens | prefijo | bajo | esperada | PC |
| 7.4 | Más lugares `ms-settings:` y de apps (datos) | 7 | 28 lugares hoy | MS docs | «abre la sección X» | decision2, e2e | prefijo + | ruido ±2 | bajo | esperada | portátil |
| 4.2 | Una pregunta por malentendido; Laya ve la pregunta | 4 | `mind.py:623-633,925-938` | SAGE-Agent | bucles de aclaración | e2e | 0 | bajo | bajo | esperada | PC |
| 5.1 | Efecto tipado en el catálogo para «corrige» (retira `SendsInputToAWindow`/`ReachesTheNetwork`) | 5 | `NativeTurnLoop.cs:484-519` | Anthropic | «corrige» seguro por construcción | decision2 S1 | 0 | nulo | medio | esperada | PC |
| 4.4/4.5 | Umbral de duda por riesgo (CRC); duda de argumentos sólo en texto libre no presente | 4 | agregados del área 4 | CRC 2208.02814; Apple | menos preguntas en lecturas; argumentos | decision2 sin los 9, devmix | 0 | sobreajuste | bajo | esperada | PC |
| 4.3 | Laya v6 con el oro ausente a veces y «corrige» sólo con p ≥ τ | 4 | `build_kev_data.py:107-110` vs `mind.py:969-980` | Gatekeeper (apoya p≥τ, no la clase «ninguna») | −2 a −4 acciones equivocadas (portátil) | decision2 sin los 9 ×semillas | 0 | fugas | medio | esperada, con reservas | PC |
| 8.1 | Registro de la sesión en el reloj, con contador propio | 8 | F015 | Tool Receipts | F015 (5 de 10), riesgo −1..−3 en d2 (portátil) | falsedades ×6 + d2 | 20-80 tokens | complacencia, no falta de dato | bajo | esperada, con reservas | PC |
| 1.1/1.2 | Compactar resultados de turnos cerrados; no forzar el final si cabe quitando historial | 1 | `mind.py:318-324,834-845` | Complexity Trap; Anthropic | 3 → 6-8 turnos recordados | sonda multi-turno nueva (ningún banco lo ve) | 0 | ids viejos; `_trim` reasigna `conversation` (borrar en sitio) | medio | esperada, con reservas | PC |
| 1.5 | Contexto +4k (tras 3.1) | 1 | 17 KB/token | config Qwen3.5 | +4k de historial | recursos | +68 MiB | VRAM | trivial | esperada | PC |
| 10.1/10.2 | Latido: P(intervenir) en la traza; forma avisar/hacer estructural | 10 | verificado con matices | PRISM; Horvitz | 0 a +3 escenas | escenas ×4 + otro banco | 0 | sobreajuste en 39 escenas | bajo | esperada | PC |
| 10.3-10.5, R10.x | motivos al paso 2; tiempos relativos; juntar latidos; ajustes del sistema retenidos en el latido | 10 | `PALANCAS-nb.md` | — | escenas, latencia | escenas | 0 | texto entrenado | bajo | esperada | PC |
| 11.x | memoria: código de error real al modelo, `exactMatch:false`, lecturas sin reescribir, freno de salida con datos de memoria (versión ajustada), `memory.save` con opcionales | 11 | `PALANCAS-nb.md` | OWASP, CaMeL, Mem0 | falsedades, privacidad | pruebas, falsedades | 0 | bajo | bajo-medio | esperada | PC (Core) |
| 7.1 | Vista de después en el recibo del acto (pasa por `_lastView`) | 7 | verificado con matices | EFR +5,94 | un paso menos por acto | CU, e2e | +0,3-1,3 s lectura, −1 decisión | índices viejos | medio | esperada | portátil + PC |
| 9.2 | Señal no verbal temprana; el aviso se cierra al sonar | 9 | `SilenceNotice.cs:95-103` | LiveKit | `first_audio_over_3s` → ~0 | e2e latencia | 0 | que moleste | bajo | esperada | PC (+ autor) |
| 9.1 | Supertonic 10 → 6-8 pasos | 9 | 1 544 ms p50 voz → sonido | Supertonic ONNX | −250-550 ms por respuesta | `sound_ms` | 0 | calidad: **oído del autor** | trivial | esperada | autor |
| 9.4 | Final en streaming + presíntesis | 9 | `llm_server.py:92-104` | PR #12379 | −0,1-0,8 s | `sound_ms` | 0 | parser | medio | esperada | PC |
| 12.1-12.9 | Medir bien: semilla real, pareo por ítem (McNemar), réplicas por edición neutra, juez de 4 clases, latencia desde el envío, precondiciones VOID | 12 | `PALANCAS-nb.md` | Miller 2024; τ-bench | decidir ganancias de <3 puntos | todos | 0 | rompe comparabilidad (re-correr base) | bajo | — | portátil |

## Plan de la fase B por tandas

Cada palanca: anuncio en el canal de mensajes con sus archivos, implementación mínima, medida en su banco, se queda sólo si gana
más que el ruido sin empeorar otro banco (si no, sale del código con su cifra), commit propio con cifra y fuente.

- **Tanda 0 (en curso): revisión.** Arreglos con prueba en worktrees: `fx-mente`, `fx-voz` (fusionado), `fx-core`,
  `fx-app` (PC); `nb-maximo-fix` (portátil: B-SYS-1, B-CU-1, B-CU-3 y los B-APP). decision2 S1 tras los arreglos de la mente
  (B-MED-1 y la alineación de B-MED-3 cambian decisiones de S1).
- **Tanda 1: medir bien (portátil 12.1-12.3) + recursos y latencia sin tocar el prefijo**: 3.1 (portátil), 3.3, 4.1, 1.4, 9.3,
  9.5 (PC). Criterio: decisiones idénticas o dentro del ruido, y la cifra de recursos o ms.
- **Tanda 2: recibos honestos**: 8.2, 7.7, 11.x de Core (PC); 6.1-6.7 (portátil). Bancos: falsedades ×6, e2e, pruebas.
- **Tanda 3: el prefijo, una a una**: 2.2, 2.3/2.6, 7.4, 5.1 (sin texto nuevo). decision2 ×3 réplicas cada una.
- **Tanda 4: System One**: 4.2, 4.4/4.5, 4.3 (reajuste de Laya con controles de fuga), 8.1.
- **Tanda 5: latido y contexto**: 10.1 (sólo traza) → 10.2-10.5; 1.1/1.2 con su sonda; 1.5 si queda VRAM.
- **Tanda 6: voz** (con el autor): 9.1, 9.2, 9.4.
- **Cierre**: suites en las dos máquinas sobre el mismo commit; recursos ≤4 GB/4 GB con voz y S1; holdout v4 una vez,
  tres configuraciones; prueba en vivo en el PC; `INFORME_MAXIMO.md`.

## Descartado, con su porqué

| Palanca | Por qué |
|---|---|
| P13.1 pista de candidatas tras el prefijo | Verificación del portátil: DTDR gana con *hard* masking en modelos pequeños; el *soft* sirve a grandes; el RAG de TinyAgent bajó 78,89 → 74,88 en 1,1B; es el mecanismo de la ayuda 9 (d2 −5) y su embedder midió 1 320 MiB (pasa 4 GB con S1). |
| P2.1 regla 2 en dos | La redacción actual se escribió para F015 (`PROGRESO.md:145,193,264-266`); tocar la regla 2 costó −8 (pcG7) y 221 frente a 231 (abSys2); la motivación salía del holdout gastado. |
| P2.4 una sola ruta `path` | c2-e1.0 aprendió el schema exacto (`ft/RECETA.md:15-17,35-39`); la ayuda 6b no movió E006/E020; sólo con reajuste del modelo (prohibido aquí). |
| Lista corta dinámica en el prompt | relee el prefijo entero (3-7 s por decisión) y el modelo nunca vio 16 herramientas. |
| Pensamiento, aunque sea en duda | brazo THINK de la decisión 20: −43 en decision2, 3× más lento, falsedades en cadena. |
| Best-of-n con verificador | sólo gana con n=32 y un RM de 14B. |
| MTP / decodificación especulativa | desactiva la reutilización de caché; el GGUF ajustado no trae cabeza MTP. |
| Calibrar una sola puntuación; subir el umbral de Laya a 0,7; duda nombre × argumento | monótona sin efecto; +1 frenada por +1 correcta perdida; empeora la cola. |
| 4.1 candidatos de duda por el catálogo, sin rollout (medida) | decision2 S1 ×3: −2,67 (IC95 −5,67; −0,33); un token ambiguo entra con la primera herramienta del catálogo y Laya corrige mal (P028); sólo −360 ms p50 en turnos con S1. Retirada en d4d2d39d2. |
| 7.5 `input.visible.path` (por ahora) | C02, C10, C11 ya cubiertos por pc-cu; falta un caso de menú sin cubrir. |
| Lo ya descartado antes | Laya primero (73,5 % vs 86,6 %), pregunta lateral (0,738), Kev, sopa, maestro 35B, ayudas 4, 5a, 6, 7, 9. |

## Holdout nuevo (renew_v4), diseño del área 12 del portátil

Potencia por McNemar (α 0,05, potencia 0,8): con discordancia 0,06 un Δ de 3 puntos pide ~520 ítems.

| Banco | Casos | Detecta (80 %) |
|---|---|---|
| Decisión | 720: comunes 120, pares mínimos 100, riesgo 60, preguntar 60, «no puedo» 50, texto 50, multi-turno 80, «¿ya lo hiciste?» 40, confirmación pendiente 40, cola larga 80, primer paso de multipaso 40 | ≈3 puntos |
| Escenas | 90: silence 50, act 15, propose 12, say 13; 8 de «volvió»; sólo señales que la App produce | ≈10 puntos (regresión) |
| E2E | 72: comunes 18, computer use 12, archivos 10, confirmación 8, multi-turno con error 10, «¿ya lo hiciste?» 4, imposibles 4, voz 6 | ≈10 puntos con 3 réplicas |
| Falsedades | 36 conversaciones | descriptivo, a mano |

Idiomas 50/15/15/20 (decisión) y 60/15/15/10 (e2e); el dictado con errores va como gemelo de un caso limpio. Sin
MASSIVE. Comprobación de casi-duplicados contra todos los bancos de práctica y los datos de Laya. GUID canario. Cifrado
7z AES-256 en `<evaluacion>\renew_v4\holdout\` (clave en `coordinacion`, fuera de evaluacion), copia a `D:`, sha256 en
`metas.json`. Lo escriben dos subagentes aislados del PC (decisión+escenas; e2e+falsedades). Se abre una vez sobre el
HEAD final con tres configuraciones: `pc-system-one` S1 off, S1 on y `renew-maximo`; decisiones repartidas entre las
dos GPUs y la ejecución en el notebook. Laya (sha) y sus umbrales quedan congelados antes de abrirlo.
