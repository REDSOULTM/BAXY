# Auditoría comparativa: Gemma 4 vs Qwen3 para Carter v4

_Generado 2026-05-08 14:45:17_

## Ranking general

| Modelo | PASS | % | P0 PASS | % P0 | Latencia avg | Latencia p95 |
|---|---|---|---|---|---|---|
| `gemma4:e2b` | 27/30 | 90.0% | 12/13 | 92.3% | 2672ms | 6375ms |
| `qwen3:4b-instruct-2507-q4_K_M` | 26/30 | 86.7% | 11/13 | 84.6% | 440ms | 969ms |
| `gemma4:e4b` | 24/30 | 80.0% | 11/13 | 84.6% | 3314ms | 15765ms |

## Desempeño por dimensión

| Dimensión | `qwen3:4b-instruct-2507-q4_K_M` | `gemma4:e4b` | `gemma4:e2b` |
|---|---|---|---|
| **honesty** | 3/3 (100%) | 3/3 (100%) | 3/3 (100%) |
| **mission** | 4/5 (80%) | 2/5 (40%) | 4/5 (80%) |
| **multilang** | 3/4 (75%) | 2/4 (50%) | 4/4 (100%) |
| **tool_routing** | 9/10 (90%) | 9/10 (90%) | 9/10 (90%) |
| **trivial_input** | 4/5 (80%) | 5/5 (100%) | 5/5 (100%) |
| **typos** | 3/3 (100%) | 3/3 (100%) | 2/3 (67%) |

## Recomendación

**Mejor confiabilidad (P0 + general)**: `gemma4:e2b` con 92.3% P0 / 90.0% total

**Más rápido**: `qwen3:4b-instruct-2507-q4_K_M` con 440ms promedio


**Trade-off detectado**: el más confiable y el más rápido son distintos. Considerá usar `qwen3:4b-instruct-2507-q4_K_M` para chat trivial y `gemma4:e2b` para misiones complejas.

## Top fallos por modelo

### `qwen3:4b-instruct-2507-q4_K_M`

- **[P1] L02** `'ok'` → tools=[]
  - esperaba ES, parece EN (0es / 2en)
- **[P0] T03** `'baja el volumen al 30'` → tools=[system_set_volume]
  - esperaba alguna de ['system_volume_set', 'system_volume_down'] (got ['system_set_volume'])
- **[P1] M04** `'abre Brave y luego ve a github'` → tools=[app_open]
  - esperaba >= 2 tools, got 1
- **[P0] X01** `'abre Notepad y escribe hola mundo'` → tools=[app_open]
  - esperaba >= 2 tools, got 1

### `gemma4:e4b`

- **[P0] T03** `'baja el volumen al 30'` → tools=[system_set_volume]
  - esperaba alguna de ['system_volume_set', 'system_volume_down'] (got ['system_set_volume'])
- **[P1] M03** `'thank you'` → tools=[]
  - esperaba EN, parece ES (2es / 0en)
- **[P1] M04** `'abre Brave y luego ve a github'` → tools=[app_open]
  - esperaba >= 2 tools, got 1
- **[P0] X01** `'abre Notepad y escribe hola mundo'` → tools=[app_open]
  - esperaba >= 2 tools, got 1
- **[P1] X02** `'abre la calculadora, después ciérrala'` → tools=[app_open]
  - esperaba >= 2 tools, got 1
- **[P1] X04** `'busca python en google y abre el primer resultado'` → tools=[web_search]
  - esperaba >= 2 tools, got 1

### `gemma4:e2b`

- **[P0] T03** `'baja el volumen al 30'` → tools=[system_set_volume]
  - esperaba alguna de ['system_volume_set', 'system_volume_down'] (got ['system_set_volume'])
- **[P1] X04** `'busca python en google y abre el primer resultado'` → tools=[web_search]
  - esperaba >= 2 tools, got 1
- **[P1] Y02** `'saca pantallaso'` → tools=[]
  - esperaba alguna de ['gui_screenshot'] (got [])
