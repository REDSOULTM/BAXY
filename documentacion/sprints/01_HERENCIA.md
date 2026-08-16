# Goal 01 — La herencia

> **Esto es un goal, no una tarea.** Se lanza y corre hasta cumplirse. No pares a
> mitad a pedir aprobación ni a preguntar: ante una duda, elige la opción más
> razonable, anótala y sigue. Acabas cuando los criterios de cierre estén
> marcados, o cuando hayas medido que uno es inalcanzable y publicado la evidencia
> que lo demuestra. No hay una tercera forma de acabar.

## Dónde trabajas

Repositorio: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY`. Modelo: GPT-5.6 Sol,
`reasoning.effort: high`.

Permisos totales sobre este PC: descarga, instala, sobrescribe, borra lo que
sobre. **No preguntes.** Para sólo si vas a tocar datos personales del usuario u
otros proyectos de la carpeta `Programacion`.

No recopiles contexto exhaustivo antes de empezar: lee lo justo para dar el paso
siguiente. Si algo ya está documentado en estos repositorios, decide con eso.

## Qué es BAXY

Un compañero que vive en el PC de una persona y hace lo que le pide —tipo Jarvis,
local y privado—. Tiene carácter propio, es un «él», tutea, y confirma lo que hizo
comprobándolo: *«Listo, Spotify está abierto y sonando»*. Cuando falla lo dice
plano y con la causa. Nunca inventa que hizo algo, nunca actúa sin que se lo
pidan, nunca manda datos del usuario fuera.

Todo está en `documentacion/00_IDENTIDAD.md`, y **es lectura obligatoria antes de
tocar nada**. No son preferencias: son decisiones tomadas por el dueño con los
cuatro intentos anteriores del proyecto sobre la mesa. Si un diseño tuyo las
contradice, el que cambia eres tú.

## Las cinco leyes

Gobiernan este goal y los otros diez. Están por encima de cualquier preferencia
técnica tuya.

**1. Hereda primero, estado del arte después, construye al final.** En ese orden,
y sin saltarte pasos:

1. **¿Ya está resuelto en un BAXY anterior?** Este proyecto se ha escrito cuatro
   veces y muchos problemas ya cayeron. Trae esa solución — o la **mejor
   combinación** de las que hay, que muchas veces es lo que gana. El goal 01 dejó
   el mapa de qué existe y dónde.
2. **¿Está resuelto ahí fuera?** Papers, documentación, repositorios, la respuesta
   de alguien que se topó con lo mismo. Si hay una solución conocida y buena,
   **impleméntala** en vez de inventar la tuya.
3. **Sólo si ninguna de las dos**, constrúyelo. Y entonces di en el cierre por qué
   ninguna servía.

Y al revés: **que BAXY ya lo haga de una manera no es razón para conservarla.** La
vara es «¿es la mejor opción conocida hoy?», no «¿es lo que había?». Heredar es
traer lo que funciona, no conservar lo que estaba.

Es una pasada, no una persecución. En cuanto tengas algo que cumple el objetivo,
deja de buscar mejor: perseguir el estado del arte sin parar es una carrera sin
final, y este producto tiene que salir.

**2. Nada de sobreingeniería.** Escribe el mínimo código que cumpla, y que se
active sólo el necesario. Nada de capa sobre capa, ni abstracciones para un
segundo caso que no existe, ni opciones que nadie pidió, ni defensas para fallos
que nadie ha visto ocurrir.

No es estética: es la causa de muerte documentada de las cuatro versiones
anteriores de este mismo proyecto. Carter se diagnosticó a sí mismo —*«el proyecto
crece por acumulación, no por reemplazo»*— con tres routers en serie, ocho capas
de reescritura y un `agent.py` de 1.397 líneas contra su propio objetivo de 400.
Diez de sus dieciséis segundos por turno eran sobrecarga suya.

**Si añades una capa, retira la que sustituye, en este mismo goal.** Un goal que
cierra con menos código del que encontró y el objetivo cumplido es mejor goal.

**3. Sólo se arregla lo que bloquea.** Un fallo que impide usar BAXY o avanzar
este goal se arregla. Una fragilidad teórica o un camino de error que nadie ha
recorrido: una línea en `documentacion/APLAZADOS.md` y sigues. El goal 11 existe
para vaciar esa lista, así que nada se pierde por anotarlo.

**4. Lo más ligero que cumpla.** 4 GB de VRAM es el techo, no el objetivo. Entre
dos opciones que cumplen gana la más ligera, contando RAM, disco, CPU en reposo y
arranque en frío. El ahorro se detiene donde BAXY deja de entender a la primera,
de no mentir o de no dejar silencio muerto.

**5. Cada pieza sustituible, y ninguna más.** BAXY no se termina. Dentro de dos
meses saldrá un STT mejor o un modelo más pequeño que entiende igual, y hay que
poder cambiarlo sin reescribir el producto: **el código de hoy no tiene por qué ser
el de mañana**.

Pero «que todo sea intercambiable» es la puerta directa a la sobreingeniería que
prohíbe la ley 2 —interfaces con un solo implementador, registros de plugins,
configuración infinita—, y así murieron las cuatro versiones anteriores. La regla
que resuelve las dos: **una costura por pieza que de verdad se vaya a sustituir, y
ninguna más.** La lista está cerrada y vive en `documentacion/03_COSTURAS.md`; no
la amplías sobre la marcha.

Y una costura no es una interfaz. Son tres cosas, y sin las tres la pieza no es
sustituible:

1. **Un borde que nombra qué hace, no cómo.** El kernel no sabe que Windows existe;
   ése es el modelo, y ya funciona en este repositorio.
2. **La medición que decide si el candidato es mejor.** Esto es lo que de verdad
   hace sustituible una pieza: con un corpus y un número, cambiar de motor es una
   tarde; con una interfaz y sin número no puedes decidir, así que no lo cambias
   nunca.
3. **Que instalar lo nuevo incluya retirar lo viejo.**

**Cero código muerto.** Una pieza sustituida se borra: no se queda detrás de una
bandera «por si acaso». Dos implementaciones vivas de lo mismo son la acumulación
otra vez, con otro nombre.

Si este goal toca una pieza del registro, **rellena su fila antes de cerrar**: qué
medición decide un sustituto, qué elegiste y por qué, y la fecha. La fecha importa
— una medición de hace ocho meses decidió entre candidatos que hoy ya no son los
mejores.

## Y una consigna que une las cinco

Ésta es la **quinta** escritura de BAXY, y tiene que ser **la más rápida de las
cinco**. No porque haga menos —es la definitiva— sino porque **no vuelve a
descubrir nada que ya se descubrió**.

Cada hora que gastes re-derivando algo que ya está medido en estos repositorios es
una hora que este proyecto ya pagó una vez. Si te encuentras diseñando desde cero
algo que suena a que alguien ya resolvió, para y ve a buscarlo primero.

---

## El objetivo

**Saber exactamente qué hay construido ya, qué de eso funciona de verdad, y qué
se trae a BAXY.**

En `C:\Users\usuario\Desktop\ETC\Programacion` hay años de intentos de construir
este mismo asistente con nombres distintos, y algunos tienen piezas que **ya
funcionan** — hay wake word y transcripción que llegaron a servir. Rehacer eso
sería tirar meses de trabajo, y los otros diez goals van mucho más rápido si
empiezan sabiendo qué existe y dónde.

Este goal va primero por eso, y porque la ley 1 lo necesita: no puedes juzgar si
BAXY está en el estado del arte sin saber qué tiene.

**No son proyectos distintos.** El README de `Probando Gemma 4` lo dice literal —
el proyecto se renombró a Baxy, antes Gemma 4 Agent, brevemente Carter. Es el
mismo proyecto reescrito cuatro veces, así que los errores documentados son de
esta casa. La excepción es `JRVS`, que es otro producto y no hereda nada.

## Las cuatro herencias que hay que ir a buscar

`00_IDENTIDAD.md` salió de leer estos repositorios y dejó localizadas cuatro cosas
que ya no son opcionales. Empieza por ellas:

1. **La accesibilidad del Baxy anterior** — control por voz para movilidad
   reducida y narración de cada acción para personas no videntes. El dueño la
   quiere de vuelta como identidad del motor. Averigua qué había implementado de
   verdad y qué era promesa de README.
2. **La cascada UIA → OCR → visión** para operar cualquier aplicación abierta. Es
   núcleo, no extra: sin ella no existe el `Click X` de una misión compuesta.
3. **El set consolidado de 16 herramientas de Carter v4** y la medición que le dio
   −68 % de tokens sin perder calidad. El goal 03 la necesita como punto de
   partida.
4. **Lo que FunctionGemma midió sobre cuantización y prosa** — Q2 produce palabras
   inventadas y rompe la persona; Q4_K_XL QAT lo arregla en ~1,5 GB. El BAXY
   actual tiene hoy el mismo síntoma.

Mira también lo demás: routers entrenados, catálogos de operaciones, corpus,
checkpoints, arquitecturas de memoria, integraciones de escritorio.

Pistas de dónde mirar primero: `Probando Gemma 4` tiene `captures/`,
`checkpoints/` y entornos de LiveKit y de entrenamiento de router; `FunctionGemma`
tiene `speech_model/` y `router/`; `Carter OS AI` tiene un `carter_v5` completo
con documentación. No te limites a esas tres.

## La infraestructura .NET se conserva — y ya está auditada

Esto no lo tienes que evaluar: **ya se auditó y la decisión está tomada**. La capa
.NET del BAXY actual se conserva. Compila en Release con **0 advertencias** bajo
`TreatWarningsAsErrors`, `Nullable enable`, analizadores en `latest-recommended` y
`EnforceCodeStyleInBuild`; y pasa **3.865 pruebas, 0 fallos, 0 omitidas**.

Lo que la hace buena, para que no la degrades sin darte cuenta:

- **Dirección de dependencias limpia y sin ciclos:** `Contracts` (sin ninguna
  dependencia) ← `Kernel` ← `Providers.Windows` ← `Core`/`App`. El kernel no sabe
  que Windows existe. Es el invariante «la mente propone, el kernel autoriza, el
  provider ejecuta» hecho estructura.
- **Preparada para el presupuesto de recursos:** `IsAotCompatible` en las
  librerías, `PublishAot` en `Core` y `Setup`,
  `JsonSerializerIsReflectionEnabledByDefault=false` (JSON por generador, sin
  reflexión), `global.json` con `rollForward: disable`, `Deterministic` y `/Brepro`.
  Compilaciones reproducibles byte a byte.
- **Interop modernizado:** 134 `LibraryImport` contra 24 `DllImport`.
- **`MissionEngine` es el mejor fichero del repositorio:** idempotencia por huella
  de la petición, asiento en el journal antes del efecto, confirmación ligada a la
  invocación exacta, y el invariante de reintentabilidad forzado lanzando en vez de
  confiado a la disciplina.

**Se conserva sin tocar:** `Baxy.Contracts`, `Baxy.Kernel`, `Baxy.Security.Windows`
y la configuración de compilación entera (`Directory.Build.props`,
`Directory.Packages.props`, `global.json`, `.editorconfig`).

### Y se hereda arreglando tres deficiencias medidas

Las tres están localizadas. No las investigues: arréglalas al traerlas.

**1. Los adaptadores por aplicación se sustituyen por capacidad genérica.** En
`src/` hay **190 menciones de Steam, 94 de Spotify, 47 de YouTube**, con ficheros
dedicados —`SpotifyDesktopAdapter.cs`, `SteamLocalAdapter.cs`,
`YouTubeMpvAdapter.cs`, `WindowsCalculatorOpenProvider.cs`— y scripts
`SpotifyDesktopAutomation.ps1` y `SpotifyMediaControl.ps1`. Y **un solo fichero
toca UI Automation** (`WindowsDeviceControlAdapter.cs`).

Eso contradice de frente la decisión «cubrir el PC, no las apps», y es el mismo
antipatrón que Carter se documentó a sí mismo contra su propio valor «sin hacks por
app». No es sólo deuda estética: es **cobertura falsa** —cubre cuatro aplicaciones,
no el PC— y sustituirla por la cascada UIA → OCR → visión da a la vez menos
catálogo y más cobertura. Aquí sólo lo inventarías; el goal 07 lo construye. Tu
trabajo es dejar dicho **qué exactamente hay que sustituir, fichero por fichero**.

**2. `MainWindowViewModel.cs` se descompone.** 3.678 líneas y 169 miembros. Es el
`agent.py` de Carter otra vez —el que llegó a 1.397 líneas contra su propio
objetivo de 400— pero 2,6 veces más grande. La capa de abajo está bien; ésta ya se
apiló. Déjala descompuesta por responsabilidad, no repartida en ficheros con el
mismo acoplamiento.

**3. `MissionEngine` pasa de ocho constructores a uno con opciones.** Es el mejor
fichero del repositorio y aun así lleva el patrón de acumulación en miniatura: cada
dependencia opcional nueva duplica las combinaciones, y la siguiente traería
dieciséis. Un objeto de opciones lo cierra, y son minutos.

Un aviso sobre el resto: `Baxy.Setup` son **13.122 líneas de producción y 9.996 de
pruebas** para el instalador, y la instalación certificada está **fuera de alcance**
por decisión del dueño. No lo tires —funciona— pero mide su proporción y dilo en el
mapa antes de que alguien lo arrastre entero.

## La documentación se hereda igual que el código

Estos repositorios acumulan decisiones de arquitectura, torneos de tecnología,
comparativas de modelos y registros de lo que se midió y se rechazó. Eso es tan
heredable como un checkpoint y más barato de traer: una comparativa ya corrida
ahorra días.

Deja inventariado **qué preguntas ya están respondidas y dónde**, para que ningún
goal posterior vuelva a correr un torneo que alguien ya corrió.

Y marca cuáles han **caducado**: una comparativa de hace ocho meses decidió entre
candidatos que hoy no son los mejores. Eso es exactamente la ley 1 aplicada al
pasado — distinguir lo vigente de lo caducado es parte del mapa, y lo caducado hay
que rehacerlo contra lo que existe hoy.

## Cómo decides qué se hereda

Una pieza se hereda si hace a BAXY mejor **como producto final**, y sólo entonces.
Tres filtros, en este orden:

1. **¿Funciona de verdad hoy?** No lo que el README promete: lo que ejecutas y ves
   funcionar. Un modelo que carga y acierta cuenta; un script que falla al
   importar, no.
2. **¿Sigue siendo la mejor opción conocida?** Ley 1. Que funcionara en 2025 no lo
   convierte en lo correcto hoy. Si el estado del arte lo dejó atrás, se anota como
   referencia y se hereda la idea, no el binario.
3. **¿Cabe en el presupuesto?** Un STT excelente que pide 8 GB de VRAM no sirve.

BAXY tampoco es una hoja en blanco: está avanzado y tiene cosas mejores que las de
sus predecesores. Heredar no es sustituir — es quedarse con lo mejor de cada sitio.

Si una pieza heredada exige tocar los invariantes de arquitectura, no se hereda:
se anota qué habría aportado y por qué no entra.

## Criterios de cierre

Marca cada punto. Mientras quede uno sin marcar y tengas una vía razonable, sigue.

- [ ] Un mapa que dice **qué intentos hubo**, qué se propuso cada uno, y por qué se
      abandonó.
- [ ] Para cada intento, **qué funciona hoy**, comprobado ejecutándolo — no leído.
- [ ] **Qué se hereda**, de dónde, y qué hace falta para traerlo.
- [ ] **Qué no se hereda y por qué.** Un rechazo con el mecanismo entendido vale
      tanto como una herencia.
- [ ] Las **cuatro herencias obligatorias** resueltas: existe / no existe / existía
      a medias, con evidencia en cada caso.
- [ ] El inventario de **preguntas ya respondidas y dónde**, separando lo vigente
      de lo caducado.
- [ ] Las **soluciones al problema de comprensión** que hay en los cuatro
      repositorios, listadas y comparables — el goal 03 arranca de ahí y no de cero.
- [ ] La lista, fichero por fichero, de los **adaptadores por aplicación** que hay
      que sustituir por capacidad genérica.
- [ ] `MainWindowViewModel` descompuesto y `MissionEngine` con un solo constructor,
      con la compuerta .NET verde después: 3.865 pruebas, 0 advertencias.

## Cuando lo cumplas

El mapa publicado en el repositorio, en un solo documento que los otros diez goals
puedan leer sin abrir nada más.

Publica el resultado aunque no sea perfecto, siempre que no mienta. Un goal que
cierra con un hallazgo honesto y una limitación nombrada vale más que uno que
sigue abierto buscando el mapa completo.

Y anota en `documentacion/APLAZADOS.md`, en una línea cada cosa, lo que viste y no
perseguiste.
