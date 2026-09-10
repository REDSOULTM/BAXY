"""Observe registered compose input and HTTP boundaries without changing values."""
import itertools
import json
import os
from pathlib import Path
import threading
import time
import traceback

from baxy_mind.llm import LlmRuntime

private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-compose762-private'
lock = threading.Lock()
sequence = itertools.count()
original_post = LlmRuntime._post
original_compose = LlmRuntime.compose_user_message


def log(filename, value):
    with lock, (private / filename).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'time': time.monotonic(), 'pid': os.getpid(), **value},
                                ensure_ascii=False) + '\n')


def observe_post(self, payload, *args, **kwargs):
    number = next(sequence)
    log('http-posts.jsonl', {'id': number, 'stage': 'request', 'payload': payload,
                           'args': args, 'kwargs': kwargs})
    try:
        response = original_post(self, payload, *args, **kwargs)
    except Exception as error:
        log('http-posts.jsonl', {'id': number, 'stage': 'failure', 'errorType': type(error).__name__,
                               'detail': str(error), 'traceback': traceback.format_exc()})
        raise
    log('http-posts.jsonl', {'id': number, 'stage': 'response', 'response': response})
    return response


def observe_compose(self, user_text, intent, facts, *args, **kwargs):
    number = next(sequence)
    log('compose-boundary.jsonl', {'id': number, 'stage': 'input', 'user_text': user_text,
                                 'intent': intent, 'facts': facts, 'args': args, 'kwargs': kwargs})
    try:
        result = original_compose(self, user_text, intent, facts, *args, **kwargs)
    except Exception as error:
        log('compose-boundary.jsonl', {'id': number, 'stage': 'failure', 'errorType': type(error).__name__,
                                     'detail': str(error), 'traceback': traceback.format_exc()})
        raise
    log('compose-boundary.jsonl', {'id': number, 'stage': 'output', 'result': result})
    return result


LlmRuntime._post = observe_post
LlmRuntime.compose_user_message = observe_compose
