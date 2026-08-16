# Carter v2 — Sesión de Trabajo (27 de Abril, 2026)

## Estado de Git
- **Commit realizado:** `fix(test): use valid PNG fixture for vision fallback test`
- Se corrigió el fallo en `tests/test_medium_priority.py` que causaba errores en el guard de visión.

## Backend y Modelos
- **Diagnóstico:** El entorno tenía `CARTER_LLM_MODEL=llava:7b`. Este modelo es de visión y no soporta tool-calling nativo en Ollama, lo que rompía los probes.
- **Acción:** 
    - Se modificaron `probe_all_tools.py` y `probe_text_hardening.py` para incluir un chequeo de `supports_tools`.
    - Ahora, si se intenta usar un modelo como `llava`, `phi4` o `gemma3` para probes de herramientas, el script se detiene con un error fatal explicativo.
- **Modelo Recomendado:** Se verificó la disponibilidad de `qwen3:8b` y `qwen3:14b` en el sistema.

## Verificación (Closure Gate)
- **Pytest:** 815 PASSED (100%). La base de código es estable.
- **Probe All Tools:** 96% (159/165).
    - **Fallos de Entorno:** `pdf_from_docx` falló por falta de componentes de Office.
    - **Fallos de Archivo:** Errores de `Permission Denied` en `sample.docx` (posiblemente abierto en Word o bloqueado).
    - **Fallos de Lógica:** `UNIV-3` (Universal Runner) y `S25-INTENT-3` (Intent Continuity) no resolvieron correctamente con `qwen3:8b`.

## Conclusión
- El proyecto es más robusto ante errores de configuración.
- El "Closure Gate" no está totalmente cerrado debido a dependencias locales (Office) y locks de archivos.
- **Siguiente paso:** Limpiar `probe_assets`, asegurar que no haya procesos de Office colgados y re-intentar con `qwen3:14b` si se busca el 100% en tareas complejas.

---
*Sesión finalizada por el usuario.*
