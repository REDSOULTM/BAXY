
# Read-only instrumentation, scoped to this diagnostic process tree.
import time as _time407
from baxy_mind import planner as _planner407, router as _router407
from baxy_mind import turn_evidence as _evidence407, skill_registry as _skills407
_begin407 = _time407.monotonic()
def _event407(event, **fields):
    with (Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-retrieval-startup407-private/startup-observer.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'event': event, 'pid': os.getpid(), 'seconds': round(_time407.monotonic() - _begin407, 3), **fields}) + '\n')
_prior_ready407 = _router407.ProcessIntentRouter.try_ready
def _ready407(self, timeout=0.0):
    value = _prior_ready407(self, timeout)
    if value and not getattr(self, '_c03_observed_ready407', False):
        self._c03_observed_ready407 = True
        _event407('router_ready')
    if self._failed and not getattr(self, '_c03_observed_failed407', False):
        self._c03_observed_failed407 = True
        _event407('router_failed', failure=self._failure)
    return value
_router407.ProcessIntentRouter.try_ready = _ready407
_prior_build407 = _evidence407.TurnEvidenceService._build
def _build407(self, *args, **kwargs):
    _event407('corpus_build_start')
    try:
        return _prior_build407(self, *args, **kwargs)
    finally:
        _event407('corpus_build_end', diagnostics=self.diagnostics)
_evidence407.TurnEvidenceService._build = _build407
_prior_load407 = _skills407.SkillRegistry.load_default
@classmethod
def _load407(cls, *args, **kwargs):
    try:
        value = _prior_load407(*args, **kwargs)
    except Exception as error:
        _event407('resources_failed', error=type(error).__name__)
        raise
    _event407('resources_built', semantic=kwargs.get('encoder') is not None)
    return value
_skills407.SkillRegistry.load_default = _load407
