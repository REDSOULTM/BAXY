# Copia exacta del repositorio — comprobación 741

La prueba original pasó: **1 pass, 0 fallos, 0 skips en 21,72 s**, con su límite
de 45 s intacto. Se ejecutó con una traza Git local; no se modificaron la prueba,
el helper, los filtros LFS ni los archivos que se materializan. La copia fue
eliminada y permanecen sólo el worktree de trabajo y el de recuperación anterior.

La traza mide 14,159 s en `git worktree add` y 2,833 s en `remove`; dentro del
checkout, actualizar archivos consume 12,406 s. El proceso del filtro LFS vive
3,580 s, que incluyen esperas: no equivalen al coste de copiar un solo archivo.
La hipótesis de que el LFS de 304,7 MB explica los fallos anteriores queda sin
probar. Antes había 6,018 GiB de RAM disponibles; tampoco se ha aislado la RAM
como causa. Los timeouts anteriores se conservan como resultados válidos.

Este resultado permite comprobar ahora el candidato completo. No sustituye Full
ni certifica que el empaquetado siempre vaya a cumplir bajo cualquier carga.
