"""Observe the existing pooled HTTP error body without consuming it."""
import io
import json
import os
from pathlib import Path
import time
import urllib.error

if destination := os.environ.get('C03_WIRE_TRACE_DIR'):
    from baxy_mind.llm import LlmRuntime

    _c03_original_post = LlmRuntime._post

    def _c03_traced_post(self, payload, *args, **kwargs):
        started = time.monotonic()
        row = {'payload': payload}
        try:
            result = _c03_original_post(self, payload, *args, **kwargs)
            row['response'] = result
            return result
        except urllib.error.HTTPError as error:
            row['httpError'] = {'code': error.code, 'reason': str(error.reason),
                'body': error.fp.getvalue().decode('utf-8', errors='replace')
                if isinstance(error.fp, io.BytesIO) else None}
            raise
        finally:
            row['seconds'] = time.monotonic() - started
            with (Path(destination) / f'wire-{os.getpid()}.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')

    LlmRuntime._post = _c03_traced_post
