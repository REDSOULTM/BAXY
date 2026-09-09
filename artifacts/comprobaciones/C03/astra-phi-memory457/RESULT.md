# 457 — Phi-4-mini,9/11 útiles; sin promoción

Plantilla nativa coincide exactamente con el tokenizer oficial para los dos
mensajes sin tools. Microsoft muestra generación greedy/max500; se usa ese
perfil por su documentación, no por copiar el default de otro modelo.
Archivo heredado R81, SHA01999f17; backend b10865. R81 sigue rechazando sus
argumentos en el workload antiguo: ésta es otra responsabilidad y otro código.

Resuelve nombres, relación de hermana y caso mixto. Falla lectura protegidaES
con negación falsa de acceso y EN con explicación genérica.9/11, todas stop.
RAM954,46MiB/GPU3390,51MiB;6,125s carga+peticiones. Sólo diagnóstico nativo,
no consumo de producto entero ni admisión de rutas/voz/aceptación fresca.

458 contrasta sólo representación de los tres casos protegidos; no hay modelo
ni fuente promovidos. Ficha/informe oficial y límites en PREREG.

## Respuestas literales

### actual437-t7

El nombre guardado en mi memoria privada es Jordan.

Útil: Conserva los datos y el alcance solicitado.

### actual437-t4

The name saved in private memory is Jordan.

Útil: Conserva los datos y el alcance solicitado.

### name-marta

El nombre guardado en mi memoria privada es Marta.

Útil: Conserva los datos y el alcance solicitado.

### compound-name

El nombre guardado en mi memoria privada es Ana María.

Útil: Conserva los datos y el alcance solicitado.

### third-person

El nombre de tu hermana es Nina.

Útil: Conserva los datos y el alcance solicitado.

### two-records

Jordan, Nina

Útil: Conserva los datos y el alcance solicitado.

### memory.enable

The memory configuration has been successfully enabled on the PC.

Útil: Conserva los datos y el alcance solicitado.

### memory.save

The memory save operation was completed successfully. No sensitive data was saved, and no corrections were made. The PC's state was updated accordingly.

Útil: Guardado correcto, con detalles innecesarios sobre sensibilidad/correcciones y estado.

### redacted-es

No tengo acceso ni capacidad para almacenar o recuperar información personal, como lo indica el dato de situación proporcionado.

Fallo: Niega acceso y capacidad de memoria pese a lectura verificada.

### redacted-en

Private memory stores sensitive information, such as passwords, personal data, and confidential communications.

Fallo: Responde qué suele almacenar la memoria; no informa el registro secreto protegido observado.

### mixed-es

En la memoria privada, se ha guardado el color favorito del usuario, que es el turquesa, y un secreto que no se ha revelado.

Útil: Conserva los datos y el alcance solicitado.
