# Preflight de calidad676 — intento con entorno incorrecto

El primer intento pasó `-QualityPython C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe` a `scripts/test_source_quality.ps1 -Mode Fast` y terminó con código1 antes de analizar fuente. El resultado de `exec_command` (chunk71fd9e) informó `source_quality_preflight_failed: quality_ruff_version_mismatch`: esperaba `ruff 0.15.22`, pero ese Python respondió `No module named ruff`.

El archivo redirigido quedó vacío; `astra-focus-coverage-source676/FAST_ENVIRONMENT_ERROR.log` conserva esos cero bytes, no una transcripción del error. Este documento registra el mensaje observado en la herramienta. La ejecución posterior usó el entorno BAXYQuality predeterminado y pasó Fast entero; su salida está en `astra-focus-coverage-source676/FAST.log`. No se instalaron dependencias en el Python del producto para resolverlo.
