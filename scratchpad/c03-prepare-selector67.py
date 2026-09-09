from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-selector-history65.py').read_text(encoding='utf-8')
target = root / 'scratchpad/c03-selector-catalog67.py'
assert not target.exists()
source = source.replace('astra-selector-history65', 'astra-selector-catalog67')
source = source.replace("('captured', 'no_context', 'scoped_history')", "('captured', 'file_description')")
start = source.index("            if variant == 'no_context':")
end = source.index('            client.begin_request(40)', start)
source = source[:start] + '''            if variant == 'file_description':
                tool = next(item['function'] for item in payload['tools']
                    if item['function']['name'] == 'baxy_filesystem__read__text')
                tool['description'] = 'Lee el contenido UTF-8 de un archivo del sandbox usando su identidad revalidada y devuelve su hash.'
''' + source[end:]
start = source.index("prereg = {'method':")
end = source.index("(out / 'PREREG.json')", start)
source = source[:start] + '''prereg = {'method': 'Four exact source63 selector packets captured in files64-wire. '
          'After65/66 history prompts/roles failed to retain all correct selections, change hypothesis to the catalog description: '
          'read.text names only UTF8 and identity, omitting its file target and sandbox scope. '
          'Compare original with only that declared function description clarified; all dialogue, request, other tools, '
          'system prompt and inference parameters remain byte-equivalent. No guards, retries or actual functions run. '
          'Not human acceptance, UI/audio or model without BAXY.',
          'wireSha256': hashlib.sha256(wire_path.read_bytes()).hexdigest(),
          'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
''' + source[end:]
target.write_text(source, encoding='utf-8')
print('prepared67')
