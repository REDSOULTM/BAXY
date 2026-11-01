# Guiones del banco de sesión larga (noche P0.6)

`scripts/renew/bench_sesion_larga.py armar` encadena casos sueltos de los bancos de decisión en una conversación; estos
tres guiones, en cambio, son una tarde coherente de una misma persona, escrita entera, con turnos que remiten a los
anteriores («ábrelo», «ese archivo», «lo de antes»), confirmaciones en dos turnos (duda → «ya, hazlo») y lecturas
largas del dominio. Mismo formato que la sesión que arma `armar` (`version`, `turnos` con `n`, `id`, `case`, `bank`,
`category`, `family`, `text`, `expect`, y `lecturas`), así que `correr` los lee igual.

| Guion | Dominio | Turnos | Tandas de 10 |
|---|---|---|---|
| `sesion-oficina.json` | correos, documentos, calendario, tareas, notas | 50 | 5 |
| `sesion-juegos.json` | juegos, música y vídeo, audio, capturas | 45 | 5 |
| `sesion-sistema.json` | archivos, papelera, respaldos, procesos, red, ajustes | 55 | 6 |

Los escribieron subagentes que no vieron ningún diff ni ningún banco ni frase real: todo inventado, con sólo el
catálogo `catalog-final8c.json` a la vista. `family` dice qué prueba cada turno: `referencia` (remite a un turno
anterior; su expect lleva el dato que sólo ese turno dio), `confirmacion` (los dos turnos de una confirmación),
`no_puedo` (algo fuera del PC: que no diga que lo hizo), `riesgo` y `comun`.

Se corren con la misma tanda que la sesión de 50 (`<evaluacion>\noche\sesion_larga\ses.sh`, su 6.º argumento es la
sesión) y un brazo propio por guion, porque la tanda N arranca de la sesión que dejó la del mismo label:

```
bash ses.sh <worktree> oficina-base 1 10 "" F:/.../artifacts/renew/sesion_larga/sesion-oficina.json
bash ses.sh <worktree> oficina-base 11 20 "" F:/.../artifacts/renew/sesion_larga/sesion-oficina.json
...
py -3.12 -X utf8 scripts/renew/bench_sesion_larga.py resumir ses-oficina-base
```

`py -3.12 -X utf8 valida_guiones.py <worktree con scripts/renew/bench_sesion_larga.py> <guion>...` comprueba sin GPU que el runner los lee: forma,
cada operación y argumento en el catálogo, la categoría que deduce `category`, que `judge` acepta la decisión ideal de
cada turno y rechaza un «listo» donde no toca, y el cuerpo que `observation` da a lecturas y búsquedas.

`observation` da a la primera llamada del turno n el texto que empieza en `lecturas[(n*3+1) % len(lecturas)]`, por
rotación y no por lo que se pidió. Para que «mándale la hora que dice esa nota» tenga el dato, cada turno que lee lleva
`"lectura": i` (su texto en `lecturas_base`) y `coloca_lecturas.py <guion>` lo pone en la ranura que el runner lee;
las demás ranuras van por rotación. Si se edita un guion, se vuelve a pasar por `coloca_lecturas.py` y por el validador.
