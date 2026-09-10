"""Paired complete status category: preserve facts during actor recovery."""
from pathlib import Path
import argparse

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('arm', choices=['baseline', 'candidate'])
arm = parser.parse_args().arm
source = (root/'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix = source[:source.index("history = [{'role'")]
prefix = prefix.replace('astra-native-subject612', 'astra-machine-actor701-'+arm).replace(
    'C03-native-subject612-private', 'C03-machine-actor701-'+arm+'-private')
exec(compile(prefix, __file__, 'exec'))

panel = []
questions = {
    'wifi.status': [
        ('¿Estoy conectado a alguna red Wi-Fi?', 'es'),
        ('¿Este PC tiene conexión Wi-Fi?', 'es'),
        ('Dime el estado de la conexión inalámbrica.', 'es'),
        ('Comprueba si el equipo está conectado al wifi.', 'es'),
        ('Del Wi-Fi de este computador, dime si está conectado.', 'es'),
        ('Is this PC connected to Wi-Fi?', 'en'),
        ('Tell me whether the wireless connection is active.', 'en'),
        ('Am I connected to a Wi-Fi network?', 'en'),
        ('Baxy, revisa si el Wi-Fi está connected.', 'mixed'),
        ('La conexión wireless de este PC, ¿está activa?', 'mixed'),
    ],
    'network.status': [
        ('¿Hay alguna interfaz de red conectada en este PC?', 'es'),
        ('Dime si el equipo tiene un enlace de red activo.', 'es'),
        ('¿Está conectado este computador a una red?', 'es'),
        ('Comprueba el estado del enlace de red del equipo.', 'es'),
        ('De las interfaces de red, ¿hay alguna conectada?', 'es'),
        ('Does this PC have an active network link?', 'en'),
        ('Tell me if any network interface is connected.', 'en'),
        ('Is this computer connected to a network?', 'en'),
        ('Baxy, ¿hay alguna network interface conectada?', 'mixed'),
        ('El enlace de red del equipo, ¿está online?', 'mixed'),
    ],
}
for operation, prompts in questions.items():
    for connected in [False, True]:
        for index, (text, language) in enumerate(prompts):
            observed = ({'connected': connected, 'authority': 'netsh_wlan_status_secondread'}
                        if operation == 'wifi.status' else
                        {'online': connected, 'connectedInterfaceCount': 1 if connected else 0,
                         'interfaceTypes': ['ethernet'] if connected else []})
            panel.append({'case_id': operation+'-'+str(int(connected))+'-'+str(index),
                'text': text, 'language': language, 'expected': observed,
                'criterion': 'State the observed PC connection state in the request language. Preserve negation and Wi-Fi versus network-link scope; no invented SSID, Internet reachability, changes or assistant-as-subject claim.',
                'facts': {'situation': json.dumps({'kind':'operation', 'operation':operation,
                    'polarity':'success', 'verified':True, 'succeeded':True, 'observed':observed}, ensure_ascii=False)}})
for value in [0, 37.25]:
    for index, (text, language) in enumerate([
        ('¿Cuánta CPU estoy usando?', 'es'), ('Dime el uso actual del procesador.', 'es'),
        ('What is the current CPU usage?', 'en'), ('How much CPU am I using?', 'en'),
        ('Baxy, ¿cuánto CPU usage tiene este PC?', 'mixed'),
    ]):
        observed = {'scope':'cpu', 'cpu':{'usagePercent':value,'physicalCoreCount':6,
                    'logicalProcessorCount':12,'model':'Example Processor'}, 'failures':[]}
        panel.append({'case_id':'cpu-'+str(value)+'-'+str(index), 'text':text,'language':language,
            'expected':observed,'criterion':'Preserve the measured PC CPU percentage, subject and language; no assistant process usage or unobserved hardware claim.',
            'facts':{'situation':json.dumps({'kind':'operation','operation':'system.status',
                'polarity':'success','verified':True,'succeeded':True,'observed':observed},ensure_ascii=False)}})
assert len(panel) == 50
write(private/'panel.json', panel)
if arm == 'candidate':
    assert (private/'panel.json').read_bytes() == (private.parent/'C03-machine-actor701-baseline-private/panel.json').read_bytes()
assert psutil.virtual_memory().available >= 1800*2**20

class NativeCompositor(LlmRuntime):
    def __init__(self, case):
        self._gguf = config['gguf']
        self.case = case
        self.calls = 0

    def _post(self, payload):
        self.calls += 1
        append(private/'requests.jsonl', {'case_id':self.case['case_id'],'call':self.calls,'payload':payload})
        request = urllib.request.Request(url+'/v1/chat/completions',
            data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=30) as response:
            result = json.load(response)
        append(private/'responses.jsonl', {'case_id':self.case['case_id'],'call':self.calls,'response':result})
        assert not violations
        return result

runner = source[source.index('command = json.loads'):]
start = runner.index("write(out / 'PREREG.json', {")
end = runner.index("log = (private / 'launch.log')", start)
runner = runner[:start]+'''write(out/'PREREG.json', {
    'utc':datetime.now(timezone.utc).isoformat(), 'arm':arm,'cases':50,
    'method':'Actual compositor plus local native transport on the same50new synthetic facts and questions. First drafts and every retry recorded; this is integration diagnosis, not model-alone or survey/reserve acceptance. CPU controls retained. Candidate may change only machine-subject recovery; no first prompt, validator, model or topology change.',
    'inheritance':'694H0127/H0433 verified disconnectedWLAN produce first-person drafts; wrong_actor correctly rejects subject but generic online recovery loses scope and third retry explicitly demands First person.579/580 already qualified draft-aware machine actor recovery for CPU; reuse it rather than add a second mechanism.',
    'research_reused':'Official Qwen2507 documented0.7/0.8/k20/minp0 and native chat roles, checked in699/700; candidate uses existing qualified CPU repair profile only after the detected subject error. No universal profile claim.',
    'sources':['https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507'],
    'command':command,'manifest_sha256':manifest_sha,'model_sha256':sha(config['gguf']),
    'server_sha256':sha(command[0]),'source_sha256':sha(root/'src/baxy_mind/llm.py'),
    'panel_sha256':sha(private/'panel.json'),'producer_sha256':sha(Path(__file__)),
    'source_adopted':False, 'criteria':'Per-case declared criterion; all finals manually reviewed. Empty is failure, retries are not additional successes. Compare raw first requests and responses pairwise before attributing gains to repair.',
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240},
})
''' + runner[end:]
start = runner.index('    for row in panel:')
end = runner.index('    complete=True', start)
runner = runner[:start]+'''    for row in panel:
        client = NativeCompositor(row)
        begin = time.monotonic()
        final = client.compose_user_message(row['text'],'status',row['facts'])
        append(private/'finals.jsonl', {'case_id':row['case_id'],'text':row['text'],
            'final':final,'calls':client.calls,'seconds':time.monotonic()-begin})
        print(row['case_id']+' calls='+str(client.calls)+' nonempty='+str(bool(final)),flush=True)
''' + runner[end:]
runner = runner.replace('Collected40 native subject-attribution drafts; adjudication pending.', 'Collected50 compositor outcomes; adjudication pending.')
exec(compile(runner,__file__,'exec'))
