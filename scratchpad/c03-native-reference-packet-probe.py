from pathlib import Path

path = Path(__file__).resolve().with_name('c03-observation-selection-probe.py')
source = path.read_text(encoding='utf-8')
source = source.replace("base / 'astra-observation-selection'", "base / 'astra-native-reference-packet'")
source = source.replace("client.stage = 'weak_identity'\n            weak = [name for name in names if client.operation_is_the_requested_effect(case['text'], name, contracts[name])]",
                        "weak = None")
source = source.replace("client.stage = 'native_contextual'", "client.stage = 'native_reference_packet'")
source = source.replace("'native_contextual': native", "'native_reference_packet': native")
source = source.replace("        response = super()._post(payload, *args, **kwargs)",
    """        if 'tools' in payload:
            payload = dict(payload)
            messages = payload['messages']
            payload['messages'] = [messages[0], {'role': 'user', 'content': json.dumps({
                'previous_dialogue_for_references_only': messages[1:-1],
                'current_request_to_interpret': messages[-1]['content'],
            }, ensure_ascii=False)}]
        response = super()._post(payload, *args, **kwargs)""")
source = source.replace("Eight consumed or synthetic controls; no fresh acceptance.",
                        "Eight identical consumed controls from observation-selection. Single change to native AUTO: prior dialogue is reference data in a JSON object alongside the literal current request, not replayed user/assistant turns. System prompt, functions, sampling, budget and history content unchanged. No weak-identity calls repeated. No fresh acceptance.")
exec(compile(source, str(Path(__file__)), 'exec'))
