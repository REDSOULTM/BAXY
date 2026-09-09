# C03 — tramo16: ventanas por título y procesos compartidos

EN_CURSO;Goal-c03/main intacto. Autoridad/identidad vigentes,sin subagentes niFull.
Tramo15 fue progreso:proyección cancelada/capacidades mínimas ycontraste real.

Causa investigada en tramo14:WindowsWindowControlProvider buscaba Process.GetProcessesByName
y sólo MainWindowHandle. No resuelve títulos naturales ni todas las ventanas de un
host compartido. Se hereda EnumWindows y la comparación normalizada de títulos de
WindowsInstalledApplicationPlatform;se elimina la enumeración por ventana principal.
Cada candidato conserva HWND/PID/inicio del proceso yse verifica individualmente;
se añade título observado para desambiguación yprosa,con readback del título.

Contrato explícito:window.resolve añade byTitle boolean opcional,defaultfalse;
process sigue siendo proceso por defecto ylleva título sólo con byTitle=true.
No permitir que un título suplante una solicitud explícita por proceso. Nombre de
operación/riesgo/confirmación/identidad no cambian. Sin aliases por aplicación.
Handler transporta selector;IWindowControlProvider yfake dueño actualizados.

Prueba nativa crea3ventanas STATIC propias con un mismo dueño:exacta,dos porprefijo,
prefijo parecido excluido,ausente rechazado,proceso devuelve todas ylookup porproceso
no acepta título. Destruye sólo sus propios HWND.14pass proveedor (13previas+nativa).
23passintegración C03FactPreservation/MvpLocalTransientHandlerMatrix incluye título
en resultado ybyTitle atravesando handler. Format0. Logs c03-window-title-explicit-*,
c03-window-title-format.log. Primera versión implícita de selector pasó14/22,pero se
hizo selector explícito para conservar semántica deprocess;no usar resultados viejos
como única validación. CA2012 inicial deltest corregido usando AsTask, sin supresión.

Core esNativeAOT:el exe publicado anterior era de01:33;un testmanaged no lo actualiza.
Proceso18819 terminó exit0 y publicó nuevoCore tras23testsverdes. Conductor confirmó
copia del exe actualizado; PREREG incluye su huella.
Se ejecutó astra-qwen2507-window-title,6turnos:pedir cierre por título Ventana
C03 de prueba, cancelar,repetir,confirmar,hora y tareas. FixtureC03TitleFixture.exe
con ese título (distinto del proceso),sin documentos. Prereglauncher incluye fuente
provider/Core/catálogo yexeNativeAOT. No100frescos,promoción ni verificación deUI.

Resultado: sesión81116 terminó0,98,41s,GPU3499,56MiB,RAM4596,71MiB. Sólo1/6 útil/fiel,
aunque6publicados. t1 timeoutvoz→unavailable yprosa interna; t3 window.resolve vetado
por domain_grounding; t6 falsa negativa de acceso a tareas. Fixture38428 siguió viva.
ADJ individual en astra-qwen2507-window-title/ADJUDICACION.md. Proveedor verificado
en tests, selección integrada NO aprobada. Continuación causal en ASTRA-TRAMO-17.md.

Pregunta deldueño sobre esfuerzo:se recomendó High base yXHigh puntual segúnAGENTS,
sin afirmar óptimo medido ni cambiar ajustes. OpenAI Docs consultada:
https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra
La recomendación es juicio de trabajo,no evidencia de benchmark High contraXHigh.
