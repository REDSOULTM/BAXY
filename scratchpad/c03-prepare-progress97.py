from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-progress-state96.py').read_text(encoding='utf-8')
source = source.replace("'astra-progress-state96'", "'astra-progress-stages97'")
source = source.replace("for variant in ('state_only',):", "for variant in ('understanding', 'preparing_steps', 'acting', 'step_two_of_three'):")
source = source.replace("if variant == 'state_only':", "if variant:")
source = source.replace('situation[\'state\'] = "understanding the person\'s request"', '''situation['state'] = {
                    'understanding': "reviewing the person's request",
                    'preparing_steps': "preparing the steps for the request",
                    'acting': "working on the current step",
                    'step_two_of_three': "working on the current step",
                }[variant]
                if variant == 'step_two_of_three':
                    situation.update(step=2, totalSteps=3)''')
start = source.index("prereg = {'method':")
end = source.index("    'sourceSha256':", start)
source = source[:start] + '''prereg = {'method': 'Native stage-data transfer after96 removes future-goal inference but uses awkward literal '
    'understanding phrasing. Two language packets; four factual activity fixtures each: reviewing request, '
    'preparing steps, working current step, working step2 of3. These are assumed phase fixtures, not observed '
    'execution or UI evidence. Original progress instruction and greedy non-thinking sampler unchanged, '
    'request body still withheld from narrator only, no source changes. Judge natural phase-faithful text, '
    'no invented effects/results and preservation of supplied step count. No fixed visible response or promotion.',
''' + source[end:]
target = root / 'scratchpad/c03-progress-stages97.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
