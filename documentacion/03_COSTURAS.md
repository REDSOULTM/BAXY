# Las costuras — por dónde se cambia BAXY

BAXY no se termina. Dentro de dos meses saldrá un STT mejor, un LLM más pequeño que
entiende igual, una cuantización que no rompe la prosa. **El código de hoy no tiene
por qué ser el de mañana.**

**BAXY entero es modular a propósito.** No sólo el LLM y la voz: la memoria, la
verificación, la automatización de aplicaciones, la capa visual, el journal — cada
pieza se cambia **una por una, sin reescribir el producto**.

Este documento dice **dónde está cada costura, qué mide su cambio, y qué hay puesto
hoy**. Cada goal que toca una pieza rellena su fila. El goal 11 no cierra con
ninguna vacía.

## Esto va en dos niveles, y confundirlos es el error

«Que todo sea modular» y «nada de sobreingeniería» sólo conviven si se separan dos
cosas que suelen ir juntas y no son la misma:

- **La forma del código** — que cada pieza tenga un borde y una responsabilidad.
  Esto **aplica a todo BAXY, sin excepción**, y no cuesta nada: es simplemente
  escribirlo bien. Sin esto, nada es sustituible jamás.
- **El mecanismo de cambio** — la medición que decide y la declaración en el
  manifiesto. Esto **sí cuesta trabajo**, así que se le pone a las piezas que de
  verdad se van a comparar contra un candidato. Ésas son las que están en el
  registro.

Dicho corto: **todo BAXY es modular; el registro es la lista de lo que además
tiene una forma medida de cambiarse.**

## Nivel 1 — la forma, que aplica a todo

Sin excepciones, en cualquier pieza que escribas:

- **Una responsabilidad por pieza.** Si al describir un fichero necesitas la
  palabra «y» tres veces, son tres piezas. `MainWindowViewModel` con 3.678 líneas
  y 169 miembros es el contraejemplo, y está dentro de este repositorio.
- **Nadie conoce las tripas de nadie.** Se depende del qué, no del cómo. Si cambiar
  el interior de A obliga a tocar B, no hay borde entre A y B.
- **Las dependencias apuntan hacia dentro.** `Contracts` no depende de nada,
  `Kernel` sólo de `Contracts`, los providers de ambos. Nunca al revés.
- **Nada global y mutable.** Un estado compartido que cualquiera toca es el
  acoplamiento que no se ve hasta que intentas cambiar algo.
- **Cero código muerto.** Lo sustituido se borra en el mismo cambio. Dos
  implementaciones vivas de lo mismo son la acumulación con otro nombre.

Esto es lo que hace que **cualquier** pieza de BAXY se pueda cambiar mañana, esté o
no en el registro. Es también, literalmente, lo que las cuatro versiones anteriores
no hicieron.

## Nivel 2 — el mecanismo de cambio

Una pieza del registro necesita tres cosas, y sin las tres no es sustituible **de
verdad**:

1. **Un borde que nombra qué hace, no cómo.** Es el nivel 1, ya lo tienes.
2. **La medición que decide si el candidato es mejor.** Esto es lo que de verdad
   hace sustituible una pieza: con un corpus y un número, cambiar de motor es una
   tarde. Con una interfaz preciosa y sin número puedes cambiarla, pero no puedes
   saber si has mejorado o empeorado — así que no la cambias nunca.
3. **La declaración en el manifiesto**, para que el cambio no pueda ser silencioso.

Lo que **no** hace falta y no se escribe: una interfaz con un solo implementador
«por si algún día», un registro de plugins, o configuración para elegir entre
implementaciones que no existen. Eso no es modularidad — es peso.

## Los tres tipos de borde, y cuál le toca a cada pieza

No todas las piezas se cambian igual. Hay exactamente tres formas, y ninguna
requiere un sistema de plugins.

### 1. Frontera de proceso — el LLM, el STT, el wake word, el TTS

Estas piezas **no viven dentro de la aplicación**. Corren como proceso aparte y
hablan por un protocolo versionado (`baxy.local.v1`) con mensajes tipados sobre
JSONL. El lado .NET conoce el protocolo, no el motor.

Consecuencia práctica: **cambiar el LLM no recompila nada**. Se apunta a otro
binario y a otro modelo, se corre la medición, y ya. Lo mismo para el motor de STT
o el de wake word.

Es la frontera más fuerte que hay y ya está construida. No la sustituyas por
llamadas en proceso «para ganar latencia» sin medir lo que pierdes en
sustituibilidad.

### 2. Frontera de contrato — verificación, providers, operación de apps

Viven dentro de .NET, detrás de `Baxy.Contracts` y `Baxy.Kernel`, que **no
dependen de nada**. El kernel autoriza; el provider ejecuta; el kernel no sabe cómo.

Cambiar una pieza aquí es escribir la implementación nueva y **borrar la vieja en
el mismo cambio**. Sin banderas, sin dos caminos vivos, sin interfaz nueva: el
contrato ya existe.

### 3. Frontera de datos — el catálogo, los corpus, los índices

El catálogo tipado es **datos, no código**. Cambiar su forma o su tamaño no es
refactorizar: es publicar otro catálogo y volver a medir.

## Cómo se declara una pieza: el manifiesto

Éste es el mecanismo que ata todo, y ya existe en el repositorio — se inventó en
R281 como auditoría y aquí se promueve a arquitectura.

Cada pieza sustituible se **declara** en el manifiesto de runtime: su nombre, su
**SHA-256** y su configuración. Así:

```json
"expected": {
  "ggufName": "gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf",
  "ggufSha256": "cd4526...",
  "llamaServerName": "llama-server.exe",
  "llamaServerSha256": "38a9d2...",
  "gpuLayers": 99
}
```

La razón está escrita en el propio artefacto, y vale para todas las piezas:

> Registrar la identidad aquí convierte un cambio silencioso de modelo en una
> compuerta roja.

Esa frase es la regla entera. **Ninguna pieza cambia en silencio.** Si el binario
que corre no es el declarado, la compuerta se pone roja. Eso es lo que hace que la
modularidad no se convierta en caos: puedes cambiarlo todo, pero no puedes cambiar
nada sin decirlo.

*Pendiente conocido:* hoy el manifiesto tiene `manifestIsVersioned: false`. Que sea
versionado es trabajo del goal 02, y sin eso la declaración no sobrevive a un
cambio de esquema.

## El registro

Cubre el producto entero, no sólo la pila del modelo. **Está abierto pero no es
libre:** se añade una fila cuando una pieza vaya a compararse de verdad contra un
candidato, y se añade **con su medición**. Una fila sin medición es una fila
mentirosa.

### La pila que entiende y decide

| Pieza | Borde | Qué decide el cambio | Elegido hoy | Goal | Fecha |
|---|---|---|---|---|---|
| **LLM decisor** | Proceso | | | 03 | |
| **Cuantización** | Proceso | | | 06 | |
| **Runtime de inferencia** | Proceso | | | 03 | |
| Recuperador / embeddings | Datos | | | 03 | |
| Reconocedor determinista | Contrato | | | 03 | |
| Forma del catálogo | Datos | | | 03 | |
| Planificador de misiones | Contrato | | | 07 | |

### La pila de voz

| Pieza | Borde | Qué decide el cambio | Elegido hoy | Goal | Fecha |
|---|---|---|---|---|---|
| **Wake word** | Proceso | | | 09 | |
| **STT** | Proceso | | | 09 | |
| **TTS** | Proceso | | | 09 | |

### La pila que actúa sobre la máquina

| Pieza | Borde | Qué decide el cambio | Elegido hoy | Goal | Fecha |
|---|---|---|---|---|---|
| Verificación de efectos | Contrato | | | 05 | |
| Automatización de apps (UIA) | Contrato | | | 07 | |
| OCR | Proceso | | | 07 | |
| Motor de visión | Proceso | | | 07 | |

### El producto alrededor

| Pieza | Borde | Qué decide el cambio | Elegido hoy | Goal | Fecha |
|---|---|---|---|---|---|
| Almacén de memoria | Contrato | | | 10 | |
| Journal de invocaciones | Contrato | | | 05 | |
| Capa visual (bandeja / WebView) | Contrato | | | 10 | |
| Instalación y arranque | Contrato | | | 10 | |

**Las columnas:**

- **Borde** — cuál de los tres tipos de arriba. Determina qué cuesta cambiarla.
- **Qué decide el cambio** — el corpus o banco, el número que hay que batir, y
  dónde está el procedimiento. **Es la columna importante.** Sin ella la pieza no
  es sustituible aunque tenga el mejor borde del mundo.
- **Elegido hoy** — qué está puesto y por qué ganó.
- **Goal** — quién rellenó la fila.
- **Fecha** — cuándo se midió. Una medición de hace ocho meses decidió entre
  candidatos que hoy ya no son los mejores: la fecha es lo que avisa de que toca
  volver a mirar.

## Cómo se sustituye una pieza, dentro de dos meses o de dos años

1. Se lee la fila: qué medición decide.
2. Se corre esa medición sobre el candidato nuevo, **sin tocar el umbral**. Si el
   resultado no llega, la respuesta es otro candidato, no un umbral más laxo.
3. Si gana, entra — se actualiza el manifiesto con su nombre y su hash, y la
   implementación anterior **se borra en el mismo cambio**.
4. Se actualiza la fila con lo elegido y la fecha.

Nada de esto exige reabrir el producto ni volver a discutir la arquitectura. Ése es
el punto entero: que mejorar BAXY sea una tarde, no una quinta reescritura.
