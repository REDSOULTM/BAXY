"""Apply the owner's revised scope and evidence references; no product changes."""
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
DOCS = ROOT / "documentacion/sprints/Sprints comprobación"
authority = DOCS / "C03_ASTRA_AUTORIDAD.md"
text = authority.read_text(encoding="utf-8")
text = text.replace("# C03 — completar la respuesta veraz de BAXY\n", "# C03 — completar la respuesta veraz de BAXY\n\nActualización vigente del objetivo, 2026-09-08: [texto íntegro del dueño](../../../artifacts/comprobaciones/C03/astra-baseline-full526/GOAL_OBJECTIVE.md), SHA-256 `6ca6aec0928cb4e50a5cfeb29108d962e7669b9b63a7e2eb77ea92b02889bb5a`. Sustituye las cláusulas anteriores sobre publicación, Full, reserva, encuesta, audio y escalado. Todo lo demás conserva su alcance.\n")
text = text.replace("Los100 casos humanos frescos y el resto del cierre C03 siguen obligatorios.", "La reserva humana auditada y el resto del cierre C03 siguen obligatorios conforme a la actualización del objetivo.")
old = "Actualización expresa del dueño: no repetir Full entre cambios o tramos. Usa\npruebas dueñas y mediciones del producto durante la reparación; ejecuta Full\ncuando esté resuelto todo lo necesario para cerrar C03 y comprueba verde entero.\nLa ejecución ya iniciada puede terminar; no autoriza encadenar otra compuerta."
assert old in text
text = text.replace(old, "Actualización vigente del dueño: commit de control de todo el WIP y Full de línea base inmediato, publicando su resultado real. Después, Full al adoptar una fuente que toque C# y Python juntos y Full de cierre sobre el candidato final; no por cada edición. Cada fuente adoptada se commitea con sus dueñas verdes y checkpoint, y se publica en Goal-c03 cuando sus dueñas estén verdes. Main permanece intacto.")
old = "1. Cien turnos normales frescos, congelados antes de ejecutarlos y leídos y\n   adjudicados individualmente: 100/100 útiles y fieles a lo pedido, en los tres\n   idiomas y distribuidos entre las ocho rutas de respuesta. Sin hechos o\n   palabras inventados, plantillas, fugas internas, agotamientos ni silencios."
assert old in text
text = text.replace(old, "1. Hasta 100 turnos españoles humanos acreditados, con procedencia, contexto y exposición auditados, distribuidos entre las ocho rutas y congelados antes de ejecutarse; todos útiles y fieles. Inglés y mezcla natural se adjudican aparte con el material humano disponible, incluidos los cuatro ejemplos aprobados, sin cuotas ni traducciones. Sin hechos o palabras inventados, plantillas, fugas internas, agotamientos ni silencios.")
text = text.replace("4. Pruebas dueñas", "4. Cobertura consultable de los 742 casos en el registro privado: `verification_status` por `case_id` y evidencia de variantes que cambien nombres, valores, orden, referencias e idioma. Cada checkpoint cuenta cubiertos, abiertos y no aplicables; los 3 negativos y 18 sin marca siguen siendo límites.\n5. Loopback: recuperar íntegramente la publicación de voz. Micrófono con AEC: medir supresión de la propia voz de BAXY. Voz humana física, calibración wake y FAR/FRR corresponden a C08; dejar estado, evidencia y reanudación en sus filas sin cerrarlas.\n6. Pruebas dueñas")
text = text.replace("Mantén C03 EN_CURSO hasta demostrar el cierre. Si aparece un bloqueo externo\nreal que no puedes resolver, documenta la evidencia y la reanudación exacta.", "Mantén C03 EN_CURSO hasta demostrar el cierre. Actualiza filas propias de la matriz al cumplirlas; en filas ajenas añade «evidencia disponible — owner CXX» sin cambiar su estado. Repara defectos ajenos sólo si bloquean C03. Ante exigencias contradictorias o material insuficiente para cumplir una, detente y pregunta al dueño antes de gastar más campañas.")
authority.write_text(text, encoding="utf-8")
formal = DOCS / "C03_RESPUESTA_VERAZ.md"
text = formal.read_text(encoding="utf-8")
text = text.replace("**Un goal, tramos A–D reanudables.", "Actualización de alcance del dueño, 2026-09-08: la reserva, publicación, Full, encuesta y audio se rigen por [el objetivo vigente](../../../artifacts/comprobaciones/C03/astra-baseline-full526/GOAL_OBJECTIVE.md). Las cifras y exigencias anteriores de este prompt se interpretan con esa sustitución explícita.\n\n**Un goal, tramos A–D reanudables.", 1)
formal.write_text(text, encoding="utf-8")

matrix = DOCS / "03_MATRIZ_DE_CRITERIOS.md"
lines = matrix.read_text(encoding="utf-8").splitlines()
refs = {
    "G03C.06": "evidencia disponible — owner C07: astra-private-product521, pico GPU 3497,559 MiB (3,42 GiB), RAM 2013,480 MiB con runtime registrado; sin UI/voz, no acredita el pico conjunto de esos componentes. Reanudar C07 con medición conjunta. Evidencia conservada en 892c506.",
    "G06.04": "evidencia disponible — owner C08: VoiceFeedbackTests.VoiceFeedbackUsesSharedComposer y Goal06VisibleVoiceTests.NarrationEmitsStructuredFactsNotSpanishProse; MainWindowViewModel.cs:2880–2893 entrega el mismo body publicado a VoiceSpeakAsync. Suite Integration en Full526: 3263 pass, 0 fail, 1 skip agregado (otros opt-in en log). Acredita contrato, no voz física; C08 reanuda calibración y hablantes, C03 separa loopback completo de supresión AEC.",
    "G05.03": "evidencia disponible — owner C04: Goal05LyingExecutorTests.LyingNoteCreateCannotMakeMissionEngineClaimSuccess exige failed, Verified=false, EffectMayHaveOccurred=true y verification_failed; LyingAudioExecutorCannotMakeMissionEngineClaimSuccess comprueba postlectura sin éxito falso. Suite Integration verde en Full526; C04 conserva validación extensa de reintentabilidad y efectos reales. No se cierra la fila.",
    "G04.05": "Actualización C03: fuente506 retiró el bypass conversation_reply/initial_reply; fuente516 sustituyó aliases privados por una gramática acotada; fuente520 retiró una instrucción causante de observación inventada. Evidencia y patches en astra-memory-configuration516/astra-status-evidence520, commit892c506. Dueñas516:1962pass/0skip; dueñas520:3406pass+121subtests/0skip. Full526 rojo por otros tests: no declara cierre global.",
    "G06.05": "Actualización C03: personalidad sigue en src/baxy_mind/llm.py (SYSTEM_PROMPT/USER_MESSAGE_PROMPT); permisos conservan dueño Kernel. Fuente520 y sus3406pass+121subtests en892c506; Full526 no certifica C03 íntegro.",
    "G04.06": "Publicación actual: commit de control892c506 en Goal-c03, main intacto5f572ee. Todavía sin push: Full526 rojo (25fail Python), pendiente resolver dueñas y publicar. No se cumple igualdad HEAD/remoto.",
    "G06.06": "Mismo estado de publicación que G04.06:892c506 local; Full526 rojo, sin push todavía; main intacto. Objetivo vigente sustituye esperar al cierre para commitear.",
    "G06.01": "Objetivo actualizado: hasta100ES acreditados; EN/mezcla aparte sin cuotas. Auditoría518:112sin coincidencia en tres corpus,101con original completo; todavía0congelados, faltan contexto y exposición posterior. Encuesta742:0cubiertos/742abiertos/0no aplicables individualmente en registro privado336, recuento527; no equivale a742fallos de producto.",
}
for key, note in refs.items():
    matches = [i for i, line in enumerate(lines) if line.startswith("| " + key + " /")]
    assert len(matches) == 1, key
    i = matches[0]
    lines[i] = lines[i].rstrip().removesuffix("|").rstrip() + " " + note + " |"
matrix.write_text("\n".join(lines) + "\n", encoding="utf-8")

checkpoint = """# C03 — baseline Full526 rojo; revisión de alcance y registro527

Objetivo íntegro activo en la tarea 01a07974-2a33-7ed3-ba87-2436944e8115. Autoridad vigente: astra-baseline-full526/GOAL_OBJECTIVE.md, identidad y AGENTS. Rama Goal-c03, commit de control 892c506cdd1a583048ed80af8e63703ec329a236 (todo WIP); main intacto 5f572ee1b48cb5e2543ee5e06510e51057c9c845. Sin push todavía; sin agentes. BAXY manual cerrado, encuesta742/rev1248 preservada. No diagnóstico GPU activo. Full60236 recogido con exit1.

Full526: estática/build verdes, 0 warnings/errors. .NET4427pass/0fail/1skip agregado;16mensajes opt-in omitidos en log, no hardware acreditado. Python9984pass/25fail/3skip+466subtests,676,16s. Resultado íntegro en astra-baseline-full526/RESULT.json y full.log. No repetir Full por edición: dueñas ahora; Full cuando una adopción toque C# y Python juntos, y al cerrar. Commits por fuente adoptada con dueñas verdes; push a Goal-c03 al cumplirlas.

Encuesta: **0 cubiertos,742 abiertos,0 no aplicables**;3negativos y18sin marca conservados como límites. Es estado de adjudicación individual, no tasa de fallos. Registro existente C03-survey-requirements336-private/requirements.jsonl ahora usa verification_status=open y enlaces de evidencia vacíos. Hash y números consultables en SURVEY_REQUIREMENTS336.json; copia anterior privada en C03-baseline-state527-private. No inferir cobertura desde tests de selección ni descartar por autoría falsa.

Fuente vigente: effect_intent503, __main__506, llm520, parser privado C#516. Dueñas5161962pass/0skip; dueñas5203406pass+121subtests/0skip, Fastverde. Full descubre otras expectativas/contratos que requieren diagnóstico. Producto521:9/11finales útiles; memoria real deshabilitada correctamente, pero guardado narra metadatos y pregunta de memoria confunde capacidad con activación. RAM2013,480MiB/GPU3497,559MiB, sin UI/voz. Manifiesto13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed intacto.

523/524 no promueven modelos: receta documentada no corrige dos fallos; Qwen3.5 mejora guardado/progreso, falla actor en lecturaES y capacidad.525 terminado25992exit0: omitir pregunta natural en tres lecturas empeora;9EOS, no adoptar; falta cierre formal de525. No nuevas campañas de modelos antes de reparar Full y organizar cobertura. La configuración justa por modelo ya consta en AGENTS.

Reserva518:112sin coincidencia en tres corpus,101con original completo.0certificados/congelados. Nueva autoridad permite hasta100ES por ocho rutas; EN/mezcla humanos aparte, sin cuotas. Auditar contexto y exposición484–525 antes de congelar. Loopback íntegro y supresión AEC se evalúan separados; voz humana física/wake/FAR/FRR sonC08. Matriz527 incorpora evidencia disponible de C07/C08/C04 sin cerrar sus filas.

Siguiente: diagnosticar los25fallos de full.log por causa, empezando tests/test_c03_request_preservation.py (15fallos). Preservar sellos históricos; no hacerlos coincidir arbitrariamente con fuente nueva. Actualizar cobertura por caso sólo con conducta y variantes verificadas. Después resolver C03 restante, reserva, recuperación/UI/audio, Full final y publicación. Una contradicción o falta de material exige preguntar al dueño antes de campañas. Estados anteriores preservados en astra-baseline-state527/*-before.md.
"""
(BASE / "CHECKPOINT.md").write_text(checkpoint, encoding="utf-8")
(BASE / "HANDOFF.md").write_text(checkpoint.replace("# C03 — baseline Full526 rojo; revisión de alcance y registro527", "# Handoff C03 — 527, Full526 rojo"), encoding="utf-8")
relevo = BASE / "RELEVO_ACTIVO.json"
data = json.loads(relevo.read_text(encoding="utf-8"))
data.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint="527: control892c506; Full526 rojo (25fallos Python); encuesta0cubiertos/742abiertos/0NA.", continuation="Diagnosticar fallos de Full526 empezando test_c03_request_preservation.py; sin nuevas campañas de modelo. Objetivo actualizado en526/GOAL_OBJECTIVE.md.", surveyVerificationCounts={"covered": 0, "open": 742, "not_applicable": 0})
relevo.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
with (ROOT / "documentacion/APLAZADOS.md").open("a", encoding="utf-8") as stream:
    stream.write("\n- C03, 2026-09-08: el objetivo actualizado (artifacts/comprobaciones/C03/astra-baseline-full526/GOAL_OBJECTIVE.md) sustituye las antiguas restricciones no-commit/no-Full, cuota trilingüe y voz humana física dentro de C03; las anteriores se conservan sólo como evidencia.\n")
print("Updated authority, matrix references (states unchanged), checkpoint, handoff and active relay.")
