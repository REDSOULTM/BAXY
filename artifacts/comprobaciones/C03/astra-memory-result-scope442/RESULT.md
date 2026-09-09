# 442 — omitir la pregunta inventa otro actor

No adoptar. Jordan ES pasa de «Mi nombre es Jordan» a «Jordan ha visto la
memoria»: sigue siendo una afirmación falsa. Marta y Ana María quedan como valor
aislado; hermana, lista y controles enable/save siguen útiles. EN «I found Jordan»
pierde el alcance explícito del registro. No certificar8/8 ni introducir el
alcance en fuente. Todos stop;8,984s/GPU3173,5625MiB/RAM1153,65625MiB, sin
violaciones, manifiesto intacto, cliente cerrado. Fuente436 sigue vigente.

No se atribuye el fallo a KV ni se cambia precisión: issue primario20035 de
llama.cpp (consultado2026-09-08) es b8184/Linux/modelos27B/35B, bug no confirmado
cerrado como not planned. Sus diferencias PPL son menores que sus errores y el
autor contempla ruido. No demuestra fallo q8_0 en b9980/CUDA/4B ni mejora f16.
https://github.com/ggml-org/llama.cpp/issues/20035

443 aborda el otro bloqueo privado ya demostrado401: redacción sin valor visible.
La proyección convierte sensibilidad en el literal [REDACTED]; el modelo lo copia
y niega acceso. Probar un estado tipado redacted=true omitiendo value, manteniendo
la protección previa y sin cambiar un solo byte de valor normal. No declara que
todos los recuerdos sean del usuario ni intenta corregir nombres con este cambio.
