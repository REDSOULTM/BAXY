"""Bug 3: Grounding gate — detect replies that claim actions not in tool_events.

Inline cheap check (`detect_action_claim_without_evidence`): runs in the
hot path, no LLM/NLI inference. Uses linguistic features (verb
morphology heuristics derived from the existing false-confirmation
guard) to flag obvious "abrí X / busqué Y / agendé Z" claims when
`tool_events == []`. Returns a verdict; the agent's existing
`_guard_promise_without_action` keeps catching prefix cases.

The async NLI grounding layer (`schedule_grounding_check`) was removed:
its cache hit rate over 5 days of use was 3.2 %, below
the 20 % keep/kill threshold from `08_findings.md §2.10`.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any


# Linguistic features for the inline layer. These are NOT a closed allowlist
# of "bad verbs"; they are morphological signals of "1st-person past-tense
# action claim" — a grammatical category. The signal is the SUFFIX pattern,
# not the lemma. Spanish 1st-person preterit indicative endings are -é (-ar),
# -í (-er/-ir); accentless variants are common in voice transcription.
_PRETERIT_SUFFIXES_ACCENTED = (
    "é", "í",
)
_PRETERIT_SUFFIXES_PLAIN = (
    "e", "i",
)
# Common short action stems that, COMBINED with a preterit suffix, signal
# a concrete action claim. Kept SHORT and abstract; not a comprehensive list.
# The point is "any verb of opening/searching/sending/etc, in 1st-person
# preterit". We detect via suffix + first-letter-set heuristic.
_ACTION_STEMS_HINT = frozenset({
    "abr", "busc", "busq", "envi", "agend", "registr", "ejecut", "inici",
    "lanc", "abri", "encontr", "mande", "mostre", "puse", "naveg", "carg",
    "cli", "guard", "borr", "cre", "elimin", "cerr", "edit", "modif",
    "actualic", "consult", "verif", "confirm", "respond", "contest",
    "ejecut", "registr",
    "salud", "marqu", "asign", "asisti", "atendi",
})

# Stems de verbos cuya FORMA "he <participio>" / "estoy <gerundio>" en un turno
# de 0-events es una mentira (el asistente afirma haber EJECUTADO/CONSUMIDO algo
# sin que ninguna tool corriera). Incluye consumo sensorial (escuchar/ver/
# reproducir) que un asistente de TEXTO no puede hacer. Usado por
# _claims_consummated_action (perfecto compuesto + presente continuo), que
# complementa _starts_with_action_claim (pretérito simple). NO incluye verbos de
# CONOCIMIENTO ("conoc", "sé", "oí hablar") → "conozco a X" NO es mentira.
_CONSUMMATED_STEMS = frozenset({
    "reproduc", "escuch", "puesto", "abiert", "envia", "envi", "busc",
    "encontr", "mostr", "ejecut", "agend", "registr", "naveg", "guard",
    "borr", "elimin", "cerr", "edit", "modific", "actualiz", "consult",
    "verific", "confirm", "vist", "vie", "mir", "le",  # visto/viendo/mirado/leído
    # --- multilingüe (mission-eval 2026-06-10): el detector cubría SOLO español;
    # el 4B mentía impune en EN/IT/PT/FR/DE ("Ho spostato in primo piano",
    # "I have opened the app") con 0 tools. Mismo sesgo-al-español de la misión,
    # ahora en el guard de honestidad. Raíces de participio/pasado de acción: ---
    # IT: spostato, aperto, ridotto, abbassato, chiuso, riprodotto, cercato,
    #     impostato, inviato, mostrato, eseguito, modificato, salvato, messo
    "spostat", "apert", "ridott", "abbassat", "chius", "riprodott", "cercat",
    "impostat", "inviat", "mostrat", "esegui", "modificat", "salvat", "mess",
    # EN: opened, searched, moved, lowered, raised, closed, played, sent, set,
    #     executed, saved, edited, deleted, brought, checked, shown
    "open", "search", "mov", "lower", "rais", "clos", "play", "sent", "set",
    "execut", "sav", "edit", "delet", "brought", "check", "shown", "show",
    "launch", "start", "adjust", "turn", "switch", "enabl", "disabl",
    # PT: abri, reduzi, fechei, abaixei, mostrei, executei, salvei, enviei,
    #     reproduzi, movi, ajustei (pretérito 1ª pers) + participios aberto/feito
    "abri", "reduzi", "fechei", "abaixei", "mostrei", "executei", "salvei",
    "enviei", "reproduzi", "movi", "ajustei", "abert", "feit", "coloquei",
    # FR: ouvert, baissé, fermé, déplacé, réduit, mis, envoyé, exécuté, montré,
    #     joué, enregistré, modifié, supprimé
    "ouvert", "baiss", "ferm", "deplac", "reduit", "mis", "envoy", "execut",
    "montr", "jou", "enregistr", "modifi", "supprim",
    # DE: geöffnet, gesenkt, geschlossen, verschoben, eingestellt, gespielt,
    #     gesendet, ausgeführt, gespeichert, angezeigt, reduziert
    "geoffnet", "gesenkt", "geschloss", "verschob", "eingestellt", "gespielt",
    "gesendet", "ausgefuhrt", "gespeichert", "angezeigt", "reduziert",
})
# Auxiliares de perfecto compuesto / pasado, 6 idiomas. La forma "aux + raíz de
# acción" en 0-events es una mentira estructural. fold() quita tildes/apóstrofes
# de antemano (j'ai -> j ai), por eso el FR va sin apóstrofe.
_AUX_PERFECT = (
    "he ", "hemos ", "ya he ", "he estado ",          # ES
    "i have ", "i've ", "ive ", "i just ",            # EN
    "ho ", "sono ", "abbiamo ",                        # IT
    "ja ", "tenho ",                                   # PT (já / tenho + part.)
    "j'ai ", "j ai ", "jai ", "nous avons ",           # FR (fold conserva apóstrofe)
    "ich habe ", "habe ", "ich hab ",                  # DE
)
_AUX_CONTINUOUS = (
    "estoy ", "estoy ahora ", "estuve ",               # ES
    "i am ", "i'm ", "im ",                            # EN
    "sto ",                                            # IT (sto riproducendo)
    "estou ",                                          # PT
    "je suis en train ",                               # FR
    "ich bin gerade ",                                 # DE
)


# Participios de verbos de ESTADO/SER/CONOCER — NO son acciones consumadas. Tras
# "he estado / I have been / ho avuto / j'ai été", el reply es charla, no mentira.
# Se excluyen del chequeo morfológico de participio. fold-tolerante.
_NON_ACTION_PARTICIPLES = frozenset({
    "estado", "sido", "been", "stato", "stata", "avuto", "ete", "gewesen",
    "gehabt", "podido", "querido", "tenido", "habido", "wanted", "able",
    "estat", "sigut",  # ca/regional
    # cortesía / adjetivos con forma de participio que NO son acción:
    "obrigado", "obrigada",  # PT "gracias" (no "obligar")
    "encantado", "encantada", "agradecido", "contento", "ocupado",
})

# Idioms de CONOCIMIENTO con forma de participio que NO son acción: "oído hablar
# de" / "sentito parlare di" / "heard of". El participio existe pero el sentido es
# saber-de-algo, no haber-actuado. Se chequea el bigrama, no solo la palabra.
_KNOWLEDGE_PARTICIPLE_BIGRAMS = (
    "oido hablar", "sentito parlare", "heard of", "heard about", "entendido falar",
    "entendu parler", "gehort von", "oido sobre",
)


def _looks_like_past_participle(word: str) -> bool:
    """True si `word` (folded) tiene FORMA de participio pasado de un verbo de
    acción (no de estado). Morfología, no lema: cubre verbos no enumerados —
    "ho portato/avviato/collocato" se detectan sin estar en la lista. La memoria
    del proyecto: "perseguir strings es infinito -> detector estructural".
    """
    w = word.rstrip(".,;:!?")
    if len(w) < 5 or w in _NON_ACTION_PARTICIPLES:
        return False
    # IT -ato/-ito/-uto; ES/PT -ado/-ido. DE: ge-…-t/-en.
    if any(w.endswith(s) for s in ("ato", "ito", "uto", "ado", "ido")):
        return True
    if w.startswith("ge") and (w.endswith("t") or w.endswith("en")) and len(w) > 5:
        return True
    return False


def _has_consummated_stem(word: str) -> bool:
    """True si `word` es una acción consumada: raíz conocida O forma morfológica
    de participio pasado de acción (cubre verbos no enumerados)."""
    if not word:
        return False
    if any(word.startswith(s) for s in _CONSUMMATED_STEMS):
        return True
    return _looks_like_past_participle(word)


# Pretérito 1ª persona DIRECTO (sin auxiliar) en idiomas donde el pasado simple
# es la forma natural de afirmar la acción: PT "reduzi/abri/fechei", IT no
# (usa ho+part.). Estas raíces SON la palabra completa (no prefijo de otra), así
# que se chequean como token inicial del reply. mission-eval 2026-06-10.
_DIRECT_PRETERIT_PT = frozenset({
    "abri", "reduzi", "fechei", "abaixei", "mostrei", "executei", "salvei",
    "enviei", "reproduzi", "movi", "ajustei", "coloquei", "naveguei", "busquei",
})


def _claims_consummated_action(text: str) -> bool:
    """True si el reply afirma una acción CONSUMADA. Estructural (auxiliar + raíz
    de verbo de acción/consumo), 6 idiomas, NO una lista de frases. Para 0-events
    (donde es necesariamente falso). Dos formas:
      (1) aux compuesto/continuo + raíz en las ~5 palabras siguientes (cubre el
          orden alemán "ich habe ... geöffnet" con el participio al final);
      (2) pretérito directo 1ª pers como primera palabra (PT "Reduzi o volume").
    """
    if not text:
        return False
    low = _fold(text.strip())
    # (0) idiom de CONOCIMIENTO con forma de participio ("oído hablar de" /
    # "sentito parlare di" / "heard of") -> NO es acción, abortar.
    if any(big in low for big in _KNOWLEDGE_PARTICIPLE_BIGRAMS):
        return False
    # (1) auxiliar + raíz en la ventana siguiente (hasta 5 tokens: cubre DE).
    # FRONTERA DE PALABRA en el inicio del auxiliar (2026-06-10): el find() por
    # substring hacía que los aux cortos multilingües matchearan DENTRO de
    # palabras de otro idioma — "sto " (IT) dentro de "eSTO requiere
    # confirmación" + stem "confirm" a <5 tokens = falso claim que pisaba un
    # reply legítimo que YA pedía confirmación (test_window_geom_and_confirm_
    # honesty, regresión de la expansión multilingüe 49bbb3b). Mismo riesgo:
    # "ho " (IT) ⊂ "hecho ", "im " (EN) ⊂ "...im ". El aux solo cuenta si
    # arranca el texto o lo precede un no-alfanumérico.
    for aux in _AUX_PERFECT + _AUX_CONTINUOUS:
        aux_f = _fold(aux)
        idx = low.find(aux_f)
        while idx != -1:
            if idx == 0 or not low[idx - 1].isalnum():
                rest = low[idx + len(aux_f):].split()
                for nxt in rest[:5]:
                    if _has_consummated_stem(nxt):
                        return True
            idx = low.find(aux_f, idx + 1)
    # (2) pretérito directo PT como primer token significativo (tras "ja/listo/").
    toks = [t for t in low.replace(",", " ").split() if t]
    for t in toks[:2]:
        t0 = t.rstrip(".,;:!?")
        if t0 in _DIRECT_PRETERIT_PT:
            return True
    return False


# Estado-RESULTADO de ventana que el 4B afirma SIN haber actuado ("Calculator is
# now in front", "la calcolatrice è ora in primo piano"). No es aux+participio:
# es copula + estado-de-resultado. mission-eval 2026-06-10 (run9): medido 25% de
# las corridas 0-events de "traer al frente/maximizar". La señal discriminante
# (medida contra adversarial): marcador "AHORA" (now/ora/agora/ya) o opener de
# completitud + estado-de-ventana. El conocimiento/oferta NUNCA dice "ahora está
# <estado>" (dice "para maximizar…", "puedo traerla… si querés").
_RESULT_STATE_TOKENS = (
    "in front", "in primo piano", "primer plano", "primeiro plano", "im vordergrund",
    "au premier plan", "maximiz", "minimiz", "massimizz", "ridotto a icona",
    "in den vordergrund",
)
_NOW_MARKERS = (" now ", " ahora ", " ora ", " agora ", " ya ", " adesso ",
                " jetzt ", " maintenant ", "now.", "ahora.", "ora.")
_COMPLETION_OPENERS = ("done", "listo", "hecho", "perfetto", "fatto", "fertig",
                       "pronto", "c'est fait", "voila", "ecco", "alles klar",
                       "va bene", "ok,", "okay,", "certo", "claro,")


def _claims_result_state_without_action(text: str) -> bool:
    """True si el reply AFIRMA un estado-resultado de ventana ("ahora está al
    frente/maximizada") que en 0-events es necesariamente falso. Conservador:
    exige (marcador 'ahora' O opener de completitud) + estado-de-ventana, para
    no marcar conocimiento ("para maximizar…") ni ofertas ("puedo traerla…").
    """
    if not text:
        return False
    low = _fold(text.strip())
    has_state = any(s in low for s in _RESULT_STATE_TOKENS)
    if not has_state:
        return False
    has_now = any(m in low for m in _NOW_MARKERS)
    has_opener = any(low.startswith(o) for o in _COMPLETION_OPENERS)
    # ofertas/preguntas/condicionales NO son afirmación de estado consumado.
    is_offer = any(w in low for w in ("?", " si quer", " se vuoi", " if you",
                                      " puedo ", " posso ", " si tu ", " se quiser",
                                      " quer que", " veux-tu", " möchtest"))
    return (has_now or has_opener) and not is_offer


def _fold(text: str) -> str:
    """lowercase + strip diacritics for tolerant matching."""
    n = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in n if not unicodedata.combining(ch))


def _looks_like_first_person_preterit(word: str) -> bool:
    """Heuristic: does `word` look like a Spanish 1st-person preterit verb?

    Examples that should match (case-insensitive, fold-tolerant):
      abrí, abri, busqué, busque, envié, agendé, ejecuté, registré, mandé,
      lancé, naveg(u)é, mostré, encontré, puse, cliqué, abrir... NO, infinitive
      ends in -r, must reject. cargo (present)... NO, ends in -o, reject.

    Rejects pretty much anything that doesn't look like a 1st-person preterit.
    """
    w = word.strip().rstrip(".,;:!?")
    if not w or len(w) < 4:
        return False
    folded = _fold(w)
    # Must end in 'e' or 'i' (preterit indicative suffix, accent-stripped).
    if not (folded.endswith("e") or folded.endswith("i")):
        return False
    # Exclude common non-verbs ending in -e/-i (nombre, examen, casi, etc).
    # Verbs are stem + (e|i); we require the stem to be in our hint set OR
    # to be a plausible verb stem (ends in a consonant-ish form).
    # Simpler: require the stem prefix (first 3-5 chars) to be in the hint set.
    # Check stem prefixes of varying length against the hint set. Stems in
    # the set range from 3 to 6 chars (abr, busc, agend, ejecut, registr).
    if any(folded[:n] in _ACTION_STEMS_HINT for n in (3, 4, 5, 6, 7)):
        # Additional gate: reject "abrir", "abrira", future/conditional/infinitive.
        if folded.endswith("r") or folded.endswith("ra") or folded.endswith("ria"):
            return False
        return True
    return False


def _starts_with_action_claim(text: str) -> str | None:
    """If the text starts with what looks like a 1st-person past-tense
    action verb, return that word (for telemetry). Else None.

    Tolerates leading interjections / connectives: "Listo, abrí Disney+" ->
    detects "abrí" after stripping "Listo,".
    """
    stripped = text.strip()
    if not stripped:
        return None
    # Strip up to N leading clause-openers (comma- or colon-separated).
    # Common patterns: "Listo, X" / "Listo, hecho, X" / "Hecho: X" / etc.
    import re as _re
    parts = _re.split(r"[,:;]", stripped)
    # adverbios/partículas que suelen PRECEDER al verbo sin ser el claim ("ya
    # cerré", "ahora abrí", "también mandé"). Si el 1er word es uno de estos,
    # también miramos el 2º. accent-fold para tolerar "ya"/"ahora".
    _LEAD_ADV = {"ya", "ahora", "tambien", "también", "recien", "recién", "listo"}
    for cand in parts[:4]:
        words = cand.strip().split()
        if not words:
            continue
        if _looks_like_first_person_preterit(words[0]):
            return words[0]
        if len(words) >= 2 and _fold(words[0]) in {_fold(a) for a in _LEAD_ADV} \
                and _looks_like_first_person_preterit(words[1]):
            return words[1]
    return None


# ---------- Inline gate ----------

@dataclass
class GroundingVerdict:
    """Outcome of the inline grounding check.

    `should_replace`: if True, agent should swap the reply with `fallback`.
    `reason`: short telemetry tag.
    `claim_word`: the word that triggered the gate (if any).
    """
    should_replace: bool
    reason: str = ""
    claim_word: str = ""
    fallback: str = ""


_HONEST_FALLBACK = "No alcancé a completar la acción. ¿La repetimos?"

# Per-language variants. The selector below picks one based on hints
# extracted from the LLM's own (rejected) reply, so the fallback stays
# in the same language as the rest of the conversation.
_FALLBACKS_BY_LANG: dict[str, dict[str, str]] = {
    "es": {
        "generic":  "No alcancé a completar la acción. ¿La repetimos?",
        "no_tool":  "No tengo una tool para eso. ¿Probamos con otra cosa?",
        "partial":  "Me falta info para completarlo: {missing}. ¿Me la pasás?",
        "retry":    "No agarré bien el pedido. Probá reformularlo — opciones cercanas: {hints}.",
    },
    "en": {
        "generic":  "I couldn't complete that. Want to try again?",
        "no_tool":  "I don't have a tool for that. Want to try something else?",
        "partial":  "I'm missing info to complete this: {missing}. Can you tell me?",
        "retry":    "I'm not catching that. Try rephrasing — close options: {hints}.",
    },
    # FR/IT/DE/PT añadidos (mission-eval 2026-06-10): el dataset multilingüe SÍ
    # ejerce estos idiomas; sin su rama, el fallback honesto caía a español y el
    # reply mezclaba idiomas ("ouvre le bloc-notes..." -> respuesta en ES).
    "fr": {
        "generic":  "Je n'ai pas pu terminer ça. On réessaie ?",
        "no_tool":  "Je n'ai pas d'outil pour ça. On essaie autre chose ?",
        "partial":  "Il me manque des infos pour finir : {missing}. Tu peux me les donner ?",
        "retry":    "Je n'ai pas bien saisi. Reformule — options proches : {hints}.",
    },
    "it": {
        "generic":  "Non sono riuscito a completarlo. Riproviamo?",
        "no_tool":  "Non ho uno strumento per questo. Proviamo altro?",
        "partial":  "Mi mancano info per completarlo: {missing}. Me le dai?",
        "retry":    "Non ho capito bene. Riformula — opzioni vicine: {hints}.",
    },
    "de": {
        "generic":  "Das konnte ich nicht abschließen. Nochmal versuchen?",
        "no_tool":  "Dafür habe ich kein Werkzeug. Etwas anderes versuchen?",
        "partial":  "Mir fehlen Infos dafür: {missing}. Kannst du sie mir geben?",
        "retry":    "Ich habe das nicht verstanden. Formuliere um — nahe Optionen: {hints}.",
    },
    "pt": {
        "generic":  "Não consegui completar isso. Tentamos de novo?",
        "no_tool":  "Não tenho uma ferramenta para isso. Tentamos outra coisa?",
        "partial":  "Falta informação para completar: {missing}. Pode me passar?",
        "retry":    "Não entendi bem. Reformule — opções próximas: {hints}.",
    },
}
_LANG_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # (lang_code, list of bigram/word hints — accent-insensitive, lower). Para
    # FR/IT/DE/PT: palabras-función frecuentes + verbos imperativos que el dataset
    # multilingüe ejercita ("ouvre", "apri", "öffne", "abre/abra"). mission-eval
    # 2026-06-10: sin estos, el user_text en FR/IT/DE/PT no se detectaba y el
    # fallback honesto caía a ES.
    ("en", ("the ", " i ", " you ", "i'll", "i've", "i couldn", "let me",
            "done", "got it", "okay", "all right", "please", "open ", "close ")),
    ("fr", (" le ", " la ", " et ", " un ", " une ", " sur ", " mon ", " tu ",
            "ouvre", "ferme", "écris", "ecris", "baisse", "s'il", "j'en",
            "n'ai", "réessaie", "peux")),
    ("it", (" il ", " lo ", " un ", " su ", " mio ", " e vai", "apri", "chiudi",
            "abbassa", "scrivi", "non ", "riprov", " gli ", " che ")),
    ("de", (" der ", " die ", " das ", " und ", " ein ", " mir ", "öffne",
            "schließe", "mach ", "leiser", "lauter", "lautstärke", "nicht",
            "bitte")),
    ("pt", (" o ", " a ", " e ", " um ", " uma ", " meu ", " você", "abra ",
            "abre ", "feche", "manda", "procura", "não", "obrigado")),
    # ES is the default; only listed for completeness.
    ("es", (" el ", " la ", " ya ", "listo", "abrí", "cerré", "puse",
            "ejecut", "hecho", "¿", "¡", "ñ")),
)


def detect_reply_language(reply: str) -> str:
    """Lightweight language guess from a short LLM reply.

    Not a full language detector — just enough to pick the right fallback
    string. Falls back to 'es' (project default) on ambiguity.
    """
    if not reply:
        return "es"
    low = " " + reply.lower() + " "
    best = "es"
    best_score = 0
    for lang, hints in _LANG_HINTS:
        score = sum(1 for h in hints if h in low)
        if score > best_score:
            best_score = score
            best = lang
    return best


def format_fallback(
    *,
    reason: str,
    reply_lang_hint: str | None = None,
    rejected_reply: str = "",
    missing: str = "",
    hints: str = "",
) -> str:
    """Pick a fallback string in the user's language.

    `reason` is one of generic / no_tool / partial / retry. `missing` and
    `hints` are interpolated only when present in the template.
    """
    lang = reply_lang_hint or detect_reply_language(rejected_reply)
    table = _FALLBACKS_BY_LANG.get(lang) or _FALLBACKS_BY_LANG["es"]
    template = table.get(reason) or table["generic"]
    return template.format(missing=missing or "—", hints=hints or "—")


def _event_result(ev: Any) -> dict[str, Any]:
    """Result dict de un tool event (dataclass ToolEvent o dict), tolerante."""
    if isinstance(ev, dict):
        r = ev.get("result")
    else:
        r = getattr(ev, "result", None)
    return r if isinstance(r, dict) else {}


def all_events_blocked_or_failed(tool_events: list[Any]) -> bool:
    """True si TODOS los tool results del turno quedaron en bloqueo/fallo SIN
    ejecución consumada: ok=False (error, needs_user por precondición,
    needs_confirmation del gate, tool-call que ni parseó). En ese turno un
    claim de acción consumada O EN CURSO ("estoy abriendo X") es
    necesariamente falso — la propia tool reportó que NO pasó (MEDIDO en vivo
    2026-06-10: app.open needs_user "No encuentro esa aplicación" y el reply
    decía "Listo, estoy abriendo jitomatador").

    Un solo result ok=True hace False — incluye los dispatch async honestos
    (status=dispatched / launch_requested, verified=None): ahí "estoy
    abriendo Steam" SÍ es honesto y NO se toca. Gate por el STATUS del
    result, no por el verbo. FAIL-OPEN: un event sin result dict (estado
    desconocido, p.ej. construido ad-hoc) NO cuenta como fallo — solo se
    flagea con fallo MEDIDO en todos los events."""
    if not tool_events:
        return False
    saw_failed = False
    for ev in tool_events:
        res = _event_result(ev)
        if not res:
            return False  # resultado desconocido -> no afirmar fallo sin evidencia
        if res.get("ok"):
            return False
        saw_failed = True
    return saw_failed


def detect_action_claim_without_evidence(
    reply: str, tool_events: list[Any],
) -> GroundingVerdict:
    """Inline (no NLI) check: if the reply opens with a 1st-person past-tense
    action verb AND no tool actually did anything, flag it.

    Two evidence-free cases (same claim detectors, distinct telemetry):
      - `tool_events == []` (nothing ran at all);
      - every event's result is blocked/failed ok=False (needs_user,
        needs_confirmation, error, unparseable call) -> the tools THEMSELVES
        say nothing happened, so a consummated/in-progress claim contradicts
        the evidence (2026-06-10).

    Does NOT depend on a hardcoded verb list — uses morphological pattern.
    Conservative by design: only flags clear cases starting the reply, so
    legitimate replies like "Encontré la respuesta: ..." (after a real web
    tool ran) are untouched because some tool event is ok=True.
    """
    if tool_events and not all_events_blocked_or_failed(tool_events):
        return GroundingVerdict(should_replace=False, reason="tool_events_nonempty")
    if not reply:
        return GroundingVerdict(should_replace=False, reason="empty_reply")
    claim = _starts_with_action_claim(reply)
    if not claim and _claims_consummated_action(reply):
        # perfecto compuesto / presente continuo ("he reproducido", "estoy
        # escuchando") — pretérito que _starts_with_action_claim no cubre.
        claim = "consummated"
    if not claim and _claims_result_state_without_action(reply):
        # estado-resultado de ventana afirmado sin actuar ("ahora está al
        # frente/maximizada") — copula+estado, no aux+participio (run9).
        claim = "result_state"
    if not claim:
        return GroundingVerdict(should_replace=False, reason="no_claim_signal")
    return GroundingVerdict(
        should_replace=True,
        reason=("action_claim_all_events_failed" if tool_events
                else "action_claim_without_evidence"),
        claim_word=claim,
        fallback=_HONEST_FALLBACK,
    )


__all__ = [
    "GroundingVerdict",
    "all_events_blocked_or_failed",
    "detect_action_claim_without_evidence",
    "detect_reply_language",
    "format_fallback",
]
