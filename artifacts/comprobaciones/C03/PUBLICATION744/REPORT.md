# Publicación reproducible — C03, tramo 744

Full6 terminó rojo, con un único fallo: el test de auditoría V8 todavía esperaba la huella del programa actual anterior a la reparación 740. Sus hashes de evidencia histórica y todos sus resultados numéricos siguen intactos. El registro actual de `__main__.py` se actualizó a `908c4276977761e1c64f20b005dfd8dde0a0180869fc11d8c26e02577e5f5f99`.

Full6: .NET **4574 aprobadas, 0 fallos y 1 skip agregado**; además hay 16 mensajes explícitos de omisiones opt-in que no se cuentan como aprobaciones. Python: **11398 aprobadas, 1 fallo, 3 skips y 466 subtests aprobados**, 736,77 s. Las pruebas originales de sidecar (3 s) y empaquetado (45 s) pasaron sin modificarlas. El resultado rojo permanece en `../FULL6_742/ADJUDICATION.json`.

Git exige LF en fuente viva. `voice_aec.py`, `voice.py` y las dos declaraciones STT contenían CRLF o finales mezclados; se normalizaron después de terminar Full6. La primera comprobación de 744 detectó también `voice.py` y se completó la normalización. En ese archivo sólo cambiaron los bytes locales: coincide con el blob ya versionado. No se añadieron excepciones de formato a fuente viva. Las excepciones de `.gitattributes` sólo conservan artefactos históricos y sus conductores de diagnóstico.

El árbol actual de **407 archivos Python** tiene SHA-256 `edaa6459d951f43de878d41ae67e1bbd7d5fc108b915d6fc65d451ab306f7491`. Las declaraciones STT actuales lo reflejan. Los registros de campañas anteriores no se actualizaron.

Validación posterior: los tests de auditoría V8, protocolo, pipe no bloqueante, ciclo del sidecar/proceso, captura de voz, AEC, evaluadores STT y programa de wake terminaron con **111 pass, 0 fail, 1 skip ambiental**, 6,58 s. Ese skip requiere datos de una campaña de voz ciega; no acredita audio físico. Full7 se ejecutará sobre los bytes canónicos antes de adoptar el candidato integrado.

No hubo inferencia, cambios de modelo ni cobertura nueva: encuesta **26 cubiertos, 716 abiertos, 0 no aplicables**. C03 sigue en curso.
