# Otra incompatibilidad de BAXY con el razonamiento de K2

La gramática compacta del validador de efectos obliga a generar JSON desde el primer token, mientras la plantilla de K2 todavía está dentro del razonamiento. En los tres pedidos de hora —español, inglés y mezcla— el servidor devolvió `content` vacío y este JSON en `reasoning_content`:

```json
{"request_type":"stable_conversation","effect_count":"zero"}
```

Además de estar en el canal incorrecto, esa clasificación es falsa para una lectura de hora actual. No se recupera como respuesta final ni se modifica el validador para aceptarla.

El control discriminante exigía la cadena JSON `"GBNF_ACTIVE"` mediante una gramática de un único resultado. El servidor la devolvió exactamente dentro del razonamiento, también con respuesta final vacía. **La gramática sí se aplica; se aplica en una posición incompatible con el razonamiento.** Esto corrige la hipótesis preliminar de que pudiera ignorarse. La copia de parámetros restantes del cuerpo en `tools/server/server-common.cpp:1391-1396` explica que llegue al sampler aunque el generador automático no la produzca.

Se comparó cada pedido con su esquema JSON original, manteniendo pesos, backend, mensajes, muestreo, semilla y perfil high práctico. Cambió sólo la representación de la restricción. Cada petición activó un presupuesto total de19s, incluidos reintentos.

| Pedido | GBNF compacto | Esquema original |
|---|---|---|
| «Dime la hora.» | Final vacío,1,515s | Timeout,19s |
| «What time is it?» | Final vacío,1,563s | Timeout,19s |
| «Dime the current time, por favor.» | Final vacío,1,562s | Final JSON a11,453s; identifica lectura externa pero cuenta cero efectos |

Ninguna de las seis salidas cumple el contrato completo. El esquema original permite separar razonamiento y JSON final, pero por sí solo todavía no resuelve calidad y plazo. Son pruebas de compatibilidad de una frontera concreta, no una clasificación global de modelos ni cobertura de la encuesta.

Los tres formatos anteriores de732 sí mostraron herramientas/prosa y JSON final separado, con la salvedad de su reintento tardío: [reporte732](../K2_HORIZON_CONTRACT732/REPORT.md). La evidencia731 ya mostró que apagar el razonamiento reducía38/50 a19/50 en el panel nativo. No procede introducir K2 en todas las capas actuales y atribuirle estos fallos como incapacidad del modelo original.

Picos del servidor:3446,23MiB de VRAM y824,72MiB de RAM.61s de diagnóstico, sin infracciones de memoria; no mide UI/voz ni consumo conjunto. Sesión41764 terminal exit0, servidor cerrado. Fuente productiva y manifiesto intactos. El campo `contract_met=false` del control discriminante significa que no hubo el final exigido; no que la gramática se ignorase.

**Siguiente decisión:** conservar razonamiento nativo y usar el esquema original para la salida estructurada; verificar cómo comunicar ese contrato al modelo antes de una tanda integrada. Mantener validaciones y plazos. Qwen sigue provisional; K2 no está promovido. Encuesta:26 cubiertos,716 abiertos,0 no aplicables. Full5 conserva dos fallos originales; C03 continúa abierto.
