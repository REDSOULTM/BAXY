"""Read the actual UI message collection from the preserved owner heap via SOS."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-transcript281'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-owner264-heap280'
tool = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-diagnostics-tools/dotnet-dump.exe'
dump = private / 'owner264.dmp'
source = (private / 'messages-array.log').read_text(encoding='utf-8-sig')
list_info = (private / 'messages-list.log').read_text(encoding='utf-8-sig')
count = int(re.search(r'instance\s+(\d+)\s+_size\s*$', list_info, re.MULTILINE)[1])
assert count == 121
parts = re.split(r'^\[(\d+)\] ([0-9a-fA-F]+)\s*\n', source, flags=re.MULTILINE)
messages = []
for position in range(1, len(parts), 3):
    index, address, body = parts[position:position + 3]
    if int(index) >= count:
        continue
    assert 'Name:        Baxy.App.ConversationMessage' in body
    fields = {}
    for field in ('Speaker', 'Body', 'IsUser', 'CreatedAt', 'Route'):
        match = re.search(r'instance\s+([0-9a-fA-F]+)\s+<' + field + r'>k__BackingField', body)
        assert match, (index, field)
        fields[field] = match[1]
    messages.append({'index': int(index), 'objectAddress': address, 'fields': fields})
assert [message['index'] for message in messages] == list(range(count))
addresses = list(dict.fromkeys(message['fields'][field] for message in messages
    for field in ('Speaker', 'Body', 'Route') if int(message['fields'][field], 16)))
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Follow actual MainWindowViewModel.Messages -> ObservableCollection.items -> List._items and _size from SOS. Decode only the first _size live collection entries in order. Use official SOS dumpobj for string fields, verifying UTF16 length. No whole-heap string search or guessed ordering.',
    'viewModelAddress': '0270721aa180', 'messagesAddress': '00000270721aa3e8',
    'listAddress': '00000270721aa420', 'arrayAddress': '0000027075b1daa0',
    'count': count, 'privateDirectory': str(private), 'uniqueStringObjects': len(addresses),
    'limits': 'Collection backing the UI, not a new pixel capture. Timestamp addresses preserved; no inferred timestamps. Development owner session, not fresh acceptance.'}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
values = {}
logs = []
for batch_index, start in enumerate(range(0, len(addresses), 40), 1):
    selected = addresses[start:start + 40]
    command = [str(tool), 'analyze', str(dump)]
    for address in selected:
        assert re.fullmatch('[0-9a-fA-F]+', address)
        command.extend(['-c', 'dumpobj ' + address])
    command.extend(['-c', 'exit'])
    log_path = private / f'strings281-{batch_index}.log'
    assert not log_path.exists()
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW)
    log_path.write_bytes(result.stdout)
    logs.append(log_path)
    assert result.returncode == 0
    output = result.stdout.decode('utf-8-sig').replace('\r\n', '\n')
    blocks = re.split(r'^Name:        System.String\s*\n', output, flags=re.MULTILINE)[1:]
    assert len(blocks) == len(selected), (len(blocks), len(selected))
    for address, block in zip(selected, blocks, strict=True):
        header, fields = block.rsplit('\nFields:\n', 1)
        value = header.split('\nString:      ', 1)[1]
        length = int(re.search(r'instance\s+(\d+)\s+_stringLength\s*$', fields, re.MULTILINE)[1])
        assert len(value.encode('utf-16-le')) // 2 == length, (address, length, len(value))
        values[address] = value
transcript = []
for message in messages:
    fields = message['fields']
    body = values[fields['Body']]
    transcript.append({'index': message['index'], 'objectAddress': message['objectAddress'],
        'speaker': values[fields['Speaker']], 'body': body, 'isUser': fields['IsUser'] == '1',
        'route': values.get(fields['Route']), 'createdAtAddress': fields['CreatedAt'],
        'bodySha256': hashlib.sha256(body.encode('utf-8')).hexdigest()})
json_path = private / 'TRANSCRIPT281.json'
assert not json_path.exists()
json_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
markdown = ['# Sesión manual264 — colección de mensajes recuperada', '',
    'Orden y textos de MainWindowViewModel.Messages conservados en la copia de memoria280. No se inventan mensajes de error donde no existe respuesta. La colección es el estado de la UI; esta extracción no es una captura de pantalla.', '']
for message in transcript:
    markdown.extend([f"## {message['index']:03d} · {'Usuario' if message['isUser'] else 'BAXY'}", '', message['body'], ''])
md_path = private / 'TRANSCRIPT281.md'
md_path.write_text('\n'.join(markdown) + '\n', encoding='utf-8')
report = {'utc': datetime.now(timezone.utc).isoformat(), 'count': len(transcript),
    'userMessages': sum(message['isUser'] for message in transcript),
    'baxyMessages': sum(not message['isUser'] for message in transcript),
    'allUtf16LengthsVerified': True, 'collectionOrderVerified': True, 'arrayCapacity': 128,
    'privateJson': str(json_path), 'privateMarkdown': str(md_path),
    'jsonSha256': hashlib.sha256(json_path.read_bytes()).hexdigest(),
    'markdownSha256': hashlib.sha256(md_path.read_bytes()).hexdigest(),
    'sourceLogs': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in logs},
    'freshAcceptance': False, 'renderedUiVerified': False}
(out / 'RESULT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False), flush=True)
