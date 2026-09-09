"""Local-only owner questionnaire; persists judgments separately from source data."""
from pathlib import Path
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import argparse
import json
import os
import secrets
import threading

parser = argparse.ArgumentParser()
parser.add_argument('--directory', type=Path, required=True)
args = parser.parse_args()
directory = args.directory.resolve()
dataset = json.loads((directory/'data.json').read_text(encoding='utf-8'))
ids = {row['id'] for row in dataset['records']}
token = secrets.token_urlsafe(32)
lock = threading.Lock()
review_path = directory/'answers.json'

def now():
    return datetime.now(timezone.utc).isoformat()

def save_json(path, value):
    temporary = path.with_suffix(path.suffix+'.writing')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)

if not review_path.exists():
    save_json(review_path, {'schema':'baxy.owner-questionnaire.v1',
        'datasetId':dataset['datasetId'],'updatedAt':now(),'revision':0,'answers':{}})
review = json.loads(review_path.read_text(encoding='utf-8'))
if review['datasetId'] != dataset['datasetId']:
    raise RuntimeError('Existing answers belong to a different dataset')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def allowed_host(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def reply(self, code, value, content_type='application/json; charset=utf-8'):
        body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed_host():
            self.reply(403,{'error':'Host not allowed'})
            return
        path = urlsplit(self.path).path
        if path in ('/','/index.html'):
            self.reply(200,(directory/'index.html').read_bytes(),'text/html; charset=utf-8')
        elif path == '/data.json':
            self.reply(200,{**dataset,'reviewToken':token})
        elif path == '/review':
            with lock:
                self.reply(200,review)
        elif path == '/messages.txt':
            self.reply(200,(directory/'messages.txt').read_bytes(),'text/plain; charset=utf-8')
        else:
            self.reply(404,{'error':'Not found'})

    def do_POST(self):
        expected_origin = f'http://127.0.0.1:{self.server.server_port}'
        if (not self.allowed_host()
            or self.headers.get('Origin',expected_origin) != expected_origin
            or not secrets.compare_digest(self.headers.get('X-Review-Token',''),token)):
            self.reply(403,{'error':'Request not allowed'})
            return
        if urlsplit(self.path).path != '/review':
            self.reply(404,{'error':'Not found'})
            return
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 32768:
                raise ValueError('Invalid size')
            payload = json.loads(self.rfile.read(length))
            if payload.get('datasetId') != dataset['datasetId'] or payload.get('id') not in ids:
                raise ValueError('Unknown message')
            patch = payload.get('patch')
            if not isinstance(patch,dict) or not patch or not set(patch) <= {'authorship','capability','note'}:
                raise ValueError('Invalid judgment')
            for key,value in patch.items():
                if key=='note':
                    if not isinstance(value,str) or len(value)>2000:
                        raise ValueError('Invalid note')
                elif value is not None and type(value) is not bool:
                    raise ValueError('Invalid choice')
        except (ValueError,TypeError,AttributeError):
            self.reply(400,{'error':'Invalid review data'})
            return
        with lock:
            entry = {**review['answers'].get(payload['id'],
                {'authorship':None,'capability':None,'note':''}), **patch, 'updatedAt':now()}
            review['answers'][payload['id']] = entry
            review['revision'] += 1
            review['updatedAt'] = now()
            save_json(review_path,review)
            self.reply(200,{'saved':True,'revision':review['revision']})

server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
save_json(directory/'SERVER.json',{'pid':os.getpid(),'startedAt':now(),
    'url':f'http://127.0.0.1:{server.server_port}/','directory':str(directory),
    'userOwned':not dataset.get('qa',False),'automaticClose':False})
server.serve_forever(poll_interval=.5)
