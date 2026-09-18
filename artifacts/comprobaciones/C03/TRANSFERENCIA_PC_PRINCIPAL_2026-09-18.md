# Prompt para el agente del OTRO PC — empaquetar el estado privado de C03 para el PC principal (REDPC)

Eres el agente que trabajó el goal C03 en este PC (rama `codex/kiro-goal-c03`, estado 653/742,
último commit `bb02fdb21`). El PC principal (hostname REDPC, usuario `usuario`, mismas rutas
`C:\Users\usuario\AppData\Local\BAXY`) ya tiene la rama, el runtime (Qwen3-4B-Instruct-2507
Q4_K_M, llama-server, Tesseract, WhatsApp Desktop, Discord) y compila el HEAD. Lo que NO tiene es
el estado privado que vive fuera de git. Su registro es del 2026-09-12 (154/742, SHA
`58986cb8…`), no el actual. **No inventes nada: sólo copia.** Nada de esto se sube a git.

Crea `C:\Users\usuario\Desktop\C03-transfer\` y deja dentro UN zip `C03-transfer-<fecha>.zip`
(o varios si pasa de 2 GB) con estas rutas RELATIVAS a `C:\Users\usuario\` preservadas, más un
`TRANSFER_MANIFEST.txt` (ruta relativa, bytes, sha256 de cada fichero). Sin ese manifiesto no
se acepta la transferencia.

## Obligatorio (sin esto el PC principal no puede medir ni adjudicar)

1. `AppData\Local\BAXY\C03-survey-requirements336-private\` **entera** (requirements.jsonl y
   todos los `.bak`). Antes de empaquetar, verifica y escribe en el manifiesto:
   `Get-FileHash requirements.jsonl -Algorithm SHA256` debe ser
   `fffae5b5ecce86296d61b1070cd518ac8f6d9b6528fec5861cf9faa1baec83e4` (registro tras
   CHROMETABS1843, 653/742). Si no coincide, di cuál es y por qué (¿hubo una adjudicación
   posterior?), y empaqueta igualmente el fichero vigente.
2. **El utillaje raíz**: `root_prepare.py`, `root_adjudicate_from_decisions.py`,
   `root_publish_from_adjudication.py`, `next_tanda.py`, los `root_case*`/`root_collect*`,
   `n_case.sh`, `msgsend_case.sh`, `approve_message_send.py`, y cualquier otro script del
   método de tanda. Localízalos con
   `Get-ChildItem -Recurse -Filter root_prepare.py $env:LOCALAPPDATA\Temp\claude, $env:LOCALAPPDATA\BAXY, $env:USERPROFILE\.claude`
   y copia **el directorio completo** que los contiene (normalmente el `scratchpad` de la
   sesión de Claude: `AppData\Local\Temp\claude\<slug>\<sesión>\scratchpad\`). Si hay varios
   scratchpads con versiones distintas, incluye todos y di cuál es el vigente.
3. Todos los `AppData\Local\BAXY\C03-*-tooling\` (al menos `C03-msgsend1845-tooling`,
   `C03-chrometabs1843-tooling`, `C03-discord1839-tooling`, `C03-msg1837-tooling`).
4. `AppData\Local\BAXY\C03-repairs1843-build\` y, si existe, `C03-repairs1845-build\`
   (como mínimo `build.py` y `BUILD_READY.json`; los binarios se pueden regenerar allí).
5. Los instrumentos sellados más recientes, enteros:
   `AppData\Local\BAXY\C03-chrometabs1843-instrument-v1\`,
   `C03-discord1839-instrument-v1\`, `C03-msg1837-instrument-v*\` y cualquier
   `C03-msgsend1845-instrument-v*\` si llegó a sellarse. Los `derive_*.py` leen del
   instrumento anterior; sin ellos no se puede sellar el siguiente.
6. Los JSON sueltos en la raíz de `AppData\Local\BAXY\` (`C03-catalog-capabilities.json`,
   `C03-recogniser-baseline.json` y cualquier otro `C03-*.json`).
7. La memoria de la campaña: `C:\Users\usuario\.claude\projects\<slug-del-repo>\memory\`
   entera (MEMORY.md y todos los .md).
8. `AppData\Local\BAXYRuntime\mind-runtime-v1.json` y `assets.local.json` (sólo para
   comparar SHAs; NO empaquetes modelos ni binarios salvo que difieran de lo que dice el
   manifiesto del 2026-09-12: gguf `3605803b…`, llama-server `38a9d28e…`).

## Opcional (segundo zip, si el disco lo permite)

9. Todo lo demás de `AppData\Local\BAXY\` con fecha de modificación posterior al
   2026-09-12 03:20 (instrumentos, privates, profiles, proposals de las tandas 1036–1845).
   Si pesa demasiado, prioriza los directorios de las tandas de mensajería, Steam/Epic, UI y
   correo, que son los frentes que quedan abiertos.

## Cómo entregarlo

Deja el zip en `C:\Users\usuario\Desktop\C03-transfer\` de este PC y avisa al dueño; él lo lleva
al PC principal a la misma ruta. En tu respuesta final indica: ruta del zip, tamaño, SHA256 del
zip, el SHA256 de `requirements.jsonl` que empaquetaste y la lista de rutas que NO encontraste.
