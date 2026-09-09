"""Actual CPU subject/quantity repair and unaffected conversational controls."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-survey-readonly568.py').read_text(encoding='utf-8')
for old, new in [('astra-survey-readonly568', 'astra-cpu-actor-product582'), ('C03-survey-readonly568-private', 'C03-cpu-actor-product582-private'), ('C03-readonly-profile568', 'C03-cpu-actor-profile582'), ('c03-owner568-hook', 'c03-owner582-hook')]:
    source = source.replace(old, new)
start = source.index('specs = ['); end = source.index('cases = ', start)
source = source[:start] + '''specs = [
    ('H0007', ['Dime cuantos nucleos de CPU tiene este PC y que modelo de procesador es.',
               'What processor does this PC have, and how many physical cores?',
               '¿Cuántos núcleos físicos y procesadores lógicos tiene mi equipo?',
               'Tell me the physical core count, logical processor count, and CPU model.',
               '¿Qué procesador tengo y cuántos núcleos tiene?',
               'How many cores does this computer have?']),
    ('H0065', ['cuánta cpu estoy usando', 'How much CPU am I using right now?',
               '¿Qué porcentaje de CPU estoy usando?', 'What is the current CPU usage?']),
    ('H0350', ['cuánto uso de CPU tengo', 'cuánto procesador estoy ocupando en este momento',
               'What percentage of the CPU is in use?']),
    ('conversation-controls', ['Me llamo Luisa. ¿Cómo me llamo?', '¿Cómo te llamas?']),
    ('compound-regression', ['Dime la hora y si está silenciado el sonido.']),
    ('network-regression', ['Is this computer connected to the internet?']),
]
''' + source[end:]
source = source.replace("'owner historical survey' if index == 0 else 'assistant development variant'", "'owner historical survey' if case_id.startswith('H') and index == 0 else 'assistant development variant'")
source = source.replace('source555. Five survey requirements each with literal and two new variants: charging, battery percentage, volume/mute, internet connectivity and prohibitions naming three browsers across ES/EN.', 'source581. Six topology variants575, four CPU usage variants including failed historical first person, three additional usage variants for H0350, conversational name/identity, compound clock/audio and network controls. Seventeen actual turns.')
source = source.replace('Verify every final against actual native observations; prohibited openings must yield no effect.', 'Compare each CPU final to that turn actual usage/physical/logical/model observation. Where a first-person actor defect occurs, verify actual rejected draft, repair profile, preserved facts and final. Correct first answers must not spend a correction.')
source = source.replace('Correct observation scope, values/state and subject; no invented success or permanent limitations. Negation preserves app and does not execute the action. Publication alone is not coverage. Charging/current connectivity are observed snapshots, not physical unplug/restore tests.', 'No first-person assistant ownership/process claim from whole-machine CPU observations. Preserve quantities and proper subject under reordered and first/second-person questions, ES/EN. Luisa is synthetic conversational data in this isolated profile, not a request for permanent storage. No UI/voice credit, no physical mutations.')
exec(compile(source, __file__, 'exec'))
