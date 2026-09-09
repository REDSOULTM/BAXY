# C03 — tramo 24: cobertura de formato e idioma en el ajuste

2026-09-06. EN_CURSO. La tanda anterior fue progreso: adjudicaciones individuales,
exportación literal y Fast confirmado verde. No fue cierre de C03. No se cambia
el criterio100/100 ni se ejecuta Full mientras el candidato falle en conducta.

## Diagnóstico e herencia

La petición literal y la política de idioma llegan en los payloads de chat;
la política de conocimiento permite el formato concreto pedido. No hay prueba
de pérdida de la petición en los casos examinados. No se añade filtro por frase.

El corpus de piloto2 tiene84ejemplos:28mixed con una oración,20es+20en con una
y8es+8en con dos. Ninguna petición de entrenamiento exige un número de oraciones.
La salida integrada t13 ignoró dos oraciones, aunque el diagnóstico anterior
con otro historial sí las respetó. Hipótesis: falta cobertura de obediencia al
formato, especialmente mezclando idiomas; se medirá en temas no entrenados.

Herencia conservada: los84ejemplos revisados y el entrenamiento de pérdida sólo
en la respuesta procedente de Probando Gemma4. Lectura acotada de su
dataset_finetune/curated/train_v3.jsonl: no se importa en masa. La segunda fila
contiene «me llamo Baxy, no Baxy» y otra describe envío externo con permiso,
incompatible con la privacidad actual. Esto demuestra errores concretos, no que
todo el corpus antiguo sea inválido. No se cambia ni elimina ese proyecto.

## Hipótesis de intensidad, descartada

astra-lora-pilot2-half-scale-ready:27casos idénticos, adaptadorv2 a0,5,
sesión96432 TERMINAL0,22,41s,GPU3519,56MiB,RAM3247,34MiB.
Mejora algunas explicaciones, pero pierde mezcla de idiomas en audio/compuestos
y mantiene traducciones repetidas. No promover ni buscar otra escala a ciegas.

Primer lanzamiento astra-lora-pilot2-half-scale terminó sin respuestas: el CLI
b9980 separa FNAME:SCALE y no acepta el colon de D:. Se conservó RESULT con error;
segundo lanzamiento usa ruta desde la raíz de la unidadD comprobada. No se
reparó llama.cpp ni se confundió el error de arranque con calidad del modelo.

## Piloto de cobertura

astra-lora-pilot3-data:132ejemplos (84heredados+48de formato en los mismos8temas).
Los nuevos siguen dos oraciones en ES/EN/mixed, con y sin historial mixto.
Misma base inicial y mismos hiperparámetros; no se continúa desde pesosv2.
30holdout:18anteriores sin entrenar+12nuevos en4temas,con dos oraciones e idioma
explícito, congelados antes del entrenamiento. No son aceptación del producto.
TRAIN SHAbb1858124b9d8cc8060002b997780f18843f6bf9e9a3a67475242a39fce7951d.
HOLDOUT SHA77a08029c8ca8828dec82824d69964ce20cded59725a60c5334d305571d3e1b5.

Entrenamiento sesión61646 TERMINAL0:278,61s,GPU3047,54MiB,RAM4669,26MiB,
132ejemplos,max410tokens,66actualizaciones. Safetensors SHA
190bbdd78a58548f0eebaf818efce04df35025595c180becd388324356caed67.
Conversión74063 TERMINAL0: llama.cppb9980, salida c03-pilot-lora-v3-f32.gguf
en la base entrenable. Evaluación sesión67544 TERMINAL0:39casos por brazov2/v3
con scratchpad/c03-evaluate-lora-pilot3.py. V2 26,95s y v3 31,74s; ambos con
GPU3521,56MiB. Las27respuestas anteriores de controlv2 permanecen idénticas.
Nada se promueve por pérdida, memoria ni finalización del script.

Adjudicación completa de78respuestas: v2 25/39 frente a v3 32/39. Nuevos formatos
4/12→9/12; casos previos21/27→23/27. La mejora no permite promover: v3 afirma
que hielo ocupa más espacio que el mismo volumen de agua y niega que el cifrado
haga ilegibles los datos. También conserva cuchillo por cuchara y pierde idioma
en archivo/carpeta. No se ejecuta otra captura integrada de un candidato con
esas regresiones conocidas. PRUEBAS_AJUSTE_3_C03.md contiene literales y razones.
La escala descartada quedó adjudicada16/27, con27literales en PRUEBAS_ESCALA_C03.md.

Hipótesis de formato respaldada parcialmente: mejora en temas nuevos. No resuelve
la conservación del conocimiento al ajustar. Siguiente acción: revisar y heredar
un subconjunto factual del corpus anterior, excluyendo temas de los holdouts
consumidos; no seguir duplicando los mismos8temas, no otro barrido de intensidad.
Los ejemplos requieren revisión individual: confianza declarada y categoría del
corpus antiguo no prueban que sean correctos. No entrenar sobre respuestas del panel.
Todas las sesiones terminales; sin modelo ni fixture propios pendientes.

Pendientes intactos: desarrollo verde,100nuevos,ocho rutas,recuperación aparte,
UIreal,runtime registrado reproducible,Fullfinal,publicación fuera de main y
continuidad de contratos afectados hasta12.3. Fuente del producto sin cambios
en este tramo; pruebas dueñas/Fast anteriores siguen siendo las últimas.
