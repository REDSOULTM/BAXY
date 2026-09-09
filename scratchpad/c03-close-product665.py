"""Preserve the real grammatical regression; the candidate is not adopted."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-close-window-facts660-661.py').read_text(encoding='utf-8')
source=source[:source.index("out = base / 'astra-window-facts-source660'")]
source=source.replace('window-facts-product661','literal-product665')
source=source.replace("old = home / 'C03-language-product655-private'","old = home / 'C03-window-facts-product661-private'")
source=source.replace("assert [r['final'] for r in finals] == [r['final'] for r in old_finals]", "changed = [i+1 for i,(a,b) in enumerate(zip(finals,old_finals)) if a['final'] != b['final']]")
source=source.replace("failed = case['case_id'] == 'focus-variant-es'","failed = case['case_id'] == 'package-positive-es'")
source=source.replace('Reproduces655: correct state but unnecessary internal English word foreground in Spanish.','New grammatical error: un ventana visible. Installation and visible count are correct; fails Spanish naturalness. Prior661 had a grammatical answer to this same observation.')
source=source.replace('# Producto661 — 23/24, sin cambios en los24 finales de655','# Producto665 — 23/24; foco reparado, regresión gramatical')
start=source.index("note = '''")
end=source.index('seal(out, private',start)
source=source[:start]+'''note = """# 665 — foco reparado, regresión en concordancia española

Las24 respuestas se revisaron con sus observaciones y capturas independientes.23/24 correctas: t24 elimina foreground y conserva el foco/maximización; t13 ahora dice «tiene un ventana visible». Los hechos de instalación/cantidad se mantienen, pero la concordancia española falla. Antes661 ese mismo caso era correcto. No se adopta664: cambiar el fallo de lugar no demuestra mejora global.

Todas24 actividades igualan los finales. Las16 lecturas de aplicaciones y cuatro referencias conservan sus hechos; Chrome tiene ahora una ventana, no dos como661, y la respuesta respeta la observación actual. Snapshots antes/después coinciden, con AUMID sin errores; no son captura continua ni UI. GPU3497,559MiB,RAM2276,344MiB,40,297s,sin infracciones y registro/fuente estables durante la prueba. No mínimo global ni ahorro ni UI/voz conjunta. Encuesta26/716/0. Completar666 antes de restaurar la fuente660 y seguir la alternativa de representación medida663.
"""
''' + source[end:]
source=source.replace("'source':660", "'source':664, 'adopted':False")
source=source.replace("'all_finals_identical_to655':True", "'changed_indices_from661':changed")
source=source.replace("'application_reads_correct':16", "'application_facts_correct':16, 'application_prose_correct':15")
source=source.replace("'failed_cases':['focus-variant-es']", "'failed_cases':['package-positive-es']")
exec(compile(source,__file__,'exec'))
print({'product665':'23/24','adopted':False})
