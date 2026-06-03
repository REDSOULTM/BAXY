# HOTFIX 2026-05-17 (E.5) — Smalltalk gate calibration + media queries enrichment

> Continuá el chat post hotfix E (8444329 / 1bf8ab8 / a3a970a /
> d6f7512 / 553e493). Sprint chico de calibración. Surgió DEL
> sprint E mismo: el operador detectó que `pone benson boone`
> aislado dispara el smalltalk gate (delta=0.028 > θ=0.025) y
> devuelve `[]`. El test `test_play_music_es` solo pasa por
> cache-hit accidental con `test_play_music_en` que corre antes
> alfabéticamente. En frío, router_v2 falla en queries cortas
> tipo "pone X". Esto bloquea F porque es exactamente la familia
> de bugs que F asume resueltos.
>
> Fuente: `project_router_v2_calibration #7` (memoria del operador).

---

## Contexto

El bug:

```
>>> RouterV2.reset()
>>> route_v2('pone benson boone')
([], {'source': 'smalltalk', 'smalltalk_delta': 0.028, ...})
```

Delta=0.028, threshold=0.025 → smalltalk gate fires → subset
vacío. Sin embargo `pone benson boone` es claramente una request
de música, NO smalltalk.

Por qué el test del sprint E pasaba:
1. `test_play_music_en` corre primero (alfabético) → `route_v2('play benson boone')` → media en subset → cachea el embedding.
2. `test_play_music_es` corre después → `route_v2('pone benson boone')`. e5-small embebe ambas queries casi al mismo punto (cosine > 0.88 → CACHE_THETA), entonces hit del cache → devuelve el subset cacheado del EN sin pasar por el smalltalk gate.
3. En frío (operator real, primera vez que dice "pone X"), no hay cache → smalltalk gate fires → fallo.

Causas raíces (no son una sola):
- **Calibración**: el delta 0.025 fue medido en Sprint 8a contra un probe set chico. Queries cortas en imperativo voseo + nombre propio tienen delta cercano al threshold porque los nombres propios no agregan mucha señal "tools" al embedding (el modelo no conoce "benson boone").
- **Material BM25 pobre para `media`**: el `tool_descriptions.yaml` actual tiene queries de música pero predominan formas tipo "reproducí X", "play X", "música de X". Faltan formas rioplatenses cortas tipo "pone X" sin objeto musical explícito.

---

## OBJETIVO

Dos commits chicos, atacar el problema por los DOS lados:

1. `fix(routing)`: subir `SMALLTALK_DELTA_THETA` de 0.025 a 0.030.
   Más estricto: el delta tiene que ser MÁS claramente smalltalk
   para que la gate fire. Calibrado con el probe del operador
   (0.028 ahora pasa = correcto).
2. `fix(routing)`: enriquecer `media.example_queries.es` con 5-6
   imperativos cortos rioplatenses tipo "pone X". Aumenta señal
   BM25 + dense para `media` cuando aparece "pone <nombre>".

Juntos: la gate es más estricta + media tiene más señal → "pone X"
en frío llega a `media` top-K.

---

## REGLAS GENERALES

1. PortandoLoMejor. Commits chicos, prefijos `fix(routing):`.
2. Cambiar SOLO el threshold y las queries de `media`. NO toques
   otras tools en el YAML.
3. NO toques planner.py, router_v2.py beyond el threshold value,
   las 65 compound tools, modes.py.
4. NO instales libs nuevas.
5. NO `git add -A`.
6. Cero matching de idioma del user — el delta sigue siendo
   estructural (cosine similarity), no keyword.
7. Verificación post-commit:
   - `python -m pytest gemma4_agent/ -q` debe pasar.
   - Suite del sprint E debe seguir verde (30 tests router_v2).
   - El smoke en frío de "pone X" debe pasar.

---

## FIX E5.1 — Tighten smalltalk delta threshold

### E5.1.1 — Editar `gemma4_agent/router_v2.py`

Localizar:
```python
SMALLTALK_DELTA_THETA = 0.025  # smalltalk - tools >= this → gate fires
```

Cambiar a:
```python
# Smalltalk delta threshold. Calibrated 2026-05-17 (hotfix E.5)
# after the audit detected that 'pone benson boone' had
# delta=0.028 — just above the old 0.025 threshold — firing
# the gate on a clear music request. Raising to 0.030 means the
# gate only fires when the smalltalk signal is more clearly
# dominant. The probe results that anchor this value:
#   "hola, como estas?"     delta=0.033   (still fires ✓)
#   "thanks"                delta=0.060   (still fires ✓)
#   "gracias"               delta=0.080   (still fires ✓)
#   "pone benson boone"     delta=0.028   (no longer fires ✓)
#   "abrime el Steam"       delta=0.014   (never fired ✓)
SMALLTALK_DELTA_THETA = 0.030
```

### E5.1.2 — Editar test del banding

`gemma4_agent/test_router_v2.py::ConstantsSanityTest::test_smalltalk_delta_theta_band`:
verificar que el band `[0.01, 0.10]` sigue siendo correcto. 0.030
está dentro → el test ya pasa sin cambios.

Pero hay que actualizar el comment del threshold para que el
diff sea visible.

### E5.1.3 — Smoke test cold del repro

Crear `gemma4_agent/test_smalltalk_gate_calibration.py`:

```python
"""Smalltalk gate calibration probes (hotfix E.5 2026-05-17).

These tests run the router in a FRESH state (RouterV2.reset())
before each probe so cache hits from prior tests can't mask
calibration regressions. The bug fixed here: hotfix E's
test_play_music_es passed only because test_play_music_en
(alphabetically earlier) cached the embedding; a cold call to
'pone benson boone' fired the smalltalk gate.

We test:
  - True smalltalk still fires the gate (hola, gracias, thanks).
  - Short imperative music commands DO NOT fire the gate cold.
  - Steam-ish commands DO NOT fire the gate.

All probes are reset-isolated. Cross-lingual is checked separately
to verify the multilingual encoder still handles non-ES/EN cleanly.
"""
from __future__ import annotations

import unittest

from gemma4_agent.router_v2 import MODEL_PATH, RouterV2, route_v2


@unittest.skipUnless(MODEL_PATH.exists(), "e5-small ONNX model not installed")
class SmalltalkGateColdTest(unittest.TestCase):
    def _route_cold(self, query: str) -> tuple[list[str], dict]:
        """Force a fresh router so no cache hit pollutes the result."""
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        return router.route(query)

    # --- Smalltalk should still fire ---
    def test_hola_fires_smalltalk(self) -> None:
        _, tel = self._route_cold("hola")
        self.assertEqual(tel.get("source"), "smalltalk")

    def test_gracias_fires_smalltalk(self) -> None:
        _, tel = self._route_cold("gracias")
        self.assertEqual(tel.get("source"), "smalltalk")

    def test_thanks_fires_smalltalk(self) -> None:
        _, tel = self._route_cold("thanks")
        self.assertEqual(tel.get("source"), "smalltalk")

    def test_gracias_por_todo_fires_smalltalk(self) -> None:
        # Was a regex false-positive in v1; v2 should classify as
        # smalltalk (delta well above 0.030).
        _, tel = self._route_cold("gracias por todo")
        self.assertEqual(tel.get("source"), "smalltalk")

    # --- Music commands must NOT fire smalltalk (the bug) ---
    def test_pone_benson_boone_does_NOT_fire_smalltalk_cold(self) -> None:
        # The bug: delta=0.028 fired the gate at theta=0.025. With
        # the new theta=0.030, this should land on hybrid retrieval.
        subset, tel = self._route_cold("pone benson boone")
        self.assertNotEqual(
            tel.get("source"), "smalltalk",
            f"smalltalk gate fired with delta={tel.get('smalltalk_delta')}; "
            f"subset={subset}",
        )

    def test_pone_los_redonditos_does_NOT_fire_smalltalk_cold(self) -> None:
        subset, tel = self._route_cold("pone los redonditos")
        self.assertNotEqual(tel.get("source"), "smalltalk")

    def test_play_queen_does_NOT_fire_smalltalk_cold(self) -> None:
        subset, tel = self._route_cold("play queen")
        self.assertNotEqual(tel.get("source"), "smalltalk")

    # --- Action commands still work ---
    def test_abrime_steam_does_NOT_fire_smalltalk_cold(self) -> None:
        subset, tel = self._route_cold("abrime el Steam")
        self.assertNotEqual(tel.get("source"), "smalltalk")
        self.assertIn("steam", subset)


if __name__ == "__main__":
    unittest.main()
```

### E5.1.4 — Commit

`fix(routing): tighten smalltalk delta threshold from 0.025 to 0.030`

Mensaje:

```
fix(routing): tighten smalltalk delta threshold 0.025 -> 0.030

Audit during hotfix E execution: 'pone benson boone' (cold cache)
produced delta=0.028, just above the old threshold of 0.025, so
the smalltalk gate fired and returned []. The hotfix E test
suite passed only because alphabetical test ordering put
test_play_music_en first; its cached embedding masked the cold-
call regression for test_play_music_es.

Calibration probe (re-measured this commit):
  smalltalk side (gate SHOULD fire):
    'hola, como estas?'   delta=0.033 ✓
    'thanks'              delta=0.060 ✓
    'gracias'             delta=0.080 ✓
  tools side (gate should NOT fire):
    'pone benson boone'   delta=0.028 (was firing wrongly, now OK)
    'abrime el Steam'     delta=0.014 ✓ (always OK)
    'play queen'          delta=~0.015 ✓

Tightening the threshold from 0.025 to 0.030 leaves a 3-point
margin for the smalltalk side and excludes the music-request
delta range that was misfiring. The 0.01-0.10 band sanity test
in ConstantsSanityTest still passes.

New test file test_smalltalk_gate_calibration.py runs each probe
through RouterV2.reset() to defeat cache-hit pollution between
tests. Pins the contract for cold calibration regressions.

Language-agnostic: the threshold is a cosine-delta floor, not a
keyword. Works across any language the encoder handles.
```

---

## FIX E5.2 — Enrich `media.example_queries.es` with short imperatives

### E5.2.1 — Inspeccionar el entry actual

```bash
python -c "
import yaml
with open('gemma4_agent/tool_descriptions.yaml', encoding='utf-8') as f:
    d = yaml.safe_load(f)
media = next(e for e in d if e['name'] == 'media')
print('purpose:', media['purpose'][:200])
print('es queries:')
for q in media['example_queries']['es']:
    print(f'  - {q}')
"
```

### E5.2.2 — Editar `gemma4_agent/tool_descriptions.yaml`

Localizar el entry `media:` (es el del Sprint 8b.2.3). En la
sección `example_queries.es`, agregar 5-6 imperativos cortos.
NO removas queries existentes; solo agregás.

Ejemplo de adiciones (adaptá a las queries reales que ya tiene):

```yaml
- name: media
  purpose: |
    ...  # unchanged
  domain: media
  example_queries:
    es:
      - "pone Daredevil en netflix"            # existing
      - "reproduce algo de los redonditos en spotify"  # existing
      - "dale play a stranger things en netflix"       # existing
      - ...                                    # other existing entries
      # Hotfix E.5 2026-05-17 — short rioplatense imperatives.
      # The cold-route bug had 'pone benson boone' firing the
      # smalltalk gate because the dense embedding lacked anchor
      # phrases of the form "pone <proper noun>" without a music
      # domain word. These give the encoder + BM25 explicit
      # material for that shape.
      - "pone benson boone"
      - "pone queen"
      - "poneme algo tranqui"
      - "pon una canción"
      - "play queen"
      - "ponme algo de los redonditos"
    en:
      - ...  # existing entries unchanged
```

NO modifiqués el `purpose`. NO toqués las queries `en` salvo que
falten formas equivalentes obvias.

### E5.2.3 — Verificación de parse

```bash
python -c "
import yaml
from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS
with open('gemma4_agent/tool_descriptions.yaml', encoding='utf-8') as f:
    d = yaml.safe_load(f)
assert len(d) == 65, f'expected 65, got {len(d)}'
yaml_names = {e['name'] for e in d}
tool_names = {s['function']['name'] for s in COMPOUND_TOOL_SCHEMAS}
assert yaml_names == tool_names, 'name mismatch'
media = next(e for e in d if e['name'] == 'media')
assert any('pone' in q for q in media['example_queries']['es'])
print('ok')
"
```

### E5.2.4 — Smoke test cold para validar fix conjunto

Agregar a `gemma4_agent/test_smalltalk_gate_calibration.py`:

```python
def test_pone_benson_boone_routes_to_media_cold(self) -> None:
    # The end-to-end smoke: cold cache, the query should land
    # in hybrid retrieval AND surface 'media' in the subset.
    subset, tel = self._route_cold("pone benson boone")
    self.assertEqual(tel.get("source"), "hybrid",
                     f"got source={tel.get('source')}, expected hybrid")
    self.assertIn("media", subset,
                  f"media missing from cold subset: {subset}")

def test_pone_redonditos_routes_to_media_cold(self) -> None:
    subset, tel = self._route_cold("pone los redonditos")
    self.assertEqual(tel.get("source"), "hybrid")
    self.assertIn("media", subset)
```

### E5.2.5 — Rebuild del index (verificación manual)

Después del cambio en YAML, router_v2 reconstruye el index en
cold-start. `RouterV2.reset()` + `_ensure_loaded()` fuerza el
rebuild. Tu test smoke debería pasar.

Si el rebuild no aparece automático (cache de embeddings en
disco), buscar:
```bash
grep -n "embeddings.*cache\|index.*cache\|_load_failed" gemma4_agent/router_v2.py
```

Si hay cache persistente, agregar invalidation por hash del YAML.
(Probablemente no hay — el index actual se construye in-memory en
cold-load. Verificar y dejar TODO si surge.)

### E5.2.6 — Commit

`fix(routing): enrich media.example_queries.es with short rioplatense imperatives`

Mensaje:

```
fix(routing): enrich media.example_queries.es with short imperatives

Companion to the smalltalk threshold fix. Audit during hotfix E:
'pone benson boone' (cold cache) fired the smalltalk gate. The
threshold change (0.025 -> 0.030) keeps it out of smalltalk, but
the query still has to LAND on 'media' once it reaches hybrid
retrieval. With the previous example_queries.es entries
predominantly using phrases like 'reproducí X en Y' or
'dale play a X', the dense+BM25 signal for 'pone <proper noun>'
without an explicit music domain word was thin.

Fix: 6 new short imperatives in media.example_queries.es:
  - 'pone benson boone'
  - 'pone queen'
  - 'poneme algo tranqui'
  - 'pon una canción'
  - 'play queen'  (EN parity)
  - 'ponme algo de los redonditos'

These give the encoder explicit anchor phrases of the
'pone <proper noun>' shape. BM25 also benefits — the lemma 'pone'
appears multiple times in the doc.

NO other entries modified. NO purpose changes. NO non-ES additions.
NO regex anywhere.

Tests cover the end-to-end cold-route smoke: with this YAML +
the new threshold, 'pone benson boone' and 'pone los redonditos'
land on 'media' from a fresh RouterV2.reset().

(If a future sprint observes the same bug shape for other
proper-noun queries — actors, video titles, brands — extend the
SAME pattern: add more 'pone X' / 'play X' / 'mira X' anchors
to media. Do NOT widen the smalltalk delta further; 0.030 is the
calibrated value.)
```

---

## REPORTE FINAL

Devolveme:
1. Hashes de los 2 commits.
2. Output de los tests específicos:
   ```bash
   python -m pytest gemma4_agent/test_smalltalk_gate_calibration.py gemma4_agent/test_router_v2.py gemma4_agent/test_routing_audit_repros.py -v
   ```
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`.
4. Repro post-fix EN FRÍO:
   ```bash
   python -c "
   from gemma4_agent.router_v2 import RouterV2, route_v2
   # Cold call each — no cache pollution.
   for q in ['pone benson boone', 'pone los redonditos',
             'pone queen', 'play queen', 'poneme algo tranqui',
             'instala vlc', 'apaga la pc',
             'hola', 'gracias', 'gracias por todo']:
       RouterV2.reset()
       subset, tel = route_v2(q)
       print(f'{q!r:35s} -> source={tel.get(\"source\"):9s} top3={subset[:3]}')
   "
   ```

## CRITERIO DE ÉXITO

- 2 commits aterrizados.
- ≥10 tests nuevos verdes (`test_smalltalk_gate_calibration.py`).
- Suite completa verde (modulo Sprint 3a pre-existing failure).
- Cada query "pone X" en el repro frío debe ir a `source=hybrid`
  con `media` en top-3.
- Cada query smalltalk (`hola`, `gracias`, `gracias por todo`)
  debe seguir cayendo en `source=smalltalk` con subset vacío.
- Los 30 tests del sprint E siguen verdes después del cambio.

## NO HACER (anti-scope)

- NO bajes el threshold más allá de 0.030 — la calibración del
  probe lo banda en [0.030, 0.040]. Más alto deja queries
  smalltalk legítimas pasando a hybrid; más bajo reintroduce
  el bug.
- NO agregues queries en otros idiomas (FR/IT/DE) a `media.es`.
  Si ese caso aparece en uso real, abrir issue separado.
- NO toques otras tools en el YAML. Si otras tools tienen el
  mismo bug shape (proper-noun query firing smalltalk), eso es
  trabajo de un sprint futuro con probe explícito por tool.
- NO inventes una nueva métrica delta-by-length o similar. Es
  tentador pero requiere recalibrar todo. El threshold simple
  resuelve el caso reportado.
- NO modifiques el `purpose` de `media`. El cambio es solo en
  `example_queries.es`.
- Si el rebuild del index falla porque hay cache persistente de
  embeddings, NO inventes una solución improvisada — emit TODO,
  marca el sprint como parcialmente-completado, y reportá. Ese
  caso requiere su propio sprint.
