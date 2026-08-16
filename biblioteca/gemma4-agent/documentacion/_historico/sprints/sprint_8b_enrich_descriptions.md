# PROMPT — Sprint 8b (enriquecer las 65 tool descriptions)

> Continúa el mismo chat de Claude Code (Sprints 0-8a).
> **Sprint 8b:** reescribir las 65 tool descriptions al formato
> `purpose + example_queries` (ES + EN como anchor multi-idioma).
> Asume que 8a quedó mergeado y `router_v2.py` está vivo detrás del
> flag `GEMMA4_ROUTER_V2=1`.
>
> Plan completo:
> - **8a:** infra (e5-small ONNX + bm25 + RRF + gate + cache). DONE.
> - **8b:** enriquecer las 65 descriptions con example_queries ES+EN. (este)
> - **8c:** blind test + tuning + self-improving loop. ~1 noche.

---

## Origen del diseño

Investigación de Claude Research (mayo 2026), sección 2:
> "Sin queries de ejemplo en idiomas concretos, el bi-encoder
> multilingue se apoya 100% en alineación interlingual del modelo.
> En la práctica falla con frases coloquiales/regionales (`dale play`,
> `armame algo para mostrar`, `podés apagarme la wifi`). Solución:
> Tool2Vec-style enrichment — descripciones cortas + 3-6 example
> queries en idiomas ancla. El resto de idiomas viaja en el espacio
> de embeddings sin queries explícitas porque el modelo es
> multilingue."

Decisión del usuario (chat previo):
- ES + EN como idiomas ancla.
- El modelo (multilingual-e5-small) cubre PT/FR/IT/DE/etc sin
  example_queries explícitos en esos idiomas.

## Estado del repo al arrancar

- HEAD: el commit del cierre de 8a (sprint8a.4 o 8a.5).
- Working tree limpio.
- 65 compound tools intactas.
- `gemma4_agent/router_v2.py` existe pero apagado por default.
- `gemma4_agent/semantic_router.py` viejo sigue siendo el path de
  fallback del router viejo. NO tocarlo hoy.
- `gemma4_agent/tool_descriptions.yaml` NO existe todavía (vos lo
  vas a crear).

---

## Prompt completo (copy/paste al chat existente)

```
Continuamos. Estado: rama PortandoLoMejor, HEAD <commit-cierre-8a>,
working tree limpio, 65 compound tools, router_v2.py vivo (flag off).

# OBJETIVO DE SPRINT 8b

Crear `gemma4_agent/tool_descriptions.yaml` con las 65 tools en formato
enriquecido (purpose + example_queries en ES+EN), y modificar
`router_v2.py` para que cargue de ahí en vez del dict viejo
`TOOL_DESCRIPTIONS` de `semantic_router.py`.

Resultado al cierre: 65 entries YAML, router_v2 indexa desde YAML,
todos los tests pasan, blind smoke test del usuario (Sprint 8c) listo
para correr.

# REGLAS GENERALES

1. PortandoLoMejor. Commits chicos, prefijo "sprint8b.X:".
2. NO toques planner.py ni semantic_router.py viejo (sigue usándose
   en path regex-first del router default).
3. NO modifiques las 65 compound tools (los schemas en
   `gemma4_agent/tools.py` son la fuente de verdad de capabilities).
4. Si encontrás que una tool no tiene entry en TOOL_DESCRIPTIONS
   viejo (62 de 65 lo tienen), generala desde cero leyendo su
   schema en COMPOUND_TOOL_SCHEMAS. Anotá cuáles agregaste.
5. NUNCA git add -A. Archivos específicos.
6. Verificación post-commit:
   - YAML parsea OK (`python -c "import yaml; yaml.safe_load(open('gemma4_agent/tool_descriptions.yaml'))"`).
   - `len(yaml.safe_load(...)) == 65`.
   - router_v2 carga el YAML sin errores en `_build_index`.
   - `python -m pytest gemma4_agent/test_router_v2.py -v` verde.
   - `python -m pytest gemma4_agent/ -q` mantiene los 743 tests verde
     (1 pre-existing failure permitida, documentar si aparece otra).

# FORMATO DE CADA ENTRY

```yaml
- name: office
  purpose: |
    Create and edit office documents — Word (.docx), PowerPoint
    (.pptx), Excel (.xlsx), PDF. Includes opening, editing,
    saving, exporting, and converting between formats.
  domain: documents
  example_queries:
    es:
      - "hazme un power point sobre los planetas"
      - "armame una presentacion para mañana"
      - "abri el word que tengo en escritorio"
      - "creame un excel con los gastos del mes"
      - "convertir este docx a pdf"
      - "hoja de calculo para llevar cuentas"
    en:
      - "make a powerpoint about the solar system"
      - "create a presentation for tomorrow"
      - "open the word doc on my desktop"
      - "build a spreadsheet for monthly expenses"
      - "convert this docx to pdf"
      - "draft a report in word"
```

# CRITERIOS PARA CADA CAMPO

## `name`
Exactamente el nombre de la compound tool en COMPOUND_TOOL_SCHEMAS.
Si dudás, listá las 65 primero con:
```python
from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS
print([t["function"]["name"] for t in COMPOUND_TOOL_SCHEMAS])
```

## `purpose` (2-4 líneas, EN)
- Inglés, técnico, sin marketing.
- Capta el **qué hace** y **cuándo se usa**, NO el API exacto
  (eso lo ve el LLM en el schema).
- Si la tool tiene 10+ actions, mencioná las 3-4 más usadas.
- Evitá repetir keywords de example_queries — son fuentes
  complementarias para BM25.

## `domain` (1 palabra, EN)
Categoría amplia. Usá una de estas (o agregá si justificás):
`documents`, `audio`, `browser`, `media`, `messaging`, `gui`,
`system`, `filesystem`, `vision`, `web`, `smart_home`,
`gaming`, `dev`, `automation`.

## `example_queries.es` (4-6 frases)
- Frases reales que diría un hispanohablante (rioplatense
  preferido — el usuario habla así). Mezcla coloquial + neutro.
- Cubrí variantes ortográficas comunes:
  - con/sin acento (`presentación` / `presentacion`).
  - con/sin espacio (`power point` / `powerpoint`).
  - voseo/tuteo (`armá` / `arma`, `podés` / `puedes`).
  - imperativo coloquial (`dale play`, `tirame`, `armame`).
- Que NO sean traducciones literales de las inglesas — perdés
  cobertura léxica.
- 1-2 frases regionales fuertes ("hace", "armame", "decime")
  para que BM25 las capture.

## `example_queries.en` (4-6 frases)
- Inglés natural, mix US/UK.
- Imperativo + interrogativo + declarativo:
  - "make me a presentation"
  - "can you open the word doc"
  - "I need a spreadsheet for X"
- Cubrí el caso "user describes intent without naming the tool":
  - "I need slides for the team meeting tomorrow"
  - "draft something I can show the team"

## QUÉ NO HACER en example_queries

- NO copies frases de los TOOL_RULES (eso es el system prompt
  del LLM, no del retriever).
- NO uses comodines tipo `<topic>` o `[X]` — frases enteras.
- NO repitas la misma plantilla con 4 nombres distintos
  ("make a pptx", "make a docx", "make an xlsx"). El retriever
  ve eso como 1 query.
- NO uses jerga muy nichada de un solo usuario.

# WORKFLOW

## 8b.1 — Inventario y formato base

1. Listá las 65 tools y agrupalas por domain mental:
   - documents (office, pdf, ...)
   - audio (audio, speech, music)
   - browser, web, vision
   - messaging (whatsapp, telegram, ...)
   - media (steam, youtube, spotify, ...)
   - system (smart_home, gui, system, filesystem, ...)
   - dev
   - automation

2. Creá `gemma4_agent/tool_descriptions.yaml` vacío con un
   header de explicación (comment) y un primer entry de
   ejemplo (`office`, ya redactado arriba) para validar el
   formato.

3. Validá con `yaml.safe_load`. Commit:
   "sprint8b.1: bootstrap tool_descriptions.yaml with format spec"

## 8b.2 — Redactar las 65 entries

Estrategia:
- Grupos de 5-8 tools por commit, agrupadas por domain.
- Después de cada commit corré
  `python -c "import yaml; d=yaml.safe_load(open('gemma4_agent/tool_descriptions.yaml')); print(len(d), 'entries OK')"`.

Orden sugerido (alto valor primero):
1. Office + documents (office, pdf, filesystem).
2. Browser + web + vision.
3. Audio + media (audio, music, spotify, youtube, steam).
4. Messaging (whatsapp, telegram).
5. System + GUI + smart_home.
6. Resto (dev, automation, calendar, etc).

Para cada tool, leé su entry en COMPOUND_TOOL_SCHEMAS para
entender qué hace, y leé también si tiene entry en
`TOOL_RULES` (en `gemma4_agent/tool_rules.py` o `.md`) para
captar el cuándo-usar.

Commit por grupo: "sprint8b.2.<n>: enrich <domain> tools
(N entries)".

## 8b.3 — Cablear `router_v2.py` para leer del YAML

Modificá `_build_index` en router_v2.py para leer de YAML
en vez del dict de `semantic_router.TOOL_DESCRIPTIONS`:

```python
import yaml
from pathlib import Path

TOOL_DESCRIPTIONS_YAML = Path(__file__).parent / "tool_descriptions.yaml"

def _load_tool_descriptions() -> list[dict]:
    if not TOOL_DESCRIPTIONS_YAML.exists():
        return []
    with TOOL_DESCRIPTIONS_YAML.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or []

def _build_index(self) -> None:
    descs = _load_tool_descriptions()
    if not descs:
        log.warning("router_v2: no tool_descriptions.yaml — disabled")
        self._disabled = True
        return

    # Para cada tool armamos un "document" para BM25 y un texto
    # para el embedding. El document mezcla purpose + queries en
    # ambos idiomas para que BM25 tenga material léxico.
    self._tool_names = []
    self._bm25_docs = []
    self._embed_texts = []

    for d in descs:
        name = d["name"]
        purpose = d.get("purpose", "").strip()
        qs_es = d.get("example_queries", {}).get("es", [])
        qs_en = d.get("example_queries", {}).get("en", [])

        # BM25 doc: purpose + todas las queries concatenadas.
        bm25_doc = " ".join([purpose, *qs_es, *qs_en]).lower()

        # Embed text: purpose + queries unidas pero separadas con
        # un newline para que el modelo no las funda. e5 prefiere
        # un prefix "passage:" para docs (vs "query:" para queries).
        embed_text = "passage: " + purpose + "\n" + " | ".join(qs_es + qs_en)

        self._tool_names.append(name)
        self._bm25_docs.append(bm25_doc.split())
        self._embed_texts.append(embed_text)

    # Build BM25 y dense embeddings.
    from rank_bm25 import BM25Okapi
    self._bm25 = BM25Okapi(self._bm25_docs)
    self._dense = self._encode_batch(self._embed_texts)

    # Centroid de tools para el smalltalk gate.
    import numpy as np
    self._tools_centroid = np.mean(self._dense, axis=0)
    self._tools_centroid /= np.linalg.norm(self._tools_centroid) + 1e-12
```

También: cuando `route(query)` encodea la query, prefijala con
`"query: "` (es el protocolo de e5).

Commit: "sprint8b.3: wire router_v2 to read from tool_descriptions.yaml"

## 8b.4 — Tests de cobertura

Agregá a `test_router_v2.py`:

```python
def test_yaml_has_65_entries():
    import yaml
    from pathlib import Path
    p = Path(__file__).parent / "tool_descriptions.yaml"
    assert p.exists()
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 65, f"Expected 65 entries, got {len(data)}"

def test_yaml_entries_have_required_fields():
    import yaml
    from pathlib import Path
    p = Path(__file__).parent / "tool_descriptions.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    for entry in data:
        assert "name" in entry
        assert "purpose" in entry and len(entry["purpose"]) >= 30
        assert "example_queries" in entry
        assert "es" in entry["example_queries"]
        assert "en" in entry["example_queries"]
        assert len(entry["example_queries"]["es"]) >= 3
        assert len(entry["example_queries"]["en"]) >= 3

def test_yaml_names_match_compound_tools():
    import yaml
    from pathlib import Path
    from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS
    p = Path(__file__).parent / "tool_descriptions.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    yaml_names = {e["name"] for e in data}
    schema_names = {t["function"]["name"] for t in COMPOUND_TOOL_SCHEMAS}
    assert yaml_names == schema_names, (
        f"YAML/schema mismatch.\n"
        f"In YAML not in schemas: {yaml_names - schema_names}\n"
        f"In schemas not in YAML: {schema_names - yaml_names}"
    )

@pytest.mark.skipif(not _model_available(), reason="e5 ONNX not downloaded")
def test_power_point_routes_to_office():
    from gemma4_agent.router_v2 import RouterV2
    r = RouterV2.get()
    result = r.route("hazme un power point sobre los planetas")
    assert "office" in result.subset[:5], (
        f"office not in top-5: {result.subset[:5]}"
    )

@pytest.mark.skipif(not _model_available(), reason="e5 ONNX not downloaded")
def test_coloquial_play_routes_to_music_or_media():
    from gemma4_agent.router_v2 import RouterV2
    r = RouterV2.get()
    result = r.route("dale play a algo de los redonditos")
    subset_top3 = result.subset[:3]
    assert any(t in subset_top3 for t in ("music", "spotify", "media", "audio")), (
        f"music-ish not in top-3: {subset_top3}"
    )
```

Commit: "sprint8b.4: test_router_v2 covers yaml schema + intent routing"

## 8b.5 — Log de cierre

Creá `docs/architecture/sprint_prompts/_sprint8b_log.md` con:
- Cantidad de entries totales.
- Cuáles tools NO tenían entry en TOOL_DESCRIPTIONS viejo y vos
  generaste de cero.
- Decisiones de domain controvertidas (ej: `youtube` ¿es media o
  browser?). Justificá.
- Stats: avg purpose length, avg example_queries por idioma.
- Sample de 5 entries random pegadas como evidencia.
- Lista de commits del sprint.

Commit: "sprint8b.5: log of 8b completion"

# REPORTE FINAL (al usuario)

Al terminar, devolveme:
1. Cantidad final de entries (debe ser 65).
2. Si alguna tool quedó con purpose <30 chars o queries <3 por
   idioma — eso es un bug, listalo.
3. Top-3 dudas de redacción que tuviste (ej: "spotify_local vs
   spotify_web") para que vos las arbitres después.
4. Output de `pytest gemma4_agent/test_router_v2.py -v`.
5. Output de `pytest gemma4_agent/ -q` (los 743 tests + nuevos).

# CRITERIO DE ÉXITO

- 65 entries YAML, todas con campos requeridos.
- router_v2 indexa OK desde YAML.
- test_router_v2 verde (los 2 nuevos que requieren modelo se
  skipean si no está descargado — eso está bien).
- Resto de la suite verde (743+).
- 0 cambios en planner.py, semantic_router.py, agent.py.
- Working tree limpio post-cierre.

# NO HACER (anti-scope)

- NO migrar el router default a v2 (eso es 8c).
- NO borrar TOOL_DESCRIPTIONS viejo de semantic_router.py (queda
  como fallback hasta 8c).
- NO crear example_queries en idiomas además de ES/EN. Confiamos
  en el multilingual de e5.
- NO inventar tools nuevas, NO consolidar tools existentes.
- NO escribir purposes de >200 chars (token budget del prompt
  ya está justo).
```

---

## Lo que hace este sprint

Migra de descripciones tipo `"create PowerPoint, Word, Excel
documents"` (1 línea, EN-only, sin variantes léxicas) a entries
tipo Tool2Vec con purpose + 4-6 queries ES + 4-6 queries EN.

Eso da material léxico al BM25 (variantes ortográficas, voseo,
imperativos coloquiales) y material semántico al e5
(frases-intención completas, no keywords).

## Lo que NO hace

- No cambia el router default. El flag `GEMMA4_ROUTER_V2=1`
  sigue siendo opt-in.
- No corre blind test (eso es 8c).
- No toca planner.py.

## Estimación de esfuerzo

- 8b.1: 20 min (formato + 1 ejemplo).
- 8b.2: 4-6 horas (65 tools × ~5 min cada una con investigación
  del schema). El agente lo hace en una corrida nocturna.
- 8b.3: 30 min (cableo + prefix e5).
- 8b.4: 30 min (tests).
- 8b.5: 15 min (log).

Total: ~6-8h de agente trabajando solo.
