# C03 — runtime218–219 — normalización integrada, fidelidad aún abierta

La dependencia instalada es sherpa-onnx1.13.4+baxy.2. La única distribución que
cambió fue sherpa-onnx(baxy.1→baxy.2); core sigue1.13.4. Los modelos y el manifiesto
registrado13b971b3… permanecen intactos. No se promocionó Qwen3.5 ni RAW en esta tanda.

## Cambio reproducible

El wheel contiene la selección por stream207 y la corrección matemática3857 de
Eoin Houstoun, merge0967a08db705d8eec9cf5cef962c8ec57c16e4a8. No incluye las sondas
215/216: la receta rechaza cualquier diff distinto de los tres archivos previstos.
Comprueba ambos parches por hash, diff exacto y aplicación inversa; no hace reset.

Wheel: runtime_wheels/sherpa_onnx-1.13.4+baxy.2-cp312-cp312-win_amd64.whl
SHA256: abb55ee911483d7e9be5b874d168ee50273f59dec8f862dfb4c6cce0cabd665b
Extensión: 675d563506dc24466f09951ec07ba980053d385afca4caf5e26ca80281a0b4c0
Parche de normalización: 79cb34698cf0fb6083d8f66ab194970e5fddef9e26422f469183822412e87c48

scripts/build_sherpa_runtime.py habilita y ejecuta math-test antes de empaquetar.
Conserva wrapper/licencias/core y añade procedencia de3857 al aviso y metadata.
baxy.1 y los parches anteriores se conservan como rollback/evidencia, sin cambiar
sus hashes. CMake y su fuente externa quedan preparados para los dos parches
productivos; los bundles de observación permanecen aislados.

## Validación ejecutada

- Receta build_sherpa_runtime.py, workspace externo sherpa205, VS2022CMake:
  exit0; suite original math-test8pass/0skips, incluidos los dos tests3857.
- pytest tests/test_sherpa_runtime_package.py -q:1pass/0skips,0,31s.
- Combinada de voz/lock/paquete/corrector:109pass/1fail,7,37s. El fallo era el
  reemplazo de un nombre baxy.1 que ya no estaba en el lock. La prueba ahora
  modifica el prefijo del wheel independientemente de versión y exige que la
  mutación ocurra; no se relajó el verificador.
- Reintento dueño --lf -x -q verde; suite completa test_python_runtime_lock.py:
  12pass/0skips,0,66s. Voz91/corrector6/paquete1 habían pasado en la combinada.
- .\scripts\lock_python_dependencies.ps1 -Profile Runtime -Check:exit0,
  regeneración idéntica. Se usa el Python registrado explícito.
- .\scripts\test_source_quality.ps1:Fast exit0; Release2,93s,0avisos/errores.
- Instalación del lock entero con pip --only-binary=:all: --require-hashes
  --no-deps:exit0; delta de distribuciones exactamente el previsto.

Primer instalador218 falló antes de pip al buscar el nombre de metadata con
guion en lugar de underscore. Se conserva el fallo; el reintento normaliza
nombres para comparar. No hubo cambio de runtime en ese primer intento.

## Producto219

VoiceEngine real y extensión instalada, sin inyección nativa, con salida TTS
inerte. Los63 PCM exactos217 pasan por transcribe_pcm; el helper observado
reproduce63/63 transcripciones nativas217. Correcciones públicas adicionales:
0. Tres casos recuperados213 producen callbacks directos.
Los literales de esos callbacks se conservan en DIRECT.json.

Carga:5.640s; RSS:1181.28MiB.
No son medición de presupuesto conjunto ni aceptación física. Wake:
unavailable/wake_verifier_manifest_missing. No se elude la calibración.

**63 paridades no son63 pases de fidelidad.** Se conservan las regresiones217:
eco añadido, pérdida de palabras y30→3años en un control inglés. No se afirma
que integrar la normalización resuelva toda la voz. No se ejecutó Full durante
esta reparación; su verde final sigue siendo obligatorio para cerrar C03.

## Continuación

Retomar RAW/Speex212 con el normalizador válido ya instalado. La evidencia211
demuestra que RAW excluye los efectos Windows en el cliente real. Falta incorporar
esa captura de forma mantenible y verificar interrupción física/voz humana,
conservando los controles que detectaron pérdidas. No repetir filtros con el
normalizador antiguo ni hacer barridos de umbrales/ganancias.

Todos los procesos propios se recogieron:95776build,12778Fast,18567producto219;
resto terminaron directamente. No procesos vivos ni cambios de volumen esta tanda.
Snapshot218 y TRAMO218_219_PINS conservan fuente/logs/paquete/resultados.

C03 completo sigue activo: wake/voz/ocho rutas,100humanos frescos aún sin congelar
y100/100 útiles, averías y recuperación, UI/audio físico final,4GB conjuntos,
runtime/instalación/continuidadC04–C09,Full/publicación fuera main.
