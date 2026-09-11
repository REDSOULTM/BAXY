# Estado para el dueño — 11 de septiembre

La encuesta llegó a **45/742 cubiertos**. Se acreditaron dos lecturas de audio y siete solicitudes de apertura en estas tandas. Las dos correcciones de apps están publicadas y comprobadas: recuperan peticiones con cortesía y describen correctamente aperturas ya verificadas.

| Qué se midió | Resultado | Qué falta |
|---|---|---|
| Primera tanda de apps | 1/52 respuestas válidas; ninguna alta. Una apertura incierta de Calculadora arrastró las peticiones siguientes. | Conservar ese diagnóstico sin repetir el panel completo. |
| Audio | 26/52 válidas; 21 literales correctos. Dos lecturas recibieron crédito con variantes pertinentes. | Generalizar ajustes y silencio; conservar cantidades en palabras, mitad y máximo. |
| Apps tras las correcciones | 15 de 25 casos ejecutados: 10 válidos, 5 fallidos. Siete variantes válidas y tres créditos: Notepad, WhatsApp y Opera. | La continuación acreditó otras cuatro solicitudes; quedan tres límites sin ejecutar. Audio pasa primero por número de pendientes. |

La última tanda se detuvo al caer la RAM libre bajo 768 MiB. Se conservaron los resultados y las aperturas inciertas de Steam y Discord. Tras terminar la prueba, se cerró normalmente la nueva ventana de Opera y salió la instancia de Steam abierta por el diagnóstico; se recuperaron 5106,73 MiB de RAM libre. Discord quedó en segundo plano. El Administrador de tareas se conserva como lo dejaste.

| Recursos, medidos por separado | VRAM pico | RAM residente pico |
|---|---:|---:|
| Apps847 | 3497,56 MiB | 2392,03 MiB |
| Audio848 | 3499,56 MiB | 2437,42 MiB |
| Apps853, parcial | 3497,56 MiB | 2449,31 MiB |
| Continuación853, parcial | 3497,56 MiB | 1886,62 MiB |

Las cuatro ejecuciones quedaron bajo el techo de 4 GB de VRAM. El muestreo de RAM del árbol puede incluir aplicaciones descendientes; no representa sólo el modelo. Audio quedó restaurado y verificado en **31 %, sin silencio**.

| Avance formal | Estado |
|---|---|
| Encuesta | 45/742 cubiertos; 697 abiertos; 0 no aplican. |
| Últimas 24 horas | 17 altas confirmadas, más 2 actualizaciones de casos cubiertos cuya primera fecha no se distingue. |
| Categorías | 0/35 cerradas. Audio: 48 abiertos; apps: 47; web: 46. |
| Matriz C03 | 3/11 cumplidas, 5 contradichas y 3 pendientes. |

El ritmo sigue bajo 20 altas: hubo un Full en la ventana, fallos de generalización y una parada por RAM. El ajuste aplicado es reducir a dos subagentes como máximo y ejecutar sólo casos pendientes. Audio vuelve a ser primero por cantidad de abiertos; se prepara su panel de 35 literales, 12 variantes y 5 límites. La tanda grande de apps queda sellada para su turno. H0675, OCR y los nuevos providers permanecen aparcados.

El nuevo candidato de audio pasó **3545 pruebas conjuntas, cero fallos y cero omisiones**, además de estática y compilación Release. La reparación de cantidades todavía debe medirse en el producto. El Full del candidato anterior tuvo 4754 pruebas .NET y 12907 Python aprobadas, cero fallos; una omisión agregada .NET y tres Python, además de 466 subpruebas aprobadas. Las omisiones no cuentan como aprobaciones y ese Full no se atribuye al nuevo Python.

C03 sigue en curso, sin fecha de cierre fiable. La tabla de las 35 categorías está en [el checkpoint](CHECKPOINT.md). El avance se cuenta por requisitos verificados; main y los cambios del dueño se conservan.
