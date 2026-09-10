# Corrección de atribución — tópico y preguntas de cantidad

La atribución747 de `tell me how much` era incompleta. Se retiró únicamente el tópico de tres casos y se volvió a llamar a la misma función, sin modificar fuente. El veto persistió en los tres.

La excepción en `_is_explicit_meta_or_tool_denial` (effect_intent.py:6371–6387) exige dos condiciones independientes: empezar con `tell me how` y contener doing/running/status/state/condition/configured. Las preguntas `how much memory is free`, `how much space is occupied` y `how much charge remains` no contienen esas palabras de estado. Reordenar el tópico por sí solo no las repara.

META_COUNTERFACTUAL.json conserva entradas, cuerpo sin tópico y resultados.747 permanece intacto como registro de la primera sonda. No se cambió producto ni oráculos.

Siguiente implementación: reconocer estructuralmente tópico y directiva conservando el alcance y la evidencia original; mantener ese significado en dominio, cabecera, cláusulas y comprobación de meta. La excepción de cantidades debe distinguir medición actual con alcance válido de how-to, conocimiento, otro dispositivo, pasado, negación y citas. Reutilizar el vocabulario de lecturas existentes, incluyendo comprueba. No retirar el veto de todas las lecturas ni alterar el control histórico de salud genérica. Aún no hay un parche productivo ni una segunda sonda de reparación.
