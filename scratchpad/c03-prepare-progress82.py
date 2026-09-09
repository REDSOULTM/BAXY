from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-progress-inference64.py').read_text(encoding='utf-8')
source = source.replace('progress-inference64', 'progress-baseline82')
source = source.replace("config = json.loads(reg.read_text(encoding='utf-8-sig'))", "config = json.loads(reg.read_text(encoding='utf-8-sig'))\nconfig['gguf'] = 'D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf'")
source = source.replace("    'Pon el volumen al 20%.',", "    'Pon el volumen al 20%.',\n    'Why couldn\'t you read that file?',".replace("couldn't", "couldn\\'t"))
start = source.index("prereg = {'method':")
end = source.index("          'texts':", start)
source = source[:start] + "prereg = {'method': 'Current source81 and isolated Qwen3.5 override. First actual compose payload for six technical progress requests, with existing role/sampler and no added instruction, guards or retries. Source64 prepared comparison was never run and is not a baseline. No file/audio effects, human reserve, UI or acoustic claim. Judge whether wording infers target properties or claims a new read for a why question.',\n" + source[end:]
source = source.replace("'addedInstruction': extra,", "'model': config['gguf'], 'addedInstruction': None,")
source = source.replace("for variant in ('baseline', 'inference'):", "for variant in ('baseline',):")
(root / 'scratchpad/c03-progress-baseline82.py').write_text(source, encoding='utf-8')
