"""Check the recorded isolated probes, without rerunning product or models."""
import json
from pathlib import Path
BASE = Path(__file__).resolve().parent
cs = json.loads(BASE.joinpath('dotnet-probe.log').read_text(encoding='utf-8-sig'))
py = json.loads(BASE.joinpath('python-probe.json').read_text(encoding='utf-8'))
checks = {
    'old_narrator_converts_utc': cs['oldNarrator'].endswith('02:57.'),
    'old_policy_requires_real_time': '02:57' in cs['oldRequiredLiterals'],
    'old_policy_rejects_wrong_time': cs['oldUnrelatedClockRejection']=='missing_literal_fact',
    'first_change_loses_required_time': cs['firstChangeRequiredLiterals']==[],
    'first_change_accepts_wrong_time_at_csharp_boundary': cs['firstChangeUnrelatedClockRejection'] is None,
    'end_goal09_accepts_wrong_time_at_csharp_boundary': cs['newUnrelatedClockRejection'] is None,
    'actual_contract_lacks_local_time_aug23_sep02': all('time' not in r['actual_contract']['seen'] for r in py[1:]),
    'sample_contract_has_local_time_aug23_sep02': all(r['historical_test_contract']['seen']['time']=='22:10' for r in py[1:]),
    'language_defect_predates_goal06': py[0]['language_examples']['Good afternoon']=='es',
}
result = {'scope':'historical pure-code reproduction, not E2E or a C03 acceptance',
          'passed':sum(checks.values()),'failed':sum(not v for v in checks.values()),
          'checks':checks,
          'tested_dotnet_project':'C:/Users/usuario/AppData/Local/Temp/baxy-history-pure-qcx5mojd/Probe.csproj'}
BASE.joinpath('verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
