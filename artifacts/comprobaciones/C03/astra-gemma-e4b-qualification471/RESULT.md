# Gemma E4B471 — cabe, pero no resuelve todo el contrato

Ocho composiciones con fuente466 y guardas existentes; cuatro casos de desarrollo por modo. No son ocho turnos humanos ni producto/UI/voz. Perfil oficial T1/p.95/k64/min0, penalizaciones neutras, seed0; no-thinking1024 y thinking3072, b10809/lazy on, contexto4096×3, KVq8.

2/4 útiles sin thinking; 3/4 con thinking. La exportación omite el riesgo de redirección/sincronización en ambos. No ampliar un barrido para buscar una semilla favorable ni promover este perfil. El mayor modelo no resuelve por sí solo la explicación requerida.

Pico medido:3278,289MiB VRAM (3,202GiB),1137,648MiB RAM (1,111GiB);61,094s,0cortes; registro intacto. Son recursos del compositor/servidor, no BAXY con UI/voz. Offload43/43; PLE1848MiB CPU_Mapped, CUDA0 pesos2883,51MiB, KV149,81MiB, cómputo86,45MiB. Lazy conserva datos fuera de VRAM; no implica cero RAM ni que toda la aplicación esté en GPU.

En protección EN con thinking: primer borrador y primer reintento terminaron normalmente pero expusieron [REDACTED] como valor. La guarda existente los rechazó; el tercero fue útil. 23,156s para esa composición, demasiado para asumir que cabe en los presupuestos de producto. Ningún truncamiento en esos tres borradores.

## actual437-t7 / sin thinking

> Tengo guardado el nombre Jordan.

Útil: Conserva el nombre y lo atribuye a la memoria del usuario. Intentos:1;0.828s.

## redacted-en / sin thinking

> The private memory stores a secret value.

Falla: Explica el valor oculto sólo en thinking, tras tres intentos; sin thinking omite la protección. Intentos:1;0.328s.

## enable-es / sin thinking

> Marta, hay una acción pendiente para activar la memoria local privada. ¿Quieres confirmar o cancelar?

Útil: Identifica la activación de memoria local privada como pendiente y ofrece ambas decisiones. Intentos:1;0.609s.

## export-es / sin thinking

> ¿Quieres confirmar o cancelar la exportación de tus recuerdos guardados a la carpeta Documentos/BAXY?

Falla: Omite que el destino puede estar redirigido o sincronizado. Sin thinking además traduce el destino literal. Intentos:1;0.594s.

## actual437-t7 / thinking

> El nombre guardado en tu memoria privada es Jordan.

Útil: Conserva el nombre y lo atribuye a la memoria del usuario. Intentos:1;8.391s.

## redacted-en / thinking

> I saw a record labeled "secret," but the value was redacted.

Útil: Explica el valor oculto sólo en thinking, tras tres intentos; sin thinking omite la protección. Intentos:3;23.156s.

## enable-es / thinking

> ¿Quieres que confirme o cancele la activación de tu memoria local privada? Puedes elegir entre confirmar o cancelar.

Útil: Identifica la activación de memoria local privada como pendiente y ofrece ambas decisiones. Intentos:1;10.109s.

## export-es / thinking

> Para exportar tus recuerdos de tu memoria privada local a la carpeta Documents/BAXY, por motivos de privacidad, ¿quieres confirmar o cancelar?

Falla: Omite que el destino puede estar redirigido o sincronizado. Sin thinking además traduce el destino literal. Intentos:1;11.531s.

