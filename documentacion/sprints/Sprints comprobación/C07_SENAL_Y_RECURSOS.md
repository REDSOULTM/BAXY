# C07 — Primera señal, respuesta completa y recursos reales

**Ejecutable: Grok 4.6 High; un goal con tramos reanudables.**
Predecesor: C06 cumplido. Incorpora [contrato](01_CONTRATO_DE_CAMPANA.md) y
[protocolo vigente](../00_PROTOCOLO_EJECUCION.md).

## Objetivo

Cumple los relojes de 08 y los compromisos temporales/VRAM de 03/03B/03C/07.
La velocidad se mide desde la entrada de la persona hasta la salida publicable
y el resultado real; incluye toda la cola y la composición.

## Lecturas y owners

Filas propias G03/G03B/G03C/G07/G08, Identidad y R02/R07/R10/R16.
first_signal.py, turn.signal, time_budget, composición/colas y FieldUiBridge.
Hereda medidas de 08 y la corrección del árbol de procesos de 10.2.5. Sus cifras
son baseline; no se copian como medición actual.

## Tramos de ejecución

A: relojes y población. B: una causa de sobrecarga por ventana. C: perfiles
separados y árbol completo. D: regresión de prosa/efectos y cierre de las 60
entradas. C08 revalida con escucha real. La medición de consumo aquí no acredita
hardware objetivo: la certificación GPU 4 GB/CPU 8 GB instalada pertenece a 12.2.
No adelantes prosa genérica ni ocultes fallos para mejorar cuantiles.

## Trabajo

1. Define t0 en admisión pública y relojes monotónicos: primera señal, primer
   efecto observable, respuesta final publicada, TTS y liberación de entrada.
   Registra el mayor intervalo sin salida durante todo el turno, no sólo el inicio.
   Separa arranque frío, caliente, carga y perfil CPU sin aceleración.
2. Preregistra al menos 60 turnos variados: conversación, lecturas, efectos
   simples, misiones largas, aclaración, confirmación y error. Usa C01 con
   motores reales; para los efectos, observa Windows y el resultado final.
3. Cumple p50 primera señal ≤1 s, p95 ≤2 s; acción simple completa y verificada
   p50 ≤2,5 s; ninguna tarea pasa más de 3 s sin señal. Publica todos los
   intentos, cuantiles y máximos por perfil; no escondas CPU en el promedio GPU.
4. La señal temprana sólo aparece cuando se prevé tardar, no afirma resultado y
   la formula el modelo. Elimina las rutas por plantilla que sigan existiendo;
   comprueba que tampoco las introducen el bridge o el conductor.
   Si ya existe salida útil, no insertes otro acuse para mejorar una métrica.
5. Desglosa llamadas por modelo y sobrecarga frente a la inferencia pura con
   igual prompt/modelo/tokens. Retira trabajo redundante antes de añadir capas,
   cachés o modelos. Conserva exactitud, cobertura, tres ceros y prosa natural.
6. Mide pico VRAM del runtime completo ≤4 GB durante turnos y memoria/CPU en
   reposo del árbol de procesos, incluyendo Python/ONNX/llama-server/Core/UI
   cuando estén presentes. La escucha encendida se revalida en C08.
   No declares óptimo un arreglo de sesión ONNX sólo porque pasó un mock.
7. Corrige pérdidas de respuesta y bloqueos bajo carga sin alargar plazos del
   test para aprobar. Revalida los cambios en las capacidades de C03–C06 afectadas.

## Cierre obligatorio

- [ ] Relojes desde entrada común, salida final y máximo silencio publicados
      sobre la población completa; perfiles CPU/GPU/carga/frío separados.
- [ ] Listones del 08 y silencio máximo de 3 s cumplidos, también en misiones.
- [ ] Aviso condicional formulado por modelo, sin éxitos prematuros ni plantillas.
- [ ] Pico VRAM ≤4 GB y consumo del árbol completo medidos; sin regresión frente
      al baseline reparado de 10.2.5 en condiciones equivalentes.
- [ ] Coste por llamada y sobrecarga explicados; exactitud, cobertura y tres ceros intactos.
- [ ] Filas propias cumplidas, Full verde, mediciones y cambios propios publicados.

El original permitía cerrar un estudio con una frontera Pareto inalcanzable.
En esta campaña eso se registra como límite demostrado y mantiene NO_LISTO:
no habilita el 10 ni relaja silenciosamente los requisitos del dueño.

Evidencia: artifacts/comprobaciones/C07/. Siguiente: C08.
