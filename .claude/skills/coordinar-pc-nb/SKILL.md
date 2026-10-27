---
name: coordinar-pc-nb
description: Cómo trabajan juntas las sesiones de BAXY en el PC (REDPC) y en el notebook (REDNOTE) - buzón, SSH, hub, reparto de trabajo, chequeo de privacidad antes de un push. Úsala al leer o escribir en el buzón, al repartir trabajo entre máquinas, al subir a hub o cuando la otra máquina no responde.
---

# PC y notebook

El hook de arranque dice en qué máquina estás. Las dos sesiones trabajan en paralelo; el goal dice cuál
lidera. La que lidera escribe `artifacts/renew/PROGRESO.md` y `metas.json`; la otra deja sus notas en
`artifacts/renew/PROGRESO-nb.md` y reporta por el buzón.

## Buzón

```bash
scripts/buzon.sh leer 30                  # últimas 30 líneas
scripts/buzon.sh escribir "tomo: <tarea>"  # sale con fecha y [PC] o [NB]
```

Vive en el PC; el notebook lo usa por `ssh redpc` (Tailscale). Al empezar y después de cada hito se lee.
Lo que se toma, se anuncia («tomo: …») para que nadie repita trabajo; lo que termina, con su commit y su cifra.

## Reparto

- Ninguna máquina se queda sin tarea: al terminar algo, se le da lo siguiente a la otra en el buzón.
- Cada máquina mide contra su propia base del mismo día; lo que mejora en una se confirma en la otra.
- Lo que carga la CPU o la GPU durante horas va al notebook; el PC lo usa el dueño.
- Si la otra no responde, se comprueba antes de delegar: `ssh -o ConnectTimeout=10 redpc hostname`.
  Lo que se lanza por SSH muere con la conexión: se lanza con `run_in_background` y la conexión abierta.

## Subir trabajo

1. Commits pequeños, en español, sólo los ficheros propios (nunca `git add .`).
2. **Privacidad antes de cada push.** Ningún pedido del dueño, literal o casi literal, entra en código,
   comentarios, pruebas o documentos. El chequeo corre en el PC, que tiene los pedidos reales:
   ```bash
   git diff <base>..<rama> | ssh redpc "py -I F:/BAXYeval/reales_v1/privacidad.py"
   ```
   (En el PC, sin `ssh redpc`.) Un aviso se arregla describiendo el pedido en general, no se ignora.
3. Push sólo a `hub` (`redpc:C:/Users/usuario/BAXY-coord/renew.git`). A GitHub (`origin`) únicamente si el dueño
   lo pide. Nada se fusiona en las ramas que integran sin su «adelante».
