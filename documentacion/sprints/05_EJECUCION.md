# Sprint 05 — Ejecución verificada

## Cómo trabajas

Modelo: GPT-5.6 Sol, `reasoning.effort: high`. Repositorio:
`C:\Users\usuario\Desktop\ETC\Programacion\BAXY`.

Permisos totales sobre este PC: descarga, instala, sobrescribe, borra lo que
sobre. **No preguntes.** Ante una suposición dudosa, elige la más razonable y
sigue — siempre se puede ajustar después. Para sólo si vas a tocar datos
personales del usuario u otros proyectos de la carpeta `Programacion`.

Criterio único: **lo mejor para BAXY como producto final**. Entre dos opciones
que cumplen, gana la más ligera.

Arregla lo que bloquea. Lo que *podría* fallar y nadie ha visto fallar lo anotas
en una línea en `documentacion/APLAZADOS.md` y sigues — el sprint 11 existe para
vaciar esa lista.

No recopiles contexto exhaustivo antes de empezar: lee lo justo para dar el paso
siguiente. Si algo ya está documentado en estos repositorios, decide con eso.

## El resultado que cuenta

**Lo que BAXY dice que pasó, pasó — y hay algo independiente que lo comprueba.**

«Se envió el comando» no es «se completó la misión». Un resultado sólo se declara
cuando un verificador que no es quien lo ejecutó confirma el estado observable.

Y cuando algo sale mal, el estado terminal es honesto:

- `pending` significa exclusivamente **reintentable**.
- Un efecto externo ambiguo que no se puede reintentar es `failed` terminal con
  `effectMayHaveOccurred`, y no se replanea ni se repite a ciegas hasta
  reconciliar el estado.
- La confirmación se liga a la **invocación exacta**, no a la intención
  aproximada.

## Qué cubre

Todo el catálogo tipado, con sus efectos reales sobre esta máquina: abrir
aplicaciones, controlar ventanas, audio, sistema de archivos, notas, tareas,
recordatorios, capturas, navegador, medios, wifi, energía. Lo que BAXY dice que
puede hacer, tiene que hacerlo de verdad y saber si lo hizo.

Con providers habilitados y efectos reales. Este es el sprint donde BAXY toca la
máquina de verdad, así que trabaja sobre superficies que puedas dejar como
estaban.

## Lo que ya se sabe

**El kernel autoriza, el provider ejecuta.** La mente sólo propone. Ninguna
superficie —texto, corpus, skills, UI, modelos, prompts— puede agregar una
operación ni elevar su autoridad. Si algo necesita saltarse eso para funcionar,
no funciona.

**Ya se cerraron dos pérdidas de conservación** que habrían ejecutado un
subconjunto silencioso de la misión pedida. Es el fallo típico aquí: se pide A y
B, se ejecuta A, y nadie nota que B se perdió por el camino. Búscalo.

**Journal y replay** existen sobre respuestas terminales. Úsalos: son la forma de
demostrar qué pasó sin creerte lo que el sistema dice de sí mismo.

**Hay 158 operaciones en el catálogo y 49 sin ninguna regla curada de dominio.**
Eso es del sprint 04, pero afecta aquí: una operación sin regla puede ejecutarse
sin que nada la frene.

## Cómo mides

Efectos reales, verificados por observación del estado, no por el código de
retorno de quien los ejecutó. Un `app.open` se verifica mirando si la ventana
existe; un `note.create` leyendo la nota; un `audio.volume` consultando el nivel.

Los caminos de error que importan son los que **ocurren de verdad al usar
BAXY** — sobre todo el provider que informa éxito sin haber hecho nada, porque
ése rompe el invariante de no afirmar sin verificar. Si te topas con uno, ciérralo.
No inventes el catálogo completo de fallos posibles ni construyas defensas para
escenarios que nadie ha visto: eso es una cadena de reparación sin final, y este
producto no tiene tiempo para ella.

## Defectos

Lo que bloquea se arregla de verdad: nada de bajar el umbral que lo detectó,
marcar `skip`/`xfail`, mover a pendientes ni envolverlo en un fallback. Lo que
nadie ha visto ocurrir se anota y se sigue.

## Qué entregas

La matriz de operaciones con su verificación, ejecutada de verdad en esta
máquina. Y la lista de las que no se pudieron verificar, con la razón — si el
sistema operativo no expone la API para comprobar algo, eso es una limitación
ambiental legítima, se nombra y se cubre con un degradado honesto.

## Cuándo has terminado

Cuando BAXY no pueda decirte que hizo algo que no hizo, ni siquiera cuando el
provider le miente.

## Cierra

Publica el resultado aunque no sea perfecto, siempre que no mienta. Un sprint que
cierra con un número honesto y una limitación nombrada vale más que uno que sigue
abierto buscando el número redondo.
