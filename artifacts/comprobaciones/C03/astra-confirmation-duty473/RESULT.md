# 473 — obligación genérica no se adopta

Doce composiciones,3/6 útiles en semilla0 y2/6 en17. Respecto465/467 no hay mejora global: recupera eliminación pero inventa riesgos al activar/guardar, y exporta en presente o confunde destino. Misma sustitución472, sin variante de redacción. No insistir con la obligación genérica de consecuencias ni añadir filtros por frases. Fuente466 permanece.

Primeros payloads idénticos a465/467 antes de la sustitución. PicoGPU1692,184MiB/RAM993,469MiB,61,25s,0cortes;registro intacto. No UI/audio/efectos/reserva.

## actual-enable-en / semilla0

> Got it, Jordan. I'll remember your name.

Before we do that, I need your confirmation. Enabling private local memory will allow me to recall information for you; you can either confirm this action or cancel it. Which choice do you want to make? Confirm or cancel?

Útil: Explica activar memoria antes de guardar, con opciones; largo.

## enable-es / semilla0

> Espera un momento. La acción pendiente es habilitar la memoria y el objetivo es tu memoria local. La razón es que lo solicitaste. Las consecuencias posibles son: puedes usar esa memoria ahora, pero también podrías perder datos si la habilitas sin querer. ¿Qué opción deseas tomar: confirmar o cancelar?

Falla: Inventa pérdida de datos por activar memoria.

## forget-es / semilla0

> Eso lo puedo olvidar de tu memoria local. La razón por la que necesitas confirmarlo es que esta acción no se puede revertir. Hay dos opciones disponibles: confirmar o cancelar. ¿Cuál eliges?

Útil: Acción y carácter irreversible con opciones.

## forget-en / semilla0

> I'm about to forget your favorite color in your private local memory. You can't undo this action. Which choice do you want to make: confirm or cancel?

Útil: Acción pendiente, irreversibilidad y opciones.

## sensitive-en / semilla0

> I can save your secret, but this is a memory-sensitive operation targeting your private local memory. You need to confirm you want to proceed because this action cannot be undone. Which choice do you want: confirm or cancel?

Falla: Inventa irreversibilidad al guardar un dato sensible.

## export-es / semilla0

> Estoy exportando tus recuerdos a una memoria local privada. Te lo hago por privacidad, pero puede redirigirte a otra ubicación o sincronizarla. ¿Querés confirmar o cancelar?

Falla: Afirma exportación en curso, confunde destino y omite Documents/BAXY.

## actual-enable-en / semilla17

> Got it, I remember your name is Jordan.

I am currently pending the action to enable private local memory. The reason you provided for confirmation is "memory enable." As a consequence, this action will make that memory available to me.

Which choice do you want to make: confirm or cancel?

Falla: Expone memory enable como razón interna; prosa impropia de BAXY.

## enable-es / semilla17

> Quiero que guarde tu nombre. La acción pendiente es habilitar la memoria local, y el objetivo es guardar "Marta". La razón para la confirmación es que queres que recuerde tu nombre. Una posible consecuencia es que esa información quede almacenada localmente; no es un hecho observado. ¿Qué opción prefieres: confirmar o cancelar?

Falla: Cambia sujeto a Quiero que guarde y propósito a guardar nombre en lugar de explicar autorización de habilitación.

## forget-es / semilla17

> Te puedo olvidar tu color favorito, pero esta acción no es reversible y elimina esa información de tu memoria local. ¿Querés confirmar o cancelar?

Útil: Conserva irreversibilidad, destino memoria y opciones; gramática mejorable.

## forget-en / semilla17

> I can forget your favorite color, but this action cannot be undone and it will be permanently deleted from your private local memory. Would you like to confirm this action, or cancel it?

Útil: Conserva acción e irreversibilidad.

## sensitive-en / semilla17

> I need you to confirm this action because saving sensitive information in your private local memory is irreversible. If you cancel, nothing will be saved. Which choice do you want to make: confirm or cancel?

Falla: Inventa irreversibilidad de almacenamiento.

## export-es / semilla17

> Es una acción pendiente: exportar tus recuerdos a la memoria local privada. La razón para la confirmación es la privacidad. Las posibles consecuencias son que se te pueda redirigir o sincronizar. ¿Qué opción prefieres: confirmar o cancelar?

Falla: Confunde destino con memoria local, omite destino literal y atribuye redirección/sync a la persona.

