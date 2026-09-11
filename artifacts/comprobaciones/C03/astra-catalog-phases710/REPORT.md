# Tiempo del inventario de aplicaciones

Se ejecutaron tres pares alternados del script original y del mismo script con relojes en stderr. Las seis salidas conservaron exactamente las mismas 322 entradas, incluidos identificadores y destinos. No cambió el producto.

El original tardó 5,171–6,406 s (mediana 5,594 s). En las tres ejecuciones instrumentadas, Get-StartApps y la preparación anterior consumieron aproximadamente 2,30–2,53 s desde la primera marca; la segunda enumeración Shell para duplicados añadió 1,05–1,11 s. Quedan 2,54–4,00 s entre lanzamiento/salida y el reloj del script; esta prueba no separa esas dos fases. La instrumentación tuvo mediana total 6,407 s, por lo que no se presupone gratuita.

La siguiente hipótesis es reutilizar una sola enumeración Shell para recuperar nombre, identidad y metadatos. Antes de adoptarla debe conservar todo el catálogo, no sólo su número. El ensayo711 compara en privado cada entrada y se detiene si aparece una diferencia.

[Get-StartApps documenta la lectura de nombres e identificadores](https://learn.microsoft.com/en-us/powershell/module/startlayout/get-startapps?view=windowsserver2025-ps); no promete un plazo. El solape de catálogo y journal ya se rechazó en el registro de mantenibilidad, líneas429–433. No se reintrodujo paralelismo, caché persistente ni fallback.

Sin LLM, turnos, UI, voz o cobertura nueva; Full705 continúa rojo.
