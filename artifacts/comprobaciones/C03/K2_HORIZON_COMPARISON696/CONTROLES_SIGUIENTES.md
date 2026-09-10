# Controles después de las primeras ejecuciones

Los primeros paneles completos dan21/50 para K2 0.9B Q8 y30/50 para Qwen registrado. Son resultados del conjunto nativo congelado, sin aceptación de BAXY ni evaluación ciega. El primero conserva un razonamiento incompleto tras32768tokens. Las versiones/perfiles posteriores no reemplazarán esos resultados.

Se descargó también K2 3.7B Q8 de la misma revisión del repositorio que su Q4 para contrastar precisión; el SHA verificado es `8203991019c36dd618145aa76246097252e45283a4f75c0991a0ce902a0ad7d3`. La descarga se solapó con una parte del panel3.7Q4: hubo actividad de red/disco en segundo plano. No hubo dos servidores de inferencia simultáneos. Los tiempos son observaciones del equipo, no mediciones sobre un sistema totalmente inactivo. El registro original de cuatro pesos se conserva; el quinto tiene su propio recibo.

Controles previstos antes de elegir:

- Qwen con muestreo documentado: temperatura0,7, top-p0,8, top-k20, min-p0, sin pensamiento; contexto8192, una ranura, salida máxima4096. Ese presupuesto responde a la carga corta de BAXY; se conservará cualquier corte.
- K2 0.9B BF16 con el mismo perfil high/KVq8 que su Q8: comprobar si la cuantización de pesos explica la pérdida observada. No se lo describirá como ejecución totalmente BF16, porque la caché sigue cuantizada. Si hace falta, Q8 con cachéF16 separará el efecto de esa caché.
- K2 3.7B: terminar primero la referencia high/36864ctx/32768salida/CPU-KV. Después medir un perfil de interacción con contexto8192 y caché en GPU para reducir RAM y latencia. Los modos low/medium, si se prueban, serán experimentales para despliegue y estarán separados de la evaluación high recomendada por IFM.
- La comparación con Q8 de3.7B deberá declarar las capas en CPU que exija el límite de VRAM. No se atribuirá una diferencia de latencia exclusivamente a la cuantización si cambia la distribución entre CPU y GPU.

El repaso acotado del forward0.9B no encontró discrepancia evidente en YaRN, escala QK o normalización Q/K respecto a la configuración oficial. Eso no prueba equivalencia completa de logits. IFM valida su referencia con BF16/FlashAttention-3 en H200; las conclusiones aquí quedan limitadas al backend y perfiles comprobados en Windows.

Antes de promover el nuevo backend hay otro requisito de integración: el manifiesto actual hashea sólo `llama-server.exe`. Esta compilación usa un ejecutable pequeño y DLL de implementación; el paquete completo ya está fijado en `BACKEND_BUILD_NFC.json`, pero la validación productiva debe cubrirlo también. No se cambiará ese contrato ni se promoverá el modelo hasta que la comparación justifique hacerlo.
