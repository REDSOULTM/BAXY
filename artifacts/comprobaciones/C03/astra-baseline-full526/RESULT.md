# Full de línea base 526: rojo

Commit de control `892c506cdd1a583048ed80af8e63703ec329a236`; comando `scripts/test_source_quality.ps1 -Mode Full`; salida 1. No hubo cambios de fuente durante la ejecución.

Estática y build Release aprobados, 0 advertencias y 0 errores. .NET: 4427 aprobadas, 0 fallos y 1 omisión en los resúmenes; el log también imprime otras omisiones opt-in que no acreditan ejecución. Python: 9984 aprobadas, 25 fallos, 3 omisiones y 466 subpruebas aprobadas en 676,16 s.

El resultado completo está en `full.log`; `RESULT.json` conserva las cinco suites y los 25 identificadores fallidos. No se declara C03 terminado ni se presenta esta línea base como verde.
