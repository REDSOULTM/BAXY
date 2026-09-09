"""Keep a compact current handoff; retain the previous checkpoint as evidence."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-positive-adversative498'
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    saved = out / (name.removesuffix('.md') + '-before.md')
    if not saved.exists():
        shutil.copy2(base / name, saved)
state = '''# C03: estado vigente, tramo 498

Goal completo activo. Rama Goal-c03, HEAD 2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Autoridad: C03_ASTRA_AUTORIDAD.md, identidad y AGENTS.md. Conservar todo el WIP, main y evidencia. Sin agentes, commits, publicación ni Full durante reparación. BAXY cerrado para uso manual. Encuesta terminada: 742 respuestas, revisión 1248; no cerrar sus procesos 101140 y 29800.

Fuente 498 en validación. La separación de cláusulas reconoce una segunda acción explícita tras pero/but; las citas se enmascaran sólo al buscar fronteras y la evidencia conserva el texto original. Baseline de nueve casos: 7 fallos y 2 aprobados. La primera intervención arregló las acciones pero falló los dos controles citados; fallo conservado. Con protección de citas: 25 controles aprobados. Diez controles adicionales verifican cinco tipos de comillas y una orden exterior. Cinco suites dueñas: 3174 aprobadas, cero skips, 48,78 s. Fast en sesión 13436; recoger antes de editar fuente o cargar un runtime. Llm.py sigue en la fuente 466 y el manifiesto registrado sigue con SHA 13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed.

497 cerrado: sesión 98048, exit 0; RESULT, ADJUDICATION y PINS completos. Gemma original E2B Q4, SHA 740185..., b10809 y perfil Google con thinking/lazy-on. En 14 respuestas evita las llamadas adicionales del checkpoint publicado; tres prompts renderizados coinciden exactamente con 494. Persiste el booleano de silencio invertido en tres respuestas contextuales y cuatro violaciones de la interfaz sin argumentos. No adopción. RAM 1030,965 MiB / VRAM 1681,988 MiB, 62,719 s: sólo servidor y conductor nativo, no todo BAXY.

Siguiente: terminar validación 498; repetir la mente completa de 488 con la misma referencia registrada, añadiendo el compuesto explícito con pero y la cadena real que construye MindClarificationPolicy.ResumeObjective. Revisar la primera frontera fallida antes de cambiar código. La corrección de cláusulas no reconstruye por sí sola el antecedente «volumen» de «Al 100, pero desmutealo».

Contexto pendiente: __main__ conserva historia en la llamada nativa, pero shortlist usa sólo el texto actual; 489 recuperó audio.volume con el antecedente literal y el selector omitió mute. El verificador de compatibilidad carece de historia. MainWindowViewModel 1966–1999 maneja RecoveryFailureCode antes de reanudar la aclaración. Conservar la independencia de pedidos nuevos, las retractaciones y la autoridad del catálogo; no concatenar toda la historia ni saltar las guardas. Herencia y papers en CONTEXTO_RECUPERACION489.md.

Decisiones medidas que no se reabren sin datos nuevos: 485 clíticos unmute; 487 negativas independientes; 490 perfil oficial Qwen no arregla los dos incidentes; 491 argumentos reales y 492 polaridad explícita mejoran unas respuestas y empeoran otras. 493 Gemma publicado repite llamadas; 494 raw=parsed demuestra que el parser no las añade. 495 falló HTTP antes de generar. 496 pares con iguales parámetros efectivos salvo gramática/lazy/triggers: sin gramática desaparecen extras, pero aparecen una operación ajena y prosa de éxito sin ejecución. Ninguna variante 489–497 promovida. No más barridos de sampler, gramática o redacción sin causa nueva. Campo real de audio.mute: state, true silencia y false reactiva; muted es observación.

Recursos y otros bloqueos: 425 redujo RAM conjunta 5,18→3,03→2,75 GiB con cacheRAM0/no-mmap GPU. 462 lazy-on redujo el compositor Gemma sin cambiar respuestas. 464 conductor de producto Gemma: 7/8 útiles, RAM 2653,13 MiB / VRAM 1694,18 MiB; falta confirmación de activar memoria, UI y voz. 437 Qwen3.5: 7/8, RAM 2,75 GiB / VRAM 3,10 GiB; confunde de quién es el nombre. 471 E4B, 481 Qwen Q8 y 482 Qwen3.5-9B no justifican promoción. 472–476 y 484 no resuelven todas las obligaciones y voz de las confirmaciones. Ver INVESTIGACION_MODELO_C03.md y los artefactos exactos; no volver a probar variantes rechazadas sin nueva evidencia. Incidentes manuales 264 todavía incluyen audio contextual, París, cierre Steam, reproducción YouTube/Spotify, capacidades y cierre BAXY.

Reserva humana: 204 potenciales, 192 canónicos, 12 grupos duplicados; 475 revisión semántica, 477 contraste literal/contexto, 483 exposición privada. 176/204 completos contrastados; siete fuentes originales ausentes y seis textos cortados a 100 caracteres. No reconstruirlos desde respuestas. Cero certificados, sin congelar y sin ejecutar. Falta cerrar contexto, entrenamiento y separación de desarrollo; refrescar exposición posterior a 483 antes de congelar. Autoría de encuesta y tres casos ingleses ya confirmada: no volver a preguntar. La sesión 264 es desarrollo expuesto, no reserva.

Cierre íntegro pendiente: ocho rutas y generalización de la encuesta; incidentes manuales; 100 turnos humanos frescos con procedencia/contexto, congelados antes del candidato y 100/100 útiles y fieles en ES/EN/mezcla natural; averías y recuperación aparte; UI real, voz/audio físico, ASR/wake y techo conjunto de 4 GiB VRAM; runtime, instalación y continuidad C04–C09; Full final totalmente verde y publicación fuera de main. No porcentaje ni ETA inventados. Un diagnóstico o una tanda verde no cierran C03.

Python siempre -X utf8 y lectura utf-8-sig. Privados en %LOCALAPPDATA%/BAXY. exec_command se recoge con write_stdin. No editar fuente durante pruebas, builds o runtimes. Los checkpoint y handoff anteriores están preservados en astra-positive-adversative498/*-before.md.
'''
(base / 'CHECKPOINT.md').write_text(state, encoding='utf-8')
(base / 'HANDOFF.md').write_text(state.replace('# C03: estado vigente, tramo 498', '# Handoff C03, tramo 498'), encoding='utf-8')
handoff = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
handoff.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
               checkpoint='Fuente498: 3174 pruebas aprobadas; Fast pendiente. 497 cerrado sin promoción.',
               continuation='Recoger Fast13436; después mente completa y contexto real de aclaración. C03 íntegro activo.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Current checkpoint, handoff and thread state updated; previous documents preserved.')
