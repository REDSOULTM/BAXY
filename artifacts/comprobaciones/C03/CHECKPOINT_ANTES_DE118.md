# C03 — CHECKPOINT — fuente112/native113 — EN_CURSO


Tarea01a07974-2a33-7ed3-ba87-2436944e8115, continuación de01a074f6-9e0e-7fb3-8282-a6b706198a7e.
Goal activo, ramaGoal-c03, HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49.
WIP/ajeno/evidencia preservados; sin commit/push; main excluida. Sin bloqueo externo.
Autoridad C03_ASTRA_AUTORIDAD.md/C03_RESPUESTA_VERAZ.md, identidad y AGENTS.
Historia íntegra CHECKPOINT_HISTORICO_HASTA67.md y CHECKPOINT_HISTORICO_HASTA91.md.

## Estado actual y siguiente acción

Fuente112 adoptada sobre108: Piper recibe PAD después de cada fonema conocido.
Native111 recupera saludo y dos relojes españoles; inglés sigue alterado.
85 pruebas de voz pass/0skips,7,76s; Fast33691 exit0,Release3,37s,0avisos/errores.
ASTRA-TRAMO-112.md y PRUEBAS_AUDIO110_NATIVE111.md. No repetir verdes ni Full.

Native11358330 exit0: misma voz es_MX-claude-high/PAD, sólo eSpeak es-419/en-us.
en-us recupera It is seven fourteen.; UTF-8 pasa a you'll be the fake y read
a heal. No acredita inglés fiel; no adoptar sólo cambio de fonemizador.
RESULTS/PREREG en astra-native-tts113. PCM nativo/ASR, no audio físico.
Siguiente: medir una voz Piper entrenada en inglés sobre estos mismos tres
textos consumidos; herencia Carter MODEL_TTS_TOURNAMENT_REPORT (2026-05-02)
advierte modelos por idioma, pero sus latencias eran scaffold, no aceptación.
No modelo ni selector de idioma adoptados; registro intacto.

Audio11076726/87021 exit0: UI muestra tres relojes fieles ES/EN/mezcla, pero
ASR de mic/loopback no recupera contenido. Última ventana acortada a4,56s.
GPU3502,296875MiB/RAM6015,91796875MiB con wake1,200,45s; primer1,032s excluido.
Grabaciones privadas en LOCALAPPDATA/BAXY/C03-audio110-private. Volumen
restaurado exactamente0/muted=true. Ningún App/server/captura/inferencia activo.
No aceptación acústica ni entrada hablada. Voz45 tenía83tests, no tramo83.

Fuente108/UI109 conservada: Error y Response error ante avería real; recuperación
Son las07:02. en mismo proceso.169tests/Fast verdes; PRUEBAS_UI109.md y
TRAMO108_109_PINS.json. UI107 confirma/cancela/cierra fielmente fixture real.
UI104 progreso visible y ocho finales fieles;106 averías/restauración aparte.
No repetir estos paneles sin dato nuevo. Sello UI108 conserva38archivos,
99FF9838C07CE32F25F329AACF830F62D8DD70C5931E26C2EC483B710B2CA657.

Reserva privada742/239no refutados, preview105 vistos0–154; falta155–238,
seleccionar100 literales humanos/contextuales y congelar antes de inferencia.
Tres textos ingleses admitidos por dueño en ADMISIBILIDAD_DUENO_2026-09-06.md;
no preguntar ni extender confirmación a742. C03 EN_CURSO completo: voz/audio,
reserva100, promoción/regresión del runtime, continuidadC04–C09, Full final verde
y publicación validada fuera de main pendientes. Sin subagentes ni commit/push.

## Decisiones y pruebas que no se repiten

81 panel técnico10/10 útil: archivo/UTF8/causa/checksum/capacidades/hora+audio+CPU/nivel.
Fuente74 corrige veto de operation y fallo negado;77 agrupa sólo prefijo system
(Qwen3.5 daba HTTP400);78 limita vetos por rol;81 adapta gramática existente de
enumeración nominal, manteniendo orden y catálogo.2774pytest pass/0skips;Fast81 verde.
PRUEBAS_ENUMERACION81.md y reportes74/75_76/77/78_80 conservan evidencia.

83 búsqueda vacía2/4: se convertía entries[]/count0 verificados en step_data_missing.
84 conserva file_search_no_matches antes de grounding imposible;162integración pass,
Fast verde tras corregir formato. Producto84 sigue2/4 por veto de negación y cifrado
inventado.86 reconoce no se encontró/no encontré/no se pudo en el guard existente,
preservando ausencia de fallos;1151pytest pass y181integración pass,Fast verde.
Producto86 3/4; la causa inventada nace cuando fallback descarta el contexto.
89/91 nativos: contexto como dato recupera causa/latencia y conserva cálculo/checksum.
Control límites sigue metatexto sin catálogo: no es5/5 ni aceptación de capacidades.
PRUEBAS_RECUPERACION86_89_91.md fija esa distinción y la herencia panel-opus-4/5.

82 progreso nativo4/6 con acting/in progress: porqué afirma lectura nueva; hora/CPU
produce metatexto. App ComposeMilestoneAsync siempre da acting; se pierde understanding.
85 sólo phase=understanding insuficiente.87 state=understanding the person's request
mejora parcial pero sigue leyendo.88 sustituye instrucción: aún lecturas y actor invertido.
90 rol dedicado o solicitud JSON no resuelve. NO adoptar ni apilar vetos/prompts;
se cambia estrategia a perfil/capacidad en93. PRUEBAS_PROGRESO82/85/87/88_90.md.
Todos estos son borradores nativos, no publicación real, UI ni audio.

No reabrir sin dato nuevo: borrar historial rompe referencias68; clasificador69/70
5/10 descartado; frases/roles/descripción65–67 insuficientes. Hechos en historial73
8/10 pero file2/file3 siguen mal; no implementados. is_elliptical_followup no cubre
hazlo/close that. Registrar anomalías, no borrar evidencia ni repetir hasta obtener pase.

## Runtime, reserva y cierre pendiente

Registro: Qwen3-4B-Instruct-2507 Q4_K_M,b9980CUDA12.4,KVq8,ngl99,3x4096.
Manifest SHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed.
Core AOT de UI100 SHA9bc4b041ab4741a54a930dc7387498b9d263de9d1f3ed8ef45858dbf94bf6632.
App Release101. Qwen3.5-4B-Q4_K_M local sólo override, mismo backend/perfil salvo93.
Modelo D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf.
Python de pruebas C:/Users/usuario/AppData/Local/Programs/Python/Python312/python.exe;
py apunta a313 sin pytest. Python runtime en %LOCALAPPDATA%/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.

Tres textos ingleses admitidos por «Son turnos validos» ya registrado en
ADMISIBILIDAD_DUENO_2026-09-06.md; no preguntar de nuevo ni extender a742.
Reserva privada742,239candidatos no refutados;100 aún no seleccionados/congelados.
RESERVE_PROVENANCE_AUDIT45.json reutilizable. Spanglish español natural válido;
sin cuotas/traducciones. Cuatro ejemplos ACLARACION_DUENO_2026-09-06.md vigentes.

Falta cierre completo: ocho rutas útiles, cien turnos humanos frescos/literales
congelados antes de ejecutar y100/100 adjudicados, averías+recuperación aparte,
UI escritorio real con py main.py, voz/audio físico y techo conjunto4GB; conductor
no acredita UI/audio. Regresión y hashes antes de promover runtime; continuidad
C04–C09 hasta instalación; Full íntegro verde sólo al candidato final y publicación
validada fuera de main. No cerrar por panel técnico, silencio, skip ni traza solamente.
