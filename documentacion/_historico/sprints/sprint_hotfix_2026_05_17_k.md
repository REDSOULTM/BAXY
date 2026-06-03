# HOTFIX 2026-05-17 (K) — Bilingual purpose (ES + EN) in tool_descriptions.yaml

> Continuá el chat post hotfix J.1. Diagnóstico del operador
> 2026-05-17 surfaceó la causa raíz #1 del bug "cierra steam"
> que J.1 no terminó de resolver: los `purpose` del YAML están
> en inglés, lo que da a BM25 cobertura léxica asimétrica entre
> queries EN y ES. `close` matchea 7 tool descriptions; `cierra`
> matchea 4. Resultado: queries ES con verbos imperativos
> comunes ("cierra", "abre", "borra") producen disagree entre
> retrievers más frecuentemente que sus equivalentes EN.
>
> Este sprint enriquece cada `purpose` con una línea ES paralela.
> Pure docs change. Sin cambios al router code.

---

## Contexto: el dato del diagnóstico

Del diagnostic post-J.1 (2026-05-17 ~22:00):

```
'cierra steam'   bm25_nonzero=4   agree=False
'close steam'    bm25_nonzero=7   agree=True

'cierra whatsapp' bm25_nonzero=1  agree=True (solo whatsapp matchea)
'close whatsapp'  bm25_nonzero=5  agree=False (paradójicamente)
```

`close` matchea 7 descriptions porque las `purpose` del YAML están
escritas en inglés (Sprint 8b: "purpose: technical summary in
English"). El verbo "close" aparece literalmente en descriptions
de tools como `app`, `window`, `browser`, `session`, etc. — todos
documentan acciones de "close X".

`cierra` solo matchea cuando aparece en `example_queries.es`. Eso
es 4 tools porque no todas las tools tienen "cierra" en sus
example queries (algunos usan "cerrá", "cerrame", "apaga", etc.).

**Resultado estructural**: el ranking BM25 para queries ES con
verbos imperativos comunes tiene menos señal → más ruidoso → más
disagree con dense → más subset bloat (cap=16 LOW band).

El operador del agente habla **español** (voseo argentino). Las
queries en producción son mayoritariamente ES. La asimetría afecta
**la mayoría del traffic real**, no casos edge.

---

## Por qué este sprint y no parche al router

Después de J.1, considere las 3 opciones:

| Opción | Pros | Contras |
|---|---|---|
| Parar y dejar que telemetry junte data | No risk, simple | Subset bloat persiste mientras tanto |
| Parche al router (J.2) | Rápido | Parche al síntoma; el YAML asimétrico afecta otras métricas también |
| **Enriquecer YAML (K)** | **Resuelve causa raíz; afecta TODAS las queries ES, no solo el caso reportado; pure docs change; router code intacto** | **30 min de trabajo manual sobre 65 tools** |

K gana por **resolver causa raíz**. Una vez `purpose` tiene
línea ES, BM25 matchea verbos imperativos ES con la misma riqueza
que EN, y la métrica de disagree empieza a reflejar ambigüedad
real, no asimetría léxica.

---

## OBJETIVO

Un commit chico. **Agregar una línea ES al `purpose` de cada tool
en `tool_descriptions.yaml`** (65 entries).

Format:
```yaml
- name: window
  purpose: |
    Close, focus, minimize, maximize, list, snap windows on Windows.
    Cerrar, enfocar, minimizar, maximizar, listar, encuadrar ventanas.
```

NO cambia:
- `name` (sigue siendo el tool name canónico).
- `example_queries` (ya son ES + EN; no se tocan).
- El esquema YAML general (sigue siendo dict con `name`, `purpose`,
  `domain`, `example_queries`).
- router_v2 code.
- Las 65 compound tools.

SÍ cambia:
- Cada `purpose` ahora tiene una segunda oración en ES con verbos
  paralelos a los EN.

---

## REGLAS GENERALES

1. PortandoLoMejor. Un commit chico, prefijo `docs(yaml):`.
2. **NO toques** router_v2, planner, modes, las 65 tools,
   tool_schemas, voice, las rules en `prompts/tool_rules/`.
3. **NO toques** `example_queries.es` ni `example_queries.en` —
   esos ya están bien.
4. **NO inventés acciones nuevas en el ES**. La línea ES debe ser
   una traducción literal de los verbos/conceptos clave del EN
   existente, no agregar capabilities.
5. **Mantener purpose ≤ 280 chars total** (era ≤ 200 antes; subo
   el budget porque ahora son 2 líneas). El prompt completo sigue
   siendo manejable: 65 tools × 280 = ~18KB, vs anteriores ~13KB
   — 5KB extra está OK.
6. NO instales libs nuevas.
7. NO `git add -A`.

---

## FIX K1 — Enriquecer 65 purpose con línea ES

### K1.1 — Patrón de transformación

Por cada entry, transformar:

```yaml
purpose: |
  <Single-line EN summary, technical>.
```

A:

```yaml
purpose: |
  <Single-line EN summary, technical>.
  <Single-line ES summary, mirror of the EN verbs/concepts>.
```

**Reglas para la línea ES**:

- Verbos paralelos: si EN dice `close, focus, minimize, list`, ES
  dice `cerrar, enfocar, minimizar, listar`. Forma infinitivo
  (no imperativo) — más neutro para BM25 (matchea tanto "cierro"
  como "cerrar" como "cerrame" cuando el e5 hace su parte).
- Sustantivos paralelos: si EN dice `windows`, ES dice `ventanas`.
- Si la tool tiene un nombre técnico que se usa igual en ES
  (e.g. `WhatsApp`, `Steam`, `OneDrive`, `Spotify`), mantenelo
  literal.
- **NO traduzcas marcas/productos**: WhatsApp ≠ "guasap";
  Spotify ≠ "espotifái"; Steam ≠ "vapor".
- **NO uses voseo en el purpose**: el purpose es vocabulario
  formal de catálogo. El voseo va en `example_queries.es`.
- Si el EN tiene jerga técnica sin equivalente ES claro (e.g.
  "Playwright over CDP", "ICS"), mantenelo en EN dentro de la
  línea ES, o omitilo si infla.

### K1.2 — Ejemplos de transformación

#### Ejemplo 1 — `office`:

ANTES:
```yaml
purpose: |
  Create and edit office documents — Word (.docx), PowerPoint (.pptx),
  Excel (.xlsx), and PDF export. Use for new-document creation,
  template-driven slides, and converting between formats.
```

DESPUÉS:
```yaml
purpose: |
  Create and edit office documents — Word (.docx), PowerPoint (.pptx),
  Excel (.xlsx), and PDF export.
  Crear y editar documentos office — Word, PowerPoint, Excel, PDF.
```

(Removed "Use for ... template-driven slides ... converting between
formats" porque ya pesaba ~200 chars; la línea ES alcanza con los
verbos paralelos y los formatos. El detalle de "template-driven
slides" lo cubre el `example_queries`.)

#### Ejemplo 2 — `window`:

ANTES:
```yaml
purpose: |
  Window management — list, focus, minimize, maximize, close,
  resize, move, snap left/right, send to other monitor.
```

DESPUÉS:
```yaml
purpose: |
  Window management — list, focus, minimize, maximize, close,
  resize, move, snap left/right, send to other monitor.
  Gestión de ventanas — listar, enfocar, minimizar, maximizar,
  cerrar, redimensionar, mover, encuadrar.
```

#### Ejemplo 3 — `whatsapp`:

ANTES:
```yaml
purpose: |
  Send messages, voice notes, images via WhatsApp Web or
  WhatsApp Desktop. Resolves contact names from local
  contacts, opens chats, sends pre-typed text. Use for
  "mandale a X", "decile a Y por whatsapp".
```

DESPUÉS:
```yaml
purpose: |
  Send messages, voice notes, images via WhatsApp Web or
  WhatsApp Desktop. Resolves contact names from local contacts.
  Enviar mensajes, notas de voz, imágenes por WhatsApp.
  Resuelve contactos locales, abre chats.
```

(Recortamos "Use for ..." porque example_queries ya tiene los
imperativos rioplatenses; el purpose se mantiene formal.)

#### Ejemplo 4 — `media`:

ANTES:
```yaml
purpose: |
  Play media on streaming platforms — Spotify, YouTube, Netflix,
  Disney+, HBO Max, Prime Video — via deeplinks or web flows.
  Handles auto-play, profile picking, search-and-play. Use for
  "pon X en Netflix", "play Y on Spotify".
```

DESPUÉS:
```yaml
purpose: |
  Play media on streaming platforms — Spotify, YouTube, Netflix,
  Disney+, HBO Max, Prime Video — via deeplinks or web flows.
  Reproducir en plataformas de streaming, autoplay, picking de perfil.
```

### K1.3 — Lista completa de 65 tools

Trabajá en el orden del YAML actual. Marcá cada uno con ✓ a
medida que avanzás. Si una tool ya tiene línea ES (porque su
purpose original ya era bilingüe), saltala sin cambios.

Aproximación recomendada:

1. **Documents (7)**: office, document, knowledge, source_manager,
   photo_library, study, creative_local.
2. **Browser/Web (5)**: browser, browser_real, web, vision,
   form_filler.
3. **Audio/Media (5)**: audio, audio_device, media, media_edit,
   fact_check.
4. **System (10)**: system, gui, uia, window, desktop_layout,
   clipboard, app, package, accessibility, input.
5. **Storage (6)**: filesystem, backup_sync, local_search,
   download, container, database.
6. **Messaging (5)**: whatsapp, email, contacts, notification,
   reminder.
7. **IoT/Devices (5)**: smart_home, device_settings, peripheral,
   printer_scanner, network.
8. **Dev/System (5)**: developer, terminal, registry, env,
   maintenance.
9. **Automation (8)**: routine, watcher, job_manager, state,
   verify, dependency, safety, session.
10. **Cognition (7)**: memory, notes_tasks, local_calendar,
    habit_tracker, data_analysis, skill_load, subagent.
11. **Games (2)**: steam, game_launcher.

Total: 65.

### K1.4 — Verificación post-edit

Después de cada batch (~10 entries), correr:

```bash
python -c "
import yaml
from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS

with open('gemma4_agent/tool_descriptions.yaml', encoding='utf-8') as f:
    d = yaml.safe_load(f)
assert len(d) == 65, f'expected 65, got {len(d)}'
tool_names = {s['function']['name'] for s in COMPOUND_TOOL_SCHEMAS}
yaml_names = {e['name'] for e in d}
assert yaml_names == tool_names, f'mismatch: {tool_names ^ yaml_names}'

# Char budget check.
oversized = []
for e in d:
    p = (e.get('purpose') or '').strip()
    if len(p) > 280:
        oversized.append((e['name'], len(p)))
if oversized:
    print('WARN: oversized purposes (>280 chars):')
    for name, n in oversized:
        print(f'  {name}: {n}')
else:
    print(f'ok: all {len(d)} purposes within budget')
"
```

### K1.5 — Smoke post-edit: BM25 nonzero coverage

Después de las 65 entries, validar que la asimetría se reduce:

```bash
python -c "
import numpy as np
from gemma4_agent.router_v2 import RouterV2
RouterV2.reset()
r = RouterV2.get()
r._ensure_loaded()

probes = [
    ('cierra', 'close'),
    ('abre',   'open'),
    ('borra',  'delete'),
    ('busca',  'search'),
    ('manda',  'send'),
]
for es_verb, en_verb in probes:
    es_q = f'{es_verb} algo'
    en_q = f'{en_verb} something'
    es_bm25 = r._tool_bm25.get_scores(r._tokenize_for_bm25(es_q))
    en_bm25 = r._tool_bm25.get_scores(r._tokenize_for_bm25(en_q))
    print(f'{es_verb!r:10s} bm25_nonzero={int(np.sum(es_bm25>0)):3d}'
          f'   |  {en_verb!r:10s} bm25_nonzero={int(np.sum(en_bm25>0)):3d}')
"
```

**Expectativa post-fix**: para los 5 pares, la diferencia
`abs(es_count - en_count)` debe estar ≤ 2. Si está más arriba,
ese verbo ES está sub-representado en los purposes — agregalo
explícitamente a los que aplica.

### K1.6 — Smoke: cierra steam debe mejorar

```bash
python -c "
from gemma4_agent.router_v2 import RouterV2, route_v2
RouterV2.reset()
subset, tel = route_v2('cierra steam')
print(f'subset_size={len(subset)} band={tel.get(\"confidence_band\")}')
print(f'agree={tel.get(\"retrievers_agree\")} top_score={tel.get(\"top_score\"):.4f}')
print(f'dense_top1={tel.get(\"dense_top1\")} bm25_top1={tel.get(\"bm25_top1\")}')
"
```

**Expectativa post-fix**: una de estas tres outcomes:
- `agree=True` (purpose ES suficiente para que BM25 vea "cerrar"
  en `app`/`window`/etc) → cae en HIGH/MEDIUM, cap=4 o 8.
- `agree=False` pero ratio mejora → tight_cluster cap=8.
- Si sigue en LOW cap=16, anotalo. Significa que el problema no
  era 100% léxico y la otra causa raíz (cluster geometry post-
  guard) sigue activa. NO trates de arreglarlo con más enriching
  del YAML — eso ya sería over-fitting.

### K1.7 — Commit

`docs(yaml): bilingual purpose (EN + ES) for all 65 tool descriptions`

Mensaje:

```
docs(yaml): bilingual purpose (EN + ES) for all 65 tool descriptions

Operator diagnostic post J.1 (2026-05-17 ~22:00): the BM25 leg
of router_v2 had asymmetric lexical coverage between ES and EN
queries. Concrete evidence:

  'close steam'    bm25_nonzero=7   (close matches 7 EN purposes)
  'cierra steam'   bm25_nonzero=4   (cierra only matches example_queries.es)

Cause: purposes were authored in English per Sprint 8b spec
('purpose: technical summary in English'). ES queries from the
operator (Spanish-speaking) hit fewer BM25 matches than the EN
equivalent, producing dense/BM25 disagreement on imperative
verbs ('cierra', 'abre', 'borra') and pushing routing to LOW
band (cap=16) unnecessarily.

Fix: add a single ES line to each of the 65 tool `purpose`
fields. Mirror the EN verbs/concepts in infinitive form.

  Before:
    purpose: |
      Close, focus, minimize, maximize, list windows on Windows.

  After:
    purpose: |
      Close, focus, minimize, maximize, list windows on Windows.
      Cerrar, enfocar, minimizar, maximizar, listar ventanas.

NO changes to:
- Tool names, schemas, or 65 compound tool registry.
- example_queries.es / example_queries.en (already curated).
- router_v2 code, planner, prompts/tool_rules.
- Smalltalk gate, cache, fallback paths, RRF constants.

Per-tool char budget raised from <=200 to <=280 to accommodate
the second line. Total prompt impact: ~5KB across all 65
schemas — negligible vs 32K context window.

Brand names and product names left untranslated (WhatsApp,
Spotify, Steam, OneDrive, etc.). No voseo in the purposes
themselves (formal catalog vocabulary); voseo and colloquial
forms remain in example_queries.es.

Smoke post-fix:
- `bm25_nonzero` for ES imperatives ('cierra', 'abre', 'borra',
  'busca', 'manda') is now within ±2 of EN equivalents.
- `cierra steam` routing improves: <REPORT actual band/cap>
- HIGH band coverage for ES action commands expands.

This fix attacks the root cause of J.1's residual subset bloat
for ES queries. J.1's TIGHT_CLUSTER band and BM25 saturation
guard remain in place. The 0.80 ratio threshold may need
recalibration after a week of cluster_size telemetry, but
that's data-driven follow-up — this sprint is purely lexical
parity.
```

---

## REPORTE FINAL

Devolveme:
1. Hash del commit.
2. Output de `python -c "import yaml; d=yaml.safe_load(open('gemma4_agent/tool_descriptions.yaml',encoding='utf-8')); print(len(d), 'entries')"` (debe ser 65).
3. Output del K1.5 BM25 nonzero coverage smoke (los 5 pares ES/EN).
4. Output del K1.6 `cierra steam` smoke post-fix.
5. Output de `python -m pytest gemma4_agent/ -q --tb=line` (suite no debe romperse — el YAML cambio NO debería afectar tests existentes salvo los que pinean texto literal del purpose, si los hay).
6. Repro de las 8 queries de J.1 post-fix:
   ```python
   from gemma4_agent.router_v2 import RouterV2, route_v2
   queries = [
       'cierra steam', 'close steam',
       'cierra whatsapp', 'close whatsapp',
       'abre el powerpoint que hice',
       'ayudame con un proyecto',
       'sube el volumen', 'hola',
   ]
   for q in queries:
       RouterV2.reset()
       subset, tel = route_v2(q)
       band = tel.get('confidence_band', '-')
       agree = tel.get('retrievers_agree', '-')
       cap = tel.get('adaptive_cap', '-')
       print(f'{q!r:35s} band={band!s:14s} agree={agree!s:5s} cap={cap!s:3s} size={len(subset):2d}')
   ```

## CRITERIO DE ÉXITO

- 1 commit aterrizado.
- 65 entries en YAML, todos parsean.
- Char budget: 65 purposes ≤ 280 chars cada uno.
- Suite completa verde (modulo Sprint 3a pre-existing failure +
  E.5 xfailed).
- `bm25_nonzero` ES/EN parity: diferencia ≤ 2 para los 5 verbos
  probados.
- `cierra steam` mejora medible (band sube de LOW o tight cluster
  cap se reduce — uno de los dos).
- No regression: `cierra whatsapp`, `sube el volumen`, demás
  queries HIGH siguen en HIGH cap=4.

## NO HACER (anti-scope)

- NO toques `example_queries`. Ya están bilingües y curados.
- NO uses voseo en el purpose. El purpose es catálogo formal;
  voseo va en example_queries.es.
- NO traduzcas brand names (WhatsApp, Spotify, Steam, OneDrive,
  Outlook, Gmail, Office, Word, Excel, PowerPoint).
- NO inventés capabilities nuevas en la línea ES. Tiene que ser
  mirror semántico del EN, nada más.
- NO escribas oraciones largas en español. Mantené la línea ES
  tan compacta como la EN — verbos en infinitivo separados por
  comas.
- NO toques router_v2.py — este es pure docs change. Si el
  smoke post-fix muestra que `cierra steam` sigue en LOW con
  cap=16, **acéptalo y reportalo**. Significa que la otra causa
  raíz (cluster geometry post-guard, ratio threshold incorrecto)
  sigue siendo el blocker, y eso es trabajo de un sprint futuro
  data-driven, no de éste.
- NO agregues idiomas adicionales (PT, FR, IT, DE) al purpose.
  El operador es ES; e5-small multilingual sigue cubriendo
  cross-lingual via dense. Bilingüe ES/EN es el target específico.
- NO agregues lookup tables / config / env vars. El YAML directo
  es la fuente de verdad.
- Si encontrás 1-2 purposes pre-existentes que ya son bilingües
  (por sprint 8b legacy), NO los reescribas. Mantenelos como
  están y marcalo en el reporte.

## Notas de calibración para futuros sprints

- Post-K, el `bm25_nonzero` para queries ES sube. Eso significa
  que el ratio `rrf[N]/rrf[0]` también cambia post-K. La
  calibración del TIGHT_CLUSTER (J.1) ratio=0.80 fue medida
  pre-K — puede necesitar ajuste data-driven después de 1
  semana de logs reales con el `cluster_size` telemetry.
- Si en el smoke K1.6 `cierra steam` salta a HIGH agree=True,
  eso confirma que el problema era 100% léxico. Si salta a
  TIGHT_CLUSTER, eso confirma que la geometría del cluster era
  real y el threshold de J.1 necesita ajuste menor.
- Si sigue en LOW: las dos causas raíz se acumulaban y el sprint
  L (TBD) tendría que parchear la métrica del router. Pero
  esperá data real antes de escribirlo.
