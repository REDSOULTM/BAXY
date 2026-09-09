"""Persist the published source, completed audits and pending owner clarification."""
from pathlib import Path
import json
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
ART = BASE / "astra-handoff535"
ART.mkdir(exist_ok=False)
for name in ("CHECKPOINT.md", "HANDOFF.md", "ESTADO_PARA_DUENO_2026-09-08.md"):
    (ART / (name.removesuffix(".md") + "-before.md")).write_bytes((BASE / name).read_bytes())

state = """# C03 — fuente publicada120713be; auditoría534; aclaración pendiente

Goal íntegro EN_CURSO en01a07974-2a33-7ed3-ba87-2436944e8115. Autoridad: astra-baseline-full526/GOAL_OBJECTIVE.md (sustituye publicación/Full/reserva/encuesta/audio/escalado), identidad y AGENTS. Goal-c03 y origin/Goal-c03 comprobados iguales en120713be877aaf426820174ece35a642923f5eda; main intacto5f572ee1b48cb5e2543ee5e06510e51057c9c845. Sin agentes. BAXY manual cerrado; no inferencia, medición ni suite en curso. Build servers cerrados. Encuesta742/rev1248 preservada.

**Encuesta:0cubiertos,742abiertos,0no aplicables.** Es adjudicación individual de evidencia, no742fallos. Registro privado existente336 tiene verification_status por case_id;3expectativas negativas y18sin marca siguen como límites. Hash y recuentos en SURVEY_REQUIREMENTS336.json. No dar cobertura por bindings, fixtures o pertenencia a una familia sin comprobar conducta y variantes.

Fuente vigente effect_intent503, __main__530, llm520, parser privado C#516.528 actualizó3expectativas exactas (168pass/0skip).530 reconoce only tras prohibición y conserva acciones posteriores mediante el lector de cláusulas existente:4002pass+121subtests/0skip en55,58s.531 dueñas de otras declaraciones:37pass/1skip ambiental (campaña STT ciega ausente) en121,32s; Fast verde, Release23,44s/0warnings/errors. Runtime GGUF/servidor rehasheados contra manifiesto intacto; template restaurado al hash publicado. Los sellos históricos no se reescribieron.

Full526 original sigue rojo y publicado: .NET4427pass/0fail/1skip agregado (16mensajes opt-in omitidos en log); Python9984pass/25fail/3skip+466subtests. Sus25fallos se resolvieron por las dueñas528/530/531; no se repitió Full. Full siguiente cuando una adopción toque C# y Python juntos o en candidato final. Commit por fuente adoptada y push con dueñas verdes. No cerrar C03 sin Full final y criterios completos.

Producto521 sigue9/11finales útiles: guardado narra metadatos y memoria deshabilitada se confunde con capacidad inexistente. GPU3497,56MiB/RAM2013,48MiB; conductor sin UI/voz, no total conjunto. Registro13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed.523/524/525 no promueven modelos;525 ya cerrado formalmente: quitar pregunta empeora actor y estado. No repetir esa hipótesis ni otra campaña sin causa nueva. Modelos: documentación/papers/reproducciones, perfil efectivo por rol, calidad/latencia/RAM/VRAM; defaults no descartan.

Reserva:532 revisó3041fuentes sin nuevos expuestos respecto483;533 revisó408logs/10998filas estables, sin nuevos expuestos.534 cruzó3452fuentes estables añadiendo equivalencia de puntuación/tildes:43adicionales consumidos de los112anteriores. Quedan69candidatos;66con original completo (63ES,1EN,2indeterminados),8con bandera de contexto. Falta deduplicación/contexto/rutas.0congelados/ejecutados/certificados. Detalle privado C03-orthographic-exposure534-private y fuentes532/533/518; no editar originales475/477 ni encuesta.

**Aclaración pendiente del dueño:** ya no hay saludo humano fresco en el conjunto. Se preguntó mediante request_user_input_async si acreditar la bienvenida automática al arrancar en sesiones de reserva o esperar nuevos saludos escritos por él. No asumir la opción preseleccionada ni congelar/ejecutar la reserva hasta respuesta. La obligación de consultar proviene del objetivo actualizado; no es bloqueo declarado del goal. Mientras falta respuesta, no abrir nuevas campañas para suplir esa carencia.

Después de la aclaración: completar auditoría de contexto/duplicados, cerrar conductas C03 y cobertura de encuesta; aceptación reservada cuando corresponda, recuperación/UI real, loopback completo y supresión AEC separados, recursos conjuntos y Full final. Voz humana física/wake/FAR/FRR sonC08. Matriz lleva evidencia disponible deC04/C07/C08 sin cerrar sus filas; las publicaciones C03 reflejan el código validado publicado. Continuidad C04–C09 hasta instalación documentada, sin ejecutar esos goals.
"""
(BASE / "CHECKPOINT.md").write_text(state, encoding="utf-8")
handoff = """# Handoff C03 — 535

C03 EN_CURSO, tarea01a07974-2a33-7ed3-ba87-2436944e8115, Goal-c03. Código validado publicado:120713be877aaf426820174ece35a642923f5eda; main intacto5f572ee1b48cb5e2543ee5e06510e51057c9c845. Autoridad vigente: astra-baseline-full526/GOAL_OBJECTIVE.md; leer CHECKPOINT. Sin agentes ni procesos de prueba/inferencia. BAXY manual cerrado; encuesta intacta.

Fuente __main__530/llm520/effect_intent503/C#516.528:168pass/0skip;530:4002pass+121subtests/0skip;531:37pass/1skip ambiental de campaña STT ausente. Fast531 verde, Release23,44s/0warnings/errors. Full526 rojo (25fallos Python), todos resueltos por sus dueñas; Full final aún no ejecutado. No repetir Full por edición. Registrar fuentes adoptadas con dueñas verdes y publicar rama, main fuera de alcance.

Encuesta:0cubiertos/742abiertos/0NA,3negativos/18sin marca conservados. Registro privado336 consultable; no inferir cobertura de tests estructurales. Producto521:9/11útiles, siguen metadatos al guardar y confundir capacidad con memoria desactivada. Recursos521:3,42GiBVRAM/1,97GiBRAM sinUI/voz; no consumo conjunto.525cerrado sin adopción: quitar la pregunta empeora; no repetir523–525sin causa nueva.

Auditoría534:43nuevos expuestos por tildes/puntuación sobre112; quedan66con original completo (63ES/1EN/2indeterminados), pendientes contexto/duplicados.0reserva congelada. Privado C03-orthographic-exposure534-private; heredar fuentes532/533/518, no volver a recorrer evidencia.

SIGUIENTE: esperar aclaración ya enviada al dueño: no queda saludo humano fresco, ¿bienvenida automática al arrancar las sesiones de reserva o nuevos saludos humanos? No asumir el valor preseleccionado, no ejecutar/congelar reserva ni abrir campañas para suplirla antes de respuesta. Goal activo, no marcado bloqueado. Luego contexto/duplicados y conductas/cobertura/UI/loopback-AEC/Full final. Voz humana/wake/FAR-FRR quedanC08 con evidencia, sin cerrar filas ajenas.
"""
(BASE / "HANDOFF.md").write_text(handoff, encoding="utf-8")
path = BASE / "RELEVO_ACTIVO.json"
relay = json.loads(path.read_text(encoding="utf-8-sig"))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint="535: fuente120713be publicada; dueñas25fallos resueltas; reserva534 deja63ES completos. Encuesta0/742/0.", continuation="Esperar respuesta del dueño a la aclaración de bienvenida (automática en arranque o nuevos saludos humanos), después seguir C03. No congelar/ejecutar reserva sin resolverla.", pendingOwnerClarification="Fresh reserve has no unused human greeting: automatic startup welcome or new owner-authored greetings?", publishedSourceCommit="120713be877aaf426820174ece35a642923f5eda")
path.write_text(json.dumps(relay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

matrix = ROOT / "documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md"
lines = matrix.read_text(encoding="utf-8").splitlines()
for i, line in enumerate(lines):
    if line.startswith(("| G04.06 /", "| G06.06 /")):
        fields = line.split("|")
        fields[4] = " CUMPLIDO "
        fields[5] = " Publicación de fuente validada comprobada: HEAD=origin/Goal-c03=120713be877aaf426820174ece35a642923f5eda, árbol limpio al comprobarlo tras push531; main intacto5f572ee. Incluye control892c506 y corrección88fca650. Dueñas528/530/531 y Fast verdes; Full final y aceptación C03 siguen pendientes. No equivale al cierre de las demás filas. "
        lines[i] = "|".join(fields)
matrix.write_text("\n".join(lines) + "\n", encoding="utf-8")

status = """# Estado de C03

**C03 sigue abierto.** El código validado está publicado en `Goal-c03` hasta `120713be`; `main` permanece intacto.

Se ha corregido la procedencia de los datos del historial, retirado un atajo que publicaba la prosa del selector, ampliado la configuración de memoria privada y eliminado una instrucción que inducía observaciones inventadas del PC. La última corrección conserva las explicaciones tras una prohibición sin ocultar una acción posterior. La regla de investigar cada modelo y verificar su configuración efectiva está en AGENTS.md.

El Full de línea base terminó con 25 fallos Python. Sus pruebas dueñas ya pasan: 168 aprobadas en528; 4.002 y121subpruebas en530; 37 aprobadas y1omisión ambiental en531. Fast también pasó, con cero advertencias y errores de compilación. No se ha repetido el Full final ni se considera cerrado C03.

La última medición del producto registrado dio **3,42GiB de VRAM y1,97GiB de RAM**. Fue un conductor sin interfaz y voz; falta medir todo junto. BAXY usa RAM adicional. Los4GB de VRAM siguen siendo el techo, buscando menos consumo sin perder calidad.

El panel de memoria dio9de11respuestas finales útiles. Siguen abiertos el guardado explicado mediante metadatos y la confusión entre memoria desactivada y capacidad inexistente. Las comparaciones de modelos no justificaron una promoción.

La encuesta conserva742respuestas: **0casos acreditados individualmente,742abiertos y0no aplicables**. Es el estado de evidencia vinculada, no742fallos de producto. Faltan la adjudicación y variantes verificadas; se preservan las3expectativas negativas y18sin marca.

La revisión de puntuación y tildes apartó43candidatos ya expuestos. Quedan63españoles con original completo, además de1inglés y2entradas sin idioma determinado. Falta contexto/deduplicación y no hay reserva congelada. Está pendiente tu aclaración sobre evaluar la bienvenida automática al arrancar o aportar saludos nuevos: no queda un saludo humano fresco entre esos candidatos.

Después quedan las conductas y cobertura de C03, aceptación reservada, recuperación, interfaz real, loopback completo y supresión AEC, recursos conjuntos, Full final y publicación del cierre. Voz humana física, calibración wake y FAR/FRR son deC08. No hay una estimación fiable de tiempo todavía; CHECKPOINT conserva la siguiente acción.
"""
# Keep the owner-facing report easy to read, including spacing around counts.
for old, new in {"121subpruebas":"121 subpruebas", "y1omisión":"y 1 omisión", "en528":"en 528", "en530":"en 530", "en531":"en 531", "3,42GiB":"3,42 GiB", "y1,97GiB":"y 1,97 GiB", "Los4GB":"Los 4 GB", "dio9de11respuestas":"dio 9 de 11 respuestas", "conserva742respuestas":"conserva 742 respuestas", "0casos":"0 casos", "individualmente,742abiertos":"individualmente, 742 abiertos", "y0no":"y 0 no", "no742fallos":"no 742 fallos", "las3expectativas":"las 3 expectativas", "y18sin":"y 18 sin", "apartó43candidatos":"apartó 43 candidatos", "Quedan63españoles":"Quedan 63 españoles", "de1inglés":"de 1 inglés", "y2entradas":"y 2 entradas", "deC08":"de C08"}.items():
    status = status.replace(old, new)
(BASE / "ESTADO_PARA_DUENO_2026-09-08.md").write_text(status, encoding="utf-8")
print("Handoff and matrix updated; source commit remains published; clarification pending.")
