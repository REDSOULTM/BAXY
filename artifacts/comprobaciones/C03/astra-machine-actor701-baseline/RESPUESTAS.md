# 701 — cincuenta controles de red, Wi-Fi y CPU

Todos los primeros borradores y reintentos son generaciones del modelo local. Los dos brazos conservan exactamente51peticiones y50finales.40turnos de red/WLAN no necesitaron reparación: esta población acredita regresión conservada, no mejora del actor. La revisión raíz y la revisión independiente coinciden en44correctos y6fallos de alcance/contradicción. No acredita encuesta, UI ni voz.

## wifi.status-0-0

Petición: ¿Estoy conectado a alguna red Wi-Fi?

Respuesta: No, no estás conectado a ninguna red Wi-Fi.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": false, "authority": "netsh_wlan_status_secondread"}

## wifi.status-0-1

Petición: ¿Este PC tiene conexión Wi-Fi?

Respuesta: No, este PC no tiene conexión Wi-Fi.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": false, "authority": "netsh_wlan_status_secondread"}

## wifi.status-0-2

Petición: Dime el estado de la conexión inalámbrica.

Respuesta: La conexión inalámbrica no está activa. El PC no está conectado a una red inalámbrica.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": false, "authority": "netsh_wlan_status_secondread"}

## wifi.status-0-3

Petición: Comprueba si el equipo está conectado al wifi.

Respuesta: El equipo no está conectado al wifi.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": false, "authority": "netsh_wlan_status_secondread"}

## wifi.status-0-4

Petición: Del Wi-Fi de este computador, dime si está conectado.

Respuesta: No, el PC no está conectado al Wi-Fi.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": false, "authority": "netsh_wlan_status_secondread"}

## wifi.status-0-5

Petición: Is this PC connected to Wi-Fi?

Respuesta: No, this PC is not connected to Wi-Fi.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": false, "authority": "netsh_wlan_status_secondread"}

## wifi.status-0-6

Petición: Tell me whether the wireless connection is active.

Respuesta: The wireless connection is not active. The PC is not online.

failed: Wi-Fi connectivity is expanded to the whole PC being online/offline; only WLAN was observed.

Hechos: {"connected": false, "authority": "netsh_wlan_status_secondread"}

## wifi.status-0-7

Petición: Am I connected to a Wi-Fi network?

Respuesta: No, the PC is not connected to a Wi-Fi network.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": false, "authority": "netsh_wlan_status_secondread"}

## wifi.status-0-8

Petición: Baxy, revisa si el Wi-Fi está connected.

Respuesta: El Wi-Fi no está conectado. El PC no está online.

failed: Wi-Fi connectivity is expanded to the whole PC being online/offline; only WLAN was observed.

Hechos: {"connected": false, "authority": "netsh_wlan_status_secondread"}

## wifi.status-0-9

Petición: La conexión wireless de este PC, ¿está activa?

Respuesta: No, la conexión wireless no está activa.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": false, "authority": "netsh_wlan_status_secondread"}

## wifi.status-1-0

Petición: ¿Estoy conectado a alguna red Wi-Fi?

Respuesta: Sí, estás conectado a una red Wi-Fi.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": true, "authority": "netsh_wlan_status_secondread"}

## wifi.status-1-1

Petición: ¿Este PC tiene conexión Wi-Fi?

Respuesta: Sí, este PC tiene conexión Wi-Fi.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": true, "authority": "netsh_wlan_status_secondread"}

## wifi.status-1-2

Petición: Dime el estado de la conexión inalámbrica.

Respuesta: La conexión inalámbrica está activa. El PC está online.

failed: Wi-Fi connectivity is expanded to the whole PC being online/offline; only WLAN was observed.

Hechos: {"connected": true, "authority": "netsh_wlan_status_secondread"}

## wifi.status-1-3

Petición: Comprueba si el equipo está conectado al wifi.

Respuesta: El equipo está conectado al wifi.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": true, "authority": "netsh_wlan_status_secondread"}

## wifi.status-1-4

Petición: Del Wi-Fi de este computador, dime si está conectado.

Respuesta: Sí, el PC está conectado al Wi-Fi.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": true, "authority": "netsh_wlan_status_secondread"}

## wifi.status-1-5

Petición: Is this PC connected to Wi-Fi?

Respuesta: Yes, this PC is connected to Wi-Fi.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": true, "authority": "netsh_wlan_status_secondread"}

## wifi.status-1-6

Petición: Tell me whether the wireless connection is active.

Respuesta: Yes, the wireless connection is active. The PC is online.

failed: Wi-Fi connectivity is expanded to the whole PC being online/offline; only WLAN was observed.

Hechos: {"connected": true, "authority": "netsh_wlan_status_secondread"}

## wifi.status-1-7

Petición: Am I connected to a Wi-Fi network?

Respuesta: Yes, you are connected to a Wi-Fi network.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": true, "authority": "netsh_wlan_status_secondread"}

## wifi.status-1-8

Petición: Baxy, revisa si el Wi-Fi está connected.

Respuesta: El Wi-Fi está conectado. El PC está online.

failed: Wi-Fi connectivity is expanded to the whole PC being online/offline; only WLAN was observed.

Hechos: {"connected": true, "authority": "netsh_wlan_status_secondread"}

## wifi.status-1-9

Petición: La conexión wireless de este PC, ¿está activa?

Respuesta: Sí, la conexión wireless está activa.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"connected": true, "authority": "netsh_wlan_status_secondread"}

## network.status-0-0

Petición: ¿Hay alguna interfaz de red conectada en este PC?

Respuesta: No, no hay ninguna interfaz de red conectada en este PC.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": false, "connectedInterfaceCount": 0, "interfaceTypes": []}

## network.status-0-1

Petición: Dime si el equipo tiene un enlace de red activo.

Respuesta: No, el equipo no tiene un enlace de red activo.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": false, "connectedInterfaceCount": 0, "interfaceTypes": []}

## network.status-0-2

Petición: ¿Está conectado este computador a una red?

Respuesta: No, este PC no está conectado a una red.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": false, "connectedInterfaceCount": 0, "interfaceTypes": []}

## network.status-0-3

Petición: Comprueba el estado del enlace de red del equipo.

Respuesta: El equipo no está online.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": false, "connectedInterfaceCount": 0, "interfaceTypes": []}

## network.status-0-4

Petición: De las interfaces de red, ¿hay alguna conectada?

Respuesta: No, no hay ninguna interfaz de red conectada.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": false, "connectedInterfaceCount": 0, "interfaceTypes": []}

## network.status-0-5

Petición: Does this PC have an active network link?

Respuesta: No, this PC does not have an active network link.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": false, "connectedInterfaceCount": 0, "interfaceTypes": []}

## network.status-0-6

Petición: Tell me if any network interface is connected.

Respuesta: No network interface is connected. The PC is offline.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": false, "connectedInterfaceCount": 0, "interfaceTypes": []}

## network.status-0-7

Petición: Is this computer connected to a network?

Respuesta: No, this PC is not connected to a network.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": false, "connectedInterfaceCount": 0, "interfaceTypes": []}

## network.status-0-8

Petición: Baxy, ¿hay alguna network interface conectada?

Respuesta: No, no hay ninguna interfaz de red conectada. El PC no está online.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": false, "connectedInterfaceCount": 0, "interfaceTypes": []}

## network.status-0-9

Petición: El enlace de red del equipo, ¿está online?

Respuesta: No, el equipo no está online.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": false, "connectedInterfaceCount": 0, "interfaceTypes": []}

## network.status-1-0

Petición: ¿Hay alguna interfaz de red conectada en este PC?

Respuesta: Sí, hay una interfaz de red conectada en este PC. Está en línea.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": true, "connectedInterfaceCount": 1, "interfaceTypes": ["ethernet"]}

## network.status-1-1

Petición: Dime si el equipo tiene un enlace de red activo.

Respuesta: Sí, el equipo tiene un enlace de red activo.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": true, "connectedInterfaceCount": 1, "interfaceTypes": ["ethernet"]}

## network.status-1-2

Petición: ¿Está conectado este computador a una red?

Respuesta: Sí, este PC está conectado a la red.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": true, "connectedInterfaceCount": 1, "interfaceTypes": ["ethernet"]}

## network.status-1-3

Petición: Comprueba el estado del enlace de red del equipo.

Respuesta: El equipo está online.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": true, "connectedInterfaceCount": 1, "interfaceTypes": ["ethernet"]}

## network.status-1-4

Petición: De las interfaces de red, ¿hay alguna conectada?

Respuesta: Sí, el PC está online.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": true, "connectedInterfaceCount": 1, "interfaceTypes": ["ethernet"]}

## network.status-1-5

Petición: Does this PC have an active network link?

Respuesta: Yes, this PC has an active network link.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": true, "connectedInterfaceCount": 1, "interfaceTypes": ["ethernet"]}

## network.status-1-6

Petición: Tell me if any network interface is connected.

Respuesta: The PC is online. No network interface is connected.

failed: Says no interface is connected despite the observed active interface; contradicts its own online claim.

Hechos: {"online": true, "connectedInterfaceCount": 1, "interfaceTypes": ["ethernet"]}

## network.status-1-7

Petición: Is this computer connected to a network?

Respuesta: Yes, this PC is online.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": true, "connectedInterfaceCount": 1, "interfaceTypes": ["ethernet"]}

## network.status-1-8

Petición: Baxy, ¿hay alguna network interface conectada?

Respuesta: Sí, hay una interfaz de red conectada. El PC está online.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": true, "connectedInterfaceCount": 1, "interfaceTypes": ["ethernet"]}

## network.status-1-9

Petición: El enlace de red del equipo, ¿está online?

Respuesta: Sí, el equipo está online.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"online": true, "connectedInterfaceCount": 1, "interfaceTypes": ["ethernet"]}

## cpu-0-0

Petición: ¿Cuánta CPU estoy usando?

Respuesta: Estás usando el 0% de la CPU.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"scope": "cpu", "cpu": {"usagePercent": 0, "physicalCoreCount": 6, "logicalProcessorCount": 12, "model": "Example Processor"}, "failures": []}

## cpu-0-1

Petición: Dime el uso actual del procesador.

Respuesta: El procesador no está en uso actualmente.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"scope": "cpu", "cpu": {"usagePercent": 0, "physicalCoreCount": 6, "logicalProcessorCount": 12, "model": "Example Processor"}, "failures": []}

## cpu-0-2

Petición: What is the current CPU usage?

Respuesta: The current CPU usage is 0%.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"scope": "cpu", "cpu": {"usagePercent": 0, "physicalCoreCount": 6, "logicalProcessorCount": 12, "model": "Example Processor"}, "failures": []}

## cpu-0-3

Petición: How much CPU am I using?

Respuesta: You're using 0% of the CPU.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"scope": "cpu", "cpu": {"usagePercent": 0, "physicalCoreCount": 6, "logicalProcessorCount": 12, "model": "Example Processor"}, "failures": []}

## cpu-0-4

Petición: Baxy, ¿cuánto CPU usage tiene este PC?

Respuesta: Este PC no tiene uso de CPU detectado.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"scope": "cpu", "cpu": {"usagePercent": 0, "physicalCoreCount": 6, "logicalProcessorCount": 12, "model": "Example Processor"}, "failures": []}

## cpu-37.25-0

Petición: ¿Cuánta CPU estoy usando?

Respuesta: Estás usando el 37,25% de la CPU.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"scope": "cpu", "cpu": {"usagePercent": 37.25, "physicalCoreCount": 6, "logicalProcessorCount": 12, "model": "Example Processor"}, "failures": []}

## cpu-37.25-1

Petición: Dime el uso actual del procesador.

Respuesta: El procesador actualmente está en uso con un 37,25 por ciento de ocupación.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"scope": "cpu", "cpu": {"usagePercent": 37.25, "physicalCoreCount": 6, "logicalProcessorCount": 12, "model": "Example Processor"}, "failures": []}

## cpu-37.25-2

Petición: What is the current CPU usage?

Respuesta: The current CPU usage is 37.25%.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"scope": "cpu", "cpu": {"usagePercent": 37.25, "physicalCoreCount": 6, "logicalProcessorCount": 12, "model": "Example Processor"}, "failures": []}

## cpu-37.25-3

Petición: How much CPU am I using?

Respuesta: The computer is using 37.25% of the CPU.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"scope": "cpu", "cpu": {"usagePercent": 37.25, "physicalCoreCount": 6, "logicalProcessorCount": 12, "model": "Example Processor"}, "failures": []}

## cpu-37.25-4

Petición: Baxy, ¿cuánto CPU usage tiene este PC?

Respuesta: Este PC tiene un uso de CPU del 37,25%.

correct: Facts, scope, polarity and language agree. User-directed CPU wording follows the question and does not claim assistant process usage.

Hechos: {"scope": "cpu", "cpu": {"usagePercent": 37.25, "physicalCoreCount": 6, "logicalProcessorCount": 12, "model": "Example Processor"}, "failures": []}
