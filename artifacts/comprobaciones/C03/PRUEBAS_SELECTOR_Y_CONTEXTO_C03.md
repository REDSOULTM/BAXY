# C03 — pruebas literales del selector nativo y del contexto

Desarrollo y regresión consumidos; no son los cien turnos de aceptación. Las entradas históricas y los controles sintéticos se identifican en cada CASES.json. Se preservan todos los fallos. Las transcripciones siguientes se leen de las capturas, sin reescribir respuestas.

## astra-native-primary13

[Prerregistro](astra-native-primary13/PREREG.json) · [Captura](astra-native-primary13/paired.json) · [Recursos](astra-native-primary13/RESULT.json)

Proceso: exit 0; 117.22 s; pico GPU 3499.56 MiB. Registro sin cambios: True.

### Turno 1

**Entrada literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí. El agua es H₂O, es decir, dos átomos de hidrógeno unidos a uno de oxígeno.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 2

**Entrada literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H₂O. El aire es una mezcla de gases, principalmente nitrógeno (N₂), oxígeno (O₂), y un poco de dióxido de carbono (CO₂), entre otros. H₂O es agua, no aire.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 3

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
[No hubo respuesta final visible]
```

Terminal registrado: `composition_failed`.

NO APROBADO: fallo de composición, sin respuesta útil.

### Turno 4

**Entrada literal**
```text
Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.
```

**Respuesta literal**
```text
El aire se compone principalmente de:  
- **78% nitrógeno (N₂)**: gas inerte, no participa en reacciones químicas importantes.  
- **21% oxígeno (O₂)**: esencial para la respiración de los seres vivos.  
- **0.04% dióxido de carbono (CO₂)**: necesario para la fotosíntesis y el equilibrio climático.  
- **Hidrógeno (H₂)** y **helio (He)** en cantidades muy pequeñas.  
- Otros gases como argón, neón, xenón, y trace gases.

La **humedad** es el agua en forma de vapor (H₂O) presente en el aire. Aunque el aire no es una mezcla de gases como H₂O, la humedad influye en el clima, la temperatura percibida (por ejemplo, el aire húmedo se siente más cálido aunque tenga la misma temperatura), y en procesos biológicos como la transpiración o la evaporación. La humedad también afecta la capacidad del aire para retener calor y puede influ
```

Terminal registrado: `published_final`.

NO APROBADO: explicación cortada a mitad de palabra.

### Turno 5

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network. It's like a password or label that lets your device (like a phone or laptop) connect to the network. You see it when you're searching for Wi-Fi, and you need to enter the SSID to join.
```

Terminal registrado: `published_final`.

NO APROBADO: confunde el identificador SSID con una contraseña.

### Turno 6

**Entrada literal**
```text
Dime qué dispositivo de audio está activo
```

**Respuesta literal**
```text
El dispositivo de audio activo es los altavoces (Realtek(R) Audio). El volumen está en 100 y el sonido no está silenciado.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 7

**Entrada literal**
```text
no me molesta, dime la hora
```

**Respuesta literal**
```text
No pude interpretar correctamente la solicitud.
```

Terminal registrado: `published_final`.

NO APROBADO: no interpreta una petición válida de hora.

### Turno 8

**Entrada literal**
```text
dime la hora
```

**Respuesta literal**
```text
20:41
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 9

**Entrada literal**
```text
I don't mind, tell me the time
```

**Respuesta literal**
```text
[No hubo respuesta final visible]
```

Terminal registrado: `composition_failed`.

NO APROBADO: fallo de composición, sin respuesta útil.

### Turno 10

**Entrada literal**
```text
no abras Steam, dime la hora
```

**Respuesta literal**
```text
No abro Steam, te digo que son las 14 horas.
```

Terminal registrado: `published_final`.

NO APROBADO: afirma las 14 horas sin lectura; las lecturas contiguas verifican 20:41.

### Turno 11

**Entrada literal**
```text
no me digas la hora
```

**Respuesta literal**
```text
No te digo la hora.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 12

**Entrada literal**
```text
no uses herramientas, dime la hora
```

**Respuesta literal**
```text
No uso herramientas, no puedo decir la hora.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 13

**Entrada literal**
```text
dime la hora
```

**Respuesta literal**
```text
20:41
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

## astra-native-budget13

[Prerregistro](astra-native-budget13/PREREG.json) · [Captura](astra-native-budget13/paired.json) · [Recursos](astra-native-budget13/RESULT.json)

Proceso: exit 0; 103.17 s; pico GPU 3497.56 MiB. Registro sin cambios: True.

### Turno 1

**Entrada literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí. El agua es H₂O, es decir, dos átomos de hidrógeno unidos a uno de oxígeno.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 2

**Entrada literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H₂O. El aire es una mezcla de gases, principalmente nitrógeno (N₂), oxígeno (O₂), y un poco de dióxido de carbono (CO₂), entre otros. H₂O es agua, no aire.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 3

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una nube de servicios de la empresa Microsoft que permite ejecutar aplicaciones, juegos y servicios en la nube. Es como una plataforma donde puedes jugar juegos, usar apps o incluso ejecutar computadoras en la nube, todo desde tu dispositivo. Es muy usado en el mundo de los juegos y la productividad.
```

Terminal registrado: `published_final`.

NO APROBADO: atribuye Steam a Microsoft y lo describe como nube de computación.

### Turno 4

**Entrada literal**
```text
Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.
```

**Respuesta literal**
```text
El aire se compone principalmente de nitrógeno (aproximadamente 78%), oxígeno (21%), y pequeñas cantidades de gases como argón (0,93%), dióxido de carbono (0,04%), helio, neón, hidrógeno y otros gases inactivos.  

La humedad, o vapor de agua, es el agua en estado gaseoso que se mezcla con el aire. Aunque no es un componente principal como el nitrógeno o oxígeno, la humedad influye en el clima, la temperatura percibida (por ejemplo, el aire húmedo se siente más cálido aunque esté a la misma temperatura), y es esencial para procesos biológicos como la fotosíntesis y el ciclo del agua.
```

Terminal registrado: `published_final`.

No aceptado como prueba de exactitud: termina, pero añade generalizaciones sobre humedad y procesos biológicos que la corrida no verifica.

### Turno 5

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network that devices connect to when joining a wireless internet connection. It's like a password or identifier that lets your phone, laptop, or tablet know which network to connect to.
```

Terminal registrado: `published_final`.

NO APROBADO: conserva la analogía falsa con una contraseña.

### Turno 6

**Entrada literal**
```text
Dime qué dispositivo de audio está activo
```

**Respuesta literal**
```text
El dispositivo de audio activo es los altavoces (Realtek(R) Audio). El volumen está en 100 y el sonido no está silenciado.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 7

**Entrada literal**
```text
no me molesta, dime la hora
```

**Respuesta literal**
```text
No pude interpretar correctamente la solicitud.
```

Terminal registrado: `published_final`.

NO APROBADO: no interpreta una petición válida de hora.

### Turno 8

**Entrada literal**
```text
dime la hora
```

**Respuesta literal**
```text
20:54
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 9

**Entrada literal**
```text
I don't mind, tell me the time
```

**Respuesta literal**
```text
[No hubo respuesta final visible]
```

Terminal registrado: `composition_failed`.

NO APROBADO: fallo de composición, sin respuesta útil.

### Turno 10

**Entrada literal**
```text
no abras Steam, dime la hora
```

**Respuesta literal**
```text
No abro Steam, te digo que son las 14 horas.
```

Terminal registrado: `published_final`.

NO APROBADO: afirma las 14 horas sin lectura; las lecturas contiguas verifican 20:54.

### Turno 11

**Entrada literal**
```text
no me digas la hora
```

**Respuesta literal**
```text
Alright, no te digo la hora.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 12

**Entrada literal**
```text
no uses herramientas, dime la hora
```

**Respuesta literal**
```text
No uso herramientas, no puedo decir la hora.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 13

**Entrada literal**
```text
dime la hora
```

**Respuesta literal**
```text
20:54
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

## astra-definition-context7

[Prerregistro](astra-definition-context7/PREREG.json) · [Captura](astra-definition-context7/paired.json) · [Recursos](astra-definition-context7/RESULT.json)

Proceso: exit 0; 82.11 s; pico GPU 3499.56 MiB. Registro sin cambios: True.

### Turno 1

**Entrada literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí. El agua es H₂O, es decir, dos átomos de hidrógeno unidos a uno de oxígeno.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 2

**Entrada literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H₂O. El aire es una mezcla de gases, principalmente nitrógeno (N₂), oxígeno (O₂), y un poco de dióxido de carbono (CO₂), entre otros. H₂O es agua, no aire.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 3

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma de distribución y comercio de juegos online, creada por Valve, donde puedes comprar, descargar, jugar y gestionar juegos, así como acceder a contenido adicional como mods, música y aplicaciones.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 4

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network that devices connect to when joining the internet.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 5

**Entrada literal**
```text
¿y para qué sirve?
```

**Respuesta literal**
```text
¿De qué cosa quieres saber el propósito?
```

Terminal registrado: `published_final`.

NO APROBADO: pierde el referente SSID y pregunta por un tema que ya está en el historial. turn-audit localiza la conversión de knowledge a clarify en observation_not_recital, antes del chat.

### Turno 6

**Entrada literal**
```text
define DNS
```

**Respuesta literal**
```text
DNS es un sistema que convierte nombres de dominio en direcciones IP para que los dispositivos puedan comunicarse en internet.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 7

**Entrada literal**
```text
explain what DNS does
```

**Respuesta literal**
```text
I explain what DNS does by translating domain names into IP addresses so devices can find and connect to websites.
```

Terminal registrado: `published_final`.

NO APROBADO: la primera respuesta explica DNS correctamente, pero App y compose rechazan el hostname como internal_code; la tercera composición introduce metadiscurso. No es un fallo de conocimiento en la primera respuesta.

## astra-public-host3

[Prerregistro](astra-public-host3/PREREG.json) · [Captura](astra-public-host3/paired.json) · [Recursos](astra-public-host3/RESULT.json)

Proceso: exit 0; 57.12 s; pico GPU 3497.56 MiB. Registro sin cambios: True.

### Turno 1

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network that devices use to connect to the internet.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 2

**Entrada literal**
```text
define DNS
```

**Respuesta literal**
```text
DNS (Domain Name System) es un sistema que convierte nombres de dominio humanos, como www.google.com, en direcciones IP numéricas que los ordenadores usan para identificar y acceder a servicios en internet.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

### Turno 3

**Entrada literal**
```text
explain what DNS does
```

**Respuesta literal**
```text
DNS translates human-readable domain names (like www.google.com) into machine-readable IP addresses so devices can locate and connect to websites and services online.
```

Terminal registrado: `published_final`.

APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.

## Ablación de políticas e historial

Doce llamadas directas. Mismo modelo, temperatura, presupuesto y template; se comparan presencia de las políticas y presencia del historial publicado. Se captura la primera respuesta, antes de validadores/reintentos. El historial previo exacto está en cada payload.

[Método e historial](astra-knowledge-history-factorial/PREREG.json) · [Todos los payloads y respuestas](astra-knowledge-history-factorial/posts.jsonl)

Hallazgo: con políticas y sin historial ajeno al tema, Steam se atribuye a Valve y SSID se define como nombre de red. Con historial aparecen hechos falsos; sin políticas varias respuestas agotan el presupuesto. Esto localiza una contribución del contexto, sin demostrar que el modelo aislado siempre acierte ni justificar borrar el historial general.

### Llamada 1: product_history

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es vapor de agua. Se forma cuando el agua se calienta hasta que se convierte en gas. Es muy usado en motores, centrales eléctricas y en sistemas de calefacción. En el mundo de la tecnología, "Steam" también puede referirse al servicio de juegos de la empresa Valve, pero en términos científicos, es vapor de agua.
```

Finalización del modelo: `stop`. Las respuestas `length` están incompletas y no se aprueban.

### Llamada 2: product_history

**Entrada literal**
```text
Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.
```

**Respuesta literal**
```text
El aire se compone principalmente de nitrógeno (aproximadamente 78%), oxígeno (aproximadamente 21%), y pequeñas cantidades de gases como argón (0.93%), dióxido de carbono (0.04%), helio, neón, hidrógeno y otros gases inactivos.  

La humedad, o vapor de agua, es el componente en forma de vapor que se mezcla con el aire. Aunque no es un gas en proporción fija, influye en el clima, la temperatura percibida y la capacidad del aire para retener calor. La humedad afecta el confort humano (por ejemplo, hace más cálido en verano o más frío en invierno), y es clave en procesos como la evaporación, la condensación y el equilibrio hídrico en ecosistemas.
```

Finalización del modelo: `stop`. Las respuestas `length` están incompletas y no se aprueban.

### Llamada 3: product_history

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network that devices use to connect to the internet. It's like a password or identifier that lets your phone, laptop, or tablet know which network to join.
```

Finalización del modelo: `stop`. Las respuestas `length` están incompletas y no se aprueban.

### Llamada 4: product_no_history

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma de distribución y comercio de juegos online, creada por Valve, donde puedes comprar, descargar, jugar y gestionar juegos, así como acceder a contenido adicional como mods, música y aplicaciones.
```

Finalización del modelo: `stop`. Las respuestas `length` están incompletas y no se aprueban.

### Llamada 5: product_no_history

**Entrada literal**
```text
Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.
```

**Respuesta literal**
```text
El aire se compone principalmente de nitrógeno (78%), oxígeno (21%), argón (0.9%), dióxido de carbono (0.04%) y pequeñas cantidades de gases inanimados como helio, neón, metano y vapor de agua. La humedad, o vapor de agua, es un componente variable que influye en la temperatura, la sensación térmica y en procesos como la evaporación y la condensación. Aunque no es un gas fijo, el vapor de agua afecta directamente el clima, la salud humana y los procesos biológicos, como la fotosíntesis y la respiración.
```

Finalización del modelo: `stop`. Las respuestas `length` están incompletas y no se aprueban.

### Llamada 6: product_no_history

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network that devices connect to when joining the internet.
```

Finalización del modelo: `stop`. Las respuestas `length` están incompletas y no se aprueban.

### Llamada 7: bare_history

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
¡Claro! Vamos a explicarlo de forma clara y sencilla:

### ¿Qué es el vapor (o steam)?

**El vapor**, también conocido como **vapor de agua**, es el estado de la **agua en forma gaseosa**. Es el resultado de que el agua se **calienta** hasta que se convierte en gas.

---

### ¿Cómo se forma el vapor?

1. **Agua líquida** (como en un recipiente o en un baño) se calienta.
2. A medida que aumenta la temperatura, las moléculas del agua se mueven más rápido.
3. Cuando alcanzan un cierto punto (el punto de ebullición, que es **100 °C a presión atmosférica normal**), las moléculas se separan completamente del líquido y se convierten en **vapor**.
4. Este vapor es **invisible**, pero puedes sentirlo porque se siente caliente al tocarlo o al respirarlo.

---

### ¿Qué es diferente del vapor y del agua?

| Característica       | Agua líquida       | Vapor (agua gaseosa) |
|----------------------|
```

Finalización del modelo: `length`. Las respuestas `length` están incompletas y no se aprueban.

### Llamada 8: bare_history

**Entrada literal**
```text
Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.
```

**Respuesta literal**
```text
¡Claro! Vamos a explicar con detalle **de qué gases se compone el aire** y **qué papel tiene la humedad** en el ambiente.

---

### 🌬️ ¿De qué gases se compone el aire?

El aire que respiramos en la Tierra es una **mezcla de gases** que varía ligeramente según la región, la altitud o la temporada, pero en general, su composición es aproximadamente la siguiente:

| Gas | Porcentaje aproximado (%) | Descripción |
|-----|----------------------------|-----------|
| **Nitrógeno (N₂)** | ~78% | El gas más abundante en el aire. Es inerte (no reacciona fácilmente) y es esencial para la vida porque es un componente clave en la formación de proteínas y ácidos nucleicos en los organismos vivos. |
| **Oxígeno (O₂)** | ~21% | Esencial para la respiración celular en los seres vivos. Los seres humanos y muchos animales lo usan para producir energía a través de la respiración aeróbica. |
| **Argón (Ar)** | ~0
```

Finalización del modelo: `length`. Las respuestas `length` están incompletas y no se aprueban.

### Llamada 9: bare_history

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An **SSID** (pronounced "ess-see-dee") stands for **Service Set Identifier**.

It is a unique name or identifier assigned to a wireless local area network (Wi-Fi network). Think of it as the *name* of your Wi-Fi network when you're looking for a connection on your phone, laptop, or tablet.

### Key Points About SSID:
- **Purpose**: Helps devices (like smartphones or laptops) identify and connect to a specific Wi-Fi network.
- **Example**: If your router is named "HomeWiFi" or "LivingRoom", that's the SSID.
- **Visibility**: You can choose whether the SSID is visible (broadcast) or hidden (not shown in the list of available networks). Hidden SSIDs require users to manually enter the network name.
- **Security**: The SSID itself does not provide security. Security comes from the **password** and encryption (like WPA2 or WPA3) set on the network.

### Example:
When you open your phone’s Wi-Fi settings and see a list of networks, the names listed (like "MyHome", "OfficeNet", or "GuestWiFi") are SSIDs.

✅ In short:  
**SSID = the name of your Wi-Fi network
```

Finalización del modelo: `length`. Las respuestas `length` están incompletas y no se aprueban.

### Llamada 10: bare_no_history

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
¡Claro! **Steam** es una plataforma de comercio electrónico y distribución de software, principalmente conocida por ser la tienda más grande del mundo para **juegos de computadora**. Fue lanzada en 2003 por **Valve Corporation**, la misma empresa que desarrolló el famoso juego *Half-Life 2*.

---

### 🔍 ¿Qué es Steam en resumen?

**Steam** es una plataforma que permite a los usuarios comprar, descargar, jugar, compartir y personalizar juegos (principalmente para PC), así como acceder a una gran variedad de contenido adicional como:

- Juegos (clásicos, indie, de alto rendimiento, etc.)
- Software de productividad (como herramientas de edición o simuladores)
- Aplicaciones (como Discord, OBS, o herramientas de streaming)
- Cursos y contenido educativo
- Juegos en línea y multijugador
- Comunidad y foros

---

### ✅ Características principales de Steam:

1. **Tienda de juegos**
   - Más de **70,000 juegos** disponibles (en 2024).
   - Ofrece juegos de todos los estilos: RPG,
```

Finalización del modelo: `length`. Las respuestas `length` están incompletas y no se aprueban.

### Llamada 11: bare_no_history

**Entrada literal**
```text
Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.
```

**Respuesta literal**
```text
El aire que respiramos en la Tierra es un **mezcla de gases** que varía ligeramente según la ubicación geográfica, la altitud y las condiciones climáticas, pero en general tiene una composición relativamente constante. A continuación, se explica en detalle **qué gases componen el aire** y **qué papel juega la humedad** en este sistema.

---

### 🔬 Composición del aire (por volumen)

El aire atmosférico se compone principalmente de los siguientes gases:

| Gas | Porcentaje (aproximado) | Importancia |
|-----|--------------------------|-----------|
| **Nitrogeno (N₂)** | 78% | El gas más abundante. Inerte en términos biológicos, pero es esencial para la formación de proteínas y aminoácidos. |
| **Oxígeno (O₂)** | 21% | Esencial para la respiración celular en todos los seres vivos. Los seres vivos lo utilizan para producir energía. |
| **Argón (Ar)** | 0.93% | Inerte, no participa en reacciones quím
```

Finalización del modelo: `length`. Las respuestas `length` están incompletas y no se aprueban.

### Llamada 12: bare_no_history

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An **SSID** stands for **Service Set Identifier**. It is the name of a wireless local area network (WLAN), typically used to identify and connect to a Wi-Fi network.

When you see a Wi-Fi network in your device's list, the name displayed (like "HomeWiFi" or "OfficeNet") is the SSID. It allows devices (such as smartphones, laptops, or tablets) to recognize and connect to a specific wireless network.

### Key Points:
- **Purpose**: Identifies a wireless network so devices can join it.
- **Visibility**: Can be set to visible (broadcast) or hidden (not shown in device lists).
- **Security**: The SSID itself does not provide security; it's the password and encryption (like WPA2 or WPA3) that protect the network.
- **Uniqueness**: While not globally unique, each SSID should be unique within a given area to avoid confusion.

In short, the SSID is the name you see when you search for Wi-Fi networks — it's the "name" of your wireless network.
```

Finalización del modelo: `stop`. Las respuestas `length` están incompletas y no se aprueban.
