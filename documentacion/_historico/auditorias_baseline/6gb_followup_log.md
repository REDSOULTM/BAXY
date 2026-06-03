# Followup — Soporte 6 GB VRAM + Voice por perfil
- Sesión: 2026-05-15 (autónoma nocturna, tercera continuación)
- Disparador: target de producción es 6 GB VRAM. Hoy un usuario con 6 GB lanza la app y se rompe (default apunta a Q6_K de 6.6 GB).
- Decisión clave: voice (Whisper + Piper, ambos CPU) DEBE estar disponible en TODOS los perfiles activos. Solo se apaga en standby.

---

## Cambios aplicados

### 1. `profiles.py` — `Profile.voice_enabled` + model_paths reales

- Nuevo field `voice_enabled: bool` en el dataclass.
- **performance**: `voice_enabled=True`, `model_path=None` (respeta el modelo del usuario via env var). Sigue siendo el setup del dev con 12+ GB.
- **balanced**: `voice_enabled=True`, `model_path=models/E4B/gemma-4-E4B-it-Q4_K_M.gguf`, `context_size=8192` (bajado de 16K para entrar en 6 GB), `vision_enabled=False` (mmproj rompe el budget). Este es el perfil objetivo para 6 GB.
- **light**: `voice_enabled=True`, `model_path=models/E2B/gemma-4-E2B-it-Q4_K_M.gguf`. Cabe con holgura en 4 GB y libera VRAM para gaming.
- **standby**: `voice_enabled=False` (no hay LLM al que entregar el texto).
- `apply_profile_to_env` exporta `GEMMA4_VOICE_PROFILE_ALLOWS` para que `main_window` y `voice_runner` lo lean junto al master switch del usuario.
- `_profile_with_overrides` admite `voice_enabled` en los overrides editables.

### 2. `recommend_profile()` — cortes de VRAM alineados al target

| VRAM detectada | Perfil recomendado | Motivo |
|---|---|---|
| ≥ 12 GB | performance | modelo grande del usuario (Q6_K+) |
| ≥ 6 GB | **balanced** | E4B-Q4_K_M con KV q8_0 |
| ≥ 4 GB | light | E2B-Q4_K_M |
| < 4 GB / None | light | mejor que rehusar; voice CPU sigue ON |

(Antes: 6 GB caía en light. Ahora cae en balanced, que es donde tiene que estar el target.)

### 3. `get_active_profile()` — auto-detect en primer arranque

Si `~/.gemma4/active_profile.txt` no existe (usuario nuevo), detecta VRAM con `nvidia-smi/rocm-smi` y persiste el perfil recomendado. Antes caía silenciosamente en balanced sin escribir nada.

### 4. `config.py` — default `model_path` = E4B-Q4_K_M

Antes el default era Q6_K (6.6 GB) → un usuario con 6 GB se rompía. Ahora el default es Q4_K_M (4.6 GB).

**Tu setup actual está intacto**: si tenés `GEMMA4_MODEL_PATH` apuntando a Q6_K en tu env, sigue funcionando exactamente igual. Lo verifiqué con un test:

```
TEST 1 (env var set): model_path=gemma-4-E4B-it-Q6_K.gguf
TEST 2 (no env):       model_path=gemma-4-E4B-it-Q4_K_M.gguf
```

### 5. `llama_server.py` — flags VRAM-tight para balanced/light

Para los perfiles que apuntan a Q4_K_M, añadí:
- `--cache-type-k q8_0 --cache-type-v q8_0`: KV cache cuantizada (ahorra ~50% vs F16, requiere flash-attn ON que ya estaba).
- `--no-mmap`: carga directa a VRAM, sin doble buffer en RAM.

Performance queda con KV F16 (el dev tiene VRAM holgada).

### 6. `main_window.py` — voice sync por `voice_enabled`

Antes: hardcoded `profile.name in {"performance", "balanced"}` → light NO recibía voice.
Ahora: `getattr(profile, "voice_enabled", True)` → light recibe voice (Whisper CPU sigue funcionando con cualquier VRAM).

Master switch del usuario (`Settings → voice.enabled`) sigue prevaleciendo via AND.

### 7. Settings GUI — `voice_enabled` editable por perfil

La tabla de perfiles en `ui/settings.py` ahora tiene una fila extra `voice`:

```
       Performance   Balanced   Light
ctx    32768         8192       4096
vision true          false      false
rerank true          true       false
parallel true        false      false
voice  true          true       true
model  (env var)     E4B-Q4_K_M E2B-Q4_K_M
```

Editable + persiste a `~/.gemma4/profiles.json`. RESTAURAR DEFAULTS también actualizado.

La nota explicativa al pie de la tabla ahora menciona qué modelo va en cada perfil y aclara que voice está siempre ON.

---

## Resultados de verificación

| Validación | Resultado |
|---|---|
| `py_compile` sobre los 5 archivos modificados | OK |
| Tu setup (Q6_K via env var) preservado | ✅ TEST 1 PASS |
| Usuario nuevo (sin env var) cae a Q4_K_M | ✅ TEST 2 PASS |
| voice_enabled True en performance/balanced/light | ✅ |
| voice_enabled False en standby | ✅ |
| recommend_profile(6144) → balanced (era light) | ✅ |
| `GEMMA4_VOICE_PROFILE_ALLOWS` exportado correctamente | ✅ |
| Modo A smoke (143 casos) | **143/143 PASS, 6/6 anti-bypass PASS** |
| Tests del repo (test_gx_features + router + model_info) | **71/71 PASS** |

Dos tests del repo necesitaron actualizarse para reflejar los nuevos cortes (8192 ctx en balanced, recommend(6144)→balanced). Cambio intencional, no bug.

---

## VRAM aritmética verificada

Asumiendo Windows 0.5 GB + CUDA reserve 0.3 GB = 0.8 GB de overhead fijo:

| Perfil | Modelo | Modelo VRAM | KV (config) | Total app | Cabe en |
|---|---|---:|---:|---:|---|
| performance | E4B-Q6_K + mmproj | 6.6 + 0.9 = 7.5 GB | F16 32K = ~3.0 GB | ~11.3 GB | 12 GB ✅ |
| balanced | E4B-Q4_K_M | 4.6 GB | q8_0 8K = ~0.4 GB | ~5.8 GB | **6 GB ✅** |
| light | E2B-Q4_K_M | 2.9 GB | q8_0 4K = ~0.15 GB | ~3.85 GB | 4 GB ✅ / 6 GB con margen |
| standby | (server off) | 0 | 0 | 0 | cualquiera ✅ |

Voice (Whisper small int8 CPU + Piper CPU): **0 GB VRAM, ~2-2.5 GB RAM**. Independiente de la columna VRAM.

---

## Lo que no hicimos (pendiente para después)

1. **Bench Carter 540 con E4B-Q4_K_M**: el bench que tenemos (99.81%) es con Q6_K. Para tener un número del modelo que el usuario 6 GB va a correr, hay que volver a correr el harness con Q4_K_M. Toma horas.
2. **Bench con E2B-Q4_K_M**: idem para light. El INFORME estima 80-90% pero no hay número medido.
3. **Validación en hardware real con 6 GB**: la aritmética cierra, pero el único test fiable es lanzar el server con el modelo balanced en una RTX 3060 6 GB / 4050 mobile / etc. Si pudiera hacerlo desde acá, lo haría.
4. **Mover el archivo `~/.gemma4/active_profile.txt` ya existente**: si en tu máquina hay un `active_profile.txt` con `light` viejo, la app va a leerlo y respetarlo. Si querés re-detectar VRAM al arrancar, borrá ese archivo y la próxima ejecución va a detectar 16 GB → performance → respeta tu Q6_K. Documentado en `fix_notes.md` si querés que lo agregue.

---

## Archivos modificados (esta sesión)

- `gemma4_agent/profiles.py` (~70 líneas: dataclass field, defaults, recommend_profile, get_active_profile, apply_profile_to_env)
- `gemma4_agent/config.py` (3 líneas: default model_path)
- `gemma4_agent/llama_server.py` (~15 líneas: flags condicionales por perfil)
- `gemma4_agent/ui/main_window.py` (~12 líneas: voice sync por field, no por nombre)
- `gemma4_agent/ui/settings.py` (~10 líneas: voice_enabled en tabla, nota actualizada)
- `gemma4_agent/test_gx_features.py` (2 tests actualizados para nueva tabla)

**Total**: ~110 líneas tocadas, 5 archivos de código + 1 de test. Sin nuevas dependencias. Sin git.
