# C03 — tipos de error y diagnóstico55

Controles técnicos, no reserva humana ni UI/audio. Ambos paneles:1/5 útil, sólo la hora.

## files55-trace

exit0;82.12s;GPU3497.56MiB;RAM4539.06MiB;registro intacto=True.

### t1

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final (published_final): No pude leer el archivo porque el resultado no se verificó.

No útil: la causa no permite resolver el pedido o falta prosa final. Encontrar una entrada no basta para afirmar que se leyó. El progreso de t3 en reason infiere UTF8 del nombre antes de una observación.

### t2

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final (composition_failed): composition_failed

No útil: la causa no permite resolver el pedido o falta prosa final. Encontrar una entrada no basta para afirmar que se leyó. El progreso de t3 en reason infiere UTF8 del nombre antes de una observación.

### t3

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final (composition_failed): composition_failed

No útil: la causa no permite resolver el pedido o falta prosa final. Encontrar una entrada no basta para afirmar que se leyó. El progreso de t3 en reason infiere UTF8 del nombre antes de una observación.

### t4

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final (published_final): No pude leer el archivo porque el resultado no se verificó.

No útil: la causa no permite resolver el pedido o falta prosa final. Encontrar una entrada no basta para afirmar que se leyó. El progreso de t3 en reason infiere UTF8 del nombre antes de una observación.

### t5

Entrada: Dime la hora.

Final (published_final): 01:32

Útil: hora observada y sesión recuperada.

[Hechos, borradores y vetos](astra-files55-trace/paired.json).

## files55-reason

exit0;80.09s;GPU3497.56MiB;RAM4893.38MiB;registro intacto=True.

### t1

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final (published_final): No pude buscar el archivo porque no hay datos sobre la búsqueda en el sistema.

No útil: la causa no permite resolver el pedido o falta prosa final. Encontrar una entrada no basta para afirmar que se leyó. El progreso de t3 en reason infiere UTF8 del nombre antes de una observación.

### t2

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final (published_final): No pude leer el contenido del archivo porque no hay datos disponibles.

No útil: la causa no permite resolver el pedido o falta prosa final. Encontrar una entrada no basta para afirmar que se leyó. El progreso de t3 en reason infiere UTF8 del nombre antes de una observación.

### t3

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final (composition_failed): composition_failed

No útil: la causa no permite resolver el pedido o falta prosa final. Encontrar una entrada no basta para afirmar que se leyó. El progreso de t3 en reason infiere UTF8 del nombre antes de una observación.

### t4

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final (published_final): No pude encontrar el archivo porque no hay datos de búsqueda disponibles.

No útil: la causa no permite resolver el pedido o falta prosa final. Encontrar una entrada no basta para afirmar que se leyó. El progreso de t3 en reason infiere UTF8 del nombre antes de una observación.

### t5

Entrada: Dime la hora.

Final (published_final): 01:36

Útil: hora observada y sesión recuperada.

[Hechos, borradores y vetos](astra-files55-reason/paired.json).
