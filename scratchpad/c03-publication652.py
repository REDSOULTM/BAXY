"""Publish current handoff and matrix evidence without changing adjudications."""
from pathlib import Path
import json
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
survey = json.loads((base / 'SURVEY_REQUIREMENTS336.json').read_text(encoding='utf-8'))
assert survey['verification_counts'] == {'covered': 26, 'open': 716, 'not_applicable': 0}
def git(*args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
assert git('branch', '--show-current') == 'Goal-c03'
assert git('rev-parse', 'main') == '5f572ee1b48cb5e2543ee5e06510e51057c9c845'
published = '--published' in sys.argv
commit = git('rev-parse', 'HEAD')
if published:
    assert commit == git('rev-parse', 'origin/Goal-c03')
status = f'publicada en {commit}, remoto verificado' if published else 'adoptada, pendiente de publicación'
handoff = f'''# C03 — alcance de ventanas validado; contrato factual e idioma pendientes

Goal activo, rama Goal-c03; main intacto. Fuente 652 {status}. Ninguna decisión pendiente del dueño. Autorización 536 y reiteración actual permiten histórico, encuesta y casos nuevos, con procedencia honesta y generalización ES/EN. BAXY manual cerrado. Sin agentes ni campañas activas.

## Estado y validación

LLM SHA e6993ddb155b9586dd178e5814604eb4ec25f7baf853d68a9c855d3d6e41de45; árbol Python d6516137ea188c291331c12e7a52a2d23fbbd5835770efedb56342ef34b8d7ea. Modelo Qwen2507 Q4, registro y backend b9980 intactos. 652 conserva en primer borrador y reintento el alcance instalación/ventanas de una lectura correcta de window.application.status, sin inferir procesos. 650 aisló esa instrucción: 7/8 a 8/8 primeros borradores, reproducción literal del defecto647; siete fixtures declarados además de la situación real. Paridad652: 16 payloads coinciden con650 y nueve controles ajenos quedan iguales.

Dueñas652: 3902 pases +121 subpruebas, cero skips,72,36s. Declaraciones17 pases/1 skip ambiental,1,87s. Fast exit0,Release27,28s, cero advertencias/errores. Producto653:19/20 finales correctos;16/16 lecturas por aplicación y cuatro referencias correctas. Único fallo: Which window has focus? recibe ChatGPT tiene foco. t15 ahora dice Spotify is installed but no visible windows are currently open. Capturas independientes registran AUMID por fila HWND durante cada captura: Steam2,Chrome2,WhatsApp1,otras tres aplicaciones0; cero errores de identidad. Captura secuencial, no atómica.

653: GPU3497,559 MiB,RAM1626,023 MiB,38,203s,sin infracciones. No acredita mínimo global, ahorro comparado ni UI/voz conjunta. Sus20 mensajes de actividad coinciden con finales; no es inspección de pantalla. Bienvenida t0 conservada aparte.

Encuesta742/rev1248:26 cubiertos,716 abiertos,0 no aplicables. Sólo H0040 cambió con literal y16 variantes reales653. No cubre foco inglés ni validador general. SHA privado {survey['requirements_sha256']}. Original,tres límites negativos y18 sin marca conservados. c03-update-survey653.py YA ejecutado,no repetir. Preparación/cierre/sellado650/652/653 también ejecutados. Auditoría c03-audit-publication650-653.py de sólo lectura:19 pines; verificar --staged antes de commit.

## Siguiente

{'Publicación verificada y matriz actualizada.' if published else 'Publicar650/652/653 y actualizar matriz/RELEVO con commit remoto verificado.'} Reparar contrato factual649 (4/11,siete contradicciones/afirmaciones sin respaldo aceptadas) e idioma de has en request_reading.py. No basta prohibir una palabra ni rechazar abstenciones válidas; conservar español y mezcla. No fuente ni tests nuevos para esas dos reparaciones.

Full651 es línea base anterior,no Full652:exit0;Python10411 pases/3 skips+466 subpruebas,732,07s;.NET4469 pases/1 skip agregado y16 omisiones opt-in impresas aparte. Fuente651 e1c6db6bb79bf1aa69e3c5ec72acac5656804700. Full646 rojo original preservado;24 regresiones de633 reparadas por651 sin cambiar oráculos. El encargo requiere Full al adoptar C#+Python juntos y al cierre final,no en cada edición Python.

## Resto y herramientas

Siguen encuesta,ocho rutas,UI real,loopback completo/AEC separado,error→restauración→petición normal y Full final. Continuidad C04–C09 documentada,no ejecutar esos goals. tools.mcp__node_repl__js con @oai/sky funciona para escritorio; skill computer-use y documentación leídos. Re-listar ventanas antes de seleccionar,observar antes de actuar y comprobar foco antes de escribir. No mezclar shell UIA con sky. Diagnóstico: py main.py y cerrar sólo instancia propia; no repetir launcher315 que dejaba BAXY abierto. Voz259 mide eco puro,no voz humana física C08.

Python C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8. Dotnet C:/Users/usuario/.dotnet/dotnet.exe. No solapar build/Full e inferencia. Sellos -text,no normalizar bytes. Goal completo sólo con todos los criterios probados.
'''
(base / 'HANDOFF.md').write_text(handoff, encoding='utf-8', newline='\n')
state_path = base / 'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state['continuation'] = 'Reparar contrato factual649 e idioma has; no campañas activas.' if published else 'Publicar650/652/653, actualizar matriz; después contrato649 e idioma.'
if published:
    state.update(publishedSourceCommit=commit, publishedEvidenceCommit=commit)
    p = root / 'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
    lines = p.read_text(encoding='utf-8').splitlines()
    updated = []
    for i, line in enumerate(lines):
        if any(line.startswith(f'| {case} /') for case in ['G04.06', 'G06.01', 'G06.06']):
            cells = line.split('|')
            assert cells[3].strip() == 'C03'
            cells[5] = cells[5].replace('25 cubiertos, 717 abiertos', '26 cubiertos, 716 abiertos').replace('717 fallos', '716 fallos')
            cells[5] += (f' Fuente652 publicada en {commit}, remoto verificado. Dueñas3902 pases+121 subpruebas/0 skips; declaraciones17 pases/1 skip ambiental; Fast0. Producto653:19/20 finales,16/16 lecturas por aplicación; H0040 acreditado. Foco inglés y contrato factual649 pendientes. No Full652 ni cierre global; Full651 conserva su alcance. ')
            lines[i] = '|'.join(cells)
            updated.append(cells[1].strip())
    assert len(updated) == 3
    p.write_text('\n'.join(lines)+'\n', encoding='utf-8', newline='\n')
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as f:
    f.write(f'\n\n## Publicación652 — {status}\n\nEncuesta26 cubiertos/716 abiertos/0NA, sólo H0040 actualizado con653; resto intacto. Ninguna decisión pendiente. Fuente y pruebas según RESULT652/653. Contrato factual e idioma siguen pendientes; no campañas activas.\n')
print({'published': published, 'commit': commit, 'survey': survey['verification_counts']})
