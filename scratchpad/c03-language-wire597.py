"""Repeat596 with the exact production serialization at the observed boundary."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-language-repair596.py').read_text(encoding='utf-8')
source = source.replace("source.replace('594', '596').replace('guard-boundary596', 'language-repair596')", "source.replace('594', '597').replace('guard-boundary597', 'language-wire597')")
marker = "exec(compile(source, __file__, 'exec'))"
assert source.count(marker) == 1
source = source.replace(marker, '''needle = "            append(private / 'requests.jsonl'"
serialization = """            append(private / 'builder-requests.jsonl', {'case_id': case_id, 'arm': arm, 'payload': payload})
            prefix = []
            for message in payload['messages']:
                if message.get('role') != 'system':
                    break
                prefix.append(message['content'])
            if len(prefix) > 1:
                payload = {**payload, 'messages': [
                    {'role':'system', 'content':'\\\\n\\\\n'.join(prefix)},
                    *payload['messages'][len(prefix):]]}
"""
assert source.count(needle) == 1
source = source.replace(needle, serialization + needle)
source = source.replace('Two exact593 failed English retry payloads and four declared development controls.', '596 replayed builder inputs before the production system-prefix merge.597 repeats its same two captured593 retries and four controls, then applies the exact llm.py::_post system-prefix serialization before HTTP. Both builder and actual wire payloads are saved.596 is retained but is not an effective-product replay.')
exec(compile(source, __file__, 'exec'))''')
exec(compile(source, __file__, 'exec'))
