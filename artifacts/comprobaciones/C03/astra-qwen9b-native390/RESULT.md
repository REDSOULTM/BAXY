# 390 — 9B sin mmap: cabe aislado, no mejora identidad

2/4 útiles: ambas preguntas sobre la cuenta de Windows proponen system.identity correctamente; ambas preguntas sobre la persona repiten la frase previa del asistente y no recuperan Eva. No adoptar el modelo.

Mismos cuatro casos, prompt, historial, herramientas y sampler de 387/389; --no-mmap cambia la carga. RESOURCES.json: GPU 2918,316 MiB (2,85 GiB), RAM del árbol 3987,754 MiB (3,89 GiB), 30,11 s, sin violaciones. Usa RAM adicional. No mide convivencia con voz ni mínimo de VRAM del producto. Ninguna operación ejecutada; manifest_unchanged=true.

Sin edición de fuente ni promoción de runtime. Diagnóstico de desarrollo; no acredita aceptación humana fresca, producto completo, UI ni voz física.

## actual-human-es

Contexto literal:

**user**
> Me llamo Eva.

**assistant**
> Tu cuenta de Windows es otra identidad.

Entrada:
> Quién soy?

Respuesta literal:

> Tu cuenta de Windows es otra identidad.

finish_reason: stop; 9.516 s.

## human-en

Contexto literal:

**user**
> Me llamo Eva.

**assistant**
> Tu cuenta de Windows es otra identidad.

Entrada:
> Who am I?

Respuesta literal:

> Tu cuenta de Windows es otra identidad.

finish_reason: stop; 2.75 s.

## account-es

Contexto literal:

**user**
> Me llamo Eva.

**assistant**
> Tu cuenta de Windows es otra identidad.

Entrada:
> ¿Con qué cuenta de Windows estás ejecutándote?

Respuesta literal:

> (sin prosa)

Llamada propuesta (no ejecutada):
```json
[
  {
    "type": "function",
    "function": {
      "name": "baxy_system__identity",
      "arguments": "{}"
    },
    "id": "fsqLIgFSSNrxgChP6pVPH9FNIO07f5uH"
  }
]
```

finish_reason: tool_calls; 4.687 s.

## account-en

Contexto literal:

**user**
> Me llamo Eva.

**assistant**
> Tu cuenta de Windows es otra identidad.

Entrada:
> Which Windows account are you running under?

Respuesta literal:

> (sin prosa)

Llamada propuesta (no ejecutada):
```json
[
  {
    "type": "function",
    "function": {
      "name": "baxy_system__identity",
      "arguments": "{}"
    },
    "id": "pL6sk7xQdL0pHLIZJT3Foy5SAGIcU0HZ"
  }
]
```

finish_reason: tool_calls; 4.625 s.

