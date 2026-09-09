# C03 — tramo19: comillas y objetivo del resumen

EN_CURSO. Extracción literal del18 probó cierre real,pero narración falló en C#.
Reproducción test:la ventana "Ventana C03 de prueba" y document 'Document draft'
eran falsos tartamudeos. HasRepeatedWord eliminaba comillas antes de comparar.
Ahora compara palabras contiguas separadas sólo por espacio: comillas/puntuación
conservan su frontera. Repeticiones reales siguen rechazadas. No lista de nombres
permitidos. Antes2fallos/1pass;después38/38 C03facts+Goal06VisibleVoice.

quoted-title/sesión7000:6/6publicados,41,11s,GPU3497,56MiB,RAM3983,28MiB.
Resoluciones+cancelación+nueva confirmación+cierre propioPID8992 verificados;hora y
tareas correctas. ADJ escrita. Naturalidadt2/t4 pendiente, no panelverde por terminales.

Se identificó otra pérdida de intención: CreateCompletionMessage recibía sólo lista
de resultados, mientras la entrada actual era confirmar. Se conserva completedRequest
desde execution.Objective y se transporta a Python, como ya hacen pendingRequest y
cancelledRequest. No se quitan pasos/lecturas explícitas ni se cambia prosa del prompt.
Tests propietarios: 42 .NET pass (C03FactPreservation, Goal06VisibleVoice,
MindPlanSession) y 109 Python pass (scratchpad/c03-completed-request-python.log).
Panel completed-request de 21 turnos: sesión79989 terminal0,44,05s,
GPU3497,56MiB,RAM4853,48MiB. Todos publicados, no todos correctos.
t20 conserva objetivo y cierre verificado, ya no relata resolución/maximización;
sigue coletilla técnica. t6 inventa audio desactivado pese a muted=false;
t15 ignora Spanglish y define archivo circularmente. ADJ individual escrita.
Fixture propia8708 cerrada; sin procesos Baxy/llama/fixture al recoger.
Full queda para cierre final;registro/modelo no promovidos,ningúncommit/push aún.
