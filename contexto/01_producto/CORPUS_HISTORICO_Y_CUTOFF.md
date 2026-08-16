# Corpus histórico y cutoff

## Cutoff inicial

- Hora local: `2026-07-14T06:51:49.1607549-04:00`.
- Hora UTC: `2026-07-14T10:51:49.1612548Z`.
- BAXY: branch `codex/baxy-rebuild-v3`, commit
  `02d999dd5141cea4a022833df3c109aeeaec6266`, árbol limpio antes de crear
  `contexto/`.
- Probando Gemma 4: commit
  `f97659ebe1f3c3bcf48e12a9366fa14be1a3a9e9`, con 34 entradas locales que
  deben fijarse por hash de contenido.
- FunctionGemma: 1.090 archivos observados, sin `.git`; debe fijarse por
  manifiesto de contenido.
- Agentes: manifest schema 1 generado
  `2026-07-14T10:31:49.608811+00:00`, 322 registros, 303 completados y 19
  interrumpidos; SHA-256 del manifiesto
  `90762D6047708BBD412BA3B83F90B2621740342F8517730E0EECA6C752C95F24`.

## Anclas SHA-256 iniciales

| Fuente | SHA-256 |
|---|---|
| `BAXY_GPT56_ULTRA_PROMPT.md` | `C5C98F8B2C4E5173FA55AB99AD9C00771C3CC72140BB3AF515161E8EE1E30CC9` |
| solicitud adjunta | `DBE70449F6A3D7EA7DBF2E887BF6F28B156B0BDEDDF8BE49B9FDC61E04A93C12` |
| `documentacion/00_LEEME.md` | `BE4C989B358DFE989AAD73C4864B088D05D41687ED9FBB0BFF6ECD2F6D16A78F` |
| `documentacion/01_CONTRATO_PRODUCTO.md` | `7943A5312B66C41F4D8D289A6A304E6DBA9B954D5D57B40E1C1F6BECD44C9422` |
| `documentacion/02_INDICE_FUENTES.md` | `56C5B97089A410C11F3FB81FC300A2B88DB3518BF27E3B04721B59FC06514910` |
| `documentacion/03_HALLAZGOS_AGENTES.md` | `7805C2144052E5DBBA33164B3EEEDB17585832118359E16D1E0B4F7E6EC8C0A2` |
| `documentacion/04_ARQUITECTURA_TECNOLOGICA.md` | `F10C6649F13A3AC02276AE84415FDB7339846D86EF3F8459F286E847B78C8023` |
| `documentacion/05_FALLOS_Y_REGRESIONES.md` | `4DBB685C92B87FF30664D6EAE9B80388F17208FC9AF0852D3097BA3983AA6B61` |
| `documentacion/agentes/README.md` | `5A16DA41C49B6E3F8A22766C44161805C29F8F28076C62193BBA83685B5B0E5A` |
| `documentacion/agentes/INDICE.md` | `DCB5F6F3A191ED2026A55FF6443068FAC4677BC4D2367C5398413D01235D60C8` |

## Familias incluidas

1. BAXY actual, `legacy/`, historial Git y conversación actual.
2. Carter y Probando Gemma 4, incluida la tesis y artefactos históricos.
3. FunctionGemma, router, catálogo, corpus y evaluaciones.
4. Conversaciones, logs, ejemplos, grabaciones y adjuntos disponibles.
5. Archivo sanitizado de agentes y, selectivamente, segmentos privados
   pertinentes.

## Congelamiento validado

- Manifiesto: `artifacts/corpus_cutoff/source_manifest.json`.
- Estado SHA-256: `85929373646040f54771a7e3543a5ac3d022dbce688c55d17615ae35b7eb3fbd`.
- Reproducción: dos ejecuciones consecutivas idénticas.
- Privacidad: cero rutas absolutas y cero menciones a la carpeta privada.
- Cobertura: 17 fuentes lógicas. Los corpus, trazas, tesis y documentación
  ignorados por Git tienen archivos/manifiestos propios; las rutas con espacios
  y Unicode se parsean mediante el formato NUL de Git.

## Extracción validada

- 122.744 ocurrencias de fuente revisadas y consolidadas en 14.836 mensajes:
  12.036 de producto ES/EN/spanglish y 2.800 de trazabilidad `trace_only`.
- 10.864 literales normalizados únicos, 10.867 contratos literales por alcance,
  3.969 duplicados exactos enlazados y 2.084 misiones canónicas. Los requisitos,
  instrucciones de ingeniería y fallos distintos conservan firmas de texto
  separadas; los duplicados exactos solo se consolidan dentro del mismo alcance
  de aceptación.
- 4.650 misiones reales de usuario. Ninguna misión de producto
  ES/EN/spanglish carece de operación; las trazas ajenas omiten operaciones y
  providers deliberadamente porque no autorizan efectos en BAXY 1.0.
- Cada mensaje tiene exactamente un registro en
  `tests/data/historical_message_mapping.jsonl` y cada referencia resuelve a
  `tests/data/historical_missions.jsonl`.
- Los descendientes de agentes se excluyen mediante identidad concreta de
  sesión, no mediante el `session_id` heredable de la raíz.

## Revisión semántica v3 cerrada

La revisión `2026-07-15-audio-status-v3` regeneró únicamente los
derivados bajo schema 2. El manifiesto, su payload
`85929373646040f54771a7e3543a5ac3d022dbce688c55d17615ae35b7eb3fbd` y las
122.744 ocurrencias no cambiaron. La separación por alcance produce 14.836
`message_id`: tres más que el snapshot anterior, sin añadir historia.

La polaridad ahora separa `operations` de `denied_operations`: 79 filas son
`no_action_constraint`, 98 mensajes contienen 116 efectos denegados y una
negativa pura tiene riesgo `no_effect`. La distribución queda en 8.171
conversaciones, 303 instrucciones de ingeniería, 117 fallos, 79 restricciones
de no-acción, 37 preferencias, 1.471 requisitos, 8 instrucciones de seguridad y
4.650 misiones de usuario.

La v2 hizo crecer el catálogo de 40 a 42 familias y distinguió `game.manage` (169 filas:
160 de producto y 9 de traza),
`game.purchase` (6), `game.launch` (46 filas objetivo/29 literales) y
`game.install` (81 globales: 74 filas objetivo/63 literales y 7 filas
inequívocamente ajenas conservadas solo como traza). La v3 añade
`audio.status` como familia 43 y separa exactamente 16 consultas read-only en
una misión propia; `app.open` queda en 329 y el total de misiones en 2.084.

El compromiso funcional de BAXY 1.0 es español, inglés y spanglish, incluyendo
code-switch y errores STT de esos idiomas. El campo `language` es un detector
heurístico: `other` no equivale automáticamente a fuera de alcance. Las lenguas
inequívocamente ajenas mantienen ID, hash, fuente y mapping bajo la política
`trace_only_not_acceptance_commitment`, sin crear obligación de cobertura.

Dos reconstrucciones finales A/B produjeron los cuatro artefactos idénticos byte
a byte con el builder `341e86f3…c62c74ea`; 37/37 pruebas de contrato del corpus
aprobaron. La revisión cierra la semántica derivada; los estados de
implementación siguen pendientes y se expanden desde este ledger.
