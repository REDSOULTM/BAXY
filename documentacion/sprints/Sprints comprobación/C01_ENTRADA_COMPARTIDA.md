# C01 — La entrada del agente es la entrada del usuario

**Ejecutable: Grok 4.6 High; contexto de 500K; un solo goal persistente.**
Trabajas en BAXY Definitivo, main. Predecesor: ninguno.
Incorpora como instrucciones [contrato](01_CONTRATO_DE_CAMPANA.md) y
[protocolo 500K](02_PROTOCOLO_GROK_46_500K.md). No ejecutes los otros Cxx.

## Objetivo

Implementa una forma de conducir BAXY sin abrir su ventana que utilice la misma
entrada y la misma salida de producto que la UI. Debe permitir reproducir los
fallos del usuario y observarlos sin decisiones preseleccionadas ni respuestas
artificiales. Entrega código funcionando y un comando reproducible.

## Lee sólo lo necesario

AGENTS.md, Identidad, los dos documentos comunes, estado y casos obligatorios.
Después: FieldCenter.tsx, FieldUiBridge.cs, MainWindowViewModel.cs,
MissionInputPipeline y los tests de MindShellEndToEnd. Usa docs/AI_CONTEXT_MAP.md.
La auditoría de septiembre es evidencia inicial; no vuelvas a investigar seis
turnos para descubrir el mismo fallo. Consulta la herencia específica antes de
crear un host o controlador nuevo.

## Trabajo

1. Traza la ruta del formulario a /turn, sus validaciones y su proyección de
   eventos, hasta la respuesta final. Incluye sesión, adjuntos y controles.
   Explica dónde divergen hoy las sobrecargas SubmitAsync y el bridge.
2. Obtén baseline de las pruebas propietarias y clasifica los rojos conocidos.
   Repara los impedimentos mínimos de base que bloquearían el cierre de C01;
   registra esas reparaciones para que C02 las verifique. No hay cierre con Full rojo.
3. Extrae sólo lo necesario para que UI y conductor llamen al mismo controlador
   de producto. Mantén la composición real: mente, Core, providers, journal,
   colas, stores y prosa. Retira la lógica duplicada que se sustituya.
   Si ya existe una pieza equivalente, reutilízala y demuestra su alcance.
4. Expón texto natural y controles que ya tiene el usuario, con continuidad
   entre peticiones y perfil de datos de prueba persistente. El setup se configura
   al arrancar como un perfil normal; no limpia pendientes entre turnos a escondidas.
   No añadas flags de «modo agente» que salten política, composición o verificación.
5. Devuelve al conductor el flujo público de progreso, mensajes finales y estado
   posterior. Distingue el acuse de admisión de la terminación visible. Permite
   timeouts diagnósticos y captura de silencios sin convertirlos en éxito.
6. Prueba equivalencia de adaptadores y proyección según el contrato común.
   Preserva restricciones de origen de WebView. No publiques innecesariamente
   una API de red ni expongas internos sólo por comodidad del test.
7. Ejecuta desde esa entrada los casos R01–R06. Guarda los fallos funcionales que
   corresponden a C03–C05, sin maquillarlos. Aquí se exige que el conductor los
   capture fielmente, no que ya estén reparadas todas esas capacidades.

## Cierre obligatorio

- [x] Un comando real documentado inicia runtime sin ventana, envía texto, recibe
      eventos públicos/final y conserva sesión. No es un ejemplo pendiente de implementar.
- [x] UI y conductor comparten implementación de admisión, turno y publicación;
      paridad cubierta también para entrada inválida, adjunto, cancelar y Nueva sesión.
- [x] El perfil usa los motores reales registrados; su manifiesto, commit y
      configuración se adjuntan. Ninguna operación esperada se pasa a BAXY.
- [x] Un silencio, una respuesta filtrada y una aceptación sin respuesta final
      son detectables; el conductor no inventa una salida ni repara la sesión.
- [x] Pruebas de contrato y composición real justifican la equivalencia;
      lo exclusivamente visual o acústico no se declara verificado sin su prueba.
- [x] R01–R06 quedan como regresiones reproducibles, con resultados reales.
- [x] Tests propietarios y Full verdes, con skips separados y sin nuevos ocultamientos.
- [ ] Código propio publicado, diff revisado, comando/artefactos y estado guardados.

Evidencia: artifacts/comprobaciones/C01/. Siguiente: C02.
El cierre acredita un instrumento fiel; los fallos observados siguen abiertos
en su owner y bloquean C09.
