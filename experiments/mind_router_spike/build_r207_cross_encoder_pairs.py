"""Build deterministic positive/negative BAXY operation pairs for R207."""
from __future__ import annotations
import hashlib,json,random,unicodedata
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]; SOURCE=REPO/'artifacts/development/r196_full_provenance_classifier_training.jsonl'; CAT=REPO/'artifacts/development/catalog_vocabulary_snapshot.json'; R186=REPO/'artifacts/development/bge_qwen_embedding_cascade_r186_preregistration.json'; OUT=REPO/'artifacts/development/r207_cross_encoder_pairs.jsonl'; AUDIT=REPO/'artifacts/audit/r207_cross_encoder_pairs_admission.json'; NO='__no_action__'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text(encoding='utf8').splitlines() if x]
def key(text):
 value=unicodedata.normalize('NFKD',text.casefold());return ' '.join(''.join(c for c in value if not unicodedata.combining(c)).split())
def build(out,audit):
 source=rows(SOURCE);forbidden={key(x['text']) for x in json.loads(R186.read_text(encoding='utf8'))['rows']};catalog={x['name']:x['description'] for x in json.loads(CAT.read_text(encoding='utf8'))['capabilities']};docs=catalog|{NO:'No BAXY catalog operation applies; abstain without proposing an operation.'};labels=sorted(docs);result=[]
 for row in source:
  if key(row['text']) in forbidden:raise ValueError('r207_evaluation_overlap')
  rng=random.Random(f"r207:{row['case_id']}");label=row['label'];choices=[x for x in labels if x!=label];same=[x for x in choices if x.split('.',1)[0]==label.split('.',1)[0]];neg=([rng.choice(same)] if same else [])
  while len(neg)<4:
   x=rng.choice(choices)
   if x not in neg:neg.append(x)
  for operation,target in [(label,1),*((x,0) for x in neg)]:result.append({'schema':'baxy.r207-cross-encoder-pair.v1','pair_id':f"{row['case_id']}:{operation}",'query':row['text'],'operation':operation,'operation_document':f"Operation {operation}: {docs[operation]}",'target':target,'source':row['source'],'human_semantic_audit':False,'execution_authority':False})
 if len(result)!=23700 or sum(x['target'] for x in result)!=4740:raise ValueError('r207_pair_contract_failed')
 out.write_bytes(('\n'.join(json.dumps(x,ensure_ascii=False,sort_keys=True) for x in result)+'\n').encode());report={'schema':'baxy.r207-cross-encoder-pairs-admission.v1','authority':'development_only_deterministic_positive_negative_pairs','identities':{'program_sha256':sha(Path(__file__)),'source_sha256':sha(SOURCE),'catalog_sha256':sha(CAT),'r186_sha256':sha(R186),'pairs_sha256':sha(out)},'counts':{'pairs':len(result),'positive_pairs':sum(x['target'] for x in result),'negative_pairs':sum(not x['target'] for x in result),'labels':len(labels),'evaluation_overlap_claimed':0},'constraints':{'r186_evaluation_only':True,'human_audited_training':False,'runtime_modified':False,'opened_v9':False}};audit.write_bytes((json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode());return report
def main():print(json.dumps(build(OUT,AUDIT)['counts'],sort_keys=True))
if __name__=='__main__':main()
