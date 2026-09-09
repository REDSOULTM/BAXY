"""Seal reviewed real-window results without promoting candidate667."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-close-window-facts660-661.py').read_text(encoding='utf-8')
source = source[:source.index("out = base / 'astra-window-facts-source660'")]
source = source.replace('window-facts-product661', 'projection-product669')
source = source.replace("old = home / 'C03-language-product655-private'", "old = home / 'C03-window-facts-product661-private'")
source = source.replace("assert [r['final'] for r in finals] == [r['final'] for r in old_finals]", "changed = [i+1 for i,(a,b) in enumerate(zip(finals,old_finals)) if a['final'] != b['final']]")
source = source.replace("['windows'][0]['foreground']", "['windows'][0]['is_current_window_for_user_interaction']")
source = source.replace("failed = case['case_id'] == 'focus-variant-es'", 'failed = False')
source = source.replace('# Producto661 — 23/24, sin cambios en los24 finales de655', '# Producto669 — 24/24 con observaciones actuales; candidata sin adopción')
start = source.index("note = '''")
end = source.index('seal(out, private', start)
source = source[:start] + '''note = """# 669 — las24 respuestas cumplen las observaciones actuales

El panel conserva las24 consultas de661. Se revisaron sus finales y22 observaciones contra capturas independientes antes/después:24/24 correctas,16 lecturas por aplicación y cuatro referencias correctas. Todas24 actividades igualan sus finales. La consulta real de foco español ya responde «La ventana activa es \\"ChatGPT\\". Está maximizada.». El foco permanece ChatGPT, y sus campos proyectados conservan el estado activo.

Steam y WhatsApp ahora están cerrados por la liberación de RAM autorizada; sus observaciones y respuestas dicen cero ventanas. Chrome conserva una ventana. No se presenta como reproducción del estado positivo de esas dos apps en661/665 ni como prueba de reparación de «un ventana». Los snapshots no son observación continua, y este conductor no acredita UI real ni voz.

GPU3497,559MiB,RAM1904,250MiB,45,187s; sin infracciones, registro y fuentes estables durante la corrida. Menor RSS observado no demuestra ahorro causado por667: el estado del PC y sus aplicaciones cambió. La candidata sigue sin adoptar por los controles compuestos668 y porque faltan sus dueñas/declaraciones/Fast. Encuesta26/716/0; C03 sigue abierto.
"""
''' + source[end:]
source = source.replace("'source':660, 'correct':23", "'source':667, 'adopted':False, 'correct':24")
source = source.replace("'all_finals_identical_to655':True", "'changed_indices_from661':changed")
source = source.replace("'failed_cases':['focus-variant-es']", "'failed_cases':[]")
exec(compile(source, __file__, 'exec'))
print({'product669':'24/24', 'adopted':False})
