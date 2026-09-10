# Separar la capacidad del modelo de los errores de BAXY

La preocupación del dueño es correcta: probar un modelo solo dentro de BAXY mezcla su capacidad con el efecto de los prompts, la selección, los datos recibidos, los validadores, los reintentos y el transporte. No se atribuye un fallo al modelo sin localizar dónde aparece. Tampoco está demostrado que todas las reglas sean específicas de Qwen.

Hay tres clases de evidencia, con alcances distintos:

| Prueba | Qué se comparó | Qué permite concluir |
|---|---|---|
| [Nativa699](K2_HORIZON_NATIVE699/REPORTE699.md) | Las mismas50 tareas por cada uno de6 perfiles:300 respuestas, sin instrucciones, herramientas ni schema de BAXY; plantilla y receta propias | Capacidad de los perfiles locales medidos. Qwen práctico40/50, K2 high práctico38/50. La diferencia no demuestra un ganador universal. |
| [Prompt737](FACTS_PROMPT737/REPORT.md) | K2 en ambos brazos, mismas57 preguntas y hechos; entrada directa frente al prompt de redacción de BAXY, sin el resto de capas | El prompt completo mejoró14 casos y perdió3 que eran correctos directamente;25 aciertos compartidos. El agregado mejora, pero existen pérdidas concretas. |
| [Compositor790](INVENTORY_COMPOSER790/REPORT.md) y diagnóstico792 | Integración actual con Qwen; validación y reintentos activos | Localizar errores de BAXY y probar una intervención concreta. No constituye una nueva selección K2 frente a Qwen. |

Las primeras860 respuestas de696–698 conservaban instrucciones de BAXY; llamarlas por una API nativa no las convierte en una referencia independiente. La prueba699 corrigió esa limitación. Cada perfil recibió el conjunto completo; no se repartió la mitad de las preguntas entre modelos.

"Nativo" describe aquí la ausencia de BAXY, no pesos sin cuantizar ni equivalencia demostrada con el stack de referencia del fabricante. Los informes conservan los hashes, cuantización, backend y límites de contexto. No está acreditada paridad completa de logits o calidad con BF16/SGLang.

El método de continuación es: referencia nativa con receta propia, integración por componentes sobre los mismos casos y registro de la primera pérdida. Una transformación que perjudica a K2 se revisa como integración; no basta para descartar K2. La selección final debe considerar calidad completa, español/inglés, latencia, RAM y VRAM conjunta bajo4GiB. Ni el banco dirigido de50 tareas ni los picos del servidor sustituyen la aceptación final del producto.
