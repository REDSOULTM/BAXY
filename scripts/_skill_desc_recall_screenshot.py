from sentence_transformers import SentenceTransformer, util

m = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# skill: screenshot-and-analyze (auto-inject threshold = 0.45)
CURRENT = ("Take a screenshot, run vision/OCR on it, report what's visible. "
           "Use when user asks 'qué ves', 'leé la pantalla', 'describí lo que "
           "aparece', or when an action needs visual verification before/after.")

# Candidates to compare
CANDS = {}

CANDS["C1_verbose"] = (
    "Tomá una captura de pantalla y describí o leé lo que se ve. Saca un "
    "screenshot y decime qué aparece, leeme lo que dice la pantalla, "
    "captura lo que muestra y analizalo. Take a screenshot and tell me what "
    "you see, read what's on screen. Tira um print e descreva o que aparece. "
    "Tambien para verificar visualmente la pantalla antes o despues de una accion."
)

# C2: drop generic 'verify pantalla' tail (it caused brightness FP), pack
# 'saca una captura / qué ves / dime qué ves' phrasings. <300 chars.
CANDS["C2_tight"] = (
    "Saca una captura y decime qué ves; tomá un screenshot y describilo o "
    "leé lo que dice. Qué se ve, qué aparece. Take a screenshot and tell me "
    "what you see, read what's shown. Tira um print e diz o que aparece."
)

# C3: lead hard with the exact failing phrasings, keep es/en/pt
CANDS["C3_lead"] = (
    "Saca una captura y dime qué ves. Tomá un screenshot y describilo. "
    "Captura la pantalla y leeme lo que dice. Qué ves, qué aparece, leé la "
    "pantalla. Take a screenshot and tell me what you see, read what's "
    "shown. Tira um print e diz o que aparece na tela."
)

POS = [
    # the 3 real failing messages
    "saca una captura y dime que ves",
    "tomá un screenshot y describilo",
    "captura la pantalla y leeme lo que dice",
    # extra variants es/en/pt to avoid overfitting to the 3
    "qué ves",
    "leé la pantalla",
    "describí lo que aparece en la pantalla",
    "podés sacar una foto de la pantalla y decirme qué hay",
    "tira um print e me diz o que aparece",
    "take a screenshot and tell me what you see",
    "lee lo que dice la pantalla",
]

# Negatives: chat + other intents that must NOT fire
NEG = [
    "hola como estas",
    "gracias por todo",
    "contame un chiste",
    "qué hora es",
    "mandale un mensaje a juan por whatsapp",
    "abrí spotify y poné rock",
    "subí el brillo de la pantalla",        # screen hardware, NOT screenshot
    "bajá el brillo",
    "conectate al wifi de la familia",
    "cuánto es 25 por 4",
    "qué es pytest",
    "poné una alarma a las 8",
    "cerrá la ventana",
    "abrí la pantalla completa del video",  # 'pantalla' distractor, NOT screenshot
    "buscá el archivo presupuesto en mis documentos",
]

def report(name, desc):
    d = m.encode(desc, convert_to_tensor=True, normalize_embeddings=True)
    print(f"\n=== {name} (len={len(desc)}) ===")
    pos_pass = 0; mn = 1.0
    print("POSITIVES (want >=0.45):")
    for t in POS:
        s = util.cos_sim(d, m.encode(t, convert_to_tensor=True, normalize_embeddings=True)).item()
        ok = "OK " if s >= 0.45 else "FAIL"
        if s >= 0.45: pos_pass += 1
        mn = min(mn, s)
        print(f"  [{ok}] {s:.3f}  {t}")
    print(f"  POS pass: {pos_pass}/{len(POS)}  (min pos={mn:.3f})")
    neg_fp = 0; mx = 0.0
    print("NEGATIVES (want <0.45):")
    for t in NEG:
        s = util.cos_sim(d, m.encode(t, convert_to_tensor=True, normalize_embeddings=True)).item()
        ok = "OK  " if s < 0.45 else "FP!!"
        if s >= 0.45: neg_fp += 1
        mx = max(mx, s)
        print(f"  [{ok}] {s:.3f}  {t}")
    print(f"  NEG fp: {neg_fp}/{len(NEG)}  (max neg={mx:.3f})")
    return pos_pass, neg_fp, mn, mx

# C4: C3 leading phrasings but kill the 'pantalla completa del video' FP by
# anchoring on capture+read+describe rather than bare 'pantalla', drop 'na tela'
CANDS["C4_final"] = (
    "Saca una captura y dime qué ves. Tomá un screenshot y describilo. "
    "Captura lo que se muestra y leeme lo que dice. Qué ves, qué aparece, "
    "describí o leé lo que sale en la captura. Take a screenshot and tell me "
    "what you see, read what's shown. Tira um print e diz o que aparece."
)

report("CURRENT", CURRENT)
for k, v in CANDS.items():
    report(k, v)
