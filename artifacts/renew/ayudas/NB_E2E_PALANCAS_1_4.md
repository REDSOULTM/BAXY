# Palancas 1-4 juntas: e2e s0-2 pareado en el notebook (2026-10-19)

- **Brazos:** A = producto de partida `e0a7d9923` (worktree l2, recompilado); B = `hub/pc-ayudas` `a3af5c20f`
  (palancas 1-4 sin interruptor; worktree aparte, Release). Comprobado que el `baxy-core.exe` publicado de B lleva los
  campos nuevos y el de A no. Mente, lanzador y banco idénticos en los dos.
- **Modelo:** c2-e1.0 (`BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf`), leído de la línea de llama-server en cada corrida.
- **Banco:** `bench_e2e.py` de nb-ayudas (con `utterances()`), copiado como `bench_e2e_ay.py` a los dos worktrees;
  `bench.ps1` c684edba; `practice.json` (30 casos).
- **Orden:** A s0, B s0, A s1, B s1, A s2, B s2 (15:14-16:22), frente comprobado antes de cada corrida y por caso.
- **Guiones:** `scripts/renew/notebook/ayudas/` (`ab_e2e.sh`, `pareado_ab.py`, `campos.py`).

## Cifras

| Semilla | A | B | Δ | suben | bajan | McNemar |
|---|---|---|---|---|---|---|
| s0 | 24 | 26 | +2 (IC95 [0, +5]) | E015, E024 | — | 2/0, p=0,50 |
| s1 | 23 | 25 | +2 (IC95 [0, +5]) | E011, E023 | — | 2/0, p=0,50 |
| s2 | 25 | 25 | 0 (IC95 [-3, +3]) | E024 | E015 | 1/1, p=1,0 |
| s0-2 (media por ítem) | 24,00 | 25,33 | +1,33 (IC95 [0, +3]) | E024 (mayoría) | — | 1/0, p=1,0 |

- **Puerta:** E011 A 2/3, B 3/3; E017 3/3 en los dos; E024 A 1/3, B 3/3. E020 y E006: 0/3 en los dos.
- **Limpieza:** 0 `error` y 0 `setup_failed` en las seis corridas; 0 app.open detrás de otra ventana; MSConfig 0;
  ningún 7040 desde las 15:00.

## Qué vio el modelo en B y qué hizo

- **calculator_next (E011), s0-s2:** en s1 cambia la conducta. A se rindió sin `app_open` («la calculadora no estaba
  abierta»); B leyó el `next`, abrió la Calculadora y volvió a evaluar (850). En s0 y s2, A hizo la misma cadena sin
  la pista.
- **listed_path (E020), s1 y s2:** `file.find` en el home devolvió `listedPath` (el home) y `subfoldersEntered=false`.
  La respuesta no cambia: sigue dando el archivo más grande del home sin entrar en BAXY-bench. En s0 el modelo usó
  `filesystem.search` y el campo no salió.
- **work_folder (E024): no se disparó nunca.** En las tres semillas de B el modelo escribió con `folder=home` y acertó
  BAXY-bench. En A s2 escribió sin `folder` y falló; en A s0 escribió con `folder=home` y falló. La subida de E024 está
  en la cifra, pero no la explica el recibo de la palanca 3, porque B nunca lo vio.
- **accessible_scope:** ningún caso del e2e de práctica lo pide.
- **Variación del modelo, sin campos nuevos:** E015 (oráculo de Steam ruidoso en el tiempo: B s0 OK tras 7 clics
  fallidos, A s0 NO tras decir que abrió la biblioteca) y E023 (bucle de `task_version_conflict` en A s1).

## Resto en el home

`notas.txt` en el home de la cuenta (la línea «vacío» y 10 veces «revisar el router»; última escritura a las 15:23,
en A s0 E024). Estuvo ahí durante los dos brazos. Hay una copia en `D:\BAXYeval\renew_v1\residuos_home_2026-10-19`; el
original no se borra sin el OK del dueño.
