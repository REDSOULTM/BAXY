from pathlib import Path
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[1]
wire = root / 'artifacts/comprobaciones/C03/astra-files72-qwen35/wire-29372.jsonl'
for line in wire.read_text(encoding='utf-8').splitlines():
    row = json.loads(line)
    payload = row['payload']
    if payload.get('tool_choice') == 'auto':
        current = json.loads(payload['messages'][-1]['content'])['current_request_to_interpret']
        choice = row['response']['choices'][0]
        message = choice['message']
        print(json.dumps({'request': current, 'finish': choice['finish_reason'],
            'content': message.get('content', '')[:300], 'calls': message.get('tool_calls', [])}, ensure_ascii=False))
