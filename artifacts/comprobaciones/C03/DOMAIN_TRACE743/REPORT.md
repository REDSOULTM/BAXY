# Primera pérdida de las propuestas — seguimiento 743

Se recorrieron sin inferencia 63 controles: los tres rechazos nativos capturados
en 736 y los 60 textos de dominio conservados de 707. No se editaron fuentes,
no se ejecutaron operaciones y no se añade cobertura de la encuesta. La fuente
se mantiene congelada durante Full6. El resultado de dominio coincide con la
expectativa en 28 controles; esto no es una puntuación del modelo ni del producto.

| Caso capturado | Primera condición que retira la propuesta |
|---|---|
| H0023 | `_window_domain` rechaza el plural antes de identificar el sujeto |
| H0103 | `_window_domain` rechaza el plural antes de identificar el sujeto |
| disk-used-es | `_is_direct_request` devuelve false; `_system_status_domain` devuelve true y `_machine_status_scope` conserva disk |

La petición de disco antepone el tema a su verbo. Se reconoce el dominio, pero
la prueba de acto de habla requiere una cabecera que ese orden no satisface.
Eso acota la reparación al análisis de la petición; no justifica una excepción
para todas las lecturas ni cambiar los datos o la respuesta del modelo.

Tampoco basta añadir una `s` a ventanas: el prototipo 707 obtuvo 15 mejoras,
una pérdida, 17 peticiones válidas aún rechazadas y un falso dominio físico.
Se conserva ese rechazo. Una reparación posterior debe conservar negación,
citas, estado hipotético y distinción entre ventanas del PC y otros sentidos,
y conectar la solicitud con el inventario paginado de 730. El resultado actual
no autoriza adoptar ese prototipo ni presenta 730 como integración terminada.

Las trazas literales permanecen en el directorio privado local
`C03-domain-trace743-private/traces.json`; RESULT y DISK_CAUSE identifican
las funciones, entradas previas y hashes. Full6 sigue siendo la siguiente
comprobación que debe recogerse antes de editar el árbol validado.
