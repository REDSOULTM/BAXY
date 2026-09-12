# Revisión estática de fuente Kiro1036

Comparación exacta: `ed305c3819a1d6ebd069e783756087928449d66c` → `3a73819215ed483e3f7d3a5b36ef85bad43dfad2` (`origin/codex/kiro-goal-c03`). Sólo los cinco archivos asignados: +165/−16. No se ejecutaron pruebas, imports, compilación, GPU ni producto; no se modificó fuente, registro o rama canónica. Los ejemplos siguientes son contraejemplos razonados por lectura, no corridas.

## Hallazgos

### 1. [P1] El nuevo veto conversacional descarta respuestas válidas por estar en mayúsculas

**Owner:** `src/baxy_mind/__main__.py:6683–6692` y `6823–6840` del tip.
`_conversation_reply_is_a_bare_prompt_token` no compara vocabulario del prompt ni el pedido. Rechaza cualquier cadena sin espacios, sin cifras, con al menos tres caracteres y todas sus letras mayúsculas. Por ello respuestas legítimas como `UTC`, `NASA`, un acrónimo solicitado o el resultado de convertir una palabra a mayúsculas producen PlannerContractError. También admite signos no alfabéticos dentro de la cadena para ese rechazo: no se limita realmente a una palabra copiada. La causa demostrada de una respuesta `SIEMPRE` no acredita que cualquier palabra en mayúsculas sea filtración de instrucciones. Esta condición no existía en la base y se aplica a toda conversación.
**Corrección mínima a revisar:** retirar la generalización por capitalización. La fidelidad de una respuesta corta debe juzgarse contra el pedido/hechos con mecanismos existentes; no sustituirla por una lista de acrónimos permitidos. Bloquear contenido útil y caer a error no resuelve la respuesta original defectuosa.

### 2. [P2] Un estado presente verdadero se interpreta como estado previo inventado

**Owner:** `src/baxy_mind/llm.py:4202–4217`, especialmente4212, y4602–4603.
Con recibo de apertura nueva (`alreadyRunning=false`), la respuesta «Ya tengo la calculadora abierta.» describe correctamente el estado resultante. El nuevo patrón `ya\s+tengo\b[^.;]{0,40}abiert` la clasifica como afirmación anterior y devuelve `invented_prior_open_state`. El hecho de que la apertura haya ocurrido ahora no contradice que ahora esté abierta. La misma función reconoce en su comentario que «ya está abierta» no implica estado previo, pero aplica un criterio opuesto a su equivalente en presente «ya tengo … abierta». Esto fuerza recuperación para un final fiel y puede agotar la composición si la generación mantiene esa formulación natural.
**Corrección mínima:** limitar esta guarda a anterioridad expresada inequívocamente; retirar la alternativa de presente en lugar de introducir una frase visible obligatoria. Preservar el recibo y el resto de controles de nombres/estado.

### 3. [P2] Cualquier final con “again” se considera una reapertura, incluso su negación

**Owner:** `src/baxy_mind/llm.py:4190–4199`, especialmente4197; caller4590–4598.
Con `alreadyRunning=true`, «Paint was already open; there was no need to open it again.» explica fielmente la reutilización y niega que hiciera falta abrir otra instancia. `_claims_a_relaunch` retorna true sólo por terminar en `again.`. El caller lo rechaza aunque `_states_it_was_already_running` también sea true, porque la rama de reapertura es un OR independiente. La alternativa más amplia también puede detectar verbos dentro de una negación. Se añade una regresión de utilidad y una clasificación factual errónea donde la respuesta conserva el hecho exigido.
**Corrección mínima:** no inferir una acción por un adverbio final aislado. La condición debe exigir una afirmación positiva de reapertura, respetando la negación; mantener orientación generativa de reutilización sin exigir vocabulario fijo. No se ha verificado aquí una implementación alternativa.

## Providers: alcance real del cambio, sin hallazgo adicional confirmado

- `WindowsApplicationOpenVerifier.cs:67–102`: conserva PID, creación, ejecutable/package y MatchesReceipt; acepta HWND no nulo y visible. Solicita foreground si falta, pero devuelve Verified sin observar si el intento consiguió foco.
- `WindowsInstalledApplicationOpenProvider.cs:525–549`: conserva PID, creación, HWND y visibilidad del catálogo; tras intentar foco y esperar acepta observación sin Foreground. Success579–605 conserva AlreadyRunning/reuse y la identidad observada.
- `WindowsCalculatorOpenProvider.cs:43–66`: conserva PID, creación, HWND y visibilidad; después de100ms acepta igualmente observación sin Foreground.

La postcondición se reduce deliberadamente de «ventana visible y foreground» a «ventana visible del proceso vinculado». No demuestra que la ventana esté delante, sea la activa o haya recibido el foco; los recibos devueltos no añaden un hecho foreground verificado. La raíz debe contrastar ese significado con el criterio de producto y las afirmaciones finales al revisar evidencia. En estos cinco archivos no encontré eliminación de identidad de proceso que permita sostener un defecto adicional concreto; tampoco considero el comentario sobre flyouts prueba de cada ejecución. No atribuir crédito o reparación causal al cambio sólo por esta lectura.

## Identificación reproducible del material revisado

Git blobs base → tip:
- `src/baxy_mind/__main__.py`: `5ef5090be5cbb7d9dc10339f0eba169084ce4662` → `bad65197b44b7455d4b4355711bd532f9abb0764`.
- `src/baxy_mind/llm.py`: `d36c80cf8e073cd99f8e12a30cd48dfd10854565` → `c43a77af2c39c488a00c287f4c62edd110d70469`.
- `src/Baxy.Providers.Windows/Applications/WindowsApplicationOpenVerifier.cs`: `be073c4b64e62d7fdb64e39fe801715d9d856310` → `82a09ba9afc182c257356cd431bde4f4c4e6e32b`.
- `src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs`: `1d342c16e24dd42b89ddb827c51984068d8fdcb4` → `540c3e9c1ada34ae98feaa0ccb71052d02553fea`.
- `src/Baxy.Providers.Windows/Applications/WindowsCalculatorOpenProvider.cs`: `0af77fe87bc96a5b46326dd54d929f4f4e97c1c8` → `c1b33bf3911f7a759d387cde81e9d1e89c40f619`.

SHA256 del diff de esos cinco paths con `git diff --no-ext-diff --unified=8`, líneas unidas por LF/UTF8 sin terminador final: `620c0f786214242b284d81639ef86dbd1bab08012b30a0eb376690617886a4f9`.
Recomendación: resolver los tres nuevos falsos rechazos antes de considerar la fuente libre de regresiones. No adopción, migración ni evaluación de créditos realizadas por este agente.
