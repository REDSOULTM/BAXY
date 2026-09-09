"""Read-only payload/resource observer; registered model and native sampling unchanged."""
import json, os, time, threading
from pathlib import Path
from baxy_mind.llm import LlmRuntime
_audit=Path(os.environ['BAXY_C03_SAMPLING_AUDIT'])
_original_post=LlmRuntime._post
def _observe_post(self,payload,*args,**kwargs):
    call_id=f'{os.getpid()}:{threading.get_ident()}:{time.monotonic_ns()}'
    row={'callId':call_id,'requestId':str(getattr(self,'_request_identity','')),'payload':payload}
    try:
        response=_original_post(self,payload,*args,**kwargs)
        row['response']=response
        return response
    except Exception as exc:
        row['error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        with _audit.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
LlmRuntime._post=_observe_post
from baxy_mind.turn_evidence import TurnEvidenceService
from baxy_mind.planner import PlannerCatalog

_service_build = TurnEvidenceService._build
_catalog_init = PlannerCatalog.__init__

def _record_resource(value):
    with _audit.with_name("resource-readiness.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value) + "\n")

def _observe_service(self, *args, **kwargs):
    started = time.monotonic()
    try:
        return _service_build(self, *args, **kwargs)
    finally:
        _record_resource({"component":"turn_evidence", "seconds":time.monotonic()-started, "diagnostics":self.diagnostics})

def _observe_catalog(self, *args, **kwargs):
    started = time.monotonic()
    error = None
    try:
        return _catalog_init(self, *args, **kwargs)
    except Exception as exc:
        error = type(exc).__name__
        raise
    finally:
        _record_resource({"component":"planner_catalog", "encoderSupplied":kwargs.get("encoder") is not None, "seconds":time.monotonic()-started, "error":error})

TurnEvidenceService._build = _observe_service
PlannerCatalog.__init__ = _observe_catalog

from baxy_mind.skill_registry import SkillRegistry
_skills_init = SkillRegistry.__init__
def _observe_skills(self, *args, **kwargs):
    started = time.monotonic()
    error = None
    try:
        return _skills_init(self, *args, **kwargs)
    except Exception as exc:
        error = type(exc).__name__
        raise
    finally:
        _record_resource({"component":"skill_registry", "encoderSupplied":getattr(self,"_encoder",None) is not None, "seconds":time.monotonic()-started, "error":error})
SkillRegistry.__init__ = _observe_skills


