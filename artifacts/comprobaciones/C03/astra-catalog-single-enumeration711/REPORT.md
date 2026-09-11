# Una enumeración conserva el catálogo medido

Los tres pares alternados conservaron exactamente las mismas 322 entradas: nombre, AppID y destino para nombres duplicados. El orden bruto cambió; la comparación ordenada de todos los campos es idéntica en las seis ejecuciones. Se conservaron las salidas completas en privado.

| Par | Original | Una enumeración | Diferencia del candidato |
|---|---:|---:|---:|
| 1 | 6,719 s | 6,906 s | +0,187 s |
| 2 | 7,984 s | 3,438 s | −4,546 s |
| 3 | 5,484 s | 3,890 s | −1,594 s |

Medianas: 6,719 s y 3,890 s. Dos pares mejoraron y uno empeoró. Esta muestra pequeña no demuestra una garantía de latencia ni equivalencia para todas las instalaciones. Justifica probar la misma sustitución en el provider y verificar el arranque real; todavía no se adopta.

Se reutiliza Shell.Application/AppsFolder, que el provider ya empleaba para los destinos duplicados. Se conserva su tratamiento de metadatos ausentes y la resolución posterior de ambigüedades. No se cambian timeout, caché, contratos, selección LLM ni catálogo de operaciones.

Herencia consultada: `biblioteca/00_INDICE.md:102–114` y los trece documentos de `gemma4-agent/documentacion/04_computer_use/`. El antecedente `research/gui_eval_informe_por_tier_2026_05_24.md:238–247` menciona discovery PATH/StartApps/registro, pero no mide la sustitución por una enumeración. No se encontró un rechazo previo de esta propuesta en ese ámbito. El solape de catálogo/journal del registro de mantenibilidad, líneas429–433, permanece rechazado.

[Shell.NameSpace](https://learn.microsoft.com/en-us/windows/win32/shell/shell-namespace) y [Folder.Items](https://learn.microsoft.com/en-us/windows/win32/shell/folder-items) documentan los mecanismos usados. La equivalencia de nombres e identificadores procede de la medición local, no se deduce de esos documentos.

Sin LLM ni cobertura nueva. No es una validación de BAXY completo ni un Full verde.
