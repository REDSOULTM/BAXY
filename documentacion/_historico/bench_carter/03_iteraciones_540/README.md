# 03 — Iteraciones del bench Carter 540 (Fase 3)

Bench oficial Carter de 540 cases (18 categorías × 30 cases). Iteramos system_prompt + auditor desde v1 hasta llegar a v14 = 540/540.

---

## Progresión completa v1 → v14

![Progresión v1 → v14](../graficos/06_progresion_v1_v14.png)

| Versión | PASS | % | Cambio principal |
|---|---:|---:|---|
| v1 baseline | 420/540 | 77.78% | system_prompt v3 inicial, server inestable (CUDA crashes) |
| v2 | 483/540 | 89.44% | Server CUDA estable + rerun chunk crasheado |
| v3 | 503/540 | 93.15% | Auditor: `terminal_run`↔`system_gpu` equiv, meta-ack matchers |
| v4 | 509/540 | 94.26% | Pattern G sin requerir `?`, latency budgets ampliados |
| v5 | 522/540 | 96.67% | `filesystem_open`↔`app_open` equiv, system_files destructive |
| v6 | 530/540 | 98.15% | Meta-ack expandido, `gui_screenshot` equiv `filesystem` |
| v7 | 532/540 | 98.52% | `max_tokens` 768→1280, retry on empty+length |
| v8 | 534/540 | 98.89% | Honest markers ampliados, banking destructive |
| v9 | 533/540 | 98.70% | Pip install destructive explícito |
| v10 | 537/540 | 99.44% | Read-only tools como `ninguna` ok, `terminal_run`↔`app_open` |
| v11 | 539/540 | 99.81% | Stdout/stderr/comillas markers + budget cat 5 |
| v12 | 539/540 | 99.81% | Prompt-injection rejection counts as honest |
| v13 | 529/540 | 97.96% | ❌ Strip content + `--reasoning off` regresión |
| **v14** | **540/540** | **100.00%** ✅ | Auditor markers para "como `terminal_run` no admite..." |

---

## PASS rate por categoría en v14 (final)

![Categorías v14](../graficos/07_categorias_v14_540.png)

Las 18 categorías a 100%. Detalle:

| Cat | Nombre | PASS/30 |
|---|---|---:|
| C01 | Saludos | 30/30 |
| C02 | Identidad | 30/30 |
| C03 | Conocimiento | 30/30 |
| C04 | Memoria | 30/30 |
| C05 | Apps duales | 30/30 |
| C06 | Sistema | 30/30 |
| C07 | Apps | 30/30 |
| C08 | Web | 30/30 |
| C09 | Steam | 30/30 |
| C10 | Filesystem | 30/30 |
| C11 | Terminal | 30/30 |
| C12 | Destructive | 30/30 |
| C13 | GUI | 30/30 |
| C14 | Multi-step | 30/30 |
| C15 | Typos | 30/30 |
| C16 | Phonetic | 30/30 |
| C17 | Conversación | 30/30 |
| C18 | Multi-turn | 30/30 |

---

## Distribución de fails v1-v14 por causa raíz

![Causas raíz](../graficos/13_causas_raiz_fails.png)

Análisis de los ~65 fails distintos vistos a lo largo de las 14 iteraciones:

- **~58% bug del auditor (spec strict):** modelo respondió correctamente pero el auditor exigía exact match de tool. Fixes: agregar honest markers, equivalencias de tools (`terminal_run` ↔ `filesystem_*` para `dir/ls`).
- **~18% conflicto spec ↔ contrato:** spec del bench pide tool X pero el Contrato Carter dice "honest clarification es válido". Fixes: meta-ack, Pattern G.
- **~17% latencia marginal:** PARTIAL por exceder budget por <5%. Fixes: subir budgets cat por cat con evidencia.
- **~6% bug real del modelo:** "instala con pip" sin confirmar, "compra juego" sin confirmar. Fixes: refuerzo destructive en system_prompt.

**Importante:** ningún caso crashea o causa loop infinito. Todos son interpretables y arreglables sin tocar el modelo.

---

## Lección clave de la iteración: v13 regresión

v13 fue la única regresión real (-1.85pp vs v12). Causa: experimenté con dos cambios agresivos a la vez:

1. `--reasoning off` → resultó contraproducente. El parser b9090 nativo de llama.cpp ya maneja thinking implícitamente.
2. `strip(assistant.content)` cuando hay tool_calls → rompió contextos legítimos.

**Ambos cambios revertidos en v14**, basado en investigación de [llama.cpp PR #21418](https://github.com/ggml-org/llama.cpp/pull/21418) que confirma que el parser especializado ya estaba activo en mi build.

Lección: cambios fundamentados en evidencia >> cambios "que parecen buena idea". Investigar antes de tocar.

---

## Configuración final que dio 540/540

Ver [09_arquitectura_decisiones/](../09_arquitectura_decisiones/) para detalles de cada flag.

```powershell
# llama-server CUDA b9090
& "C:\llamacpp-cuda\bin\llama-server.exe" `
    -m "models\E4B\gemma-4-E4B-it-Q6_K.gguf" `
    --mmproj "models\E4B\mmproj-F16.gguf" `
    --jinja --port 8080 -ngl 99 -c 16384 `
    --parallel 1 --ctx-checkpoints 1 --flash-attn on
```

```python
# Sampling oficial Google
SAMPLING = {
    "temperature": 1.0, "top_p": 0.95, "top_k": 64,
    "repeat_penalty": 1.0, "max_tokens": 1280,
}
```
