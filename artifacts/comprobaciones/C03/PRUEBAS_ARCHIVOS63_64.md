# C03 — límite de consulta y fallo de recuperación63–64

Ambos paneles:2/5 útiles. Controles técnicos consumidos, no humanos reservados ni UI/audio. 63 conserva la causa real del primer pedido, pero las lecturas siguientes se rechazan. 64 reproduce con captura HTTP de sólo observación. No aprobación integral del cambio.

## files63-absolute

{
  "exitCode": 0,
  "stopReason": null,
  "elapsedSeconds": 72.11,
  "gpuPeakMiB": 3497.55859375,
  "gpuAttributionAvailable": true,
  "ramPeakMiB": 5228.2578125,
  "registrationUnchanged": true
}

### t1

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final (published_final): No pude leer el archivo porque el sistema no soporta la búsqueda por ruta absoluta.

Útil: causa específica verificada, sin afirmar inexistencia del archivo.

### t2

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final (published_final): Este pedido está fuera de mis funciones en este equipo.

No útil: negativa sin causa específica ante lectura del catálogo o pérdida del límite conocido.

### t3

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final (published_final): This is outside what I do on this PC.

No útil: negativa sin causa específica ante lectura del catálogo o pérdida del límite conocido.

### t4

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final (published_final): Este pedido está fuera de lo que hago en este PC.

No útil: negativa sin causa específica ante lectura del catálogo o pérdida del límite conocido.

### t5

Entrada: Dime la hora.

Final (published_final): Son las 02:30.

Útil: hora verificada, sesión disponible.

[Hechos, borradores, vetos y estado posterior](astra-files63-absolute/paired.json).

## files64-wire

{
  "exitCode": 0,
  "stopReason": null,
  "elapsedSeconds": 73.06,
  "gpuPeakMiB": 3497.55859375,
  "gpuAttributionAvailable": true,
  "ramPeakMiB": 5537.2734375,
  "registrationUnchanged": true
}

### t1

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final (published_final): No pude leer el archivo porque el sistema no soporta la búsqueda por ruta absoluta.

Útil: causa específica verificada, sin afirmar inexistencia del archivo.

### t2

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final (published_final): Este pedido está fuera de mis funciones en este equipo.

No útil: negativa sin causa específica ante lectura del catálogo o pérdida del límite conocido.

### t3

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final (published_final): This is outside what I do on this PC.

No útil: negativa sin causa específica ante lectura del catálogo o pérdida del límite conocido.

### t4

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final (published_final): Este pedido está fuera de lo que hago en este PC.

No útil: negativa sin causa específica ante lectura del catálogo o pérdida del límite conocido.

### t5

Entrada: Dime la hora.

Final (published_final): Son las 02:33.

Útil: hora verificada, sesión disponible.

[Hechos, borradores, vetos y estado posterior](astra-files64-wire/paired.json).

El selector elige search para leer en t2/t3; domain_grounding rechaza esa operación insuficiente. T4 no propone operación. El catálogo conserva read.text. La causa del selector se compara en65 con los mismos cuatro payloads nativos; t5 usa ruta determinista y no tiene paquete AUTO.

Proveedor:8 pass/0 skips/119ms; integración:152 pass/0 skips/8s. Core AOT publicado6368exit0, hash fe2c1cfc351abf78bd4d5080fd651eaec2e5915f83b82a30613a57df40e48fed. Modelo/registro sin cambios. Fast63/Full pendientes; Full no corresponde durante reparación.
