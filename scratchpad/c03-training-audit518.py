"""Read-only overlap check of the reserve against three inherited training/eval files."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib, json, os, re, unicodedata

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-training-audit518'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-training-audit518-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
reserve_path = private.parent / 'C03-reserve-language475-private/review.jsonl'
original_path = private.parent / 'C03-reserve-source477-private/review.jsonl'
sources = [root.parent/'FunctionGemma'/p for p in (
    'finetune_llm/curated/train_v3.jsonl',
    'router/data/router_eval_corpus.curated.jsonl',
    'router/data/router_corpus_curated_ft.jsonl',
)]
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def write(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def normalized(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', text)).strip().casefold()

write(out/'PREREG.json', {'utc':datetime.now(timezone.utc).isoformat(), 'inheritance':'Exact FunctionGemma source roots and fields from scripts/build_historical_corpus.py:45-50,1764-1769,2154-2186. Source477 verifies originals;475 contains the204 potential reserve entries. No new model inference.', 'method':'Read each source JSONL once, hash before/after, compare reserve literals against full strings in user_text,prev_text,final_reply,q; additionally normalized whitespace/NFC/casefold full strings and lines. Record exact/normalized distinction and every source line/field. Any match is a conservative exposure flag; absence is not full freshness certification. No change to reserve475 or acceptance freeze.', 'limits':'Only these three inherited training/eval corpora. Not paraphrase equivalence, all local classifiers, private C03 exposure after483, missing original sessions or context certification.', 'sources':[str(p) for p in sources], 'reserve_sha256':sha(reserve_path), 'original_verification_sha256':sha(original_path)})
reserve = list(map(json.loads, reserve_path.open(encoding='utf-8-sig')))
originals = {r['id']:r for r in map(json.loads, original_path.open(encoding='utf-8-sig'))}
exact = defaultdict(set); folded = defaultdict(set)
for row in reserve:
    exact[row['text_literal']].add(row['id'])
    folded[normalized(row['text_literal'])].add(row['id'])
hits = defaultdict(list); inventories = []
for source in sources:
    before = sha(source); count=0; malformed=0; fields=Counter()
    with source.open(encoding='utf-8-sig') as stream:
        for line_number, line in enumerate(stream,1):
            try: row=json.loads(line)
            except json.JSONDecodeError:
                malformed+=1; continue
            count+=1
            for field in ['user_text','prev_text','final_reply','q']:
                value=row.get(field)
                if not isinstance(value,str) or not value.strip(): continue
                fields[field]+=1
                matches={}
                for key in exact.get(value,set()): matches[key]='exact_full_field'
                for key in folded.get(normalized(value),set()): matches.setdefault(key,'normalized_full_field')
                for part in value.splitlines():
                    for key in exact.get(part,set()):matches.setdefault(key,'exact_line')
                    for key in folded.get(normalized(part),set()):matches.setdefault(key,'normalized_line')
                for key,kind in matches.items():
                    hits[key].append({'source':str(source),'line':line_number,'field':field,'match':kind,'source_sha256':before})
    after=sha(source)
    assert before==after
    inventories.append({'path':str(source),'bytes':source.stat().st_size,'sha256':before,'rows':count,'malformed':malformed,'fields':dict(fields),'stable':True})
review=[]
for row in reserve:
    review.append({'id':row['id'],'ordinal':row['ordinal'],'language':row['language_semantic'],'overlap':bool(hits[row['id']]),'matches':hits[row['id']],'complete_original':originals[row['id']]['complete_literal_verified_in_current_original'],'context_needed':row['original_context_needed'],'certified_fresh':False,'frozen':False,'replayed':False})
(private/'review.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in review),encoding='utf-8')
write(private/'sources.json',inventories)
summary={'utc':datetime.now(timezone.utc).isoformat(),'reviewed':len(review),'source_files':len(inventories),'source_rows':sum(r['rows'] for r in inventories),'malformed':sum(r['malformed'] for r in inventories),'all_sources_stable':True,'overlap_entries':sum(r['overlap'] for r in review),'unmatched_entries':sum(not r['overlap'] for r in review),'unmatched_complete_original':sum(not r['overlap'] and r['complete_original'] for r in review),'unmatched_languages':dict(Counter(r['language'] for r in review if not r['overlap'])),'matched_ordinals':[r['ordinal'] for r in review if r['overlap']],'certified_fresh':0,'frozen':False,'replayed':0,'private':str(private),'review_sha256':sha(private/'review.jsonl'),'sources_sha256':sha(private/'sources.json'),'limitations':'Only exact/normalized strings and lines in four fields of three known inherited corpora. No complete freshness certificate; remaining exposure/context checks and missing sources unchanged.'}
write(out/'RESULT.json',summary)
(out/'RESULT.md').write_text(f'''# Cruce con entrenamiento y evaluación heredados

Se revisaron {summary['source_rows']} filas de tres fuentes originales de FunctionGemma, con huellas estables y {summary['malformed']} líneas ilegibles. De los204 candidatos potenciales, {summary['overlap_entries']} coinciden literalmente o tras normalizar espacio, mayúsculas y Unicode con contenido de esos conjuntos; deben mantenerse fuera de una selección fresca mientras se resuelve su exposición.

Quedan {summary['unmatched_entries']} sin coincidencia en este cruce, {summary['unmatched_complete_original']} de ellos con literal completo acreditado en la fuente original. Esto no certifica frescura: faltan el contexto, otras fuentes de entrenamiento/evaluación y la exposición C03 posterior a483. No se ejecutó BAXY, no se congeló una reserva y no se modificaron los candidatos originales.

El detalle de coincidencias y líneas queda privado; el informe público sólo contiene recuentos, ordinales y huellas.
''',encoding='utf-8')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
print(json.dumps({k:v for k,v in summary.items() if k not in ('matched_ordinals','private','limitations')},ensure_ascii=False))
