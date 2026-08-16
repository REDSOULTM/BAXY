# HCI Guidelines for Vision-Based Window Control

Este documento consolida las decisiones de diseño de Interacción Humano-Computadora (HCI) aplicadas en el módulo `vision_input`. Las decisiones están fundamentadas en investigaciones de **Computación Espacial** y diseños de interfaces de usuario sin contacto.

## 1. Filtrado Cinemático (Kinematic Filtering)

Las interfaces controladas por visión inherentemente sufren de jitter (ruido de estimación de pose) y latencia. Para mantener el puntero utilizable y natural, se implementan múltiples capas de filtrado:

- **Filtro One-Euro:** El cursor de mirada (gaze) y la muñeca no aplican promedios simples, sino un filtro *One-Euro* (Casiez et al., 2012). Este filtro adaptativo aplica un fuerte suavizado a bajas velocidades (reduciendo el jitter cuando el usuario intenta mantener el cursor quieto) pero reduce el suavizado a altas velocidades (disminuyendo el lag durante movimientos rápidos).
- **Zonas Muertas (Deadzones):** Se aplica un radio de tolerancia en el que el movimiento mínimo es ignorado para evitar micromovimientos indeseados que causan clics fallidos.

## 2. Activación por Permanencia (Dwell) vs Gestos Dinámicos

Existen dos paradigmas principales para confirmar acciones en el aire, y el sistema utiliza ambos según el nivel de riesgo de la acción:

- **Gestos de Permanencia (Dwell-Time):** Usado para acciones como `PalmMediaGesture` (Pausar/Reproducir música). Requiere que la mano se mantenga abierta como una palma de manera ininterrumpida por **0.75 segundos**. El tiempo de espera asegura que el gesto no se dispare accidentalmente mientras la mano transiciona a otro estado (por ejemplo, preparándose para hacer un *Pinch*).
- **Gestos Cinemáticos (Velocidad):** Para acciones como deslizar (`Swipe` o el Latigazo), la activación no depende del tiempo, sino de un umbral de velocidad (por ejemplo, `vx > 0.4`). Esto permite que acciones urgentes se sientan instantáneas ("snappy") y evita la fatiga por espera.

## 3. Clutching y Rearm (Embrague)

Cuando un usuario hace *Scroll* (moviendo el puño cerrado de arriba a abajo), el rango físico de su brazo es limitado. Si necesitan hacer scroll continuo, deben retroceder el brazo sin deshacer el scroll.
- **Implementación de Clutching:** En `PinchScrollGesture`, si el usuario invierte la dirección de su mano después de haber iniciado un scroll, el sistema entra en una zona neutral (rearm threshold). El scroll no se revierte, permitiendo un movimiento de "bombeo" o embrague natural similar a levantar un mouse físico del escritorio para moverlo al centro.

## 4. Ley de Fitts y Magnetismo de Objetivos

La *Ley de Fitts* dicta que el tiempo requerido para moverse hacia un área objetivo es una función de la relación entre la distancia al objetivo y el ancho del objetivo. Como el puntero basado en mirada es impreciso:
- **Snapping / Magnetismo:** En lugar de requerir que el usuario haga clic exactamente en la X o la barra de título, los gestos (como Click o Scroll) siempre priorizan la ventana (Window Target) más cercana a la mirada dentro de un radio de tolerancia (220px). Esto aumenta artificialmente el ancho del objetivo, haciendo que tareas que requerirían extrema precisión visual sean triviales.

## 5. Zonas de Exclusión y Pose de Descanso

El "Problema del Toque de Midas" (Midas Touch Problem) establece que en una interfaz espacial cada movimiento podría interpretarse erróneamente como un comando.
- **Exclusión Facial:** El sistema bloquea cualquier gesto si la mano cruza una "zona de exclusión" alrededor de la cara del usuario. Esto permite que el usuario se toque la cara, se rasque, o descanse la mano en el mentón sin disparar clics accidentales o latigazos.
- **Máquina de Estados con Cooldowns:** Tras completar cualquier gesto (ej. un *Pinch Zoom* o un Clic), el sistema entra en un estado de `COOLDOWN`. Se ignora cualquier movimiento de mano hasta que el usuario "rompa" la pose (ej. abriendo la mano completamente), previniendo activaciones dobles (Double-Bounce).

---
*Este documento establece el estándar de calidad para futuras modificaciones al módulo `vision_input`. Cualquier nuevo gesto debe adherirse a estos principios.*
