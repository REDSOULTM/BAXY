"""Verify the published569 connectivity repair through shared product dispatch."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-survey-readonly568.py').read_text(encoding='utf-8')
for old, new in [('astra-survey-readonly568', 'astra-network-product570'), ('C03-survey-readonly568-private', 'C03-network-product570-private'), ('C03-readonly-profile568', 'C03-network-profile570'), ('c03-owner568-hook', 'c03-owner570-hook')]:
    source = source.replace(old, new)
start = source.index('specs = ['); end = source.index('cases = ', start)
source = source[:start] + '''specs = [
    ('H0080', ['funciona mi internet', 'Is this computer connected to the internet?',
              '¿Está mi PC conectado a internet ahora?',
              'Check whether this computer is connected to the internet.',
              'Am I connected to the internet?', 'Is this machine online?',
              'Is this computer connected to the internet, and what time is it?']),
    ('H0073-control', ['¿Está silenciado el sonido y en cuánto está el volumen?']),
]
''' + source[end:]
source = source.replace('Five survey requirements each with literal and two new variants: charging, battery percentage, volume/mute, internet connectivity and prohibitions naming three browsers across ES/EN.', 'Seven local-connectivity questions, including historical literal, failed English variant568, machine names, first-person subject, imperative check and compound clock; one prior volume/mute control. Published source569, no prompt or model changes.')
source = source.replace('Verify every final against actual native observations; prohibited openings must yield no effect.', 'Verify every final against actual native network observation; no web.search substitution or unnecessary Wi-Fi status. Compound query must preserve the clock. Volume/mute remains a control with known contradictory instruction slated for repair571.')
source = source.replace('Correct observation scope, values/state and subject; no invented success or permanent limitations. Negation preserves app and does not execute the action. Publication alone is not coverage. Charging/current connectivity are observed snapshots, not physical unplug/restore tests.', 'Current local connectivity, correct subject, complete compound request and verified values. No credit solely for publication. These are current observed snapshots, not an offline/recovery injection or physical network reconfiguration.')
exec(compile(source, __file__, 'exec'))
