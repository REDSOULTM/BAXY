# Corrección del instrumento

La primera versión sobrescribió case.history (lista) con el payload (diccionario). La etapa guarded recibió historial vacío: no aísla validadores. Además t9 cambia de ruta al añadir historial. No usar esos contrastes como evidencia causal de una sola capa. Se preservan resultados originales. Versión v2 separa historial y payload, añade etapa routed y exige igualdad del primer prompt antes de evaluar validadores. Bare/identity/system conservan utilidad diagnóstica.
