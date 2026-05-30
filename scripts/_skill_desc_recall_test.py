# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from sentence_transformers import SentenceTransformer, util

m = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

CANDS = {}

# C12 (mejor realista) baseline
CANDS["C12"] = (
    "Investiga sobre eso en internet y resumeme. Averigua que es algo y hazme un "
    "resumen. Busca info sobre el tema en la web y hace un resumen con fuentes.")

# C14: surface-forms casi literales de los 3 reales (overfit controlado a esos mensajes)
CANDS["C14"] = (
    "Investiga sobre un tema en internet. Averigua que es algo y resumeme. Busca "
    "info sobre algo y hace un resumen. Investigar o averiguar un tema en la web "
    "y resumirlo con fuentes.")

# C15: C12 + "en internet" repetido (separa de file-search) + verbo investigar reforzado
CANDS["C15"] = (
    "Investiga sobre un tema en internet y resumeme. Averigua en la web que es "
    "algo y hazme un resumen. Busca info sobre el tema en internet y hace un "
    "resumen con fuentes.")

# C16: C12 con "y resumeme/resumen" en las 3 clausulas (refuerza el componente resumen)
CANDS["C16"] = (
    "Investiga sobre eso en internet y resumeme. Averigua que es algo y resumeme. "
    "Busca info sobre el tema en la web y resumeme con fuentes. Investigar un tema "
    "online y hacer un resumen.")

# C17: C12 + en/pt corto (cobertura cross-lingue sin diluir mucho)
CANDS["C17"] = (
    "Investiga sobre eso en internet y resumeme. Averigua que es algo y hazme un "
    "resumen. Busca info sobre el tema en la web y hace un resumen con fuentes. "
    "Research a topic online and summarize it.")

POS = [
    "investiga sobre la guerra de ucrania en internet",
    "averigua que es rust y resumeme",
    "buscá info sobre X y hacé un resumen",
    "podes investigar quien gano el mundial y resumirme",
    "averiguame que paso con el accidente y hace un resumen",
    "research the history of bitcoin and give me a summary",
    "pesquisa sobre o aquecimento global e me resuma",
]
NEG = [
    "hola como estas", "gracias por todo", "contame un chiste", "qué hora es",
    "mandale un mensaje a juan por whatsapp", "abrí spotify y poné rock",
    "subí el brillo de la pantalla", "conectate al wifi de la familia",
    "cuánto es 25 por 4", "poné una alarma a las 8", "cerrá la ventana",
    "busca el archivo presupuesto en mis documentos",
]
POS_E = m.encode(POS, convert_to_tensor=True, normalize_embeddings=True)
NEG_E = m.encode(NEG, convert_to_tensor=True, normalize_embeddings=True)

best = None
for name, desc in CANDS.items():
    d = m.encode(desc, convert_to_tensor=True, normalize_embeddings=True)
    pos = util.cos_sim(d, POS_E).squeeze(0).tolist()
    neg = util.cos_sim(d, NEG_E).squeeze(0).tolist()
    core = sum(1 for c in pos[:3] if c >= 0.45)
    npass = sum(1 for c in pos if c >= 0.45)
    nfp = sum(1 for c in neg if c >= 0.45)
    print(f"\n=== {name} (len={len(desc)}) CORE={core}/3 ALL={npass}/7 NEGfp={nfp} "
          f"minCore={min(pos[:3]):.3f} avgCore={sum(pos[:3])/3:.3f} maxNeg={max(neg):.3f} ===")
    for i,(t, c) in enumerate(zip(POS, pos)):
        print(f"   {'OK ' if c>=0.45 else 'FAIL'} {c:.3f} {'core' if i<3 else '    '} {t}")
    print(f"   filesearch-neg={neg[-1]:.3f}")
