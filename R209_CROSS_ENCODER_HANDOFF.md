# Handoff — cross-encoder BAXY R207–R209

Rama transferible: `codex/baxy-cross-encoder-r209-handoff`.
Commit inicial publicado: `9fd8b59e` (`research: preregister BAXY cross-encoder evaluation`).

## Prompt operativo para el relevo

Eres responsable de BAXY en `D:\BAXY\source`. Conserva el producto integrado,
el catálogo tipado, la separación mente → kernel → provider y el árbol sucio de
otros agentes. Trabaja por mediciones reproducibles: congela entradas antes de
correr, no entrenes contra R186, publica instrumentos, pruebas, hashes y
rechazos. No abras V9 sin confirmación. No integres un candidato offline sólo
porque reduzca su pérdida: debe cumplir exactitud y abstención fuera de
catálogo, y no puede reabrir efectos no solicitados, éxitos no verificados ni
texto visible fijo. Qwen3-4B continúa activo; la misión no era reemplazarlo.
Voz, wake word y STT están fuera de alcance y el §7 no puede declararse
cumplido.

## Objetivo de la misión

Atacar el camino por modelo de BAXY sin sustituir Qwen3-4B ni añadir otro gate
léxico. BAXY ya tiene las 169 operaciones: el defecto investigado es la
asociación fiable de una formulación libre con la operación real, y la
abstención segura fuera de catálogo. Qwen continúa siendo el LLM que conversa y
planifica; este experimento evalúa un clasificador local que le puede entregar
operaciones pertinentes.

El encargo autoritativo original exige: todo local, catálogo tipado como única
autoridad, cero efectos externos, R186 como evaluación congelada y no usada
para ajustar, sin abrir V9, sin tocar voz/wake/STT. La barra exploratoria es
al menos 74/77 de R146 model-owned y 9/9 controles OOS con cero candidatos.
Una mejora no se integra al runtime sin una auditoría posterior y sin medir los
tres ceros duros del corte D.

## Estado transferible

- R207 ya produjo 23.700 pares deterministas: 4.740 positivos y 18.960
  negativos, contra 170 etiquetas (169 operaciones más `__no_action__`).
  El generador verifica disjunción textual normalizada con R186.
- R208 está prerregistrado antes de la GPU. El mecanismo es un cross-encoder
  binario que puntúa **las 170 etiquetas**, con probabilidad `compatible >=
  0.5` fijada antes de R186. No hay retriever, gate léxico ni umbral post hoc.
- R209 entrena en memoria el checkpoint local
  `D:\BAXYRuntime\experiments\mtop-operation-compatibility-verifier-v16`.
  No guarda un checkpoint y no modifica runtime, providers ni V9.
- La compuerta Full previa cerró verde: 3.865 .NET y 8.440 Python + 446
  subpruebas. Ejecutada antes de lanzar R209.

## Resultado R209

La corrida R209 se lanzó el 2026-08-14T14:54:05-04:00 con:

```powershell
& 'D:\BAXYRuntime\experiments\functiongemma-train-v1\Scripts\python.exe' `
  D:\BAXY\source\experiments\mind_router_spike\train_evaluate_cross_encoder_r209.py
```

Telemetría local no versionada: `artifacts/local-temp-r209-training/`.
Resultados ya escritos por stdout, todavía sin evaluación final:

| Época | Pérdida media |
|---:|---:|
| 1 | 0.23876836461576983 |
| 2 | 0.14872885945162692 |

R209 terminó y su recibo es
`artifacts/development/cross_encoder_r209_attested.json`. Está **rechazado**:
16/77 exactos (mínimo 74), 5/9 OOS con cero candidatos (requeridos 9/9) y
p95 0,370289 s. La pérdida bajó 0,238768 → 0,148729 → 0,128127, pero no es
una evidencia de capacidad productiva. No se guardó checkpoint ni se modificó
runtime. La auditoría R210 reproduce este veredicto.

La compuerta Full posterior a R210 cerró verde: 3.865 pruebas .NET y 8.441
pruebas Python + 446 subpruebas, cero fallos, en 2026-08-14.

R211 inventarió de forma estática la señal estructural del snapshot del
catálogo: 169 operaciones en 31 familias; 125 con argumentos requeridos y 44
sin ellos. Confirma que schema y riesgo aportan señal tipada, pero **no** una
ontología explícita de dominio. Es evidencia diagnóstica, no un candidato ni
un cambio de runtime: quedan expresamente prohibidos un gate léxico y cualquier
selección de operación derivada de R211. La Full posterior a R211 aprobó el
2026-08-14: 3.865 .NET y 8.442 Python + 446 subpruebas, cero fallos.

R212 hace explícito el límite de la alternativa estructural pura. Eliminó
nombre de operación, nombre de campo, descripciones y valores de enum, y
conservó únicamente forma de schema y riesgo. Las 169 operaciones colapsan en
97 clases de equivalencia; 101 quedan en clases ambiguas y la mayor tiene 12
operaciones, por lo que el máximo teórico de selección exacta por esa señal es
97/169 (57,3964 %). Puede validar una llamada ya conocida, pero no groundear un
dominio de formulación libre ni elegir operaciones. El artefacto R212 es
`artifacts/audit/catalog_structural_discriminability_r212.json`
(`e21ddcb103353dafb561adc63e5cb8a391f75c49208a805decb362acf5fcff5c`).
No autoriza runtime, gate léxico ni un corte B nuevo: no hay candidato que un
corte pueda acreditar.

El ledger integral y el registro de mantenibilidad del checkout actual ya
tenían cambios ajenos sin versionar. No se incluyeron para no mezclar campañas;
el rechazo R210 queda documentado y atestado en esta rama, pero el agente de
relevo debe reconciliar esas dos entradas canónicas con el propietario de sus
cambios antes de declarar la campaña actualizada en esos registros.

Si se retoma en otro equipo, el proceso GPU no se puede transportar: verificar
los SHA del preregistro y relanzar R209 desde cero sólo si hace falta repetirlo,
conservando R186 como holdout.

## Archivos de la línea

- `experiments/mind_router_spike/build_r207_cross_encoder_pairs.py`
- `artifacts/development/r207_cross_encoder_pairs.jsonl`
- `artifacts/audit/r207_cross_encoder_pairs_admission.json`
- `experiments/mind_router_spike/preregister_cross_encoder_r208.py`
- `artifacts/development/cross_encoder_r208_preregistration.json`
- `experiments/mind_router_spike/train_evaluate_cross_encoder_r209.py`
- `experiments/mind_router_spike/audit_cross_encoder_r210.py`
- `tests/test_r207_cross_encoder_pairs.py`
- `tests/test_cross_encoder_r208.py`
- `tests/test_cross_encoder_r210.py`
- `experiments/mind_router_spike/audit_catalog_structural_signal_r211.py`
- `artifacts/audit/catalog_structural_signal_r211.json`
- `tests/test_catalog_structural_signal_r211.py`
- `experiments/mind_router_spike/audit_catalog_structural_discriminability_r212.py`
- `artifacts/audit/catalog_structural_discriminability_r212.json`
- `tests/test_catalog_structural_discriminability_r212.py`

También están versionadas en esta rama las entradas necesarias para reproducir
R207 sin depender del árbol sucio original: el oráculo R146, el prerregistro
R186, el corpus R196 y sus tres generadores con pruebas. El snapshot de
vocabulario de catálogo ya pertenecía al historial base.

## Continuación obligatoria

1. Conservar el recibo R209 y auditoría R210: esta línea quedó rechazada, no
   reabrirla cambiando umbral o ajustando con R186.
2. El ledger integral y el registro de mantenibilidad ya registran R207–R212
   como investigación rechazada, sin integración productiva.
3. Commitear y hacer push sólo los ficheros propios de esta línea, preservando
   el gran árbol sucio preexistente.

## Siguiente frente según el ledger canónico leído el 2026-08-14

No repetir otro clasificador textual de operaciones sin una hipótesis nueva:
R209 cierra esa línea como rechazada. R212 también descarta que sólo la forma
no léxica de schema/riesgo pueda producir el grounding de dominio buscado. Usar
las descripciones para seleccionar volvería a ser un mecanismo textual y no
queda autorizado por R212. Por tanto no se abre un corte B nuevo hasta contar
con una hipótesis que aporte una ontología de dominio independiente y un
candidato no léxico que esa población pueda refutar. Le siguen medir primera
señal/acción verificada/latencia de voz, misiones físicas dependientes, una
línea wake nueva y el ciclo de instalación limpia. Estas tareas no se iniciaron
en esta rama.

Antes de proponer esa derivación, lee `src/baxy_mind/effect_intent.py` alrededor
de `_curated_domain_is_grounded`: el catálogo snapshot sólo aporta `name`,
`description`, `argumentsSchema` y `risk`; no tiene una ontología de dominios.
El mismo módulo documenta un intento anterior de gate léxico derivado del
catálogo, rechazado porque aumentó el sobre-veto del corte B de 224/560 a
385/560. Por tanto la siguiente hipótesis debe ser estructural y evaluarse en
un oráculo fresco; no es permiso para añadir una sexta puerta léxica.

Voz, wake word y STT están fuera de alcance: el §7 no puede declararse
cumplido en esta campaña.
