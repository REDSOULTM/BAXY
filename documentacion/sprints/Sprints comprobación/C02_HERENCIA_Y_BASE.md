# C02 — Herencia integrada y base reproducible

**Ejecutable: Grok 4.6 High; contexto de 500K; un solo goal persistente.**
Predecesor: C01 cumplido. Incorpora [contrato](01_CONTRATO_DE_CAMPANA.md) y
[protocolo 500K](02_PROTOCOLO_GROK_46_500K.md). Tu responsabilidad es restaurar
los compromisos de base de 01/02 y la integración histórica pertinente de 09.5.

## Objetivo

BAXY debe arrancar con sus piezas correctas, reproducirse desde el repositorio
publicado y pasar sus compuertas. La herencia seleccionada debe estar integrada,
sin depender de fuentes del intento anterior que parezcan este runtime.

## Lecturas dirigidas

Filas G01 y G02 de la [matriz](03_MATRIZ_DE_CRITERIOS.md), mapa de herencia,
decisiones 09.5 pertinentes, base/00_COMPUERTA.md y auditoría de septiembre.
Usa sus rutas exactas; no recorras toda la biblioteca. Revisa main.py, discovery
de runtime, setup/manifiestos y el owner que explique cada rojo.

## Trabajo

1. Verifica HEAD, cambios propios/ajenos, runtime real y comando compartido de
   C01. Reproduce el estado actual: no heredes los conteos antiguos como resultado.
2. Completa el inventario del 01, con procedencia ejecutable y cuatro herencias
   obligatorias: accesibilidad, UIA/OCR/visión, catálogo consolidado y prosa/
   cuantización. Comprueba lo conservado y sus rechazos; no trasplantes por novedad.
   Concilia el delta de 09.5 sin relanzar toda su recuperación.
3. Revisa la lista de adaptadores por app y la descomposición comprometida de
   MainWindowViewModel y MissionEngine. Completa responsabilidades separadas
   cuando siga incumplida; no declares cumplimiento por contar líneas o renombrar
   métodos. Mantén las pruebas del comportamiento que se extrae.
4. Elimina dependencias accidentales de la carpeta BAXY anterior mediante
   aprovisionamiento/manifiestos reproducibles de activos, sin borrar ni modificar
   ese repositorio. Comprueba modelo, binarios y Python realmente cargados.
5. Resuelve los rojos de base con su causa. En b2505da dos evaluadores STT esperan
   un sello anterior al cambio de scripts/goal095_09512_integrate.py. Revisa linaje
   antes de actualizar la expectativa; no reescribas contratos de campañas históricas.
   Diferencia el STT intermitente y la prueba untracked de identidad SessionOptions.
   No borres pruebas ajenas ni confundas identidad de objetos con consumo medido.
6. Verifica sellos UI/runtime y detección de binario diferente. Prepara un clon
   limpio del commit con setup documentado; sólo activos externos declarados pueden
   aprovisionarse. No copies una carpeta de desarrollo «hasta que funcione».
7. Full dos veces sobre árbol congelado y otra en clon limpio, como exige el 02.
   La entrada común también debe arrancar y realizar una lectura real allí.
   No exige aún que todos los casos de prosa posteriores estén resueltos:
   conserva esos fallos de producto y no los llama éxitos.

## Cierre obligatorio

- [ ] Todas las filas propias G01/G02 tienen evidencia actual o procedencia
      histórica verificable para hechos históricos; integración actual probada.
- [ ] Las cuatro herencias y las decisiones 09.5 no dejan fuentes omitidas sin justificar.
- [ ] Runtime correcto y reproducible; manifiesto versionado sin secretos y
      binarios identificados; ninguna ruta accidental al código del otro BAXY.
- [ ] Descomposición y ownership del 01 cumplidos, sin capas duplicadas ni pérdida de conducta.
- [ ] Full verde dos veces y clon limpio verde; skips detallados no cuentan como pass.
- [ ] C01 permanece funcional en el clon con los mismos controles y proyección.
- [ ] Cambios propios publicados, estado y evidencia enlazados; ninguna limpieza de trabajo ajeno.

Evidencia: artifacts/comprobaciones/C02/. Siguiente: C03.
