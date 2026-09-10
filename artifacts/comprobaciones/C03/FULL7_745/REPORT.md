# Full7 — candidato integrado de C03

El comando `powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test_source_quality.ps1 -Mode Full` terminó con **exit 0** en **1543,547 s**. Los **1233 archivos congelados** conservaron sus bytes durante toda la corrida.

- .NET: **4574 pass, 0 fail, 1 skip agregado**. Los 16 mensajes explícitos de omisiones opt-in se conservan aparte; no cuentan como passes.
- Python: **11399 pass, 0 fail, 3 skips ambientales y 466 subtests pass**, 706,70 s.
- Compilación Release: 20,95 s, sin warnings ni errores. Todas las etapas estáticas pasaron.
- Los originales de sidecar y empaquetado conservaron sus límites de 3 y 45 segundos. El test V8 pasó con la huella actual corregida y sus evidencias históricas intactas.

Es validación de la fuente integrada705+712+730+738+740+744. No es cierre de C03 ni prueba de UI, voz física, consumo conjunto o cobertura de encuesta. Full6 rojo permanece publicado. La corrección del campo descriptivo PREREG.log está documentada en el propio archivo; la ejecución siempre escribió al directorio privado Full7 correcto.
