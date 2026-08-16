# Evolución causal de Carter a BAXY 1.0

## Propósito y criterio

Esta genealogía no presume que lo más reciente sea mejor ni que un conteo de
tests pruebe un producto. Reconstruye qué problema intentó resolver cada etapa,
qué evidencia dejó y qué decisión impone a BAXY 1.0. La autoridad temporal es
el cutoff `2026-07-14T10:51:49.1612548Z`, estado
`85929373646040f54771a7e3543a5ac3d022dbce688c55d17615ae35b7eb3fbd`.

La genealogía conserva mensajes de cualquier lengua como evidencia histórica,
pero el compromiso funcional de BAXY 1.0 es español, inglés y spanglish,
incluidos code-switch y errores de STT cuya intención pertenezca a esos
idiomas. Los casos inequívocamente ajenos son `trace-only`: no aportan cobertura
de producto ni obligan capacidades nuevas. La etiqueta derivada `language` es
heurística y no puede usarse como filtro mecánico, porque textos objetivo breves
también pueden aparecer como `other`.

Estados de decisión:

- **Heredar**: conservar el principio y volver a demostrarlo en el producto
  nuevo.
- **Rediseñar**: conservar la necesidad, no la implementación histórica.
- **Competir**: candidato sin aprobación hasta el torneo reproducible.
- **Descartar**: patrón refutado o incompatible con el contrato.
- **Referencia**: evidencia o caso de regresión, no componente reutilizable.

## Cronología causal

| Etapa | Evidencia primaria | Lo que se aprendió | Decisión 1.0 |
|---|---|---|---|
| Carter OS v1, 6–10 abril | Carter `c84d0cb7`→`42fbda8d`; rebuild, watchdog de VRAM, perfiles, UIA y benchmark | Un agente local puede actuar, pero visión por coordenadas, procesos ajenos y backends no atestados producen falsos estados | Heredar medición de recursos y accesibilidad primero; rediseñar identidad y verificación |
| Carter v2, 16–22 abril | `f8803fba`, `9b112943`, `c36c9da5`, `20d6f6ed`, `249db625` | Ledger, verificación post-acción, memoria contextual y terminación de subprocess son obligaciones del runtime | Heredar los invariantes; no portar el bucle completo |
| Carter universal, 23–30 abril | `61cc5b1a`, `c34ba4e`, `e2f1737`, `565701a`, `0d30805`, serie de redirects del 26 de abril | UIA→OCR→visión es mejor que coordenadas ciegas; hacer al LLM único cerebro y reparar cada fallo con redirects acumula colisiones | Heredar la cascada de percepción; descartar redirects ad hoc y la autoridad única sin contratos |
| Auditoría Carter 540 | `legacy/Carter_v4/CARTER_540_REAL_PROGRESS_REPORT.md`: 417/540 reales frente a 489/540 automáticos, 72 falsos positivos | Un harness puede validar stubs o despachos sin validar efectos, GUI ni composiciones | Referencia obligatoria; acceptance por estado final y evidencia física |
| Probando Gemma 4, 10 mayo–11 junio | historial `7aeec7b`→`bc3204b`; `documentacion/01_arquitectura/ARCHITECTURE.md` | La mayor parte de los fallos vivía en bordes: ciclo de vida, recuperación, audio, identidad, persistencia y verificación | Heredar casos y contratos; rediseñar por cortes verticales |
| Router y corpus reales | `documentacion/02_router/05_HISTORIAL_SPRINTS.md`; `34dc4d9`, `f928878`, `3148341` | 99,64 % curado podía caer a 85,7 % en logs; equivalencia 89,1 %; un holdout contaminado o un índice desincronizado fabrica progreso | Heredar corpus real y abstención; separar train/eval y verificar el camino ejecutado |
| Voz y audio | VAD/AEC/wake/LID entre `e4fb432` y `f355223`; informes de STT | Parakeet fue rápido y sin alucinación en silencio, pero la recuperación de entidades quedó en 81 %; simulación AEC no basta para hardware | Competir STT/VAD/TTS; gate físico de wake, barge-in, ruido, code-switch y entidades en español, inglés y spanglish |
| Memoria, computer-use y visión | `documentacion/08_memoria_jarvis/README.md`; `documentacion/04_computer_use/README.md` | La memoria necesita inspección/olvido; UIA→OCR→visión y verificación triestado reducen falsas certezas | Heredar interfaces y casos; memoria proactiva default-off hasta consentimiento |
| Reducción del stack, 13–20 junio | experimento sin guards `406905a`→`4fe4fb1`; catálogo `9817be2`; fixes de forma hasta `b8d03e6` | Quitar toda protección expone confabulación; conservar sólo protecciones estructurales medidas es viable | Rediseñar guards como invariantes pequeños, generales y probados |
| FunctionGemma split, 17–25 junio | `_FUNCTIONGEMMA_INTEGRACION_2026-06-17.md`; FunctionGemma `INTEGRATION_HANDOFF.md`; `router/README_ROUTER.md` | Un modelo 270M CPU puede ser caller después de shortlist, pero el primer split rompió abstención 0/3; luego 13/14 no-tool y 12/13 standalone siguieron sin ser perfección | Competir, no aprobar; schema/modelo/encoder forman una unidad versionada |
| Perfil 4 GB | `documentacion/09_finetune/DECISION_MAESTRA_4GB.md`; commits `121ea2f`→`d2814b5` | E2B fue el candidato práctico pero sobre-activaba; visión lazy y CPU liberan VRAM; nunca hubo medición en GPU física de 4 GB | Competir perfiles y declarar proxy; prohibido afirmar 4 GB hasta medirlo |
| BAXY limpio inicial, 2–9 julio | BAXY `4a83f2d`→`7a99d47` | Se recuperaron voz, memoria, GUI, RAG, skills y routing, pero una suma de componentes no constituye release | Referencia y cantera de casos; no portar el árbol entero |
| Gemma unificado, 11 julio | `7626c47`, `2b17d05`; auditoría con activación 0/11 | Health sin identidad permitió atribuir respuestas al servidor/modelo equivocado | Rediseñar attestation de proceso, modelo, puerto y request |
| Tool Ecosystem v2, 12–14 julio | `6dd84f9`→`ee06786`; `legacy/README.md` | Llegó a 94 registradas/91 seguras/3 aisladas y 39 workflows en el perfil estable, pero conteos, pruebas offline y gates diseñados no equivalen a producto final | Heredar contratos, casos, replay y canal privado; rediseñar UX y providers |
| Reconstrucción BAXY 1.0 | `d3b92a3`→cutoff/corpus actual | El archivo anterior es evidencia de solo lectura; 122.744 ocurrencias se consolidaron en 14.836 mensajes —12.036 de producto y 2.800 de traza— y, tras la revisión derivada v2, 2.083 misiones sin cambiar cutoff ni procedencia | Construir contratos verificables para español, inglés y spanglish; conservar lenguas inequívocamente ajenas solo como trazabilidad |

## Árbol de decisiones

| Tema | Heredar | Rediseñar/competir | Descartar |
|---|---|---|---|
| Ejecución | ledger, invocation ID, timeout, cancelación, verificación independiente | providers por operación y composición transaccional | éxito al emitir clic/tool call |
| Routing | abstención, no-tool, corpus real, shortlist | router/modelo mediante torneo | catálogo gigante inyectado y redirects por frase |
| Riesgo | confirmar dinero, irreversibilidad, privacidad, privilegios y trabajo sin guardar | UX de confirmación proporcional | confirmar toda mutación o confiar toda mutación |
| Computer-use | UIA→OCR→visión; verificación triestado | grounding y fallbacks medidos | coordenadas ciegas y visual-diff como única prueba |
| Voz | VAD, AEC, ducking, LID y corrección como candidatos | stack final por corpus físico en español, inglés y spanglish, incluido code-switch y errores de STT | asumir que una transcripción simulada o calidad en lenguas ajenas prueba el producto 1.0 |
| Memoria | inspeccionar, olvidar, procedencia y límites | esquema cifrado y consentimiento | logging conductual ilimitado o proactividad opaca |
| GUI | estado de boot y capacidades reales | shell tecnológico por torneo | mostrar “listo” con cero capacidades |
| Recursos | presupuestos medidos, carga lazy y perfiles incompatibles | perfil 4 GB en hardware real | extrapolar desde GPU de 16 GB |
| Release | paquete reproducible, instalación limpia, rollback, checksum | tecnología de empaquetado | depender del Python y árbol del desarrollador |

## Cadena de autoridad

1. Decisión explícita del usuario y contrato actual.
2. Efecto físico reproducible asociado a artefacto y commit.
3. Prueba automatizada que observa el estado final.
4. Artefacto primario histórico.
5. Auditoría de agente corroborada.
6. Inferencia o diseño pendiente.

La repetición entre agentes no aumenta el nivel. Una afirmación histórica
contradicha se conserva como lección, nunca como estado vigente.

## Cierre de esta etapa

La genealogía queda especificada cuando cada lección tiene regresión en
`05_FALLOS_Y_REGRESIONES.md` y cada informe de agente relevante tiene una
clasificación en `09_LEDGER_EVIDENCIA_AGENTES.md`. No aprueba ninguna
tecnología ni gate del producto nuevo.
