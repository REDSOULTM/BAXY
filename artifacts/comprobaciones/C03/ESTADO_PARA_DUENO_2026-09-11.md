# Estado de C03 — 11 de septiembre de 2026

La encuesta subió a **38/742 cubiertos**. Se ejecutaron las tandas de apertura de aplicaciones y audio; sus fallos están escritos por caso. Hay dos correcciones de apps integradas, con 3504 pruebas específicas aprobadas; la revisión estática y compilación Release también terminaron sin fallos.

| Qué se midió | Resultado | Qué falta |
|---|---|---|
| Apertura: 35 literales, 12 variantes y 5 límites | 1/52 respuestas válidas; ningún crédito nuevo. Una apertura de Calculadora sin verificar dejó pendientes las peticiones siguientes. | Comprobar las correcciones de interpretación y descripción del resultado en una tanda corta independiente. |
| Audio: 35 literales, 12 variantes y 5 límites | 26/52 válidas; 21 literales correctos. Dos lecturas reciben crédito con variantes actuales y anteriores. | Generalizar ajustes y silencios; corregir peticiones con números escritos, mitad y máximo. |

La prueba de audio terminó dejando el sonido silenciado al 100 %. Ya se restauró y verificó el estado anterior: **31 %, sin silencio**. Las aplicaciones abiertas por la prueba se conservaron.

| Recursos, medidos por separado | VRAM pico | RAM residente pico |
|---|---:|---:|
| Apps847 | 3497,56 MiB | 2392,03 MiB |
| Audio848 | 3499,56 MiB | 2437,42 MiB |

Ambas tandas quedaron por debajo del techo de 4 GB de VRAM y sin infracciones de las guardas.

| Avance formal | Estado |
|---|---|
| Encuesta | 38/742 cubiertos; 704 abiertos; 0 no aplican. |
| Últimas 24 horas | 10 altas confirmadas, más 2 actualizaciones de casos cubiertos cuya fecha de primera alta no se distingue. |
| Categorías | 0/35 cerradas. Apps: 54 abiertos; audio: 48; web: 46. |
| Matriz C03 | 3/11 cumplidas, 5 contradichas y 3 pendientes. |

En la ventana hubo una validación completa y fallos de producto que impidieron llegar a 20 altas. El ajuste es concreto: H0675 y la lectura de pantalla quedan aparcados; los próximos paneles tienen conversaciones independientes y se centran en los literales pendientes. Apps conserva la mayor masa abierta. Su siguiente tanda corta ya está sellada: 10 literales, 10 variantes y 5 límites, antes de pasar a la tanda grande.

La última validación completa, del candidato anterior, terminó con 4754 pruebas .NET y 12907 Python aprobadas, cero fallos; una omisión agregada .NET y tres Python, además de 466 subpruebas aprobadas. Las omisiones no cuentan como aprobaciones. Las correcciones nuevas todavía necesitan su medición en el producto.

C03 sigue en curso y no hay una fecha de cierre fiable. El avance se cuenta por requisitos verificados, no por tamaño del panel. La tabla de las 35 categorías está en [el checkpoint](CHECKPOINT.md). Main y los cambios del dueño se conservan.
