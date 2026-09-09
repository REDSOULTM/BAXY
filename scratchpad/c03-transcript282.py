"""Recover exact UTF16 from the owner heap; SOS text rendering dropped accents."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
import re
import struct
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-transcript282'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-owner264-heap280'
tool = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-diagnostics-tools/dotnet-dump.exe'
dump = private / 'owner264.dmp'
source = (private / 'messages-array.log').read_text(encoding='utf-8-sig')
info = (private / 'messages-list.log').read_text(encoding='utf-8-sig')
count = int(re.search(r'instance\s+(\d+)\s+_size\s*$', info, re.MULTILINE)[1])
assert count == 121
parts = re.split(r'^\[(\d+)\] ([0-9a-fA-F]+)\s*\n', source, flags=re.MULTILINE)
messages = []
for position in range(1, len(parts), 3):
    index, address, body = parts[position:position + 3]
    if int(index) >= count:
        continue
    assert 'Name:        Baxy.App.ConversationMessage' in body
    fields = {name: re.search(r'instance\s+([0-9a-fA-F]+)\s+<' + name + r'>k__BackingField', body)[1]
        for name in ('Speaker', 'Body', 'IsUser', 'CreatedAt', 'Route')}
    assert fields['IsUser'] in ('0', '1')
    messages.append({'index': int(index), 'objectAddress': address, 'fields': fields})
assert [message['index'] for message in messages] == list(range(count))
addresses = list(dict.fromkeys(message['fields'][field] for message in messages
    for field in ('Speaker', 'Body', 'Route') if int(message['fields'][field], 16)))
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Same verified MainWindowViewModel.Messages chain as281. Official SOS dumpobj supplies stringLength, readmemory supplies raw bytes at the SOS-confirmed firstChar offset0xC; decode strict UTF16LE, check length. CreatedAt layout from SOS: offsetMinutes at0 and DateTime._dateData at8. Read only121 active collection entries.',
    'priorFailure': '281 stopped before exporting because SOS dumpobj rendered welcome length42 while managed stringLength46. It dropped non-ASCII characters. No lossy transcript accepted.',
    'count': count, 'privateDirectory': str(private), 'pixelCapture': False, 'freshAcceptance': False}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
logs = []
def run(commands, name):
    path = private / name
    assert not path.exists()
    args = [str(tool), 'analyze', str(dump)]
    for command in commands:
        args.extend(['-c', command])
    args.extend(['-c', 'exit'])
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW)
    path.write_bytes(result.stdout)
    logs.append(path)
    assert result.returncode == 0
    return result.stdout.decode('utf-8-sig').replace('\r\n', '\n')
lengths = {}
for batch, start in enumerate(range(0, len(addresses), 40), 1):
    selected = addresses[start:start + 40]
    output = run(['dumpobj ' + address for address in selected], f'lengths282-{batch}.log')
    blocks = re.split(r'^Name:        System.String\s*\n', output, flags=re.MULTILINE)[1:]
    assert len(blocks) == len(selected)
    for address, block in zip(selected, blocks, strict=True):
        fields = block.rsplit('\nFields:\n', 1)[1]
        length = int(re.search(r'instance\s+(\d+)\s+_stringLength\s*$', fields, re.MULTILINE)[1])
        assert 0 <= length <= 32768
        lengths[address] = length
requests = [(int(address, 16) + 12, length * 2) for address, length in lengths.items() if length]
requests.extend((int(message['fields']['CreatedAt'], 16), 16) for message in messages)
memory = {}
for batch, start in enumerate(range(0, len(requests), 40), 1):
    selected = requests[start:start + 40]
    output = run([f'readmemory {address:016x} -c {size} -l 1' for address, size in selected], f'memory282-{batch}.log')
    for line in output.splitlines():
        match = re.fullmatch(r'([0-9a-fA-F]{16}):((?:\s+[0-9a-fA-F]{2})+)\s*', line)
        if not match:
            continue
        address = int(match[1], 16)
        data = bytes.fromhex(match[2])
        for offset, value in enumerate(data):
            assert memory.get(address + offset, value) == value
            memory[address + offset] = value
def read(address, size):
    return bytes(memory[address + offset] for offset in range(size))
values = {}
for address, length in lengths.items():
    raw = read(int(address, 16) + 12, length * 2)
    value = raw.decode('utf-16-le')
    assert len(value.encode('utf-16-le')) == length * 2
    values[address] = value
transcript = []
for message in messages:
    fields = message['fields']
    raw_date = read(int(fields['CreatedAt'], 16), 16)
    offset_minutes = struct.unpack_from('<i', raw_date, 0)[0]
    ticks = struct.unpack_from('<Q', raw_date, 8)[0] & ((1 << 62) - 1)
    assert -840 <= offset_minutes <= 840
    utc = datetime(1, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=ticks // 10)
    created = utc.astimezone(timezone(timedelta(minutes=offset_minutes)))
    assert created.date().isoformat() == '2026-09-07'
    body = values[fields['Body']]
    transcript.append({'index': message['index'], 'objectAddress': message['objectAddress'],
        'speaker': values[fields['Speaker']], 'body': body, 'isUser': fields['IsUser'] == '1',
        'route': values.get(fields['Route']), 'createdAt': created.isoformat(), 'createdAtUtcTicks': ticks,
        'bodySha256': hashlib.sha256(body.encode('utf-8')).hexdigest()})
assert transcript[0]['body'].startswith('¡Hola! Aquí BAXY.')
assert transcript[1]['body'] == 'Hola hablame de paris, donde podria ir?'
assert all(left['createdAtUtcTicks'] <= right['createdAtUtcTicks'] for left, right in zip(transcript, transcript[1:]))
json_path = private / 'TRANSCRIPT282.json'
assert not json_path.exists()
json_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
markdown = ['# Sesión manual264 — mensajes recuperados de la colección de UI', '',
    'Textos UTF16 y orden de MainWindowViewModel.Messages conservados en la copia280. Las horas proceden de CreatedAt. No se inventan respuestas ausentes. Esta extracción recupera el estado de la UI; no es una nueva captura de pantalla.', '']
for message in transcript:
    markdown.extend([f"## {message['index']:03d} · {'Usuario' if message['isUser'] else 'BAXY'} · {message['createdAt']}", '', message['body'], ''])
md_path = private / 'TRANSCRIPT282.md'
md_path.write_text('\n'.join(markdown) + '\n', encoding='utf-8')
report = {'utc': datetime.now(timezone.utc).isoformat(), 'count': len(transcript),
    'userMessages': sum(message['isUser'] for message in transcript),
    'baxyMessages': sum(not message['isUser'] for message in transcript),
    'allUtf16LengthsVerified': True, 'collectionOrderVerified': True, 'timestampsMonotonic': True,
    'arrayCapacity': 128, 'privateJson': str(json_path), 'privateMarkdown': str(md_path),
    'firstTimestamp': transcript[0]['createdAt'], 'lastTimestamp': transcript[-1]['createdAt'],
    'jsonSha256': hashlib.sha256(json_path.read_bytes()).hexdigest(),
    'markdownSha256': hashlib.sha256(md_path.read_bytes()).hexdigest(),
    'sourceLogs': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in logs},
    'freshAcceptance': False, 'renderedUiVerified': False}
(out / 'RESULT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key:value for key,value in report.items() if key != 'sourceLogs'}, ensure_ascii=False), flush=True)
