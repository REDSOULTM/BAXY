# C03 — reconocimiento integrado, 207–208

## Resultado

La dependencia corregida ya está instalada mediante el lock con hashes.
VoiceEngine.transcribe_pcm reproduce las47 lecturas greedy203 y cuatro segmentos
antes erróneos (3/0,15/0,21/0,23/0) llegan completos al callback real de
_decode_utterance. TTS inerte y callback de diagnóstico: no efectos, UI ni audio
físico acreditados. Las47 paridades no convierten errores menores de ASR en pases.

_decode_offline_text solicita greedy sólo sin hotwords y verifica el método
efectivamente aplicado. La primera carga lo comprueba antes de publicar el
reconocedor. Beam sigue en las verificaciones wake y en el apoyo contextual.
Ambas entradas comparten _correct_transcript con el corrector conservador existente.
No cambian AEC, KWS, umbrales, GGUF, modelos acústicos ni manifiesto registrado.

## Dependencia e instalación

La inspección de RECORD corrigió el plan206: la extensión .pyd pertenece al
paquete sherpa-onnx, no al core. Versión instalada sherpa-onnx1.13.4+baxy.1;
sherpa-onnx-core sigue oficial1.13.4. AFTER.json demuestra que ésta fue la única
distribución cambiada. Wheel SHA256:
2ee49c501c97ad69be14449ecc739b37d856e33f9065ddf7565ffa6b626d7ee0.
Extensión SHA25649c696327587214eda554b9d621cb95f4aec259f817373bbd684ae654ad343b8,
idéntica a la probada206. Fuente/parche/licencias/procedencia/RECORD conservados.

runtime_wheels/README.md documenta la receta scripts/build_sherpa_runtime.py.
El script comprueba commit y diff exactos, compila y empaqueta; rechaza sustituir
un wheel existente por bytes distintos. Se exige revisar/versionar otro build;
no se promete igualdad binaria entre compiladores/rutas diferentes.
El wheel se instala sin compilador desde pylock.runtime-win-x64.toml con SHA256.
El verificador admite exclusivamente rutas runtime_wheels/<nombre> sin escapes,
además del origen PyPI anterior. No se desactiva verificación ni se relajan hashes.
El generador convierte sólo file-URLs del directorio autorizado a wheels.path.
Regeneración -Check exit0: lock idéntico. Core y resto del grafo no cambian.

Fallos conservados: primer wheel tenía versión original en METADATA por CRLF;
resolver lo rechazó. Está fuera del producto como wheel207-invalid-metadata.whl.
El builder se corrigió y el test de paquete comprueba identidad y todos los hashes.
Primer lock portable falló porque pip emitió URL file absoluta; se corrigió la
conversión en el generador y se mantuvo el rechazo del verificador. Un intento de
ruff en el Python de runtime falló por módulo ausente; se usó el entorno de calidad
existente, sin instalar herramientas allí. Ruff y Fast posteriores verdes.

## Validación

- pytest tests/test_mind_voice_runtime.py:91 pass,0 skips (8,05s inicialmente).
- Combinación voz/lock/paquete:103 pass,0 skips (6,16s).
- Tras añadir el rechazo de nombre con ruta, test_python_runtime_lock:12 pass,
  0 skips (0,63s); test_sherpa_runtime_package:1 pass,0 skips (0,26s).
- test_voice_corrector:6 pass,0 skips (0,26s), salida observada en la herramienta.
- test_source_quality.ps1:Fast exit0; Release9,61s,0 avisos/errores.
- lock_python_dependencies.ps1 -Profile Runtime -Check:exit0, idéntico.
- astra-product208:47 paridades de PCM,4 callbacks recuperados; proceso3087 exit0.

Carga VoiceEngine5,641s, RSS1168,04MiB en el diagnóstico; no coste combinado final.
VAD cargado; streaming es opt-in y no se activó. Wake sigue unavailable con
wake_verifier_manifest_missing; no presentar estas pruebas como calibración.
Manifiesto del runtime sigue SHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed.
Qwen3.5 continúa siendo override experimental y Speex el AEC del producto.

## Siguiente

Todos los procesos de este tramo terminaron y se recogieron. Fuente vigente207,
no192. Las corridas antiguas que fijan fuente192/172 o el sherpa original son
históricas; no reutilizarlas sin prereg nuevo. No editar evidencia sellada.
Retomar fallo físico183: interrupción falsa por eco, independiente del ASR ahora
corregido. Usar la evidencia física ya capturada antes de otra repetición. La
activación/calibración sigue abierta; pregunta opcional sobre Grabación(2) pendiente.
También siguen pendientes ocho rutas finales, reserva100 humana congelada y
100/100, averías/recuperación, UI y audio físico finales, recursos/runtime,
instalación/continuidadC04–C09, Full íntegro y publicación fuera main. C03 EN_CURSO.
