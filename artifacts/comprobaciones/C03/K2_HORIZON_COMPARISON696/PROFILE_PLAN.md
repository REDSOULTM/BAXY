# Comparación real K2 Horizon / Qwen — plan anterior a resultados

Orden solicitado por el dueño: detener reparaciones/tandas de Qwen y comparar K2 realmente antes de seleccionar el modelo para seguir C03. La tanda694 ya terminó; se conserva sin adoptar693. No hay promoción por expectativas ni por este plan.

Los cuatro GGUF descargados están fijados por revisión, bytes y SHA256 en WEIGHTS.json. El backend IFM35999d1 se compila aislado para Windows, CUDA13.0.88 y SM86. El runtime registrado permanece disponible. Preparación no equivale a inferencia.

El panel consta de50peticiones:20selecciones de operación y30de prosa/conversación. Capturas694/521 y variantes nuevas están diferenciadas; ninguna se presenta como aceptación humana fresca. PANEL_PLAN.json conserva criterios e índice; mensajes y observaciones completos permanecen privados. En los paquetes que omiten una herramienta necesaria, abstenerse delimita correctamente al modelo pero no acredita la capacidad de BAXY. No se puntuará una lectura inventada como mejora.

## Perfiles a medir

| Perfil | Configuración prevista | Propósito |
|---|---|---|
| K2 0.9B Q8 | high; T0,6/top-p0,95; salida32768; contexto36864;1slot; KVq8; FA;512/128batch | Verificar carga y parser, luego primera comparación |
| K2 0.9B BF16 | Mismo perfil de referencia | Comprobar que una pérdida no proviene de cuantización |
| K2 0.9B Q4 | Mismo perfil tras compatibilidad | Medir ahorro y pérdida de calidad, sin presuponer equivalencia |
| K2 3.7B Q4 referencia | high; T1/top-p0,95; salida32768; contexto36864;1slot; KVq8; FA;512/128batch; caché o capas en CPU si exige el presupuesto | Darle presupuesto de razonamiento recomendado y medir el coste RAM/latencia |
| K2 3.7B Q4 interactivo | Ajustar concurrencia/contexto/batch o esfuerzo sólo después de la referencia; fijar antes de ejecutar | Determinar si conserva calidad dentro del presupuesto del producto |
| Qwen registrado | Backend b9980 y perfil registrado:3slots×4096, KVq8, sin razonamiento, payloads originales | Línea base real del candidato actual |
| Qwen documentado | T0,7/top-p0,8/top-k20/min-p0; no pensamiento; contexto y presupuesto de salida explícitos según la carga | Evitar descartar Qwen por un perfil desfavorable |

Los parámetros son específicos de cada modelo. La comparación de geometrías distintas se declarará: una prueba secuencial nativa no mide concurrencia del producto. No se forzará a K2 a los presupuestos breves de Qwen. Una salida cortada sigue siendo incompleta y exige investigar contexto/presupuesto, no declarar incapaz al modelo.

Referencias de configuración: [K2 0.9B](https://huggingface.co/IFM/K2-Horizon-0.9B), [K2 3.7B](https://huggingface.co/IFM/K2-Horizon-3.7B), [Qwen2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507). Son referencias de autores; la receta llama.cpp/Windows necesita comprobación propia. El conversor GGUF conserva en0.9B YaRN factor16/base8192/betas128y4; en3.7B RoPEbase10000000, coincidentes con los config oficiales examinados.

## Qué contará como evidencia

Primero se observarán respuesta española con hechos, JSON Schema y llamada de herramienta. El autoparser dinámico del fork puede inferir delimitadores de razonamiento desde la plantilla; la ausencia de un parser dedicado por nombre no prueba incompatibilidad. Se conservarán stream y campos nativos para verificarlo.

Después se registrarán las50salidas por perfil, sin corregirlas antes de juzgar: operación solicitada, alcance/negación, hechos y unidades, sujeto, orden, idioma, brevedad, causa del error y ausencia de acciones inventadas. Los tiempos separarán primer token de razonamiento, primer contenido y final. Se medirán RAM/VRAM del proceso y arranque; no se describirá el servidor aislado como consumo de todo BAXY.

El límite preventivo de la corrida es3800MiB de VRAM atribuida y768MiB libres de RAM. No se utiliza la memoria física extra de la GPU para declarar que cabe bajo el techo de4GiB. Un aborto de recursos conserva su causa y conduce a otro perfil justificado; no es un fallo semántico del modelo.

Un candidato prometedor debe atravesar después BAXY real: extracción/validación de argumentos, kernel, provider, prosa, interfaz y voz. Se fijarán hashes y una restauración comprobada antes de promoverlo. C03 y sus742requisitos permanecen completos y abiertos mientras esa evidencia falte.
