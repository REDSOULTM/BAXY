from pathlib import Path
import json, os, sys, time
root = Path.cwd()
sys.path.insert(0, str(root/'src'))
os.environ['PYTHONPATH'] = str(root/'src')
from baxy_mind.router import ProcessIntentRouter, RequestBudgetEncoder
from baxy_mind.turn_evidence import TurnEvidenceService
started = time.monotonic()
router = ProcessIntentRouter()
service = TurnEvidenceService()
last = None
try:
    print(json.dumps({'phase':'initial','diagnostics':service.diagnostics}), flush=True)
    service.start(RequestBudgetEncoder(router), lambda: router.try_ready(.5))
    while time.monotonic()-started < 210:
        ready = router.try_ready(.05)
        state = (ready, service.state, service.failure, getattr(router, '_failure', ''))
        if state != last:
            print(json.dumps({'seconds':round(time.monotonic()-started,2), 'state':state, 'diagnostics':service.diagnostics}), flush=True)
            last = state
        if service.state in {'ready','failed','unavailable'}:
            break
        time.sleep(1)
    print(json.dumps({'phase':'result','seconds':round(time.monotonic()-started,2),'diagnostics':service.diagnostics}), flush=True)
finally:
    service.stop(timeout=1)
    router.close()
