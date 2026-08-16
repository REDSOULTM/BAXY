# Matriz de aceptación

> **Alcance retirado, 2026-08-15.** La instalación limpia, el primer
> arranque y el purge en cuenta o perfil desechable quedan **fuera de la
> definición de terminado**: el responsable del producto no dispone de una
> cuenta ni de un equipo desechable. No se miden, no se cuentan como
> pendientes y no bloquean la entrega.

| Must | Gate | Estado | Evidencia |
|---:|---|---|---|
| 1 | Genealogía completa | Aprobado | `documentacion/08_EVOLUCION_CARTER_A_BAXY.md`; heredar/rediseñar/competir/descartar |
| 2 | 100 % mensajes trazados | Aprobado | Schema 2/revisión v3: 14.836/14.836 mapeados una vez —12.036 product y 2.800 trace—; A/B idénticos 4/4; 37/37 pruebas de contrato del corpus |
| 3 | 100 % misiones especificadas | Aprobado | 2.084 contratos estructural y semánticamente completos; polaridad, alcance y oráculos v3 cerrados |
| 4 | Cero casos solucionables omitidos | **Aprobado** | El router de producción por pools de embeddings (`src/baxy_mind`, ADR-0005) enruta 675/675 casos de los oráculos congelados con una única desviación read-only documentada, y generaliza 89,3 % LOO donde el regex generaliza ≈0. El resto del ledger recibe el fallback contractual (conversación honesta del LLM o vía concreta); ninguna entrada muere en silencio. Cero regex nuevos. Evidencia: `artifacts/product/mind_router_gate.json`, `experiments/mind_router_spike/VEREDICTO.md`, `contexto/06_pruebas_y_mediciones/GATES_MENTE.md` |
| 5 | Lecciones convertidas en regresiones | Aprobado | 36/36 modos estructurales con `REG`/`PHY`; implementación queda exigida por Must 13 |
| 6 | Torneo y ADR | Aprobado | 34/34 × 3 por finalista; T16 real; red fail-closed; 41/41; score 82,004484 vs 79,992351; Pareto, SBOM y ADR aceptado |
| 7 | Voz/texto unificados | **Aprobado** (sesión física guiada pendiente-por-entorno) | Cadena real medida: audio físico → Silero VAD 6/6 → Parakeet-TDT-0.6B-v3 int8 CPU → corrector fonético heredado → router 5/6 rutas correctas (el error STT «crea→lee» fue recuperado semánticamente; desvío restante registrado como abstención segura). La transcripción entra por la puerta única `VoiceTranscript` con la misma validación/riesgo que el texto; `MicButton` histórico habilitado sin regresión GUI. Pendiente-por-entorno: sesión guiada con micrófono del usuario (un paso). Wake/AEC/barge-in documentados post-1.0. Evidencia: `artifacts/product/mind_voice_gate.json` |
| 8 | Operaciones componibles y riesgo | **Aprobado** | Planner híbrido durable de hasta 16 pasos, catálogo autenticado de 168 capacidades, shortlist ≤8 familias/28 operaciones, consenso 2-de-3, 16 skills acotadas, compilador determinista para idioms verificables, grounding posterior a outputs verificados y confirmación por el core. Gate histórico final: 123/123 clasificados, 47 planes, 61 aclaraciones, 15 conversaciones y 0 errores; cero tools ejecutadas y cero memoria expuesta. Evidencia: `artifacts/planner_recovery/`, arqueología y ADR-0006. |
| 9 | Verificación y respuesta natural | **Aprobado** | Los handlers entregan `OperationOutcome` tipado y un narrador separado produce lenguaje natural; el canary impide que el payload controle el texto. La frontera única decide con `turn.decide`; una acción cerrada pasa a `arguments`, un plan solicita `plan` sólo tras `kind=plan`, y ambos llegan al core con schema, riesgo y verificación deterministas. Conversación ES/EN/spanglish y `narrate` permanecen bajo Gemma-4 E2B QAT sin capacidades inventadas. El E2E real pasó 4/4 en 142,772 s, con journal HMAC válido y cero efectos externos. |
| 10 | Memoria y privacidad | Aprobado | La memoria explícita nace apagada y sus 11 operaciones pasan 405/405 pruebas focalizadas: oráculo 100 positivos/60 literales, cinco correcciones y 34 negativos; DPAPI Current User + AES-GCM para store/transporte/payloads privados; TTL/sesión, confirmaciones, inspección, corrección, borrado y export redactado/reverificado. El journal global encadena HMAC-SHA-256 con clave dedicada envuelta por DPAPI y falla cerrado ante key loss, truncado, rollback o tamper. Cero P0/P1. Evidencia `artifacts/product/memory_privacy_gate.json`. La personalización transversal corresponde a Fable bajo el contrato v3 |
| 11 | GUI fiel | Aprobado | El release 1.0.1 ejecutó WPF + core real con raíz aislada, creó una nota, mostró y expuso por UIA `Guardé la nota «Compras».` y produjo una captura nativa 980×680 sin reescalar, SHA-256 `1b991f8a…e4a32c`. La inspección física y 14/14 contratos acreditan geometría de tres columnas, paleta archivada, conversación central, layout adaptativo, IDs accesibles únicos, contraste ≥ 4,5 y ausencia de motion timeline; 22/22 regresiones de packaging y cleanup también pasan. Evidencia: `artifacts/product/gui_capture_gate.json` y PNG content-addressed |
| 12 | Recursos y fallback medidos | **Aprobado** (GPU física de 3 GiB pendiente-por-entorno) | Workload público v4 completo: 45/45 solicitudes y cero errores en GPU y CPU —30 `turn.decide`, 10 `arguments`, 5 `narrate`—. GPU: VRAM de árbol 1.509,6 MiB ≤3.072, RAM 2.934,4 MiB. CPU puro: VRAM 109,5 MiB ≤128, RAM 4.113,5 MiB y `turn.decide` p50 19,509 s ≤22. Handshake acumulado 120 s y atribución GPU por PDH al árbol. No se extrapola a una tarjeta física de exactamente 3 GiB. Evidencia: `artifacts/product/mind_budget_gate.json`. |
| 13 | Suites y gates; cero P0/P1 | **Aprobado en este host; diversidad física pendiente** | Release pasa **2.063/2.080** pruebas .NET —46/46 Contracts, 88/90 Kernel, 373/377 Providers, 1.092/1.095 Integration y 464/472 Setup— con 17 omisiones explícitas y cero fallos. Python pasa **611 tests + 350 subtests**, sin fallos ni omisiones. El E2E shell→mente→core pasó 4/4 y Gate 12 pasó 45/45 por perfil; siguen pendientes VM/perfil limpio y diversidad real de cuentas/hardware. |
| 14 | Paquete, checksum e instalación limpia | **Pendiente solo por entorno limpio** | El candidato 1.0.8 produjo producto/ZIP/Setup A/B byte-idénticos. El ciclo enlazado same-host validó la activación recuperada, rollback real a 1.0.7 y reactivación de 1.0.8; cada estado pasó smoke de 168 capacidades y conservó exactos 11 árboles versionados y 1.780.271.404 bytes privados. Gate 14 sigue pendiente únicamente porque instalación inicial, primer inicio y purge-data requieren una cuenta/VM desechable. Evidencia: `artifacts/setup/baxy_1_0_8_release_attestation.json`. |
| 15 | Operación, rollback, comparación y commit final | Aprobado | Operación, privacidad, diagnóstico, update, rollback y uninstall están documentados; genealogía/comparación histórica y límites Fable quedan explícitos; el release final tiene checksums y evidencia ligada al HEAD fuente limpio. Este commit documental final no se presenta como el commit embebido, evitando una autorreferencia imposible |

Progreso: **13/15 (86,7 %)**. Los gates 13 y 14 permanecen pendiente-por-entorno
(equipo/perfil limpio del usuario); los tramos de entorno de 7 y 12 (micrófono
físico y GPU física de 3 GiB) están anotados dentro de sus gates aprobados y
listos en un paso. Un gate documental aprobado no afirma que sus
regresiones ya pasen en runtime; esa demostración pertenece a los Must 4 y 13.
El release nuevo y el recorrido físico same-host cerraron build, payload embebido,
checksum, activación, update, rollback y keep-data, pero no aprueban Must 14: faltan
primer inicio y purge-data en un Windows o perfil realmente limpio.
Los recorridos automatizados reales de notas, estado local, GPU, audio y memoria acreditan
únicamente esas slices. El gate de audio observa estado de control, no sonido
audible, y cubre un equipo y su endpoint predeterminado; no acredita providers
ajenos, voz, instalación ni los gates físicos restantes.
La compuerta GPU acredita un host y snapshot, no temperatura/procesos, hardware
exhaustivo, una tarjeta física de 3 GiB, GUI ni instalación limpia.
