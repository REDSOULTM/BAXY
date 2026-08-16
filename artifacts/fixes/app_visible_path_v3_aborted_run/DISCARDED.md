# Corrida descartada del harness de camino visible

Estas trazas son de una corrida de `scripts/measure_app_visible_path.ps1` que se
detuvo a propósito y **no debe usarse como medición**.

Motivo: en esa versión del harness, un bloque *warm* que tenía que arrancar su
propio proceso enviaba un turno de calentamiento que la traza registra como un
turno más, pero el índice no lo declaraba. Como la atribución es por posición
dentro del bloque, ese turno habría desplazado un lugar a los cinco escenarios
de ese bloque y habría contaminado el brazo caliente.

La corrección fue declarar `warmup_turns` en cada bloque del índice y consumirlos
en `scripts/summarize_app_visible_path.py` antes de atribuir escenarios. La
corrida buena, con esa corrección, está en `../app_visible_path_v3/`.

Se conservan los archivos crudos sólo como registro de que la corrida existió y
por qué se descartó. No hay `index-*.json` para ellos, así que el resumidor no
puede procesarlos aunque se intente.
