"""Compare local backend token IDs with the pinned official Rust tokenizer."""
from pathlib import Path
import hashlib
import json
import random
import urllib.request
import tokenizers


def verify(base_url, size, out):
    assert base_url.startswith('http://127.0.0.1:')
    path = Path('D:/BAXYRuntime/experiments/models/k2-horizon-20260909') / f'K2-Horizon-{size}-tokenizer.json'
    reference = tokenizers.Tokenizer.from_file(str(path))
    cases = ['', 'Hola, ¿qué tal?', 'Read the current CPU usage.', 'Baxy, dime la RAM free.',
        'cafe\u0301', '\u0301a', '!\u0301a', 'क्\u200dष', 'क्\u200cष', 'می\u200cروم',
        '1234', '١٢٣٤', '!\r\n', '\u00a0a', 'a\u200bb', '✈️', '👩\u200d💻',
        "It's WE'RE they'd I'll", "'s 'T 're 'VE 'M 'LL 'D", '1234567890123',
        '  \n \r\n \t ', 'a\u200db', '\u200ca', '\u200d', '\u0301',
        '!!\u0301a', '#\u200d#', 'a\u200d\u200cb', 'foo\u200bbar',
        '¿Cuánta memoria está utilizada?', 'GPU 4.25 GiB, RAM 16 GiB',
        '<|ifm|im_start|>assistant\n<ifm|think>\n', '</ifm|think>',
        'a\x00b', '😀😃👩\u200d👩\u200d👧\u200d👦']
    alphabet = ['a', 'Z', 'á', '中', 'क', 'م', '\u0301', '\u093e', '\ufe0f', '\u200c',
        '\u200d', '\u200b', '0', '9', '٢', '³', '!', "'", ' ', '\n', '\r', '\t', '\u00a0', '👩', '💻']
    rng = random.Random(696)
    cases += [''.join(rng.choice(alphabet) for _ in range(rng.randint(1, 80))) for _ in range(250)]
    records = []
    for text in cases:
        expected = reference.encode(text, add_special_tokens=False).ids
        request = urllib.request.Request(base_url + '/tokenize',
            data=json.dumps({'content': text, 'add_special': False, 'parse_special': True}).encode(),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.load(response)
        actual = result['tokens']
        records.append({'text': text, 'expected': expected, 'actual': actual, 'equal': expected == actual})
    out.mkdir(parents=True, exist_ok=True)
    (out / 'TOKENIZER_PARITY_DETAILS.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    summary = {'model_size': size, 'tokenizers_version': tokenizers.__version__,
        'reference_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'cases': len(cases),
        'equal': sum(r['equal'] for r in records), 'mismatches': sum(not r['equal'] for r in records),
        'method': 'Exact token IDs without automatic BOS/EOS; special-token recognition enabled on both. Unicode adversarial fixtures and fixed-seed mixed strings. No generation.'}
    (out / 'TOKENIZER_PARITY.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    assert summary['mismatches'] == 0, summary
    return summary
