# C03 — checkpoint tras APPS1029, REPAIR1030, 1031 y 1032

**137/742 cubiertos, 605 abiertos, 0 no aplican; 109 altas en la ventana de 24 h recalculada aquí; 0/35 categorías cerradas.** C03: 3/11 cumplidos, 5 contradichos, 3 pendientes. Sin estimación fiable de cierre completo. **RAM:** picos de tanda 2662,84 / 2580,30 / 2580,30 / 2652,30 MiB sobre 32 530 MiB de la máquina. **VRAM:** picos 3494,93 / 3492,93 / 3492,93 / 3494,93 MiB, por debajo de la guarda 3800 y del techo 4096. **Pruebas omitidas:** suites dueñas, Fast y Full, por instrucción explícita del dueño; omitidas, no verdes, no aprobadas. Registro actual SHA `e9622300757b30a26fca21d84fbbde8afc85b5cec73aea1be03c9f600ef10ee3`.

**Lo que sumó: +7 en esta sesión, de 130 a 137.** APPS1029 aportó 3 (H0085, H0315, H0317) y REPAIR1032 aportó 4 (H0251, H0588, H0683, H0706). REPAIR1030 y REPAIR1031 no aportaron ninguna y se explica por qué más abajo. La categoría «Abrir aplicaciones» pasó de 14 a 21 cubiertos.

## El instrumento que ordena el trabajo

`scratchpad/c03-open-mass-by-reach.py` cruza la masa abierta con el alcance del reconocedor: de los 612 abiertos que había, **157 ya llegaban al camino determinista** y 455 caían al modelo. En SYSTEM1028 el determinista cumplió 9/14 y el modelo 3/15, así que el orden de trabajo es por abiertos que ya llegan, no por abiertos totales. Por eso se eligió `apps_open`, con 21 de sus 40 abiertos resolviendo `app.open` sin modelo.

## APPS1029 — la tanda ancha, y lo que midió antes de ejecutar

17 literales, 5 variantes, 5 límites; exit 0, 27 terminales, 0 infracciones, 85,5 s. 10 cumplen, 17 fallan, **+3**.

**Steam quedó declarado como ya en ejecución porque su coste está medido, no supuesto:** su árbol gasta 644,39 MiB de GPU dedicada (`scratchpad/c03-app-gpu-cost.py`, el mismo contador que usa la guarda), y `WindowsInstalledApplicationOpenProvider` arranca con `UseShellExecute = false`, así que dentro del árbol medido habría roto la guarda de 3800 MiB. La guarda no se tocó: se declaró el entorno y el runner lo verifica. Los picos de las cuatro tandas confirman además que las apps que Windows activa por servicio no se atribuyen al árbol: 3492–3495 MiB **con Paint lanzado dentro de la tanda**.

Los 17 fallos son cinco causas, en `APPS1029/DIAGNOSIS.md`. Las dos que se repararon:

- **B, prosa:** las once vueltas de `app.open` sobre Steam recibieron el MISMO payload, con `was_running_before_open: true`; la prosa lo dijo en tres y lo omitió en ocho, publicando «Abrí Steam.» sobre un proceso vivo desde horas antes. El hecho no estaba en ninguna lista obligatoria: `required_fact_count` era 0.
- **A, verificación:** calculadora y configuración devolvían `verification_failed` con `effectMayHaveOccurred=true` **mientras la app quedaba abierta** —`CalculatorApp` pid 40560 arrancó a las 01:50:51, dentro de la ventana de la tanda—, porque los tres proveedores de apertura exigían que la ventana tuviera el primer plano.

## REPAIR1030 — la reparación funcionó y no acreditó, y lo dice

Siete literales, tres controles cubiertos, cuatro variantes, tres límites; exit 0, 17 terminales, 0 infracciones, 52,9 s. Los siete dejaron de mentir y los tres controles volvieron idénticos: **cero regresión**. Pero cuatro de siete publicaron la misma frase byte a byte y los siete publicaron la instrucción de reintento con vocabulario interno («antes de este turno»). El invariante 5 prohíbe respuestas visibles fijas, así que **crédito 0**, y la causa era mía: la instrucción llegaba como oración declarativa publicable.

## REPAIR1031 — invalidada por el escritorio, y de ahí salió la reparación grande

Las diecisiete vueltas devolvieron `verification_failed`, **incluidas Steam y Discord, que ocho minutos antes habían verificado con recibo sobre el mismo proceso y la misma ventana**. La ventana de primer plano era «Configuración rápida» de ShellHost.exe (handle 65862), que no cede el foco; Steam, Discord y el Paint recién lanzado estaban visibles en pantalla (`scratchpad/c03-window-state.py`). Ningún juicio de conducta es posible sobre ese material: **crédito 0, y el registro no cambió de estado por ella**.

Eso convirtió la causa A en hecho general: no es cosa de apps UWP. Exigir primer plano para afirmar «la app está abierta» convierte una condición del escritorio en un fallo de producto.

## REPAIR1032 — las dos reparaciones juntas, +4

12 literales, 3 controles, 5 variantes, 3 límites; exit 0, 23 terminales, 0 infracciones. 13 cumplen, 10 fallan, **+4**: H0251, H0588, H0683 y H0706, todos con recibo verificado de proceso y ventana donde antes había `verification_failed`. Par de crédito: dev-01 (Paint) y dev-02 (Mapa de caracteres), lanzamientos reales con frases distintas. Se declara que el par es español; el inglés del camino lo ejercitan H0588 y H0683, que pasaron en inglés.

Lo que **no** acreditó y por qué: las siete vueltas de Steam publicaron «La app Steam ya estaba abierta.» —verdad, con el destino nombrado— pero idénticas entre sí y con forma de la instrucción. El criterio sellado antes de ejecutar dice que eso falla aunque sea verdad, y no se relaja después de ver el resultado.

**Defecto espejo encontrado:** H0575 publicó «Ya tengo la calculadora abierta.» con `alreadyRunning=false`, dando por anterior un estado que acababa de crear. El chequeo nuevo sólo cubre la dirección contraria.

## Lo que está medido para la próxima reparación

Las tres respuestas veraces y **distintas** de APPS1029 —H0315, H0317 y dev-05— salieron del **primer borrador, sin instrucción correctiva**. La instrucción de reintento homogeniza. La reparación siguiente es que el hecho viaje como hecho con nombre propio y el primer borrador lo diga, no que una instrucción dicte la frase; y cubrir la dirección espejo. Sigue habiendo 7 literales de Steam y H0575 esperando exactamente eso.

| Tanda | Cumplen/ejecutados | Créditos | VRAM MiB | RAM MiB | Segundos |
|---|---:|---:|---:|---:|---:|
|1021|6/22|1|3499.56|2463.06|98.25|
|1022|21/25|10|3497.56|2467.25|85.75|
|1025|13/25|3|3499.56|2435.66|191.56|
|1028|14/31|4|3494.93|2587.37|154.80|
|1029|10/27|3|3494.93|2662.84|85.55|
|1030|7/17|0|3492.93|2580.30|52.94|
|1031|0/17 (invalidada)|0|3492.93|2580.30|52.94|
|1032|13/23|4|3494.93|2652.30|—|

**Compilación:** el cambio .NET se compiló por el arranque vigente (`main.compile_if_needed`), con `build_exit 0`, un arranque real del producto que sustituye el Core efectivo (`warmup_exit 0`, contestó «Hola, ¿en qué puedo ayudarte?») y `dotnet build-server shutdown` (`shutdown_exit 0`). El publish AOT necesita `vswhere.exe` en PATH —`%ProgramFiles(x86)%\Microsoft Visual Studio\Installer`—; sin eso el enlazado nativo falla con MSB3073. Y el Core exige que su directorio privado sea **hijo directo** de `%LOCALAPPDATA%\BAXY`: con una ruta anidada se niega a arrancar y el conductor publica `blocked_environment: runtime_not_ready`, que es lo que confundió al primer calentamiento.

**No repetir:** elección Qwen/backend/perfil 792; herencia 802; frescura 536; web 1010/1017 sin hipótesis nueva; fuente 800; paneles enteros por un fallo aislado; H0675, OCR y providers nuevos siguen aparcados. Efectos Spotify 962, Steam, Discord, Calculator, Settings y Explorer del PC réplica no se reconcilian aquí. Objetos 975/980/986 preservados. Sin limpieza global.

**Orden por masa abierta:** música 39, web 36, apps 33, archivos 32, mensajería 31, aclaración 31, instalación 31, agenda 29, vídeo 26, conocimiento 25, audio 23, conversación 22, interacción 22.
