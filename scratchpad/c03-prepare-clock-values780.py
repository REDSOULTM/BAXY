"""Prepare a bounded calendar/clock-value probe, inheriting composer776 mechanics."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'scratchpad/c03-battery-values776.py').read_text(encoding='utf-8')
source = source.replace('battery scenarios', 'clock/calendar scenarios')
source = source.replace('776', '780').replace('775', '778').replace('774', '779')
source = source.replace('BATTERY_VALUES780', 'CLOCK_VALUES780').replace('battery-values780', 'clock-values780')
source = source.replace('BATTERY_ACTOR778', 'CLOCK_SCOPE778').replace('battery-actor778', 'clock778')
source = source.replace('483 passed, 1 skipped in 5.63s', '2298 passed, 1 skipped')
start = source.index("captured = read(PREVIOUS / 'review.json')")
end = source.index('for key in list(os.environ):', start)
fixtures = '''captured = read(PREVIOUS / 'review.json')[0]['compose'][0]
template = json.loads(captured['situation'])
assert template['operation'] == 'system.time'
assert set(template['observed']) == {'version', 'utc', 'localUtcOffsetMinutes'}
OUT.mkdir()
PRIVATE.mkdir()
cases = []
values = [
    ('2026-01-01T00:15:00+00:00', -180),
    ('2026-12-31T23:45:00+00:00', 330),
    ('2024-03-01T00:05:00+00:00', -60),
    ('2025-03-01T00:05:00+00:00', -60),
    ('2026-02-01T00:10:00+00:00', -720),
    ('2026-04-01T00:10:00+00:00', -660),
    ('2026-05-01T00:10:00+00:00', -480),
    ('2026-06-01T00:10:00+00:00', -300),
    ('2026-07-01T00:10:00+00:00', -180),
    ('2026-08-01T00:10:00+00:00', -60),
    ('2026-09-01T12:00:00+00:00', 0),
    ('2026-10-01T11:59:00+00:00', 60),
    ('2026-11-01T23:59:00+00:00', 345),
    ('2026-12-01T23:59:00+00:00', 570),
    ('2026-01-15T12:00:00+00:00', 660),
    ('2026-02-15T23:30:00+00:00', 840),
    ('2026-03-15T00:00:00+00:00', 0),
    ('2026-04-15T12:00:00+00:00', 0),
    ('2026-05-15T18:07:00+00:00', -180),
    ('2026-06-15T02:09:00+00:00', 330),
    ('2026-07-15T08:03:00+00:00', -480),
    ('2026-08-15T15:42:00+00:00', 345),
    ('2026-09-15T04:58:00+00:00', 570),
    ('2026-10-15T21:11:00+00:00', -300),
    ('2026-11-15T09:26:00+00:00', -660),
]
questions = {
    'time': ['Dime qué hora es.', 'What time is it?', 'Baxy, dime the local time.'],
    'date': ['¿Qué fecha es hoy?', 'What is the current local date?', 'Mostrame the current date.'],
}
from datetime import timedelta
for index, (stamp, offset) in enumerate(values):
    local = datetime.fromisoformat(stamp) + timedelta(minutes=offset)
    for group in ['time', 'date']:
        situation = copy.deepcopy(template)
        situation['observed'].update(utc=stamp, localUtcOffsetMinutes=offset)
        language_index = (index + (group == 'date')) % 3
        cases.append({'id': f'clock780-{len(cases) + 1:02d}', 'group': group,
            'language': ['es', 'en', 'mixed'][language_index],
            'request': questions[group][language_index], 'situation': situation,
            'expected_clock': local.strftime('%H:%M'), 'expected_date': local.strftime('%Y-%m-%d'),
            'synthetic_observation': True,
            'criterion': 'Answer the requested local date/time from the supplied UTC plus explicit offset. '
                         'Accept equivalent natural wording and accurate12/24-hour forms; keep language and all additional claims faithful. '
                         'No stale value, UTC/local substitution, unsupported timezone/DST inference, empty answer or truncation.'})
assert len(cases) == 50
write(PRIVATE / 'cases.json', cases)
'''
source = source[:start] + fixtures + source[end:]
source = source.replace("'groups': {'percent': 30, 'charging': 12, 'absence': 6, 'unknown': 2}",
                        "'groups': {'time': 25, 'date': 25}")
source = source.replace('779 complete observed situation; only battery values and user request vary in declared fixtures.',
                        '779 complete observed clock situation; only UTC, explicit offset and user request vary in declared synthetic fixtures.')
target = ROOT / 'scratchpad/c03-clock-values780.py'
assert not target.exists()
target.write_bytes(source.encode('utf-8'))
print(target)
