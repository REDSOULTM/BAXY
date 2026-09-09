"""Explicit diagnostic profile and bounded fact transport; never an acceptance hook."""
import copy
import itertools
import json
import os
from pathlib import Path
import threading
import time
from baxy_mind.llm import LlmRuntime

private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-private-product464-private'
private.mkdir(parents=True, exist_ok=True)
lock = threading.Lock()
sequence = itertools.count()
context = threading.local()
original_post = LlmRuntime._post
original_compose = LlmRuntime.compose_user_message
original_command = LlmRuntime._server_command

def log(path, value):
    with lock, (private / path).open('a', encoding='utf-8') as handle:
        handle.write(json.dumps({'time': time.monotonic(), 'pid': os.getpid(), **value}, ensure_ascii=False) + '\n')

def compose(self, user_text, intent, facts, *args, **kwargs):
    before = getattr(context, 'memory', False)
    try:
        raw = facts.get('situation')
        situation = json.loads(raw) if isinstance(raw, str) else raw
        context.memory = bool(intent == 'status' and isinstance(situation, dict) and situation.get('verified') is True and situation.get('succeeded') is True and str(situation.get('operation', '')).startswith('memory.'))
        if context.memory:
            changed = copy.deepcopy(facts)
            records = situation.get('observed', {}).get('records', [])
            if situation.get('operation') in {'memory.recall', 'memory.list'} and isinstance(records, list) and all(isinstance(r, dict) and isinstance(r.get('value'), str) for r in records):
                public = [r['value'] for r in records if r['value'] != '[REDACTED]']
                if len(public) == 1 and 0 < len(public[0]) <= 256:
                    changed['requiredFacts'] = list(dict.fromkeys([*changed.get('requiredFacts', []), public[0]]))
            log('compose-overrides.jsonl', {'operation': situation.get('operation'), 'intent': intent, 'profile': 'gemma-memory-thinking460', 'facts_changed': changed != facts, 'facts': changed})
            facts = changed
        return original_compose(self, user_text, intent, facts, *args, **kwargs)
    finally:
        context.memory = before

def observe(self, payload, *args, **kwargs):
    number = next(sequence)
    active = getattr(context, 'memory', False)
    payload = copy.deepcopy(payload)
    if not active:
        payload['reasoning_budget_tokens'] = 0
    if active:
        payload.update(temperature=1., top_p=.95, top_k=64, min_p=0., presence_penalty=0., repeat_penalty=1., seed=0, max_tokens=3072, reasoning_budget_tokens=-1)
        payload['chat_template_kwargs'] = {**payload.get('chat_template_kwargs', {}), 'enable_thinking': True}
    log('http-posts.jsonl', {'id': number, 'stage': 'request', 'profile_override': active, 'payload': payload})
    try:
        response = original_post(self, payload, *args, **kwargs)
    except Exception as error:
        log('http-posts.jsonl', {'id': number, 'stage': 'failure', 'errorType': type(error).__name__, 'detail': str(error)})
        raise
    log('http-posts.jsonl', {'id': number, 'stage': 'response', 'response': response})
    return response

def command(self):
    result = [*original_command(self), '--lazy-mode', 'on', '--verbosity', '4', '--log-file', str(private / 'server.log')]
    result[result.index('--reasoning') + 1] = 'on'
    result[result.index('--reasoning-budget') + 1] = '-1'
    result += ['--reasoning-format', 'deepseek']
    (private / 'effective-server-command.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result

LlmRuntime.compose_user_message = compose
LlmRuntime._post = observe
LlmRuntime._server_command = command
