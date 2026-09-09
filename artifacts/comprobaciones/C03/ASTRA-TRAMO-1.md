# C03 — conservación del pedido, 2026-09-06

Base: `2bf3d4c`, rama `Goal-c03`. EN_CURSO, sin aceptación reservada.

Hipótesis: el compositor pierde información del pedido (saludo original y tema
en reintentos), y exige una definición incluso al pedir utilidad. Se corrige la
frontera, no se añaden vetos de vocabulario. Evidencia heredada:
`panel-opus-13/compose-audit.jsonl`, turnos 1, 4, 20, 32, 56.

Población de desarrollo congelada antes de editar: `astra-development.turns.jsonl`,
16 turnos de panel-opus-13, índices 1,2,3,4,19,20,21,22,31,32,33,34,55,56,43,44,
en ese orden. Conserva parejas de explicación/seguimiento. Es regresión, nunca
aceptación fresca. Evaluar respuesta al pedido, hechos, idioma, publicación y
rechazos de borradores válidos; leer todas las salidas. No contar publicación
como acierto.

Aceptación del tramo: pruebas dueñas, comparación antes/después sobre estos mismos
turnos y Full final. Un panel aún fallido no habilita los cien reservados.

Entorno: GGUF oficial IBM descargado y verificado con SHA-256
`e0406663965846ae22a403456eb826ccce5f450840491f71952f18a7cb78e7d5`;
registrado con `scripts/register_mind_runtime.ps1`, sin override. Los hashes de
llama-server, Python, STT, TTS y wake coinciden con el registro heredado.
El Baxy de autostart aún ejecutaba Qwen; se cerró para compilar y medir Granite.

Los archivos locales anteriores quedan íntegros en el stash
`C03 2026-09-06 preservar archivos locales previos al relevo`, de la rama
`codex/pre-goal10-local-20260824`. No aplicar sobre Goal-c03: colisionan con
evidencia ya versionada. Main no se ha tocado.

Full inicial quedó interrumpido después de iniciar dotnet-format, sin veredicto.
No constituye pass ni fallo demostrado de fuente. Logs locales en scratchpad.
