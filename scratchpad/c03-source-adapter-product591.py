"""CPU qualification through source590, without sitecustomize or method overrides."""
from pathlib import Path
import json
import os

root = Path(__file__).resolve().parents[1]
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-source-adapter-product591-private'
private.mkdir(exist_ok=False)
panel = json.loads((private.parent / 'C03-scoped-lora-product589-private/panel.json').read_text(encoding='utf-8'))
(private / 'panel.json').write_text(json.dumps(panel, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
adapter = {
    'schema': 'baxy-cpu-prose-adapter-v1',
    'gguf': 'D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f/c03-pilot-lora-v4-f32.gguf',
    'gguf_sha256': 'e28d7728c915861a798b005c22e7b9148fdce729e4a402ac5d502abdbeaccce5',
    'base_gguf_sha256': '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597',
}
(private / 'candidate-adapter.json').write_text(json.dumps(adapter, indent=2) + '\n', encoding='utf-8', newline='\n')
source = (root / 'scratchpad/c03-private-product521.py').read_text(encoding='utf-8')
for old, new in [
    ('astra-private-product521', 'astra-source-adapter-product591'),
    ('C03-private-product521-private', 'C03-source-adapter-product591-private'),
    ('C03-private-profile521', 'C03-source-adapter-profile591'),
]:
    source = source.replace(old, new)
start = source.index('cases = ')
end = source.index('\n\ncommands =', start)
source = source[:start] + "cases = [row['text'] for row in json.loads((private/'panel.json').read_text(encoding='utf-8'))]" + source[end:]
start = source.index('prereg = {')
end = source.index("(out/'PREREG.json').write_text", start)
source = source[:start] + '''prereg = {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Source590 CPU adapter owner. Same17 actual product inputs as589, using production module and explicit candidate profile environment only. No sitecustomize, monkeypatch, observer wrapper, draft or fact replacement. Private built-in compose and turn audits capture actual payloads and observations. This is development regression, not blind acceptance or registered promotion.',
    'criteria': 'Six CPU topology and seven usage variants must preserve machine subject, physical/logical counts, model, measured usage at displayed precision and ES/EN. Four name/identity/clock-audio/network controls must remain correct. Audit CPU profile selection. Conductor does not demonstrate visible UI or voice.',
    'manifest_sha256': sha(manifest), 'panel_sha256': sha(private/'panel.json'),
    'candidate_adapter': json.loads((private/'candidate-adapter.json').read_text(encoding='utf-8')),
    'sources': {name: sha(root/name) for name in ['src/baxy_mind/cpu_prose_adapter.py', 'src/baxy_mind/llm.py', 'src/Baxy.App/MindRuntimeDiscovery.cs', 'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll']},
    'private': str(private), 'case_count': len(cases),
    'resource_limits': {'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768, 'wall_time_seconds': 240},
}
''' + source[end:]
old = "str(root/'scratchpad/c03-owner521-hook')+os.pathsep+str(root/'src')"
assert source.count(old) == 1
source = source.replace(old, "str(root/'src')")
needle = "command=['py','main.py'"
assert source.count(needle) == 1
source = source.replace(needle, "env['BAXY_MIND_CPU_PROSE_ADAPTER'] = (private/'candidate-adapter.json').read_text(encoding='utf-8')\n" + needle)
assert 'sitecustomize' not in source[source.index('env=os.environ.copy()'):]
exec(compile(source, __file__, 'exec'))
