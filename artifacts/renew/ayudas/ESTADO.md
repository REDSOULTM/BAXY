# Ayudas al modelo sin reentrenar: lo adelantado antes del goal (2026-10-19)

Rama `pc-ayudas` desde `c9b18e62b` (producto final del goal de ajuste fino, e0a7d9923 con c2-e1.0). No está fusionada
en `lote-final` ni en `baxy-renew`. El prompt del goal es `PROMPT_GOAL_AYUDAS_MODELO.md`, en el PC y fuera de git.

## Holdout nuevo, sellado (no abrir)

Lo escribió un subagente aislado el 2026-10-19, antes de implementar ninguna palanca. Está en
`F:\BAXYeval\ayudas_v1\holdout\`, junto con `SEALED_AYUDAS.md`.

| Archivo | sha256 |
|---|---|
| `decision_ayudas.sealed.json` (AH001-AH240) | `74efc33cd9426add786ee801b5cae50ef2f176acaebbc80494613b47bdb42381` |
| `escenas_ayudas.sealed.json` (AE01-AE36) | `fa4d11b9c4f9e71715bf51dce4bd601c3fd074807e04f780b85ef9995bc62425` |
| `construir_ayudas.py` (generador; contiene los casos) | `5a27f33c422d834676129299e50a88fbf2bb38101b011ac8ca9b9c9b3347e7f4` |

- **Decisión:** 240 casos, por familia: rutas 60, ventana cerrada 40, modos 30, falsedad 30 y general 80.
  - Por tipo: call 155, call_any 17, ask 10 y text 58.
  - e2e segura: 236.
- **Escenas:** 36 (silencio 20, actuar 6, proponer 4, decir 6).
- **Fuga** (`fuga.py`): 0 en los casos y 0 en las cadenas de las escenas. Con el contexto entero, las escenas marcan
  solo campos de formato (fechas ISO y nombres de ejecutable).
- **Validación:** 0 errores.
- **Para la fase 4:**
  - `bench_decision.judge` no lee los `reply_re` / `reply_not_re` de los casos de texto. Hay que añadirlo antes de
    medir, sin abrir el holdout, para juzgar la honestidad de modos y falsedades.
  - En R_rutas, la lectura, la edición y la papelera solo verifican la carpeta y el nombre.

## Palancas

| # | Palanca | Estado |
|---|---|---|
| 1 | E011: `next` en `calculator_window_not_found` | implementada (8b43c520c), sin medir con el modelo |
| 2 | Modo accesible: `scope` y `notAvailableYet` en el resultado de `system.settings.set` | implementada (122e590b0), sin medir |
| 3 | E024: `folder: baxy_work` y `sameNameInHome` en el recibo de `file.write` sin `folder` | implementada (ef081d9fd), sin medir. Riesgo: que el modelo reutilice `baxy_work` como `folder` (el esquema lo rechaza) |
| 4 | E020: `listedPath(s)` y `subfoldersEntered` en el listado de `file.find` | implementada (9ec29ead4), sin medir |
| 5 | Hechos del turno antes de la respuesta final (5a partido / 5b segunda oportunidad) | diseñada (`DISENO_PALANCAS.md`) |
| 6 | Ruta del home en el significado de `folder` | en la cola del notebook (rama `nb-ayudas`), cribado decision2 s0 + escenas |
| 7 | Frase de los modos en `system.settings.set` (75 tokens) | texto exacto y plan en `DISENO_PALANCAS.md` |
| 8 | Frase de las carpetas de la persona en `filesystem.known.trash.named` (50 tokens) | texto exacto y plan |
| 9 | Pocos ejemplos dinámicos | diseño y plan |
| — | Schema con un único `path` (reentrenar) | diseño para un goal futuro |

**Suites de pc-ayudas:**
- Kernel 574/574, Contracts 69/69, Setup 477/477, pytest 32/32.
- Providers: 2320 pasan y 1 falla, `VisibleClickOnAStillWindowAnswersNotFoundAfterOneLook`, por tiempo (936 ms
  frente a 900). La base sin tocar también falla 1 de cada 4 veces.
- App Release: 0 avisos.

## Cola del notebook (enviada el 2026-10-19 a las 14:50)

Rama `nb-ayudas` desde `c9b18e62b`:

1. Inventario de errores y resultados opacos en los demás proveedores, con una propuesta de `next` por cada uno, en
   `artifacts/renew/ayudas/ERRORES_ACCIONABLES.md`.
2. Arreglos del banco, no del producto:
   - `bench_e2e.py:245-247`: `first_audio_ms` tras una confirmación (E027 s1);
   - `Test-SteamLibraryVisible`: reconocer la vista por sus marcas (E015).

   Los dos se prueban volviendo a puntuar corridas guardadas.
3. Palanca 6: implementarla, medir el prefijo y cribarla con decision2 s0 y escenas sin tocar.

## Primer paso del goal

Medir las palancas 1-4 juntas con el modelo real. Ninguna toca el prefijo ni decision2.
- e2e s0-2 de `pc-ayudas` frente al producto de partida, en la misma máquina y el mismo día, con el frente comprobado
  por semilla, más la puerta E011/E017/E024 y falsedades s0.
- Si el conjunto gana, se separan para ver qué aporta cada una.
