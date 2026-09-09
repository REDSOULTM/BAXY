from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-abstain289.py').read_text(encoding='utf-8')
start=source.index('wire=')
end=source.index('prereg=')
replacement='''import sys
sys.path.insert(0,str(root/'src'))
from baxy_mind.llm import LlmRuntime
hello=json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-app-catalog262-private/HELLO_CATALOGS.json').read_text(encoding='utf-8'))
descriptions={row['name']:{'description':row['description']} for row in hello['capabilities']}
prior=[json.loads(line) for line in (root/'artifacts/comprobaciones/C03/astra-native-scope/posts.jsonl').read_text(encoding='utf-8').splitlines()]
class Captured(Exception):
    pass
class Capture(LlmRuntime):
    def __init__(self):
        pass
    def _post(self,payload):
        self.payload=payload
        raise Captured()
cases=[]
for index,row in enumerate(prior):
    names=[tool['function']['name'].removeprefix('baxy_').replace('__','.') for tool in row['payload']['tools']]
    runtime=Capture()
    try:
        runtime._post_native_tool_selection(row['case'],names,descriptions,[])
    except Captured:
        pass
    calls=row['response']['choices'][0]['message'].get('tool_calls') or []
    expected=[call['function']['name'].removeprefix('baxy_').replace('__','.') for call in calls]
    cases.append({'case_id':f'scope-{index+1}','payload':runtime.payload,'expected':expected})
'''
source=(source[:start]+replacement+source[end:]).replace('astra-abstain289','astra-abstain290')
source=source.replace('Same seven frozen payloads/candidate order/seed/temp/max_tokens and Qwen3.5backend.','Eleven previously validated native-scope controls (development/synthetic), rebuilt through current native selector with same historical subset and current authenticated Core descriptions; before and after have identical candidates/seed/temp/max_tokens on Qwen3.5. Expected sets preserve previously adjudicated native-scope evidence.')
source=source.replace('Paris must produce sole no_effect_decision with finished tool_calls; no previously correct positive/control decision regresses.','No previously correct scope control may regress: genuine prohibition, translation, past event and knowledge remain no-effect; authorized clock and compound remain requested effects.')
(root/'scratchpad/c03-abstain290.py').write_text(source,encoding='utf-8')
