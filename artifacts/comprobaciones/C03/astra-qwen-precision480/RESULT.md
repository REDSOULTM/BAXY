# 480 — microbatch no da margen suficiente

Q4completa16respuestas,4/4controles y2/6confirmaciones porsemilla. Q8noinfiere:
GPU3802,535MiB activa guardia3800;RAM2213,746MiB,6,266s. El búfer compute síbajó
94,73→84,15MiB, pero el pico real no bajó lo suficiente. No insistir conmicrobatch
ni relajar guardia. Fuente/registrointactos; no valoración de calidadQ8.

481 cambiaNGL26→24 enambasprecisiones, conservaub128,contexto/KV/sampler.
Q8secalificaPRIMERO, antesderepetirbaselineQ4: se evita volver a gastar16turnos
baseline si la variante aún no carga. TrasladarcapasconsumeRAM; reportarlo.
El criterio4GB y la guardia3800 siguenintactos.

## Q4 actual437-t7 / semilla0

> Jordan

Útil: Valor correcto.

## Q4 redacted-en / semilla0

> The private memory contains a secret value that has been redacted.

Útil: Registro y protección correctos.

## Q4 actual-enable-en / semilla0

> Alright, Jordan. I remember your name. We're about to enable private local memory. Do you want to confirm or cancel this action?

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

> A secret value is stored in private memory, with the exact content redacted.

Útil: Registro y protección correctos.

## Q4 actual-enable-en / semilla17

> Alright, Jordan. I remember your name. We're about to enable private local memory. Do you want to confirm this action or cancel it? Choose: confirm, cancel.

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

