# Ledger de requisitos históricos

## Autoridad y artefactos

Este ledger convierte la historia congelada de Carter y BAXY en alcance
verificable. Su autoridad de contenido es el manifiesto
`artifacts/corpus_cutoff/source_manifest.json`, con cutoff UTC
`2026-07-14T10:51:49.1612548Z` y estado SHA-256
`85929373646040f54771a7e3543a5ac3d022dbce688c55d17615ae35b7eb3fbd`.
Los derivados vigentes usan schema 2 y revisión
`2026-07-15-audio-status-v3`; su acta reproducible es
`artifacts/corpus_cutoff/semantic_amendment.json`. La revisión no altera las
fuentes ni el cutoff.

Los artefactos canónicos son:

- `tests/data/historical_messages.jsonl`: un registro por mensaje consolidado;
- `tests/data/historical_missions.jsonl`: agrupación semántica canónica;
- `tests/data/historical_message_mapping.jsonl`: resultado único de cada
  mensaje y su prueba de aceptación;
- `artifacts/corpus_cutoff/extraction_report.json`: métricas y hashes;
- `scripts/build_historical_corpus.py`: extracción reproducible.

El corte privado de uso real para el Goal 10 no cambia esa autoridad. Lo proyecta
con `scripts/build_observed_user_corpora.py` y publica sólo reglas, conteos y hashes
en `tests/data/historical_observed_user_corpora.v1.json`. Sus dos JSONL locales son:

- Nivel 1: 1.947 turnos observados del runtime BAXY/Gemma, 626 textos únicos;
- Nivel 2: 808 misiones accionables observadas, 281 textos únicos.

Los prompts de desarrollo `codex/` quedan fuera. Las repeticiones reales se
conservan como frecuencia real. La igualdad de texto y contrato sirve para agrupar
causas, pero cada ocurrencia exige replay y veredicto individual.

## Resultado de cobertura

| Métrica | Resultado |
|---|---:|
| Ocurrencias de fuente revisadas | 122.744 |
| Mensajes consolidados | 14.836 |
| Mensajes de producto ES/EN/spanglish | 12.036 |
| Trazas históricas ajenas | 2.800 |
| Literales normalizados únicos | 10.864 |
| Contratos literales por alcance | 10.867 |
| Duplicados exactos enlazados | 3.969 |
| Misiones canónicas | 2.084 |
| Familias de operación componibles | 43 |
| Mensajes redactados | 656 |
| Misiones reales de producto sin operación | 0 |

Distribución por clase:

| Clase | Casos |
|---|---:|
| conversación/pregunta | 8.171 |
| misión real de usuario | 4.650 |
| requisito de producto | 1.471 |
| instrucción de ingeniería | 303 |
| feedback/fallo | 117 |
| restricción de no-acción | 79 |
| preferencia | 37 |
| instrucción de seguridad | 8 |

Distribución consolidada por familia:

| Familia | Casos |
|---|---:|
| FunctionGemma | 7.082 |
| Probando Gemma 4 | 3.789 |
| Carter OS AI | 2.028 |
| hilos Codex raíz | 1.692 |
| BAXY | 154 |
| historial local Gemma 4 | 90 |
| solicitud maestra actual | 1 |

## Revisión semántica v3 cerrada

La primera auditoría proyectó corregir 81 filas y llevar `app.open` de 350 a
337, pero esa cifra no era un resultado canónico. La revisión completa amplió
el análisis a negación, alcance de cláusula, ejemplos hipotéticos, instrucciones
de ingeniería y límites entre abrir Steam, navegar su cliente, instalar, lanzar
y comprar. Ese resultado v2 dejó `app.open=329`; la enmienda v3 separa 16
consultas read-only como `audio.status` y deja 2.084 misiones.

Las 122.744 ocurrencias, fuentes y cutoff permanecen idénticos. La separación de
contratos por alcance produce 14.836 `message_id`: tres más que el snapshot
anterior, sin sumar ocurrencias. Cada fila separa efectos autorizados (`operations`) de efectos
explícitamente rechazados (`denied_operations`): 79 mensajes son
`no_action_constraint`, 98 contienen al menos una denegación y el total es 116
etiquetas denegadas. Clase, riesgo, firma, misión y mapping se regeneraron como
una unidad; una negativa pura usa riesgo `no_effect`.

## Semántica de cada registro

Cada mensaje conserva ID estable, texto literal redactado, hash del original,
paráfrasis, clase, idioma heurístico, intención, estado esperado, operaciones
autorizadas, operaciones denegadas, encadenamiento, datos implicados, política
de riesgo y confirmación, evidencia de éxito, respuesta natural, fallback,
fuente lógica, ubicación, hash de la fuente y misión canónica. Las ocurrencias
derivadas repetidas se consolidan sin perder sus aristas de procedencia. Los
turnos humanos observados nunca se fusionan solo por compartir texto.

Cada misión agrega el resultado correcto, plan por operaciones, roles de
provider, verificación y un `acceptance_test_id`. Las misiones de producto usan
`specified_pending_implementation`; las ajenas usan
`trace_only_not_acceptance_commitment`, operaciones/providers vacíos y riesgo
`no_effect`. Estar especificado o preservado no equivale a estar implementado ni
aprobado.

## Reglas de inclusión y exclusión

- Se incluyen mensajes humanos observados, requisitos, preferencias, fallos,
  ejemplos de aceptación y casos históricos derivados hasta el cutoff.
- Las instrucciones puramente de ingeniería se conservan como restricciones,
  pero no generan tools de usuario.
- Los 70 hilos Codex incluidos son raíces relevantes propiedad del usuario.
  Los descendientes de agentes se excluyen usando la identidad concreta
  `payload.id`; `payload.session_id` puede heredar la raíz y no es un filtro
  suficiente.
- `FunctionGemma/fg_train.iter3.jsonl` no se ingiere como historia humana: es
  una expansión sintética derivada. Los casos históricos y de aceptación que
  la alimentan ya se conservan desde `train_v3`, router, evaluaciones y fuentes
  originales.
- Directorios de competidores y evidencia visual/privada no se convierten en
  mensajes. Los manifiestos privados de agentes solo aportan hashes.
- Secretos, correos, teléfonos y segmentos absolutos de perfil de Windows se
  redactan; el hash del original preserva identidad sin publicar el valor.
- Los documentos de ledger generados después del cutoff (`06+`) no vuelven a
  entrar como fuentes. Solo se leen los documentos BAXY `00`–`05` presentes
  en el commit congelado, evitando una retroalimentación autorreferencial.
- El compromiso funcional 1.0 es español, inglés y spanglish, incluidos
  code-switch y errores STT de esos idiomas. Las expresiones inequívocamente
  ajenas conservan ID, hash, fuente y mapping como
  `trace_only_not_acceptance_commitment`; no crean una obligación de producto.
- `language` es una ayuda heurística. Muchos comandos breves ES/EN aparecen
  como `other`, por lo que esa etiqueta nunca se usa sola para decidir alcance.

## Operaciones, no tools por frase

Las 43 familias son primitivas componibles, entre ellas aplicaciones,
ventanas, audio, multimedia, navegación, calendario, notas, tareas, archivos,
Office, mensajería, estado y ajustes del sistema, conectividad, juegos, visión,
OCR, memoria, notificaciones, rutinas y respaldo. Una misión como instalar un
juego y reproducir música enlaza `game.install` + `media.play`; no crea una tool
monolítica específica de esa frase.

En juegos, `game.manage` navega o consulta el cliente sin lanzar ni instalar
(169 filas globales: 160 de producto y 9 de traza);
`game.purchase` representa el compromiso monetario; `game.install` cubre
instalación, descarga, cancelación y desinstalación; `game.launch` inicia el
juego. Los oráculos target ES/EN/spanglish fijan 46 filas/29 literales de
lanzamiento y 74 filas/63 literales de instalación. Siete instalaciones en
lenguas inequívocamente ajenas permanecen únicamente como traza histórica.

## Validación reproducible

Dos reconstrucciones finales A/B con el builder
`341e86f39c90c18f7c3cfa44f651b86139a64f298043a6b86a5c160df62c74ea`
produjeron los cuatro artefactos byte a byte idénticos. Sus hashes lógicos son:

| Artefacto lógico | SHA-256 canónico |
|---|---|
| mensajes | `da9b309cdbcabc82cb6a6091f29aedff321a0ab2ebf817f14e09bf9a4708ddc8` |
| misiones | `9515424352a2de1edffa7e64ce866336614b192881a14249448af71493da8664` |
| mapeo | `d344ecde935219b64ffe850cf519503f62f7ebf24372820cdf873bf8b9ccfd88` |

Y sus hashes físicos son:

| Archivo | SHA-256 físico |
|---|---|
| `extraction_report.json` | `5c195fbf6c3be475675b4d3218dd47bbe5a6efa6a294c074718f4c660241a7ca` |
| `historical_messages.jsonl` | `9d8b2d095dcd0bafb9d2a7bb616876b34b6b0321d53597211c37a26473ac436e` |
| `historical_missions.jsonl` | `96e4f50566b657ec2f0dea89ddf6655dce2dc2ac63f17d0593ae05e9cc0c86d1` |
| `historical_message_mapping.jsonl` | `b5e9c75cf095fc417e0f2b75e36b2d5e63bdded6634e6f5fbb835f2b24794f5b` |

Los digests de filas target también quedan congelados:

| Oráculo | IDs | Literales normalizados |
|---|---|---|
| `game.launch` | `7b9ccccd5c643660e786e7699cdb15062a2fef46671a1edcea641bd72eb2c3cc` | `d51a40fdf93920a8b5ce67f4bbb74977f9e8702792b179eef333116d5ae752ba` |
| `game.install` | `76faffd5817be902a5f6477d40acdd78bbf678a0ae2b17bbbaf8bbe6d9f24d90` | `486d6e182491b0689544e03ebfd80190b0b3c5763d2f985a50041d27cc2aa595` |
| `audio.status` | `cd3512c246ca7b4fe29f98e944eac5885cd73ca478a4fa9183d21edb409c60fb` | `b35442c8154d9233b02229c7922a1bf6d266e062a3476fcd05c51cf970faf156` |

La suite exige que cada mensaje se mapee exactamente una vez, todas las
misiones referenciadas existan, ninguna misión real de producto carezca de
operación y toda traza use el contrato sin efecto, los
conteos y hashes se recalculen, no haya NUL ni rutas absolutas de perfiles de
usuario, la detección de riesgo sea proporcional y requisitos o fallos
semánticamente distintos no se fusionen bajo una etiqueta general. También
exige schema/alcance explícitos, propagación de denegaciones y digests exactos
para los oráculos de juegos y audio status. Resultado actual: 37/37 pruebas de contrato del
corpus aprobadas; la suite completa se vuelve a ejecutar en cada commit.

## Estado de release

La extracción y trazabilidad cierran el bloqueante B-002. No cierran el
producto: los 2.084 contratos permanecen especificados o preservados, pero las misiones con
efecto dentro del alcance ES/EN/spanglish aún requieren provider, replay,
prueba y evidencia. Conversaciones, requisitos, restricciones y negativas
seguras deben demostrar su resultado sin inventar un provider. Las trazas en
lenguas inequívocamente ajenas conservan mapping y procedencia, pero no son un
compromiso funcional del replay 1.0.
