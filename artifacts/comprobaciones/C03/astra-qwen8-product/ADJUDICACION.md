# Desarrollo integrado Qwen3-8B — no aceptación

Terminó exit 0, 323.76 s. Modelo y overrides descritos en PREREG.json;
registro Granite intacto. Pico del árbol 3335.57 MiB de VRAM y 6898.48 MiB
RAM; la telemetría sí estuvo disponible en el monitor de toda la corrida.
El sondeo independiente breve sin muestra no invalida este registro, pero
esta prueba tampoco certifica todas las cargas simultáneas del producto.

| Turno | Pedido | Resultado | Veredicto |
|---|---|---|---|
| 1 | Hello | Hello! How can I help you? | Útil y fiel. |
| 2 | cuánto es doce por ocho | composition_failed | Falla: no responde. |
| 3 | What is fourteen times six? | Eighty-four. | Útil y correcto. |
| 4 | Explain encryption, pero en simple | composition_failed | Falla: no responde. |
| 5 | responde en spanglish: qué es el cifrado | composition_failed | Falla: no responde. |
| 6 | what is the capital of Peru | The capital of Peru is Lima. | Útil y correcto. |

3/6 útiles y 3/6 publicados. No promover el modelo. Las bienvenidas en español
acusan instrucciones; las composiciones de progreso saludan. El audit muestra
agotamientos en preparación/decisión y no permite atribuir cada uno a una única
llamada. Fuente: paired.json, compose-audit.jsonl, turn-audit.jsonl y RESULT.json.

Siguiente contraste acotado: la proyección borraba kind y el estado acting,
dejando vacío el payload de bienvenida/progreso. Conservar esa información;
no cambiar modelo, presupuestos ni verificadores para el A/B.
