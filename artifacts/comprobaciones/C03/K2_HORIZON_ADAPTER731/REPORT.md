# Una opción de BAXY perjudica el perfil local de K2

El mismo K2 3.7B Q4 pasó de **38/50 a 19/50** al añadir únicamente `enable_thinking=false`, la opción que envía el selector actual de BAXY. Un segundo lector aceptaría una reescritura fronteriza y elevaría el resultado a 20/50; la discrepancia y los dos razonamientos se conservan. El resultado justifica corregir esa adaptación antes de juzgar K2 dentro del producto. No justifica descartar K2 ni declara que todas las reglas favorezcan a Qwen.

Se conservaron las 50 tareas sintéticas de 699 completas, pesos, backend, orden, semilla, muestreo T=1 y top_p=0,95, contexto de 8192 tokens, salida de 4096 tokens y servidor con razonamiento alto. Cada petición cambió sólo esa clave. El servidor verificó 50/50 prefijos: el nuevo flag añade el cierre del razonamiento; los prefijos originales coinciden exactamente con los 50 guardados en 699. El método real `_post` conserva intactas esas50 peticiones nativas; no tenían varios mensajes system. La fusión de múltiples systems no queda evaluada por esta igualdad.

La receta oficial K2 recomienda razonamiento alto y al menos32768 tokens de margen de salida. El perfil de 8k/4096 es el práctico ya medido, no la receta de evaluación oficial completa. El servidor siguió en high/on con presupuesto-1 para aislar la opción de la petición; no se añadieron además los flags off/budget0, temperatura0 o256 tokens de BAXY. [Ficha oficial](https://huggingface.co/IFM/K2-Horizon-3.7B#best-practices).

| Medida | Perfil high699 | Mismo perfil +flag de BAXY |
|---|---:|---:|
| Respuestas que cumplen | 38/50 | 19/50 (20 si se acepta el fronterizo) |
| Primer texto, mediana | 6.078s | 0.281s |
| Final, mediana | 8.828s | 2.195s |
| Final más lento | 74.782s | 129.203s |
| VRAM pico del servidor | 3444.23MiB | 3444.23MiB |
| RAM pico del servidor | 787.56MiB | 787.10MiB |

Comparación por caso: **3 mejoras, 22 pérdidas y 9 fallos compartidos**. Español: 22/30→8/30; inglés: 12/15→9/15; mezcla: 4/5→2/5. Los tres finales truncados del perfil modificado cuentan como fallos; una apertura correcta seguida de falsedades tampoco aprueba.

Los veredictos nuevos se sellaron antes de unir los anteriores. Se reutilizó un control histórico de una semilla: no es una réplica aleatorizada ni una medida universal de causalidad o calidad. Los picos se muestrean cada 250 ms y corresponden sólo al árbol del servidor; no acreditan UI/voz ni el techo conjunto del producto. La tanda terminó 50/50, exit 0, sin infracciones del guardián de recursos; después el conductor cerró su servidor. Runtime registrado y fuente de BAXY quedaron intactos.


Dos pérdidas concretas, con las mismas entradas: ante 10 GiB utilizables y 8 GiB usados, high respondió 2 GiB libres; con el flag respondió «0 GiB libre (10 GiB - 8 GiB).». Ante 500 GB totales y 125 GB libres, high conservó 125 GB; con el flag afirmó 0 GB libres. Las dos parejas constan en context-01 y facts-19 y en las respuestas nativas de 699 originales.

**Decisión:** K2 debe conservar razonamiento nativo en su adaptador experimental. La comparación integrada sigue pendiente: hay que mantener su receta también en los demás roles y comprobar la primera transformación incorrecta en catálogo, argumentos, validación y publicación. Qwen permanece provisional. Ninguna adopción ni crédito de encuesta: 26 cubiertos, 716 abiertos y 0 no aplicables; C03 sigue abierto.

[Entradas y respuestas completas](RESPUESTAS.md) · [Resumen y pares](SUMMARY.json) · [Criterios originales](../K2_HORIZON_NATIVE699/PANEL.json) · [Adjudicación previa a la comparación](ADJUDICATION.json).
