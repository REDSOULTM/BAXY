"""Mide el umbral fonético para strip_wake_phrase fuzzy de 'baxy'.

Por qué: el STT (Parakeet, multilingüe) transcribe la wake word inventada
"Baxy" como palabras reales cercanas (Paxi/Bixby/Max). El supresor
strip_wake_phrase compara EXACTO -> no las quita -> el LLM recibe el nombre
mal-oído como parte del comando. Este diag mide qué umbral separa los
mal-oídos de "Baxy" (DEBEN quitarse) de los arranques de comando reales
(NO deben tocarse), reutilizando la maquinaria fonética dual ES/EN del
corrector. Regla CLAUDE.md: medí el umbral, no lo inventes.

Uso: python scripts/_diag/_diag_wake_strip_threshold.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rapidfuzz import fuzz

from gemma4_agent.voice.corrector import (
    _HAS_ES_PHONETIC,
    _HAS_PHONETIC,
    _metaphone,
    _metaphone_es,
    _normalise,
)


def dual_phon(a: str, b: str) -> tuple[float, float]:
    na, nb = _normalise(a), _normalise(b)
    txt = fuzz.ratio(na, nb)
    en = (
        fuzz.ratio(_metaphone(na), _metaphone(nb))
        if _metaphone(na) and _metaphone(nb)
        else 0
    )
    es = (
        fuzz.ratio(_metaphone_es(na), _metaphone_es(nb))
        if _metaphone_es(na) and _metaphone_es(nb)
        else 0
    )
    return txt, max(en, es)


def main() -> None:
    print("phonetic EN avail:", _HAS_PHONETIC, "| ES avail:", _HAS_ES_PHONETIC)
    wake = "baxy"

    positives = ["Paxi", "Bixby", "Max", "Baxi", "Backsy", "Baxy", "Backy",
                 "Paxy", "Baxie", "Vaxi", "Maxi", "Bixie", "Paxie"]
    negatives = ["Pasame", "Maximo", "Busca", "Manda", "Pon", "Abre", "Para",
                 "Mas", "Pausa", "Mira", "Baja", "Mande", "Mete", "Reproduce",
                 "Cierra", "Sube", "Hola", "Que", "Dime", "Ponme"]

    print("\n=== POSITIVOS (mal-oídos de Baxy -> DEBEN matchear) ===")
    pos_phon = []
    for h in positives:
        t, p = dual_phon(wake, h)
        pos_phon.append(p)
        print(f"  {h:10} txt={t:3.0f}  phon(max ES/EN)={p:3.0f}")

    print("\n=== NEGATIVOS (arranques de comando -> NO tocar) ===")
    neg_phon = []
    for h in negatives:
        t, p = dual_phon(wake, h)
        neg_phon.append(p)
        print(f"  {h:10} txt={t:3.0f}  phon(max ES/EN)={p:3.0f}")

    # Separación: el umbral debe quedar entre el peor positivo "real" y el
    # mejor negativo. Excluimos el match exacto 'Baxy'(=100) del análisis de
    # frontera (ya lo captura el match exacto previo).
    pos_no_exact = sorted(p for p, h in zip(pos_phon, positives)
                          if h.lower() != "baxy")
    neg_sorted = sorted(neg_phon, reverse=True)
    print("\n=== FRONTERA ===")
    print(f"  positivos (sin 'baxy') ordenados: {[round(x) for x in pos_no_exact]}")
    print(f"  negativos top-5:                  {[round(x) for x in neg_sorted[:5]]}")
    print(f"  peor positivo: {min(pos_no_exact):.0f}  |  mejor negativo: {max(neg_phon):.0f}")
    gap = min(pos_no_exact) - max(neg_phon)
    print(f"  GAP = {gap:.0f}  ({'separable' if gap > 0 else 'SOLAPADO - cuidado'})")

    # Regla combinada propuesta: umbral fonético 80 sobre el PRIMER token.
    # A 80, ¿qué positivos rescatamos y qué negativos evitamos?
    TH = 80
    print(f"\n=== REGLA: phon(primer-token, 'baxy') >= {TH} ===")
    rescued = [h for h, p in zip(positives, pos_phon) if p >= TH]
    missed = [h for h, p in zip(positives, pos_phon) if p < TH and h.lower() != "baxy"]
    false_pos = [h for h, p in zip(negatives, neg_phon) if p >= TH]
    print(f"  positivos RESCATADOS ({len(rescued)}): {rescued}")
    print(f"  positivos PERDIDOS   ({len(missed)}): {missed}")
    print(f"  negativos FALSO-POS  ({len(false_pos)}): {false_pos}  <-- debe ser []")

    # Segunda señal: la wake va seguida de PAUSA (coma). En los logs reales:
    # "Paxi, va a..." / "Bixby, ¿qué...". Si el primer token termina en coma,
    # es evidencia FUERTE de wake -> umbral más laxo (72, el del corrector).
    # ¿Qué negativos arrancan con coma a 72? (medimos que sea seguro)
    TH_COMMA = 72
    print(f"\n=== REGLA 2: primer-token-con-coma + phon >= {TH_COMMA} ===")
    rescued2 = [h for h, p in zip(positives, pos_phon) if p >= TH_COMMA]
    fp2 = [h for h, p in zip(negatives, neg_phon) if p >= TH_COMMA]
    print(f"  positivos rescatados a {TH_COMMA}: {rescued2}")
    print(f"  negativos a {TH_COMMA} (raros con coma): {fp2}")
    print("  -> 'Paxi'(75) y 'Maxi'(75) se rescatan; 'Busca,'(67) NO (y nadie")
    print("     dice 'Busca,' como primer token igual).")


if __name__ == "__main__":
    main()
