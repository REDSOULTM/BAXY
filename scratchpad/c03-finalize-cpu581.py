"""Seal final review of percentage spellings/signs and plural processor claims."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-cpu-actor581'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


for part in ('final-owners', 'final-focal-stt', 'baseline46-corrected', 'final-owners-corrected', 'final-focal-stt-corrected', 'final-fast'):
    (out / (part + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-actor581-{part}.log').read_bytes())
assert '2156 passed, 121 subtests passed' in (out / 'final-owners-corrected.log').read_text(encoding='utf-8-sig')
assert '58 passed, 1 skipped' in (out / 'final-focal-stt-corrected.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'final-fast.log').read_text(encoding='utf-8-sig')
note = '''# Handoff C03 — fuente581, validación final

Se adopta guarda de actor acotada a observaciones CPU: no presentar uso total como consumo del asistente ni hardware del PC como propiedad de BAXY. Reutiliza los dos reintentos existentes con el borrador realmente rechazado. Qwen3-4B-Instruct-2507 usa sólo en esa reparación el perfil cualificado0,7/0,8/20/min0/presence0/repeat1/seed0; otros modelos conservan el suyo. Las respuestas correctas permanecen en un intento. La tercera reparación CPU tampoco recibe First person. Tres rechazos devuelven vacío por el contrato existente, nunca el texto rechazado.

También se rechazan cifras CPU contradichas: el validador anterior admitía99% frente a23,75 observado. Comprobación acotada a conjuntos sóloCPU, sin confundir porcentajes de otras métricas; respeta precisión mostrada, coma/punto, mayúsculas, per cent/porciento y signos, y compara conteos físicos/lógicos. Admite etiquetas de cantidades, rechaza negativos y campos bool/no numéricos. No es una validación numérica universal de observaciones mixtas. La revisión añadió plural processors y formatos/signos; las dos pruebas nuevas de inglés inicialmente pedían Describe CPU (clasificadoES) y eran rechazadas antes por idioma: se corrigió su contexto lingüístico, no la guarda.

Validación final581: baseline46 contra fuente anterior guardada,32fallos/14pass,0,73s; sólo módulo en memoria de subprocess, sin escribir árbol ni llamar al modelo. Dueñas y contratos2156pass+121subtests/0skip,10,53s. FocalCPU46+STT12=58pass/1skip ambiental,1,57s (campaña ciega sin archivos). Ruff de fuente/prueba final verde. Fast final verde completo; Release incremental1,76s,0advertencias/errores. Métricas iniciales39/2149 y logs de fallos conservados como etapas anteriores, no confundidos con final. Árbol Python7264631e11322195ec745c7ddceb9bba9e009c1336bd8d71f2faeb748ee8521a/403, históricos intactos. SóloPython en581; Full final pendiente.

578 feedback con borrador arregla actor pero greedy rompe gramática;579 perfil oficial seed0 corrige cuatro originales;580 corrige tres primeras personas indebidas en fixtures con números/modelos/idiomas distintos. Corregir un ES ya correcto empeora el trato: la guarda impide ese reintento innecesario, probado. No CPU física sintética presentada como real. Recursos nativos578–580GPU3497,559MiB/RAM720,598/720,195/725,414MiB; sin UI/voz.

Fuente576 publicada022416a0 y verificada577:9finales correctos, seis variantes hora+silencio y tres controles; GPU3497,559MiB/RAM1859,543MiB,28,766s. CPU física574 publicadaad6d9a1a, reales8/16;575 conserva datos pero falla sujeto en una variante. H0007 sigue abierto hasta producto582. Encuesta12 cubiertos/730 abiertos/0NA,742/rev1248 intactos. BAXY manual cerrado, ninguna decisión pendiente del dueño, goal activo. Main5f572ee1b48cb5e2543ee5e06510e51057c9c845 intacto.

Publicar581 y ejecutar582 (17turnos): H0007 seis variantes, H0065 cuatro, H0350 tres y controles de nombres/identidad/hora-audio/red. Verificar rechazo y reparación efectivos, cifras y sujeto; sólo entonces actualizar cada case_id. Después quedan otros defectos, cobertura de encuesta/ocho rutas, UI real, loopback íntegro/AEC como supresión, consumo conjunto, aceptación y Full final. Full526 rojo original reparado en dueñas528–531, nunca presentarlo como Full verde. C08 humano sólo evidencia/reanudación. Fast terminó; cerrar build servers propios antes de medir582.
'''
(out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out / 'RESULT.json', {'adopted': True, 'final_baseline': {'failed': 32, 'passed': 14, 'seconds': .73}, 'final_owners_and_contracts': {'passed': 2156, 'subtests': 121, 'skipped': 0, 'seconds': 10.53}, 'focal_and_stt': {'cpu_passed': 46, 'stt_passed': 12, 'environmental_skips': 1, 'seconds': 1.57}, 'fast': 'passed', 'release_incremental_seconds': 1.76, 'source_sha256': sha(root / 'src/baxy_mind/llm.py'), 'test_sha256': sha(root / 'tests/test_c03_cpu_actor.py'), 'product': 'pending582', 'survey': {'covered': 12, 'open': 730, 'not_applicable': 0}})
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
(base / 'HANDOFF.md').write_text(note, encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
state = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
state.update(checkpoint='581 final: scoped CPU actor/numeric guards;2156pass+121subtests,CPU46+STT12pass/1skip,Fast green. Survey12/730/0; product582 pending.', confirmedAtUtc=datetime.now(timezone.utc).isoformat())
write(base / 'RELEVO_ACTIVO.json', state)
print('581 final validated; ready for publication and product582.')
