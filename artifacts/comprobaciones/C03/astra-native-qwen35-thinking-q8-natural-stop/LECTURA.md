# Qwen3.5, razonamiento sin cierre forzado — resultado parcial

Se probaron las seis primeras preguntas conocidas con q8, sin low_effort ni
cierre forzado a 512 tokens. Salida total acotada a 2048 tokens, solicitud de
60 segundos y límites internos de transporte conservados. Perfil sólo diagnóstico;
el runtime registrado sigue siendo Granite. No se descargó otro modelo.

| Caso | Resultado |
|---|---|
| Doce por ocho | Timeout tras 38.03 s. |
| Diecisiete más veintiséis | Cuarenta y tres, 18.34 s. |
| Fourteen times six | Eighty-four, 18.56 s. |
| DNS caching | Timeout tras 38.02 s. |
| Why does DNS caching matter | Timeout tras 38.03 s. |
| Router | Timeout tras 38.03 s. |

**2 correctas / 6 terminadas, 4 timeouts.** Se detuvo anticipadamente el proceso
propio y su servidor: continuar las seis preguntas restantes no justificaba el
coste con ese perfil. STOP.json identifica procesos y motivo; exit -1 por
interrupción explícita. Los casos no ejecutados no cuentan como pass ni fail.

No hay pico GPU final certificado: el muestreador no cerró normalmente. Este
ensayo no demuestra el límite de toda la app ni que se resolvieran las fugas del
ensayo anterior. Retirar el cierre forzado no produjo un perfil viable para C03.
No promover ni encadenar presupuestos más altos para buscar una corrida favorable.
