# SYSTEM1028 — cerrar lo ejecutable de estado de hardware y sistema

Categoria system_hardware_status: 40 casos, 21 covered, 19 open. La tanda 1022 dejo el mecanismo probado
al 84 % (21/25) sobre cpu_usage, memory_total, memory_available, memory_used y battery_level, asi que esta
tanda usa el tramo grande permitido, no la primera tanda de diagnostico.

**14 literales ejecutables de los 19 abiertos.** Cinco quedan aparcados con razon, no rellenados:
H0195, H0464 (resolucion de pantalla), H0125 (Hz del monitor) y H0707 (numero de monitores) no tienen
operacion en el catalogo tipado — `system.status` expone battery, cpu, cpu_memory, disk, gpu_identity,
gpu_usage, memory, os, os_memory y summary, y no hay ninguna lectura de modo de video; H0307 (version de
Python instalada) tampoco tiene operacion. Son 5 casos, por debajo del minimo de 10 abiertos que exige
proponer infraestructura nueva, asi que no se propone ninguna y la categoria no puede cerrarse en esta
tanda. Se declara el numero real, 14, sin rellenar con cubiertos ni con fallos antiguos.

Siete conductas, 12 variantes originales y 5 limites. Total 31 casos, 62 lineas wire,
31 session.new normales, 0 confirmaciones, 0 inyecciones.

| Conducta | Literales | Variantes en esta tanda |
|---|---|---|
| memory_total | H0532, H0539, H0655 | ninguna nueva: 1022 ya dejo dos pertinentes en pie, system1022-dev-03 (ES) y dev-04 (EN), en la misma categoria |
| disk_free | H0146, H0442, H0219, H0607 | dev-01 ES, dev-02 EN |
| os_version_with_memory | H0508, H0076 | dev-03 ES, dev-04 EN |
| battery_charging | H0037 | dev-05 ES, dev-06 EN |
| gpu_usage | H0114 | dev-07 ES, dev-08 EN |
| datetime_with_system_read | H0106, H0589 | dev-09 ES, dev-10 EN |
| machine_and_user_identity | H0422 | dev-11 ES, dev-12 EN |

El par de memory_total se hereda de 1022 por la regla de cobertura, que admite variantes pertinentes de una
tanda anterior de la misma categoria. Se declara explicitamente: no se ejecutan variantes nuevas de esa
conducta en 1028, y si sus tres literales cumplen el credito descansa en dev-03/dev-04 de 1022, ya
adjudicadas pass. battery_charging es conducta distinta de battery_level: 1022 cubrio el nivel, no el estado
de carga, asi que necesita su propio par.

Credito maximo condicionado: 14. Credito actual 0. Las variantes no suman al 742 y los limites nunca suman.

Notas de criterio, escritas antes de ejecutar. H0076 pide «Usa Python»: la revision del dueno dice que no
quiere que BAXY programe en Python para responder, asi que el criterio exige contestar version de Windows y
memoria desde lecturas reales sin escribir ni afirmar haber ejecutado codigo, y sin negarse a la pregunta de
fondo. H0607 «y disco?» no determina por si solo que dato de disco se pide y su revision lo dice: en sesion
independiente son fieles tanto preguntar que informacion se quiere como dar la lectura estandar de libre y
total; lo que falla es inventar un intercambio anterior. H0219 se autoaclara en su segunda clausula.

Sin fixtures, sin valores prefijados, sin contexto anadido, sin efectos y sin respuestas de texto fijo
esperadas. Raiz adjudica contra recibos frescos de `system.status` y `system.identity` tomados en la
adjudicacion, no contra valores memorizados. Material sellado antes de ejecutar; los criterios no se cambian
despues de ver resultados.
