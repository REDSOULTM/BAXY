# Diagnostic only: published Qwen2507 sampling on native tool selection.
from copy import deepcopy as _copy490
_before490 = LlmRuntime._post
_private490 = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-native-profile490-private'

def _profile490(self, payload, *args, **kwargs):
    if payload.get('tools'):
        payload = _copy490(payload)
        profile = json.loads((_private490 / 'current-profile.json').read_text(encoding='utf-8'))
        payload.update(temperature=0.7, top_p=0.8, top_k=20, min_p=0.0,
                       presence_penalty=0.0, repeat_penalty=1.0,
                       seed=profile['seed'], max_tokens=1024)
    return _before490(self, payload, *args, **kwargs)

LlmRuntime._post = _profile490
