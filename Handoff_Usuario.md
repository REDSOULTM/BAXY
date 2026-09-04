# Qué está pasando con BAXY ahora mismo

Esto es un recado para ti, no para otro técnico. Puedes leerlo entero
sin saber programar.

## En una frase

Estoy en la tanda **C03**: que cada respuesta que ves (o oyes) sea
útil, natural y **fiel a lo que de verdad pasó**. El reloj ya se
publica bien. Las cien respuestas de ahora no inventan la hora ni
palabras raras, y ya no dicen que llamaron un taxi. Lo que falta para
cerrar es que deje de preguntarte si vacías la papelera o cierras una
ventana cuando le pediste otra cosa: eso es la tanda siguiente (C06).
Esta tanda **aún no se marca cerrada** por esa fila.

## Qué te pedía esta tanda

BAXY no puede:

- decir que hizo algo que no hizo;
- convertir un éxito real en «no pude»;
- convertir un «no pude confirmar» en un éxito;
- quedarse callado si no logra redactar;
- rellenar huecos con frases de plantilla.

Y tiene que hablar con su voz (un compañero, un él, que te tutea), no
con textos fijos copiados.

## El problema que heredamos

En las tandas anteriores (C01 y C02) ya se vio esto, con un reloj de
verdad al lado:

1. Le preguntas «¿Qué hora es?».
2. Por dentro, BAXY **sí lee el reloj** y lo comprueba.
3. En pantalla te decía **«No pude: no pude encontrarlo.»**

O sea: el hecho era correcto y la frase que te llegaba era mentirosa.
Eso es exactamente lo que C03 tenía que romper.

## Qué encontré (en cristiano)

Imagina tres mostradores:

1. **El que mira el mundo** (el reloj, el audio, una ventana).
2. **El que redacta** la frase que vas a leer.
3. **El que publica** esa frase en la conversación.

El mostrador 1 hacía bien su trabajo. El 2 y el 3 se peleaban.

### 1. El reloj se pedía en un formato que BAXY no usa

El reloj de verdad entrega dos datos: la hora universal y cuántos
minutos hay que sumar o restar para tu zona (aquí, cuatro horas menos).
Un muestreo viejo le pedía al redactor un campo inventado, tipo
«hora local 22:10», que **el reloj real no manda**.

El redactor no veía una hora clara, fallaba, y entonces…

### 2. Al fallar la frase, se tiraba el hecho a la basura

Si la primera redacción no pasaba el filtro, BAXY no reintentaba con
los **mismos** datos del reloj. Cambiaba el recado por «se perdieron
los hechos» y el modelo, viendo un fallo, soltaba la frase de ejemplo
del propio prompt: «no pude encontrarlo».

Por eso un éxito verificado se publicaba como fracaso.

### 3. Si se agotaban los reintentos, la respuesta desaparecía

La conversación quedaba como si nada hubiera pasado: ni la hora, ni un
aviso honesto. Tú no podías saber que había fallado, y los controles
tampoco te lo decían claro.

### 4. Las frases de «sigo con…» eran plantilla

Cuando BAXY tarda, a veces tiene que decir que sigue. Eso salía de un
molde («Sigo con [lo que escribiste]»). Esta tanda pide que también
eso lo formule el modelo, no un texto prefabricado.

### 5. Un solo paso se contaba como «misión terminada»

«¿Qué hora es?» es una sola lectura. El programa la envolvía como si
fuera una misión de varios pasos y le exigía al redactor copiar un
bloque interno ilegible. El modelo no podía, y volvía el silencio o el
«no pude».

### 6. Palabras inventadas y mentiras de «no puedo»

En las pruebas de cien frases aparecieron cosas como «decirar» (palabra
que no existe) y frases del tipo «no puedo decir la hora porque no
tengo reloj», **después** de haberte dado la hora bien en el turno de
al lado. Eso también es mentira: BAXY sí sabe leer el reloj.

### 7. Una confirmación a medias secuestraba la charla

En la primera tanda de cien, a mitad de camino BAXY se quedó preguntando
«¿confirmar o cancelar?» una y otra vez. Eso no es un defecto de la
hora: es que un asunto pendiente (borrar, mandar, etc.) captura los
turnos siguientes. Esa familia de fallos es de **la siguiente tanda
(C05)**. Yo no la doy por cerrada aquí; solo evito usarla para
«aprobar» la prosa.

## Qué ya reparé

- El redactor usa el reloj **de verdad** (hora universal + desfase) y
  dice la hora local. Ejemplo medido: a las 17:24 de tu PC, BAXY dijo
  «La hora local es 17:24.» y en inglés «The local clock shows 17:24.»
- Si la primera frase no vale, **reintenta con los mismos hechos**. Ya
  no sustituye un éxito por un «no pude encontrarlo».
- Si se acaba la paciencia del redactor, **no se esconde**: queda un
  estado de error recuperable, puedes seguir escribiendo, y no se finge
  un éxito. Lo provoqué a propósito (rechazo, tiempo agotado, cola
  vacía) y también corrí el camino real sin trampas: la hora volvió a
  salir bien.
- Un solo paso (la hora) se publica como **resultado**, no como misión
  completada.
- El «sigo con…» de plantilla ya no es lo que se publica en el producto.
  La señal de que sigue trabajando pasa por el mismo redactor.
- Un éxito no puede colarse como «no pude», ni un reloj inventado
  (por ejemplo «son las 14:30» cuando el reloj no se leyó).
- La personalidad sigue en un texto que se puede editar (el prompt).
  Las reglas de no enviar tus datos están en **otro** sitio, no mezcladas
  con el carácter.
- Lo que se lee en pantalla es lo mismo que se puede narrar en voz: no
  hay un segundo escritor para accesibilidad.

Las pruebas dueñas de este arreglo pasan. Eso no es la prueba de las
cien frases; es la red de seguridad de que el mecanismo no se rompió
al cambiarlo.

## Qué estoy haciendo ahora mismo

Ya no dejo que una pregunta de hora se resuelva «charlando». Si pides
la hora, BAXY tiene que **leer el reloj de verdad** y decir esa hora.

Lo comprobé con cinco formas distintas («¿me dices la hora?», «could
you tell me the time?», «hora ahora», etc.): las cinco dijeron
**18:45**, que era la hora de la máquina.

Volví a correr las cien. Esta vez **ningún 14:30**. Las 24 veces que
publicó una hora, coincidía con el reloj (18:47 a 19:11). Eso es el
arreglo de C03 para la hora.

**Aún no cierro la tanda.** En esas cien hay una palabra inventada
(«talcr»), un eco de la pregunta, y cuatro fallos honestos del
redactor. C03 pide cero invenciones en las cien. No voy a fingir que
eso es un diez.

Ahora mismo corre la batería completa de pruebas del repositorio
(Full). Cuando termine, o es verde y sigo con lo que falte de las
cien, o es rojo y lo arreglo.

## Qué falta para poder decir «C03 cerrado»

- Terminar y leer las cien respuestas de esta corrida. Si alguna
  inventa un hecho, una palabra o una plantilla, no se cierra.
- Volver a pasar «hola, qué puedes hacer», la hora, un error, sesión
  nueva con hora y audio, y la prueba de «se rompió el redactor».
- La batería completa de pruebas del repositorio (la compuerta Full),
  en verde.
- Dejar el trabajo publicado en la rama principal, no solo en este PC.

No voy a marcar como hecha una misión que todavía no existe (eso es
C05). No voy a relajar el filtro para que una frase falsa «pase».

## Qué no tienes que hacer tú

No hace falta que pruebes a mano, ni que juzgues las frases, ni que
copies comandos. Si la máquina se queda sin algo físico (micrófono,
altavoz), eso lo diré con nombre y cómo reanudar. El audio de verdad
(oírte y que se te oiga) es de **C08**; aquí solo dejo lista la misma
prosa para cuando llegue.

## Cómo va el mapa grande

| Tanda | Estado | En corto |
|---|---|---|
| C01 Entrada compartida | Cerrada | Tú y el agente usáis el mismo camino. |
| C02 Herencia y base | Cerrada | El árbol compila y se puede reproducir. |
| **C03 Respuesta veraz** | **En curso** | La hora ya no miente; faltan las cien y el cierre. |
| C04 en adelante | Pendiente | Efectos, misiones, comprensión, señal, voz. |

Cuando C03 cierre de verdad, el siguiente recado será C04: que lo que
BAXY dice que hizo en el PC **se pueda comprobar** mirando el mundo,
no el diario del propio BAXY.
