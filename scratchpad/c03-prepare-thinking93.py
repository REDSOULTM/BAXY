from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-progress-activity87.py').read_text(encoding='utf-8')
source = source.replace("'astra-progress-activity87'", "'astra-progress-thinking93'")
source = source.replace('client = LlmRuntime();', '''class ThinkingRuntime(LlmRuntime):
    def _server_command(self):
        command = super()._server_command()
        command[command.index('--reasoning') + 1] = 'on'
        command[command.index('--reasoning-budget') + 1] = '-1'
        command += ['--reasoning-format', 'deepseek']
        (out / 'SERVER_COMMAND.json').write_text(json.dumps(command, indent=2), encoding='utf-8')
        return command

client = ThinkingRuntime();''')
source = source.replace("for variant in ('request_interpretation',):", "for variant in ('thinking',):")
source = source.replace("if variant == 'request_interpretation':", "if variant == 'thinking':")
source = source.replace('            client.begin_request(40)', '''            payload['chat_template_kwargs']['enable_thinking'] = True
            payload['max_tokens'] = 2048
            payload['reasoning_format'] = 'deepseek'
            client.begin_request(90)''')
source = source.replace("print(json.dumps({'turn': case['turn'], 'variant': variant, 'choice': response['choices'][0]}, ensure_ascii=False), flush=True)",
    "print(json.dumps({'turn': case['turn'], 'variant': variant, 'finishReason': response['choices'][0]['finish_reason'], 'content': response['choices'][0]['message'].get('content'), 'reasoningCharacters': len(response['choices'][0]['message'].get('reasoning_content', '')), 'usage': response.get('usage'), 'timings': response.get('timings')}, ensure_ascii=False), flush=True)")
start = source.index("prereg = {'method':")
end = source.index("    'sourceSha256':", start)
source = source[:start] + '''prereg = {'method': 'Native capacity/profile contrast after85/87 data and88/90 instruction/framing failures. '
    'Same six87 factual-activity packets, original progress instruction, same Qwen3.5 GGUF and greedy sampler. '
    'Only thinking profile enabled: server reasoning on, budget-1, deepseek separation; request enable_thinking '
    'true, max_tokens2048 to separate reasoning from premature truncation. Official Qwen3.5 supports thinking '
    'by default; b9980 documents these flags. This does not adopt general sampling recommendations or promote '
    'a runtime. Preserve full raw response privately, adjudicate final content and latency/resource cost. '
    'No source, functions/UI/audio/reserve change. A length-finished answer is not accepted.',
''' + source[end:]
target = root / 'scratchpad/c03-progress-thinking93.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
