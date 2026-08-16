# Las costuras — por dónde se cambia BAXY

BAXY no se termina. Dentro de dos meses saldrá un STT mejor, un modelo más pequeño
que entiende igual, una cuantización que no rompe la prosa. **El código de hoy no
tiene por qué ser el de mañana.**

Este documento es la respuesta a «¿y cómo lo mejoro entonces?». Es la lista de las
piezas de BAXY que están construidas para ser sustituidas, con **qué medición
decide** si el sustituto es mejor. Sin ese segundo dato la pieza no es sustituible
aunque tenga una interfaz preciosa: puedes cambiarla, pero no puedes saber si has
mejorado o has empeorado, así que no la cambias nunca.

Cada goal que toca una de estas piezas rellena su fila. El goal 11 comprueba que no
queda ninguna vacía.

## Qué es una costura aquí

Tres cosas, y sin las tres no cuenta:

1. **Un borde que nombra qué hace, no cómo.** El kernel no sabe que Windows existe;
   ése es el modelo a seguir, y ya funciona en este repositorio.
2. **La medición que decide.** Un corpus, un número y un procedimiento. Con eso,
   cambiar de motor es una tarde. Sin eso, es un salto de fe.
3. **Que instalar lo nuevo incluya retirar lo viejo.** Cero código muerto: una
   pieza sustituida se borra, no se queda detrás de una bandera «por si acaso». Dos
   implementaciones vivas de lo mismo son la acumulación otra vez.

## Qué NO lleva costura

Todo lo demás. **La lista de abajo está cerrada y no se amplía sobre la marcha.**

Escribir una interfaz con un solo implementador «por si algún día» es exactamente
la sobreingeniería que mató a las cuatro versiones anteriores. Si una pieza que no
está en esta lista resulta que necesita sustituirse, se añade aquí en ese momento —
con su medición— y entonces se le hace la costura.

## El registro

| Pieza | Qué decide el cambio | Elegido hoy | Goal | Fecha |
|---|---|---|---|---|
| Modelo decisor | | | 03 | |
| Cuantización | | | 06 | |
| Runtime de inferencia | | | 03 | |
| Recuperador | | | 03 | |
| Reconocedor determinista | | | 03 | |
| Forma del catálogo | | | 03 | |
| Verificación de efectos | | | 05 | |
| Operación de apps (UIA/OCR/visión) | | | 07 | |
| Wake word | | | 09 | |
| STT | | | 09 | |
| TTS | | | 09 | |

**Columnas:**

- **Qué decide el cambio** — el corpus o banco, el número que hay que batir, y
  dónde está el procedimiento. Es la columna importante.
- **Elegido hoy** — qué está puesto y por qué ganó.
- **Goal** — quién la rellenó.
- **Fecha** — cuándo se midió. Una medición de hace ocho meses decidió entre
  candidatos que hoy ya no son los mejores: la fecha es lo que avisa de que toca
  volver a mirar.

## Cómo se sustituye una pieza, dentro de dos meses o de dos años

1. Se lee la fila: qué medición decide.
2. Se corre esa medición sobre el candidato nuevo, **sin tocar el umbral**.
3. Si gana, entra — y la implementación anterior **se borra en el mismo cambio**.
4. Se actualiza la fila con lo elegido y la fecha.

Nada de esto exige reabrir el producto ni volver a discutir la arquitectura. Ése es
el punto entero: que mejorar BAXY sea una tarde, no una quinta reescritura.
