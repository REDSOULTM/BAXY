# 658 — NLI multilingüe pequeño no cualifica para el contrato factual

El modelo oficial multilingual-MiniLMv2-L6-mnli-xnli, revisión0a71e92a, recibe pares premisa/hipótesis nativos en CPU FP32. Misma población31 de656; los hechos pasan a premisas naturales bilingües con límites explícitos. Cambian modelo y representación: no es una comparación causal de un único factor.

Perfiles2/4 hilos producen las mismas etiquetas:21/31 decisiones binarias, una falsa aceptación y nueve falsos rechazos por perfil. Acepta que Brújula está instalada frente a instalado=false; rechaza descripciones verdaderas, abstenciones y una conversión correcta de RAM. Se conservan las probabilidades y los textos. No se cambia umbral ni se excluyen ejemplos para aprobar.

CPUExecutionProvider confirmado, máscara y pares nativos, sin cortes (todos≤512tokens). Picos RSS816,418MiB con2hilos y771,473MiB con4;4,344s/3,812s incluyendo proceso y carga. Sin infracciones. No son mínimos ni incrementos medidos en BAXY conjunto. El backend se contrasta con pesos originales en659 antes de atribuir el resultado al candidato. Modelo no incorporado al runtime; encuesta26/716/0.
