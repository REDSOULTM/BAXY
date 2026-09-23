# Fase 3.5 — baseline por capas (meta 2026-09-22, entregable 2)

Corpus y cifras con `scripts/semantic_corpus.py` (build → sample → score) y `scripts/semantic_replay.py literals`
(sólo `turn.decide`, nada se ejecuta). Todo el texto es privado: `%LOCALAPPDATA%\BAXY\semantic-corpus-v1\`
(corpus, descartes con motivo y muestra por motivo, etiquetas a mano, muestra de 50 re-etiquetas). Decisiones:
`DECISIONES_OPUS_2026-09-22.md` §6–§10.

```
python -X utf8 scripts/semantic_corpus.py build && python -X utf8 scripts/semantic_corpus.py sample --size 1000
python -X utf8 scripts/semantic_replay.py literals --corpus <corpus_run.jsonl> --skip-survey --src <worktree>/src --out <capas.jsonl>
python -X utf8 scripts/semantic_corpus.py score <742.jsonl + capas.jsonl> --survey-reference <742 de b5c9fe72>
```

## Filtros (publicados)

| Capa | Filas canónicas | Fuera por idioma | Fuera por destinatario | Otras salidas | Quedan |
|---|---|---|---|---|---|
| A (uso real) | 1 866 `observed_user` + 742 encuesta + 112 turnos del registro real | 31 (18 otro idioma, 5 ruido, 8 desconocido) | 1 504 (1 503 sesiones con agentes `codex/*`, 1 código) | 413 duplicados de texto (la encuesta salió de esas trazas) | **772** (es 621, mixto 121, en 28, desconocido 2) |
| B (herencia curada) | 1 370 | 27 | 1 227 (1 081 requisitos de producto, 99 notas técnicas, 25 código, 15 charla con agentes, 6 marcado, 1 ingeniería) | 8 duplicados | **108** |
| C (sintéticos) | 7 631 | 2 267 (2 230 otro idioma) | 292 | 564 sólo-traza (no son compromiso de aceptación), 248 duplicados | **4 066** (muestra estratificada: 1 017 en 45 estratos) |

## Cifras sobre `b5c9fe72` (tag `opus55-inicio`)

| Capa | Bien | Fallos por tipo |
|---|---|---|
| **A** | **738/768 = 96,1 %** | aclaración 10, aclaración innecesaria 8, no leído 4, leído mal 4, efecto no pedido 2, límite que faltó 1, límite falso 1 |
| A · encuesta 742 (juzgada contra lo que acreditó; las abiertas por su etiqueta de lectura) | 670/676 = 99,1 % | H0086/H0254/H0690 «bajá el volumen a N» se decidían como instalar un paquete (lector de winget desde REOPEN1993) aunque estaban acreditadas como volumen |
| A · conversaciones reales de BAXY Definitivo (con su historial) | **68/91 = 74,7 %** | 4 turnos «sí/no» a una confirmación del shell fuera |
| B | 29/108 = 26,9 % | aclaración 31, límite falso 20, no leído 16, aclaración innecesaria 10, incompleto 2 (4 re-etiquetas) |
| C (muestra) | 544/1 017 = 53,5 % | aclaración 97, aclaración innecesaria 95, no leído 77, efecto no pedido 70, límite falso 65, leído mal 51, incompleto 17, efecto inventado 1 (153 re-etiquetas) |

Familias con más volumen en B: conversación 26/37, `system.status` 0/13, `task.manage` 1/9, `streaming.navigate` 0/6.
En C: conversación 427/635, `app.open` 11/38, `media.play` 8/34, `audio.volume` 19/29, `web.search` 8/21,
`vision.describe` 1/19, `media.control` 0/18, `memory.save` 0/10.

Lectura: la A pasa el 95 % por el peso de la encuesta, que el sistema actual ya acreditó; la población que dice si
BAXY entiende una conversación nueva es la de las **conversaciones reales (74,7 %)** y el held-out del dueño. B y C
mezclan fallos de BAXY (límites falsos sobre capacidades del catálogo, preguntas de más) con un oráculo del catálogo
viejo; se vigilan por dominio y toda caída se explica.

## Cifras sobre el HEAD con la clase 1 (`b280a84c`)

| Capa | Bien | Cambio frente a b5c9fe72 |
|---|---|---|
| **A** | **746/768 = 97,1 %** | +8 |
| A · encuesta 742 | 670/676 = 99,1 % | = (los 742 aislados no cambian de decisión) |
| A · conversaciones reales | **76/91 = 83,5 %** | +8 (el hueco de diálogo: respuestas a la pregunta abierta, pronombres, temas) |
| B | 29/108 = 26,9 % | = |
| C (muestra) | 544/1 017 = 53,5 % | = |

Fallos que quedan en A: aclaración innecesaria 7, aclaración 5, no leído 3, leído mal 2, efecto no pedido 2, efecto
inventado 1.
