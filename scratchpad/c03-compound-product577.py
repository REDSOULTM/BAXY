"""Read-only shared product: preserve clock and audio observations after576."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-survey-readonly568.py').read_text(encoding='utf-8')
for old, new in [('astra-survey-readonly568', 'astra-compound-product577'), ('C03-survey-readonly568-private', 'C03-compound-product577-private'), ('C03-readonly-profile568', 'C03-compound-profile577'), ('c03-owner568-hook', 'c03-owner577-hook')]:
    source = source.replace(old, new)
start = source.index('specs = ['); end = source.index('cases = ', start)
source = source[:start] + '''specs = [
    ('compound-audio-clock', ['Dime la hora y si está silenciado el sonido.',
                              'What time is it, and is the sound on mute?',
                              'Decime la hora y si el volumen está en silencio.',
                              'Dime si está silenciado el audio y qué hora es.',
                              'Check if the sound is muted and what time is it.',
                              '¿Está silenciado el sonido y qué hora es?']),
    ('indirect-audio', ['Comprueba si el audio está silenciado ahora.']),
    ('audio-regression', ['Is the sound on mute, and what is the volume level?']),
    ('network-regression', ['Is this computer connected to the internet?']),
]
''' + source[end:]
source = source.replace("'owner historical survey' if index == 0 else 'assistant development variant'", "'consumed development replay572' if case_id == 'compound-audio-clock' and index < 2 else 'assistant development variant'")
source = source.replace('source555. Five survey requirements each with literal and two new variants: charging, battery percentage, volume/mute, internet connectivity and prohibitions naming three browsers across ES/EN.', 'source576. Six clock/mute questions, changing ordering, explicit or inherited observation verb, wording and language; indirect audio, audio volume and network controls.')
source = source.replace('Verify every final against actual native observations; prohibited openings must yield no effect.', 'Verify every final against actual ordered system.time/audio.status observations. All six compound requests must retain both requested states; no claims without current observations.')
source = source.replace('Correct observation scope, values/state and subject; no invented success or permanent limitations. Negation preserves app and does not execute the action. Publication alone is not coverage. Charging/current connectivity are observed snapshots, not physical unplug/restore tests.', 'Real current read-only states. Conditional or power actions are tested only in unit owners, never issued to the real computer. No UI, voice or AEC credit from the hidden conductor. No new survey credit solely from development variants.')
exec(compile(source, __file__, 'exec'))
