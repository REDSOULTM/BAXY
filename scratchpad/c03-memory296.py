"""Compare faithful projection of AskToSave, without persistence or visible templates."""
from pathlib import Path
from datetime import datetime,timezone
import copy
import json
import sys
import urllib.request

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind import llm
out=root/'artifacts/comprobaciones/C03/astra-memory296'
out.mkdir(exist_ok=False)
cases=['me llamo emmanuel, dime hola emmanuel','me llamo Albeda','my favorite city is Lima']
facts={'situation':{'kind':'clarification','polarity':'pending','cause':'context_not_saved'}}
meaning='No persistent memory was written. The person has provided personal context; saving that context for future sessions requires their consent.'
prereg={'utc':datetime.now(timezone.utc).isoformat(),'method':'Actual owner264 index103/t54 plus2 existing parser controls. Compare original context_not_saved fallback with projection of actual AskToSave semantics. Same current source284 compositor, registered2507 backend, exact request/facts, unchanged prompts/settings. No effects or storage. Only _CAUSE_FACT entry differs in this diagnostic process.',
    'hypothesis':'Literal context not saved loses the meaning of parser outcome AskToSave (mustNotPersist=true), so the compositor asks what to do instead of acknowledging/requesting storage consent.',
    'criteria':'Owner greeting requested should be served without false storage claim; normal personal fact should produce relevant acknowledgment/consent request rather than unrelated clarification. No fixed visible text. Native success alone does not fix parser consuming mixed requests.',
    'inheritance':'Carter_v2 LLM_CONTEXT_MEMORY_REPORT.md distinguishes stated facts from confirmed persistent memory. Current parser AskToSave and MainWindowViewModel context_not_saved are authoritative; existing _CAUSE_FACT maps typed states into prose facts.',
    'cases':cases,'meaning':meaning,'facts':facts}
prereg.update(method='Same three development inputs295 through actual chat API with knowledge classification, no persistent-memory or effect authority; no source change. This tests whether AskToSave classification, rather than missing lexical memory fact, causes the lost reply.',criteria='Serve the stated conversational request without false persistence or unsupported questions. No adoption from native comparison alone.')
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
class Runtime(llm.LlmRuntime):
    def __init__(self):
        self._gguf=r'D:\BAXYRuntime\experiments\models\qwen3-4b-instruct-2507-a06e946b\Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
        self.posts=[]
    def _post(self,payload):
        payload=copy.deepcopy(payload)
        prefix=[]
        for message in payload['messages']:
            if message['role']!='system':
                break
            prefix.append(message['content'])
        if len(prefix)>1:
            payload['messages']=[{'role':'system','content':'\n\n'.join(prefix)},*payload['messages'][len(prefix):]]
        with urllib.request.urlopen('http://127.0.0.1:63490/slots',timeout=5) as response:
            assert not any(item['is_processing'] for item in json.load(response))
        req=urllib.request.Request('http://127.0.0.1:63490/v1/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=90) as response:
            response=json.load(response)
        self.posts.append({'payload':payload,'response':response})
        return response
original=dict(llm._CAUSE_FACT)
results=[]
try:
    for text in cases:
        for variant in ['conversation']:
            llm._CAUSE_FACT.clear()
            llm._CAUSE_FACT.update(original)
            if variant=='typed_meaning':
                llm._CAUSE_FACT['context_not_saved']=meaning
            runtime=Runtime()
            row={'request':text,'variant':variant}
            try:
                row['answer']=runtime.chat(text,temperature=0.0,conversation_kind='knowledge',response_language='en' if text.startswith('my ') else 'es')[0]
            except Exception as error:
                row['error']=repr(error)
            row['posts']=runtime.posts
            results.append(row)
            (out/'RESULT.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({k:v for k,v in row.items() if k!='posts'},ensure_ascii=True),flush=True)
finally:
    llm._CAUSE_FACT.clear()
    llm._CAUSE_FACT.update(original)

