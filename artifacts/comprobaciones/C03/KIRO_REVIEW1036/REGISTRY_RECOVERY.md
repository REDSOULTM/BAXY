# Auditoría de recuperación del registro Kiro

No se reconstruyó ni modificó el registro canónico. Base verificada: 742 filas, 126 cubiertos, 616 abiertos; SHA256 1a7ec3d381e4d972cb0bbdf9c55ed632216618e932614e31d2ea602a74a3eae6.

La primera escritura de KNOWLEDGE1025 no es reproducible byte a byte con la evidencia publicada: el recibo enumera siete causas, pero no preserva los valores completos de cada fila ni el algoritmo de escritura. El commit 7638f527 sólo publica ROOT_ADJUDICATION y REGISTRY_UPDATE; no hay escritor1025 versionado. SYSTEM1028 tampoco tiene escritor versionado. No se probaron combinaciones adivinadas.

La cadena siguiente verifica continuidad entre sellos declarados, no la existencia ni el contenido de los registros privados. No constituye nueva adjudicación ni acreditación.

| Tanda | Cubiertos | Altas | Continuidad SHA declarada |
|---|---:|---:|---|
| KNOWLEDGE1025 | 126 | 0 | True |
| SYSTEM1028 | 130 | 4 | True |
| APPS1029 | 133 | 3 | True |
| REPAIR1030 | 133 | 0 | True |
| REPAIR1031 | 133 | 0 | True |
| REPAIR1032 | 137 | 4 | True |
| REPAIR1033 | 144 | 7 | True |
| CLOCK1034 | 154 | 10 | True |


Archivo mínimo para recuperar el estado exacto: `C:/Users/usuario/AppData/Local/BAXY/C03-survey-requirements336-private/requirements.jsonl with SHA256 58986cb8b2b42a6d70f6648ea0e66b9a7b7e948b784963316683fb6b3f8671f7`. Debe copiarse desde REDPC y validarse antes de cualquier sustitución. READS1035 requiere además sus capturas y recibos privados; este registro no basta para adjudicarla.

No se ejecutaron producto, GPU, suites ni adjudicadores. Sólo se leyeron archivos y se escribió este informe fuera del repositorio.
