# Rutas ampliadas — desarrollo, 2026-09-06

18/18 publicados, **11/18 plenamente útiles/fieles y acordes al idioma**. No
aceptación fresca. Runtime Granite registrado, fuente sellada en PREREGISTRO.json;
sesión 12021 terminó exit 0. paired.txt/json conservan las respuestas completas.

| # | Veredicto | Motivo |
|---|---|---|
| 1 | Pasa | Saludo español natural. |
| 2 | Pasa | Capacidades reales sin afirmar efectos ya ejecutados. |
| 3 | Pasa | 03:53 coincide con la lectura de system.time. |
| 4 | Falla idioma/prosa | Hora y audio correctos, pero incluye el campo inglés «(muted)» en español. |
| 5 | Pasa | Traducción solicitada: Buenas noches. |
| 6 | Pasa | Aclara el referente que falta, sin cerrar nada. |
| 7 | Pasa | Conserva la prohibición de abrir Paint. |
| 8 | Falla | Dice que no se ha visto ninguna app abierta, sin observación; no responde al intento de abrir el programa nombrado. |
| 9 | Pasa | Saludo inglés. |
| 10 | Pasa | Hora observada, inglés. |
| 11 | Pasa | Hora, silencio y volumen coinciden con las dos lecturas. |
| 12 | Pasa | Pide aclarar el referente, sin abrir nada. |
| 13 | Falla idioma | Explicación correcta del cifrado, totalmente inglesa pese a reading=mixed. |
| 14 | Falla idioma | Saludo totalmente inglés pese a reading=mixed. |
| 15 | Falla | Pregunta cómo decir la hora en spanglish en lugar de dar la hora. |
| 16 | Falla | El pedido del archivo se transforma en «Solicitud de memoria sensible» y la respuesta repite esa proyección. No hubo confirmación exacta. |
| 17 | Falla | Ante cancelar pregunta si se quiere continuar o cancelar la memoria sensible. |
| 18 | Pasa | Lima; entrada habilitada y sin misión pendiente. |

Hay bienvenida, conversación, aclaración, resultado y resumen; error pertinente,
confirmación exacta y progreso útil siguen sin quedar acreditados. No contar
un texto publicado en una ruta distinta como cobertura de la ruta pedida.
No hubo averías inyectadas: esto no reemplaza R07.

El archivo propio permaneció intacto. FIXTURE-POST.json registra hash idéntico al
prerregistro; el agente lo retiró después con su ruta exacta. Esa limpieza no es
un efecto de BAXY ni prueba la cancelación, que falló semánticamente.

## Causas trazadas para continuar

- t4: payload clock + seen.muted/level; primer borrador inventa un reproductor,
  se rechaza; segundo conserva hechos pero copia el nombre de campo nested.
- t8: la mente clasifica unsupported y su primer texto afirma inexistencia sin
  comprobar. Tras rechazarse, C# recompone como conversation/success, sin causa;
  la política asserted_failure rechaza los siguientes límites y acaba aceptando
  una observación ausente. Preservar la disposición del turno sin inventar causas.
- t13/t14: la auditoría confirma language=mixed pero reason vacío en borradores
  totalmente ingleses. Contrastar equivalencias reales y preservación del idioma.
- t16: NaturalMemoryRequestParser.ContainsSensitiveMaterial detecta el nombre
  largo como credencial por LooksLikeCredentialToken (letras+dígitos, >=32).
  MainWindowViewModel.ExecuteMissionInputAsync enmascara el texto público;
  AddMessage vuelve a leer Messages.Last(IsUser).Body para recomponer y pierde
  la petición. Conservar privacidad y significado; no quitar el detector global.

El siguiente trabajo debe resolver estos contratos de entrada/composición;
las mediciones anteriores de modelos no justifican otro barrido.
