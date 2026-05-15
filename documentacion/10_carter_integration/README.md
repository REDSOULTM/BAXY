# 10 — Carter integration roadmap

Plan concreto para que el agente del proyecto Carter integre Gemma 4 sin romper lo que funciona.

---

## Cumplimiento de los 30 valores Carter

![30 valores Carter](../graficos/16_30_valores_carter.png)

**26 de 30 valores se cumplen en el modelo. 4 requieren wiring runtime del lado de Carter** (no son bugs del modelo).

| Valor | Estado | Acción Carter |
|---|---|---|
| 1. Local y privado | ✅ | Nada — todo on-device |
| 2. Rápido | ⚠️ | Wire streaming SSE |
| 3. Nunca mentir | ✅ | Pattern N 100% en bench |
| 4. Verificar acciones | ⚠️ | Wire verifiers (EnumWindows, pycaw, etc) |
| 5. Fallar bien | ✅ | Pattern G 100% |
| 6. Universal, no hardcoded | ✅ | system_prompt declarativo |
| 7. Sin hacks por app | ✅ | gui_deeplink general |
| 8. No depender de un modelo | ✅ | Selector hardware por VRAM |
| 9. Manejar modelos con justicia | ✅ | --jinja nativo Gemma 4 |
| 10. Texto antes que voz | ✅ | Núcleo texto = 540/540 |
| 11. Inputs triviales rápidos | ✅ | C01 p50 1.84s |
| 12. No contaminarse ventana activa | ✅ | C18 multi-turn 30/30 |
| 13. GUI/visión on-demand | ✅ | Pattern D 100% |
| 14. Memoria limpia | ✅ | C04 30/30 |
| 15. Seguro | ✅ | C12 destructive 30/30 |
| 16. Misiones compuestas | ✅ | C14 30/30 |
| 17. Transparente con progreso | ⚠️ | Wire streaming events |
| 18. Trazabilidad | ✅ | results JSON completo |
| 19. Adaptarse al lenguaje | ✅ | C15 + C16 + C17 = 90/90 |
| 20. Distinguir conversación de acción | ✅ | Pattern D + C12 |
| 21. Personalidad útil | ✅ | Reply tone correcto |
| 22. Cuidar recursos | ⚠️ | Wire `nvidia-smi` monitor |
| 23. Rollback | ✅ | env var CARTER_LLM_BACKEND |
| 24. Pruebas reales | ✅ | Bench oficial 540 cases |
| 25. Matriz brutal calidad | ✅ | 18 cat × 30 cases |
| 26. Preparado para voz | ⚠️ | Whisper integration aparte |
| 27. Preparado para cámara | ✅ | mmproj cargado, validar runtime |
| 28. Modular sin sobreingenierizar | ✅ | 16 composite tools clean |
| 29. Compañero de PC | ✅ | 540 cases lo cubren |
| 30. Ganarse la confianza | ✅ | Sin FALSE_PASS |

---

## Plan de migración (`agent.py`)

### Cambios mínimos código

```python
# ANTES (Carter actual con Ollama)
endpoint = "http://localhost:11434/v1/chat/completions"
model = "qwen3:4b-instruct-2507-q4_K_M"

# DESPUÉS (Gemma 4 vía llama-server)
endpoint = "http://localhost:8080/v1/chat/completions"
sampling = {
    "temperature": 1.0, "top_p": 0.95, "top_k": 64,
    "repeat_penalty": 1.0, "max_tokens": 1280,
}
```

### Variables de entorno

| Var | Valores | Default | Efecto |
|---|---|---|---|
| `CARTER_LLM_BACKEND` | `auto` `ollama` `llama-server` | `auto` | Fuerza adapter |
| `CARTER_TOOL_CATALOG` | `individual` `consolidated` | `individual` | Schema de tools |
| `CARTER_STREAMING` | `0` `1` | `0` | SSE en chat |

### Bootstrap script

```powershell
# scripts/start_carter_llm.ps1
$model = Get-CarterModelForVRAM   # selector hardware
$llama = "C:\llamacpp-cuda\bin\llama-server.exe"
& $llama -m "models\$model.gguf" --mmproj "models\mmproj-F16.gguf" `
    --jinja --port 8080 -ngl 99 -c 16384 `
    --parallel 1 --ctx-checkpoints 1 --flash-attn on
```

### Plan de rollback

- Mantener Ollama instalado con `qwen3:4b-instruct-2507-q4_K_M`.
- `agent.py` con flag `CARTER_LLM_BACKEND=ollama|llama-server`.
- Si Gemma 4 regresiona en producción real: cambiar variable env y reiniciar.

---

## Verifiers que Carter debe wirear (Valor 4)

Lista mínima de verifiers post-call:

```python
VERIFIERS = {
    "app_open":        verify_via_EnumWindows_or_tasklist,
    "app_close":       verify_app_no_longer_in_tasklist,
    "system_set_volume": verify_via_pycaw_GetMasterVolumeLevelScalar,
    "system_mute":     verify_via_pycaw_GetMute,
    "filesystem_write": verify_path_exists_and_size_gt_0,
    "filesystem_delete": verify_path_no_longer_exists,
    "terminal_run":    verify_real_exit_code_not_assumed,
    "gui_screenshot":  verify_file_exists_dims_reasonable,
}
```

Status enum del Contrato Carter:
```
COMPLETED | PARTIAL_WITH_NEXT_STEP | NEEDS_USER | NEEDS_ENVIRONMENT |
NEEDS_PERMISSION | UNVERIFIED | BLOCKED_BY_POLICY_WITH_SAFE_ALTERNATIVE
```

`COMPLETED` solo si verifier OK. Sino → `UNVERIFIED`.

---

## Streaming wire mínimo

```python
async def stream_response(messages):
    response = await llama_server.post(
        "/v1/chat/completions",
        json={**sampling, "messages": messages, "stream": True},
        stream=True,
    )
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            chunk = json.loads(line[6:])
            delta = chunk["choices"][0]["delta"]
            if "content" in delta:
                ui.emit_token(delta["content"])
            if "tool_calls" in delta:
                ui.emit_status(f"Llamando a {delta['tool_calls'][0]['function']['name']}...")
```

Si latencia > 5s sin nuevo token: emitir spinner + último estado conocido.

---

## Próximos pasos sugeridos para agente Carter

1. Branch `feat/gemma4-integration` (ya creado).
2. Adapter llama-server (`adapters/llamacpp.py`) — ya existe, agregar `chat_stream()` y env override.
3. Tool catalog consolidated — copiar 16 schemas + dispatcher 1:1 mapeando a 60 tools reales Carter.
4. Hardware-aware selector — `carter/hardware/profile.py` con `nvidia-smi`.
5. Verifiers — `carter/verify_runtime.py` con pycaw, EnumWindows, etc.
6. Streaming — wire SSE en agent loop.
7. Re-correr bench oficial Carter 540 con `CARTER_LLM_BACKEND=llama-server` para confirmar que integración mantiene 540/540 en producción real (no en mi harness modelo-puro).
8. Documentar en `MIGRATION_PLAN_GEMMA4.md` + `INFORME_NOCTURNO.md`.
9. Push branch sin merge — esperar review humano.

Ver `evidencia pruebas gemma4/README.md` para el paquete completo entregable al agente Carter.
