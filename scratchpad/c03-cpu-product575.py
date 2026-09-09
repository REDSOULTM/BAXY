"""Verify live physical CPU observations through the shared product after574."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-survey-readonly568.py').read_text(encoding='utf-8')
for old, new in [('astra-survey-readonly568', 'astra-cpu-product575'), ('C03-survey-readonly568-private', 'C03-cpu-product575-private'), ('C03-readonly-profile568', 'C03-cpu-profile575'), ('c03-owner568-hook', 'c03-owner575-hook')]:
    source = source.replace(old, new)
start = source.index('specs = ['); end = source.index('cases = ', start)
source = source[:start] + '''specs = [
    ('H0007', ['Dime cuantos nucleos de CPU tiene este PC y que modelo de procesador es.',
               'What processor does this PC have, and how many physical cores?',
               '¿Cuántos núcleos físicos y procesadores lógicos tiene mi equipo?',
               'Tell me the physical core count, logical processor count, and CPU model.',
               '¿Qué procesador tengo y cuántos núcleos tiene?',
               'How many cores does this computer have?']),
    ('cpu-usage-regression', ['¿Cuánta CPU se está usando ahora?', 'What is the current CPU usage?']),
    ('network-regression', ['Is this computer connected to the internet?']),
    ('audio-regression', ['¿Está silenciado el sonido y en cuánto está el volumen?']),
]
''' + source[end:]
source = source.replace("'owner historical survey' if index == 0 else 'assistant development variant'", "'owner historical survey' if case_id == 'H0007' and index == 0 else 'assistant development variant'")
source = source.replace('source555. Five survey requirements each with literal and two new variants: charging, battery percentage, volume/mute, internet connectivity and prohibitions naming three browsers across ES/EN.', 'source574. Six CPU topology questions: historical literal plus changed order, wording, physical/logical distinction, model and ES/EN. CPU usage, network and audio regression controls.')
source = source.replace('Verify every final against actual native observations; prohibited openings must yield no effect.', 'Verify every final against live physicalCoreCount, logicalProcessorCount and model received from the Windows provider through Core and the mind. No CPU count inferred from SMT or model name.')
source = source.replace('Correct observation scope, values/state and subject; no invented success or permanent limitations. Negation preserves app and does not execute the action. Publication alone is not coverage. Charging/current connectivity are observed snapshots, not physical unplug/restore tests.', 'Core counts and processor identity must match actual observations. CPU usage remains an independent subject-attribution control. Read only, no UI/audio output proof. Native573 changed-topology controls support generalization but are not this hardware.')
source = source.replace("'src/baxy_mind/effect_intent.py']", "'src/baxy_mind/effect_intent.py','src/Baxy.Providers.Windows/SystemStatus/WindowsSystemStatusProbe.cs','src/Baxy.Providers.Windows/SystemStatus/WindowsSystemStatusProvider.cs','src/Baxy.Providers.Windows/SystemStatus/SystemStatusContracts.cs','src/Baxy.Core/Operations/CoreOperationModels.cs','src/Baxy.Core/Operations/SystemStatusHandler.cs']")
exec(compile(source, __file__, 'exec'))
