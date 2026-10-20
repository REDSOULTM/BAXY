# Palancas 1c (place_unverified) y 8 (person_folder_sentence) en e2e, notebook (2026-10-19)

- **Binario:** `hub/pc-ayudas-6` `ea1987fb4`, compilado una vez y el mismo para todos los brazos. La ayuda se elige con
  `BAXY_AYUDAS`.
- **Brazos:**
  - A: `none`, del mismo día.
  - B: `place_unverified` (1c), entre las 18:29 y las 19:36, intercalado con A.
  - B: `person_folder_sentence` (8), entre las 19:56 y las 20:29, pareado con el A de la 1c.
- **Modelo y banco:** c2-e1.0 y el mismo banco.
- **Limpieza:** 0 `error`, 0 `setup_failed`, 0 app.open detrás de otra ventana y MSConfig 0 en las nueve corridas.
- **Guiones:** `e2e_aid.sh` y `e2e_aid2.sh` (este con `ARMS`, `A_PREFIX` y `SKIP_BUILD`).

| | s0 | s1 | s2 | Media | Δ frente a A (IC95) | Por mayoría |
|---|---|---|---|---|---|---|
| A `none` | 26 | 21 | 25 | 24,00 | — | — |
| B 1c | 26 | 24 | 26 | 25,33 | +1,33 [−0,33, +3,67] | suben E015 y E029 |
| B 8 | 27 | 26 | 26 | 26,33 | +2,33 [+0,33, +4,67] | suben E027 y E029; baja E024 |

## 1c

- **Cuándo sale la pista:** en E014 y E015, en las tres semillas. Las seis veces el modelo miró una sola vez con
  `input_visible_controls`, sin más clics.
- **E015:**
  - A dijo dos veces «Abrí Steam en la biblioteca» sin mirar (la falsedad de F019).
  - B dijo la verdad en las tres: que Steam se estaba actualizando, o que no encontró su ventana delante.
  - El OK del oráculo depende de cuándo llega Steam, no de la respuesta.
- **Coste en E014:** la primera respuesta pasa de 6,4-6,9 s a 9,3-10,0 s.
- **F019 en las falsedades s0 de B:** el modelo no usó `place`, así que la pista no salió.

## 8

- **E027, su blanco:** A 1/3 → B 3/3. B pidió confirmación las tres veces y respetó el «no»; A se negó dos veces
  diciendo que BAXY-bench era su carpeta de trabajo.
- **E024 no es de la 8:** con `folder=home` el modelo añade la línea al `notas.txt` del home. En B s2 además dijo
  «en la carpeta BAXY-bench», que es falso. A s2 hizo lo mismo.

## Combinación 1 + 2 + 3b + 1c + 8 en e2e (`2a5a0aad5`, sin la 6)

- **Brazos:** A = `none`; B = `calculator_next,accessible_scope,work_folder,place_unverified,person_folder_sentence`.
  Mismo binario, intercalados entre las 21:10 y las 22:16.
- **Limpieza:** 0 `error`, 0 `setup_failed` y 0 app.open detrás de otra ventana.
- **Latencia:** la primera respuesta queda igual, con un p50 de 5,7 a 6,2 s en los dos brazos.

| | s0 | s1 | s2 | Media |
|---|---|---|---|---|
| A `none` | 26 | 25 | 24 | 25,00 |
| B combinación | 27 | 26 | 27 | 26,67 |

- **Resultado conjunto:** Δ +1,67 (IC95 [−1,00, +4,67]). Por mayoría suben E015 y E027 y baja E024 (McNemar 2/1).
  Ninguna semilla baja.
- **Puerta en B:** E011 3/3, E017 3/3 y E024 0/3. En A: 3/3, 3/3 y 2/3.
- **E024 baja por dos vías distintas:**
  - En s0 y s1 el modelo pasó `folder=home` y escribió el `notas.txt` del home.
  - En s2 escribió sin `folder` y salió la 3b. El modelo lo contó con la verdad («en la carpeta BAXY-bench de mi
    carpeta de trabajo»), pero el caso falla igual.
  - En los brazos de hoy con la 8, E024 falló 5 de 6; sin la 8, 5 de 15 (Fisher a una cola, p = 0,055). Son brazos
    de binarios distintos: es una señal, no una prueba.
- **E015:** las tres respuestas de B fueron honestas. En s0, mirar llevó a un bucle de 11 pasos; en s1 y s2, a una
  sola mirada.
