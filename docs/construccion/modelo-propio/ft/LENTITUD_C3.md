# Por qué el candidato c3 responde más lento (2026-10-31, PC)

Rama `ft-c4-lento` (<evaluacion>\wt\c4-lento) desde f778d5d35: faa6747d6 (aviso) y c5ef41d01 (espera de rótulo). Sin
desplegar.

## Diagnóstico con el banco ciego (casos 51–160, s1 y s2; 244 turnos por brazo)

- El modelo no piensa más lento: el hueco entre pasos es de 1,6 s p50 (oficial 1,2 s).
- El candidato hace más pasos (3,1 por turno frente a 2,3) y menos turnos sin pasos (50 frente a 77): intenta más, y
  por eso logra más.
- **El aviso hablado casi nunca suena.** De 77 turnos con más de 8 s en silencio, sólo 2 tuvieron aviso. De 393 avisos
  que la mente pidió al modelo:
  - 143 se tiraron por pasar de 6 palabras o 60 caracteres («Abro LibreOffice Writer y entro a Opciones.» tiene 7);
  - 136 agotaron su plazo de 1,5 s, casi siempre mientras la visión ocupaba el único hueco del servidor;
  - 27 se tiraron por repetidos.
- **Espera de rótulo (`waitForLabel`):** sólo la usa el candidato. En 12 de 16 casos agotó los 24 s esperando un rótulo
  que la ventana quieta nunca mostró.
- **`input.visible.controls`**: p95 de 22,7 s (oficial 2,4 s). Se explica por esas esperas y por el recorrido de
  accesibilidad de Paint.NET, que agota su presupuesto de 20 s.

## Arreglos

1. **Aviso:** se admiten frases de hasta 10 palabras y 64 caracteres. Con eso se recuperan unas 95 de las 143 frases
   tiradas. La frase de 12 palabras que afirma un resultado sigue fuera.
2. **Espera de rótulo:** si la ventana muestra los mismos controles en 3 miradas seguidas, la espera termina ahí. Una
   ventana vacía o que sigue cambiando conserva los 24 s.

## Verificación

- pytest de la mente (maximo, final y prefill): 54 pasadas.
- Baxy.Providers.Windows.Tests sin las pruebas en vivo: 3.651 pasadas. Build Release con warnings como errores: 0
  errores.
- En vivo, 3 misiones propias (LibreOffice > opciones, Obsidian > configuración, Paint.NET > configuración), mismo modelo
  sA y Laya apagada; unos 4 minutos por corrida:

| | Producción f778d5d35 | ft-c4-lento |
|---|---|---|
| Primer sonido p50 | 31,8 s | **4,4 s** |
| Turnos que sonaron antes de la respuesta | 1 de 3 | **3 de 3** |
| Primera respuesta p50 | 50,8 s | 50,5 s |
| Misiones bien según el oráculo | 3/3 | 3/3 |

Ninguna de las 3 misiones usó `waitForLabel`, así que el arreglo 2 sólo está cubierto por las pruebas.

## Lo que queda

- **Pulsar un rótulo que no está tarda 17–41 s en fallar.** La visión corre en la CPU y se le pregunta hasta dos veces,
  guardando y restaurando el hueco del servidor. Es el siguiente arreglo de App.
- **Avisos de seguimiento:** cada 10 s el modelo vuelve a escribir la misma frase, que se tira por repetida, o agota el
  plazo mientras corre la visión. Por eso hay silencios largos después del primer aviso.
- **Recorrido de Paint.NET:** agota su presupuesto de 20 s.
