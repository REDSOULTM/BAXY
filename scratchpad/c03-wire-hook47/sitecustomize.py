"""Opt-in diagnostic: observe exact product HTTP payload/response without changing them."""
import json
import os
from pathlib import Path
import time

if destination := os.environ.get('C03_WIRE_TRACE_DIR'):
    from baxy_mind.llm import LlmRuntime

    _c03_original_post = LlmRuntime._post

    def _c03_traced_post(self, payload, *args, **kwargs):
        started = time.monotonic()
        result = _c03_original_post(self, payload, *args, **kwargs)
        with (Path(destination) / f'wire-{os.getpid()}.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'payload': payload, 'response': result,
                                    'seconds': time.monotonic() - started}, ensure_ascii=False) + '\n')
        return result

    LlmRuntime._post = _c03_traced_post
