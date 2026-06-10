# Baseline encoder ANTES del reentreno (J Balvin) — 2026-06-09

Medido con el encoder ACTUAL (artefacto commiteado), sobre el **holdout**
(sha256 split, excluido del entreno), modo `--inherit` (recall de producción real).

```
.venv_router_train/Scripts/python.exe scripts/router_eval.py --split holdout --slices --inherit
```

## Números a batir (GATE: ninguno debe bajar)

| slice            | recall        |
|------------------|---------------|
| **TOOL total**   | 272/278 = **0.9784** |
| NO-TOOL keep     | 82/86 = 0.9535 |
| short            | 105/106 = 0.991 |
| continuation     | 34/35 = 0.971 |
| multilingual     | 3/4 = 0.750 |
| lang:es          | 269/274 = 0.982 |
| lang:fr          | 1/1 = 1.000 |
| lang:it          | 0/1 = 0.000 |
| lang:pt          | 2/2 = 1.000 |

holdout: 1733 rows (dev=1369 holdout=364). recall misses 6, over-offers 4.

## Gate de promoción (definido ANTES de entrenar)
- TOOL recall total **≥ 0.9784** (no baja del piso de hoy).
- **Ningún idioma con n≥10 degrada** (anti-regresión per-language, como el wake).
  Los slices fr/it/pt tienen n≤2 → no son gate (muestra insuficiente); el gate
  real per-language es **lang:es** (n=274) que NO debe bajar de 0.982.
- Si algún subgrupo fuerte cae → NO se promueve, rollback con
  `git checkout HEAD -- gemma4_agent/data/router_encoder_ft/`.

## RESULTADO POST-REENTRENO (gate PASA)

Entreno: 12.891 pares, 3 epochs, batch 64, 606 steps, ~2.5 min en RTX 4060 Ti
(`scripts/_diag/_retrain_to_tmp.py` → dir temporal → swap atómico; el server
estaba corriendo con el encoder viejo en RAM, por eso el temp-dir evita el
error 1224). ONNX int8 re-exportado.

| slice          | baseline | NUEVO  | veredicto |
|----------------|----------|--------|-----------|
| TOOL total     | 0.9784   | 0.9784 | ✅ igual   |
| lang:es (n=274)| 0.982    | 0.982  | ✅ igual   |
| short          | 0.991    | 0.991  | ✅         |
| continuation   | 0.971    | 0.971  | ✅         |
| NO-TOOL keep   | 0.9535   | 0.9535 | ✅         |

**Caso J Balvin (lo que cambió):** el router ahora ofrece SOLO `web` en preguntas
culturales (media ni aparece en top-5), y los play-commands siguen liderando media:

| query                              | encoder viejo        | encoder NUEVO          |
|------------------------------------|----------------------|------------------------|
| ¿has escuchado canción de J Balvin?| media (rutea→playback)| **web:0.38** (media ausente) |
| ¿conocés a Bad Bunny?              | web (apenas)         | **web:0.48**           |
| pon stranger things en netflix     | media ✅             | **media:0.55** ✅       |
| reproducí canción de J Balvin      | media ✅             | **media:0.53** ✅       |

→ El 4B ya NO recibe `media` como opción en la pregunta cultural → no puede
alucinar un playback_status. Raíz eliminada en ORIGEN (sin media-drop heurístico).

Rollback: `mv router_encoder_ft__bak router_encoder_ft` (+ onnx). El viejo quedó
respaldado en `router_encoder_ft__bak` / `router_encoder_onnx__bak`.

## Cambio aplicado al corpus de entreno
+144 pares cultura→`web` en `tool2vec_queries.jsonl` (6 idiomas, música/cine/series,
artistas de varias regiones). Etiqueta `web` por precedente del corpus
("quien es X", "Conoces el nuevo juego de batman?"). NUNCA `media` (reproduce) ni
`knowledge` (= docs locales del user).
