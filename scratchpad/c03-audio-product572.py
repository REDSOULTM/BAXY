"""Shared product after571: actual nested audio and compound-state facts."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-survey-readonly568.py').read_text(encoding='utf-8')
for old, new in [('astra-survey-readonly568', 'astra-audio-product572'), ('C03-survey-readonly568-private', 'C03-audio-product572-private'), ('C03-readonly-profile568', 'C03-audio-profile572'), ('c03-owner568-hook', 'c03-owner572-hook')]:
    source = source.replace(old, new)
start = source.index('specs = ['); end = source.index('cases = ', start)
source = source[:start] + '''specs = [
    ('H0073-regression', ['¿Está silenciado el sonido y en cuánto está el volumen?',
                         'Is the sound on mute, and what is the volume level?',
                         'Dime la hora y si está silenciado el sonido.',
                         'What time is it, and is the sound on mute?',
                         'mostrame el volumen']),
    ('H0080-regression', ['Is this computer connected to the internet?']),
]
''' + source[end:]
source = source.replace('Five survey requirements each with literal and two new variants: charging, battery percentage, volume/mute, internet connectivity and prohibitions naming three browsers across ES/EN.', 'Audio/mute same failed instruction boundary568/570, EN equivalent, compound time/mute ES/EN, original volume reading and network regression. Published source571; actual readings only, no volume changes.')
source = source.replace('Verify every final against actual native observations; prohibited openings must yield no effect.', 'Verify every final against actual native observations. Where muted is supplied by nested state or mission result, no instruction may claim it is absent. Compound clock and mute must both be conserved. No new survey credit from repeating already covered requirements.')
source = source.replace('Correct observation scope, values/state and subject; no invented success or permanent limitations. Negation preserves app and does not execute the action. Publication alone is not coverage. Charging/current connectivity are observed snapshots, not physical unplug/restore tests.', 'Observed mute/volume polarity and clock must survive shared composition; no false absence instruction. Native receipt, final and posterior state checked. No physical audio output, AEC or UI proof from this headless conductor.')
exec(compile(source, __file__, 'exec'))
