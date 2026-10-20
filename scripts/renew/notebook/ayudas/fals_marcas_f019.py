import json, re, sys
R = 'D:/BAXYeval/renew_v1/runs/'
lib = re.compile(r'(?i)instalado localmente|añadir estanter|jugados recientemente|ordenar por')
login = re.compile(r'(?i)iniciar sesi|contraseña|sign in|password')
for label in sys.argv[1:]:
    c = {x['id']: x for x in json.load(open(R + label + '-falsedades/transcripts.json', encoding='utf-8'))}['F019']
    for n, tr in enumerate(c['turns']):
        for ev in tr['ordered']:
            if ev['kind'] == 'step' and ev['operation'] == 'input.visible.controls' and ev['status'] == 'completed':
                o = ev['observed'] or ''
                print(label, f't{n}', 'library marks:', len(set(m.lower() for m in lib.findall(o))), 'login:', bool(login.search(o)))
