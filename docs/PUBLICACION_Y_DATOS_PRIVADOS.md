# Publicación del código y evidencia privada

El saneamiento de septiembre de 2026 retiró del historial publicado los corpus
históricos de mensajes, misiones y mapeos, las proyecciones privadas N10/M10/C10,
el corpus runtime combinado y las rutas de exportación privadas. Los datos
locales originales y el respaldo del historial se conservan fuera del remoto.
Esta separación aplica los avisos de `tests/data/TURN_EVIDENCE_DATA_NOTICE.md`
y `tests/data/GOAL10_CORPUS_NOTICE.md`.

El código del producto y sus pruebas no se modificaron para esta separación.
Los corpus públicos y sus avisos de atribución permanecen en el repositorio.
Los informes y hashes históricos describen las corridas originales: no se han
alterado para presentar el saneamiento como una nueva corrida del producto.

## Pruebas con evidencia local

Las pruebas y herramientas que consumen evidencia privada requieren los
archivos locales autorizados en las rutas esperadas. `.gitignore` impide su
inclusión accidental. Un clon público no incluye esas precondiciones y no
equivale al entorno completo de medición del mantenedor. No deben subirse
los corpus para resolver una precondición ausente, ni presentarse una prueba
no ejecutada como aprobada.

## Clones anteriores al saneamiento

El saneamiento cambió los identificadores de los commits. No se debe fusionar
el historial anterior con el público: ese merge volvería a publicar los datos
retirados. Antes del siguiente push, se deben conservar los cambios locales y
rebasar únicamente los commits de trabajo sobre las ramas saneadas, o usar un
clon nuevo y trasladar esos cambios. El respaldo privado no debe publicarse.
