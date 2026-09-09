# 479 — Q8 no llegó a la fase de calidad

Q4/NGL26 completó16composiciones:4/4controles memoria,2/6confirmaciones porsemilla, mismosfallos que468. RAM1685,543MiB/GPU2631,398MiB,29,703s. Mantener baseline parcial separado del allGPU468.

Q8 se detuvo en carga a3800,535MiB GPU por guardia3800;RAM2176,441MiB,5,5s,0composiciones. No superó el techo4096MiB, pero consumió el margen de diagnóstico. No hay respuestaQ8 ni juicio de calidad. Registro intacto. No recortar precisión/contexto ni subir guardia.

Búferes exactosQ8:2951,28MiB pesosCUDA0,1519,27MiB pesosCUDA_Host,KV637,50MiBGPU+280,50MiBCPU,compute94,73MiBGPU. Offload real26/37 =25capas repetidas+salida. No asumir que NGL26 excluye la salida: el backend la descarga antes.

480 conservaNGL26/contexto4096×3/KVq8/b2048 y reduce microbatch256→128 enAMBAS precisiones. Motivo medido: reducir compute temporal sin pasar más pesos aCPU (que gastaría RAM y tiempo). La cualificación guarda comando efectivo antes de arrancar incluso si corta. Si aún no cabe, registrar corte y revisar asignación con estosbúferes, no ocultarlo.

## Q4 actual437-t7 / semilla0

> Jordan

Útil: Valor correcto.

## Q4 redacted-en / semilla0

> The private memory contains a secret entry with a redacted value.

Útil: Registro y protección correctos.

## Q4 actual-enable-en / semilla0

> Alright, Jordan. I remember your name. We’re about to enable private local memory. Do you want to confirm or cancel this action?

Útil: Activación pendiente y opciones, conocer el nombre no es persistirlo.

## Q4 enable-es / semilla0

> ¿Quieres confirmar o cancelar?

Falla: Sólo opciones, omite acción.

## Q4 forget-es / semilla0

> ¿Quieres confirmar o cancelar?

Falla: Sólo opciones, omite acción/consecuencia.

## Q4 forget-en / semilla0

> Do you want to confirm or cancel forgetting your favorite color?

Falla: Omisión de irreversibilidad.

## Q4 sensitive-en / semilla0

> Do you want to confirm or cancel saving your secret in private local memory?

Útil: Naturaleza sensible, memoria privada y decisión.

## Q4 export-es / semilla0

> ¿Quieres confirmar o cancelar la exportación de tus recuerdos guardados?

Falla: Omite destino y sync.

## Q4 actual437-t7 / semilla17

> Jordan

Útil: Valor correcto.

## Q4 redacted-en / semilla17

> The private memory contains a secret entry with a redacted value.

Útil: Registro y protección correctos.

## Q4 actual-enable-en / semilla17

> Alright, Jordan. I remember your name. We're about to enable private local memory. Do you want to confirm or cancel this action?

Útil: Activación pendiente y opciones, conocer el nombre no es persistirlo.

## Q4 enable-es / semilla17

> ¿Quieres confirmar o cancelar?

Falla: Sólo opciones, omite acción.

## Q4 forget-es / semilla17

> ¿Quieres confirmar o cancelar?

Falla: Sólo opciones, omite acción/consecuencia.

## Q4 forget-en / semilla17

> Do you want to confirm or cancel forgetting your favorite color?

Falla: Omisión de irreversibilidad.

## Q4 sensitive-en / semilla17

> Do you want to confirm or cancel saving your secret in private local memory?

Útil: Naturaleza sensible, memoria privada y decisión.

## Q4 export-es / semilla17

> ¿Quieres confirmar o cancelar la exportación de tus recuerdos guardados?

Falla: Omite destino y sync.

