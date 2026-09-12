# Audio1019: dos pérdidas anteriores al provider

Base fa0fbdc56d59c3dd94bbbedb6d95ab5a3de80d4c, worktree externo `C:/Users/usuario/AppData/Local/BAXY/C03-audio1019-worktree`, rama `codex/c03-audio1019`. Propiedad exclusiva effect_intent.py y __main__.py; fuente canónica intacta. Herencia1006/1008/1011: separar la retirada de intención de la pregunta generada, sin atribuir una causa de prompt por parecido visible.

## Evidencia exacta y primera transformación

| Caso | Enlace de traza | Primera pérdida observada | Consecuencia |
|---|---|---|---|
| audio1016-dev-01, «Quisiera que se oyera más fuerte el equipo.» | shell t11, turn.decide request65 | raw y explicit_contract conservan audio.volume; information_question lo convierte en conversation/knowledge sin efectos | domain_confirmation produce «¿Quieres que el sonido del equipo sea más fuerte?». No pregunta amount ni alcanza Core. |
| audio1016-dev-03, «Dejá mudo el audio del equipo, conservando su nivel.» | shell t13, turn.decide request75 | raw audio.mute sobrevive information_question; domain_grounding lo convierte en unsupported sin efectos | raw conversación niega capacidad; compose error recibe cause=outside what I do, situación out_of_catalog y publica «No puedo dejar mudo el audio del equipo.». |

Dev01: `__main__.py:1454–1488` aplica el veto informativo cuando no hay explicit_intent y la cabeza es `que`. `effect_intent.py:4548–4585` reconoce un deseo sólo si su cabeza interna pertenece a los verbos de efecto; `se` no pertenece. El fallback heredado interpreta `que` como cabeza tras `Quisiera`. El lector de aclaración relativa, líneas2771–2782/3109–3122, sólo cubre órdenes comparativas ya enumeradas en inglés y órdenes subir/bajar volumen. La primera decisión raw propone una operación absoluta, aunque la petición exige aumento relativo sin cantidad. Cambiar únicamente el prompt de confirmación no arreglaría esta identificación de la información faltante.

Dev03: `_audio_mute_domain`, líneas5319–5358, reconoce verbos silenciar/mute y construcciones dejar EN mudo. Falta la construcción predicativa dejar MUDO + objeto de audio, pese a que el modelo propuso audio.mute. La selección explícita comparte `_MUTE_VERB` y el dominio (10279–10310); el binder `_explicit_arguments_from_evidence`, __main__.py:4967–4995, también requiere en/on para la construcción de estado. Sólo modificar el dominio dejaría esa segunda discrepancia estática pendiente. El raw de negativa tiene request_sha256 `537769c03692369f397bfcd7df8bae1dcf390a7d2138638e4a9ff70f01c7eca8` y aparece igual en la auditoría final request75; su redacción es posterior al veto. No es fallo del provider ni de un recibo.

## Propuesta mínima preparada

`repair.patch`: 14 inserciones, 1 eliminación, únicamente esos dos archivos.
- El lector `relative_spoken_volume` reutiliza `_EXPLICIT_DESIRE_REQUEST` para un deseo positivo de estado audible comparativo sobre `_LOCAL_VOLUME_DEVICE`, con cuerpo completo. Retorna el ClarificationIntent existente para audio.volume.adjust/amount. No asigna cantidad ni concede efectos. El formulador existente recibe la información faltante; no se cambia prompt, JSON ni respuesta visible.
- Una gramática compartida `_MUTE_PREDICATIVE_VERB` amplía `_MUTE_VERB` existente con dejar/poner mudo y se reutiliza en el binder de state. Dominio, selección y argumento dejan de discrepar sin duplicar el nuevo reconocimiento. Los lectores existentes conservan su objeto de audio y exclusión de scope por aplicación, polaridad falsa/ambigua y las guardas de autoridad de la ruta.

Revisión manual: la nueva forma de cantidad exige deseo + estado audible + comparación + dispositivo local y termina allí; no consume cifras, otras cláusulas, futuros, prohibiciones ni citas como ese cuerpo. El frame explícito no-acción permanece al inicio del lector. El mute no transforma conservar nivel en audio.volume ni inventa un nivel; unmute frente a mute conserva la comparación true_signal==false_signal que se abstiene. No se cambia el veto informativo global ni se amplía la capacidad por las palabras del panel.

Limitaciones: no se ejecutaron funciones, tests, imports, AST, builds, HTTP ni GPU por instrucción explícita. Los pasos posteriores de la ruta mute y la utilidad de la pregunta de cantidad necesitan corrida real. Los pares EN aprobados son evidencia comunicada por raíz, no reejecutada ni transferida automáticamente. Potencial: H0027/H0563 para cantidad y H0154/H0549 para silencio, sólo si literales actuales y pares pertinentes satisfacen sus criterios; cero créditos concedidos aquí.

## SHA256

Archivos de evidencia bajo `C:/Users/usuario/AppData/Local/BAXY/C03-audio1016-private/run/`:
- turn-audit.jsonl: `ae7d60553ffb51c0ae062b818289f558b226afab91a34f32191790de50c5b189`
- raw-replies.jsonl: `c124b3994237ab70395f6b8df08e6c3ce3da37605d545c2bac536d40d85a5486`
- compose-audit.jsonl: `99b1834ece64ec5a6e5fe419829867b8f0d040039a38bbc480683945f4632447`
- shell-trace.jsonl: `c46e85524e39832bab5737d5f19a30e4d016a915073ea9ff343dc43d6cd38c63`

Propuesta:
- repair.patch: `9a4ddcb280c77a65b26310b17c7732d06acc637bcdf084c490ef9c25a596e499`
- effect_intent.py: `3bb83dc8f0c8736c86d402d0faf656915044a9089b8b27b9b9a430b36365cade`
- __main__.py: `6d4a5856d5fc8827d9024b3f38312679e15f2cf9bf00692a895137556a0279ba`
