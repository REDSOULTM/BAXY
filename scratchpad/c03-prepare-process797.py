"""Reuse the frozen795 category for the sealed796 product candidate."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
target = root / 'scratchpad/c03-process-batch797.py'
review_target = root / 'scratchpad/c03-review-process797.py'
assert not target.exists() and not review_target.exists()
source = (root / 'scratchpad/c03-process-batch795.py').read_text(encoding='utf-8')
source = source.replace('795', '797').replace('pins793', 'pins796').replace('source793', 'source796')
source = source.replace('C03-process-panel797-private/panel.json', 'C03-process-panel795-private/panel.json')
source = source.replace('PROCESS_CATEGORY797_PLAN.json', 'PROCESS_CATEGORY795_PLAN.json')
source = source.replace('INVENTORY_VETO793/SOURCE_PINS.json', 'PROCESS_REPAIR796/SOURCE_PINS.json')
source = source.replace('registered, unmodified product', 'registered product with sealed process repair796')
source = source.replace('with published793;', 'with sealed candidate796;')
source = source.replace('Published793 owners/current pin integrity and Fast, dense764 unchanged. Full7 historical; not final acceptance.',
    'Candidate796:3248 Python owner passes, provider6, Fast0; Full gate must be0 before this launch. Not final C03 acceptance.')
anchor = "plan = read(plan_path)\n"
assert source.count(anchor) == 1
source = source.replace(anchor, anchor + "assert read(ROOT / 'artifacts/comprobaciones/C03/PROCESS_REPAIR796/FULL_EXIT.json')['exit_code'] == 0\n")
assert 'INVENTORY_VETO793' not in source and 'source793' not in source
target.write_text(source, encoding='utf-8')
review = (root / 'scratchpad/c03-review-process795.py').read_text(encoding='utf-8')
review = review.replace('795', '797').replace('source793', 'source796')
review_target.write_text(review, encoding='utf-8')
prereg = {'baseline': 795, 'candidate': 796, 'confirmation': 797,
          'panel_and_criteria_unchanged': True, 'cases': 50,
          'runner_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
          'reviewer_sha256': hashlib.sha256(review_target.read_bytes()).hexdigest(),
          'launch_requires': 'Full796 exit0 and exact14pins; registered model/backend unchanged.',
          'method': 'Whole-category product regression, not native model comparison. Fresh process values will naturally change; requested behavior and criteria are identical.'}
(root / 'artifacts/comprobaciones/C03/PROCESS_REPAIR796/NEXT797.json').write_text(json.dumps(prereg, indent=2) + '\n', encoding='utf-8')
print(json.dumps(prereg))
