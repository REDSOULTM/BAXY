"""Private observation inherited from521; production calls and values unchanged."""
import itertools
import json
import os
from pathlib import Path
import threading
import time

from baxy_mind.llm import LlmRuntime

private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-status-batch704-private'
lock = threading.Lock()
sequence = itertools.count()
original_post = LlmRuntime._post
original_decide = LlmRuntime.decide_turn


def log(filename, value):
    with lock, (private / filename).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'time': time.monotonic(), 'pid': os.getpid(), **value}, ensure_ascii=False) + '\n')


def observe_post(self, payload, *args, **kwargs):
    number = next(sequence)
    log('http-posts.jsonl', {'id': number, 'stage': 'request', 'payload': payload})
    try:
        response = original_post(self, payload, *args, **kwargs)
    except Exception as error:
        log('http-posts.jsonl', {'id': number, 'stage': 'failure', 'errorType': type(error).__name__, 'detail': str(error)})
        raise
    log('http-posts.jsonl', {'id': number, 'stage': 'response', 'response': response})
    return response


def observe_decide(self, text, candidates, *, history=None, evidence=None):
    number = next(sequence)
    log('decision-boundary.jsonl', {'id': number, 'stage': 'input', 'text': text, 'candidates': candidates, 'history': history, 'evidence': evidence})
    try:
        result = original_decide(self, text, candidates, history=history, evidence=evidence)
    except Exception as error:
        log('decision-boundary.jsonl', {'id': number, 'stage': 'failure', 'errorType': type(error).__name__, 'detail': str(error)})
        raise
    log('decision-boundary.jsonl', {'id': number, 'stage': 'output', 'result': result})
    return result


LlmRuntime._post = observe_post
LlmRuntime.decide_turn = observe_decide
