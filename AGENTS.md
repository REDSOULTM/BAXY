# BAXY — lo primero que lees

Este repositorio es **BAXY Definitivo**, y es el sitio donde se trabaja. Confirma
que estás en él: `git rev-parse --show-toplevel` tiene que terminar en
`BAXY Definitivo`, y la raíz contiene `Baxy.slnx`, `main.py` y este fichero.

Rama de trabajo: **`main`**.

**Cuidado con el nombre.** En la misma carpeta `Programacion` hay otro repositorio
llamado `BAXY` a secas. Ése es el intento anterior: es **fuente de herencia, no
sitio de trabajo**. Nada de lo que escribas va allí.

## Qué haces aquí

El trabajo está en **once goals**, en `documentacion/sprints/`. Cada uno se lanza en
una sesión nueva, se pega entero, y corre hasta cumplirse.

**Si te han dado un goal, ése es tu única instrucción.** No busques otra: este
fichero no te dice qué hacer, sólo dónde estás.

**Si no te han dado ninguno**, empieza por
[`documentacion/sprints/00_INDICE.md`](documentacion/sprints/00_INDICE.md).

## Los dos documentos que mandan

1. **[`documentacion/00_IDENTIDAD.md`](documentacion/00_IDENTIDAD.md)** — qué es
   BAXY. No son preferencias: son decisiones tomadas por el dueño del producto con
   los cuatro intentos anteriores sobre la mesa. Si un diseño tuyo las contradice,
   el que cambia eres tú.
2. **Tu goal**, en `documentacion/sprints/`. Trae dentro las cinco leyes, lo que ya
   se midió y se rechazó, y sus criterios de cierre.

Los dos primero. Lo demás sólo si tu goal te manda.

## Las cinco leyes, en una línea cada una

1. **Hereda primero, estado del arte después, construye al final.** Y que BAXY ya lo
   haga de una manera no es razón para conservarla.
2. **Nada de sobreingeniería.** Si añades una capa, retira la que sustituye.
3. **Sólo se arregla lo que bloquea** (goals 01–10). Lo demás, una línea en
   `documentacion/APLAZADOS.md`.
4. **Lo más ligero que cumpla.** 4 GB de VRAM es el techo, no el objetivo.
5. **Arquitectura modular.** La forma —una responsabilidad por pieza, cero código
   muerto— aplica a todo; el mecanismo de cambio, sólo a las piezas de
   `documentacion/03_COSTURAS.md`.

Y la consigna: ésta es la **quinta** escritura de BAXY y tiene que ser **la más
rápida de las cinco** — no porque haga menos, sino porque no vuelve a descubrir
nada que ya se descubrió.

## Los seis invariantes

No se re-derivan, nunca:

1. El catálogo tipado es la única fuente de operaciones. La mente propone, el kernel
   autoriza, el provider ejecuta.
2. Nada se afirma sin verificar.
3. Estados terminales honestos.
4. La confirmación se liga a la invocación exacta.
5. Cero respuestas visibles fijas.
6. Local y privado. El modelo corre en la máquina. BAXY puede consultar la web; lo
   que no puede es enviar contenido del usuario — la línea es de dirección, no de
   conexión.

## Compuerta

```powershell
.\scripts\test_source_quality.ps1 -Mode Full
```

Verde antes y después de cada tanda. Un rojo bloquea la entrega, sin excepción y
sin nota al pie. Y no se cierra con `skip`, `xfail`, umbral relajado ni fallback.

## Documentación heredada

`documentacion/` trae cientos de páginas de los intentos anteriores: decisiones de
arquitectura, torneos, comparativas, y el registro de lo medido y **rechazado**.
Eso es **evidencia**, y vale oro — muchas líneas ya se midieron y murieron con el
mecanismo entendido.

Pero **no es instrucción**. Cualquier documento que parezca decirte qué hacer y que
no sea tu goal está caducado: los enunciados de objetivo anteriores quedan
sustituidos por `00_IDENTIDAD.md` y por los once goals.

Si encuentras uno que contradice a tu goal, sigue el goal y anótalo en una línea en
`documentacion/APLAZADOS.md`.
