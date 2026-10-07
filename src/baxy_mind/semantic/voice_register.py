"""BAXY's own voice when it reports an act: first person singular, Chilean preterite, words spelled right.

Live 2026-10-07 (voice audit of the v2 computer-use finals): the 4B composer wrote «Abrazé a la sección de
Bluetooth» (a retry at temperature 0.7, for «Llegué»), «Ya estamos en la sección de Accesibilidad» (BAXY alone did
it) and «Ya te he encontrado Spotify», «Ya he entrado en la sección de Bluetooth» (the peninsular perfect where
Chilean tuteo says «encontré», «entré»). The action was right every time; the sentence was not BAXY's.

These readers judge the reply's wording, never the person's request. Quoted text («…», "…") is the screen's or the
person's own words and is left out. A question asks; it reports nothing and is left out too.
"""

from __future__ import annotations

import re

from .normalize import fold

# ---------------------------------------------------------------- the verbs BAXY reports doing
# Infinitives of the acts a report tells. Their first person singular preterite (and, so that a correct word is never
# taken for a misspelled one, their future and voseo imperative) are derived below by the regular rules; the
# irregular ones are listed apart.
_ACT_INFINITIVES_AR = (
    "llegar buscar entrar pasar cambiar activar desactivar apagar cerrar cargar mostrar dejar quitar borrar "
    "seleccionar deseleccionar marcar desmarcar pulsar presionar apretar tocar clicar cliquear copiar pegar guardar "
    "ajustar bajar silenciar mutear desmutear pausar reanudar iniciar lanzar ejecutar instalar desinstalar descargar "
    "enviar mandar crear renombrar programar configurar fijar encontrar mirar revisar comprobar verificar confirmar "
    "contar calcular sumar restar multiplicar minimizar maximizar restaurar ordenar organizar ampliar acercar alejar "
    "desplazar navegar visitar intentar probar usar cancelar terminar acabar empezar comenzar avisar agregar anotar "
    "apuntar eliminar limpiar vaciar llenar completar alternar conectar desconectar emparejar sincronizar actualizar "
    "refrescar recargar regresar avanzar saltar grabar capturar tomar sacar dictar escuchar desplegar expandir "
    "contraer colapsar filtrar enfocar llevar girar rotar ocultar teclear pinchar pintar dibujar rellenar marcar "
    "cortar pegar deshacer rehacer trabajar quedar dar jugar pagar reproducir arrastrar soltar mover ubicar localizar "
    "situar posicionar centrar elevar duplicar fijar desanclar anclar detectar notar observar encender estar"
).split()
_ACT_INFINITIVES_ER_IR = (
    "encender prender mover volver devolver leer resolver escoger recoger retroceder correr meter abrir escribir "
    "subir elegir dividir convertir anadir imprimir decidir recibir compartir cumplir salir seguir repetir pedir "
    "medir invertir describir suscribir permitir incluir excluir ver oir conseguir perder vender aprender comprender "
    "responder esconder"
).split()
# Irregular preterites and futures, written as said.
_IRREGULAR_FORMS = frozenset({
    "hice", "puse", "fui", "tuve", "estuve", "pude", "dije", "traje", "vi", "di", "quise", "supe", "vine", "conduje",
    "traduje", "reproduje", "deshice", "rehice", "detuve", "obtuve", "mantuve", "reduje", "introduje", "anduve",
    "haré", "pondré", "diré", "tendré", "podré", "sabré", "saldré", "vendré", "querré", "cabré", "valdré", "habré",
    "desharé", "reharé", "detendré", "mantendré",
})
# Accented words that end like a first person preterite and are no verb at all.
_NOT_A_VERB = frozenset({
    "aquí", "allí", "allá", "así", "café", "bebé", "puré", "josé", "esquí", "rubí", "colibrí", "maniquí", "comité",
    "carné", "canapé", "consomé", "corsé", "parqué", "bidé", "cupé", "tupé", "chimpancé", "olé", "esté", "dé", "sé",
    "qué", "frappé", "iraní", "israelí", "marroquí", "pakistaní", "bengalí", "paquistaní", "alhelí", "jabalí",
    "frenesí", "ají", "maní", "manatí", "berbiquí", "zaquizamí", "también", "mamá", "papá", "sofá", "allí", "ahí",
    "acá", "bonsái", "pedigrí", "baladí", "turquí", "yemení", "kuwaití", "saudí", "catalí", "hindí", "sufí", "taxi",
})


def _preterite_ar(infinitive: str) -> str:
    stem = infinitive[:-2]
    if stem.endswith("gu"):
        return stem[:-1] + "üé"
    if stem.endswith("c"):
        return stem[:-1] + "qué"
    if stem.endswith("g"):
        return stem + "ué"
    if stem.endswith("z"):
        return stem[:-1] + "cé"
    return stem + "é"


def _accented(infinitive: str) -> str:
    return infinitive.replace("anad", "añad").replace("oir", "oír")


ACT_PRETERITES_1SG = frozenset(
    {_preterite_ar(item) for item in _ACT_INFINITIVES_AR}
    | {_accented(item)[:-2] + "í" for item in _ACT_INFINITIVES_ER_IR if item not in {"oir", "leer"}}
    | {"oí", "leí", "incluí", "excluí"}
)
_KNOWN_ACCENTED_FINALS = (
    ACT_PRETERITES_1SG
    | _IRREGULAR_FORMS
    | _NOT_A_VERB
    # future first person singular («abriré», «buscaré»)
    | {_accented(item) + "é" for item in (*_ACT_INFINITIVES_AR, *_ACT_INFINITIVES_ER_IR)}
    # voseo imperative of -er verbs («mové», «encendé»); the -ir one is the preterite itself
    | {item[:-1] + "é" for item in (*_ACT_INFINITIVES_ER_IR, "poner", "hacer", "tener") if item.endswith("er")}
)

_WORD = re.compile(r"[a-záéíóúüñ]+")
_QUOTED = re.compile(r"«[^»]*»|\"[^\"]*\"|“[^”]*”|‘[^’]*’")


# An irregular verb conjugated as if it were regular («Andé» for «Anduve», «Poní» for «Puse»). Only -ar and -er
# verbs: the regular -ir form is the voseo imperative («decí», «vení»), a word; «esté» is the subjunctive.
_IRREGULAR_INFINITIVES = (
    "andar tener poner hacer traer querer saber poder caber detener obtener mantener contener deshacer rehacer "
    "suponer componer proponer disponer"
).split()
_REGULARIZED_IRREGULARS = frozenset(
    {item[:-2] + ("é" if item.endswith("ar") else "í") for item in _IRREGULAR_INFINITIVES}
)
_INFINITIVES_IN_CAR = frozenset(item for item in _ACT_INFINITIVES_AR if item.endswith("car"))


def _report_sentences(text: object) -> list[str]:
    """The reply's sentences that report, quotes taken out; a question reports nothing."""

    unquoted = _QUOTED.sub(" ", str(text or "").replace("’", "'"))
    return [
        part
        for part in re.findall(r"[^.!?;\n]+[.!?;\n]*", unquoted)
        if part.strip() and "?" not in part and "¿" not in part
    ]


def misspelled_own_preterite(text: object, said: str = "") -> str:
    """A word that is a first person preterite written wrong: «Abrazé» (-zar writes -cé), «Llegé» (-gar writes -gué),
    «Buscé» (-car writes -qué), «Busqé» (q is always followed by u) or an irregular verb made regular («Andé»). A
    word the person or the screen said (``said``) is theirs and kept. Returns the word, or "" when every word stands.

    No edit distance to the known preterites: measured on the 2026-10-07 finals and the test drafts, one or two
    letters away from a listed act is mostly another right verb («Coloqué» ~ «Cliqué», «Negué» ~ «Pegué»)."""

    said_words = set(_WORD.findall(fold(said))) if said else set()
    for sentence in _report_sentences(text):
        for word in _WORD.findall(sentence.casefold()):
            if len(word) < 3 or word[-1] not in "éí" or word in _KNOWN_ACCENTED_FINALS or fold(word) in said_words:
                continue
            if (
                word.endswith("zé")
                or (word.endswith("gé") and not word.endswith(("gué", "güé")))
                or re.search(r"q(?!u)", word) is not None
                or (word.endswith("cé") and word[:-2] + "car" in _INFINITIVES_IN_CAR)
                or word in _REGULARIZED_IRREGULARS
            ):
                return word
    return ""


# ---------------------------------------------------------------- first person plural for BAXY's own act
# «estamos en …» is BAXY's own place only when the place is a thing on screen; «estamos en septiembre», «a cuántos
# estamos», «estamos en la semana 40» speak of the date, which the person shares (uso real tanda 04/06).
_PLURAL_OWN_ACT = re.compile(
    r"\b(?:(?:estamos|estuvimos)\s+(?:en|dentro\s+de)\s+(?:la|el|los|las|una|un)\s+(?!(?:semana|mes|ano|manana|"
    r"tarde|noche|madrugada|fin|epoca|temporada|primavera|verano|otono|invierno|decada|siglo|dia|hora|mitad|"
    r"misma|mismo|mismas|mismos)\b)|"
    r"(?:llegamos|entramos|abrimos|buscamos|encontramos|cerramos|pusimos|hicimos|cambiamos|seleccionamos|elegimos|"
    r"escribimos|activamos|desactivamos|apagamos|encendimos|prendimos|pulsamos|tocamos|guardamos|calculamos)\b|"
    r"hemos\s+[a-z]+(?:ado|ido|ierto|uesto|echo|rito|uelto)\b)"
)
_ENGLISH_PLURAL_OWN_ACT = re.compile(
    r"\bwe(?:'re|\s+are)\s+(?:now\s+|already\s+)?(?:in|on|at)\s+the\b|"
    r"\bwe(?:'ve|\s+have)?\s+(?:just\s+|now\s+|already\s+)?(?:opened|went|reached|found|switched|selected|typed|"
    r"wrote|closed|turned|entered|searched|moved)\b"
)


def tells_own_act_in_plural(text: object) -> bool:
    """«Ya estamos en la sección de Accesibilidad», «We're in Settings»: BAXY alone acted, so it speaks for itself."""

    return any(
        _PLURAL_OWN_ACT.search(fold(sentence)) is not None
        or _ENGLISH_PLURAL_OWN_ACT.search(sentence.casefold()) is not None
        for sentence in _report_sentences(text)
    )


# ---------------------------------------------------------------- peninsular present perfect for a just-done act
_OWN_PERFECT = re.compile(
    r"(?P<before>.*?)\b(?:(?:me|te|lo|la|los|las|le|les|se)\s+)?he\s+(?:ya\s+)?"
    r"(?:[a-z]+(?:ado|ada|ido|ida)|abierto|puesto|hecho|escrito|vuelto|cubierto|descubierto|resuelto|devuelto|"
    r"impreso|dicho|visto|deshecho|rehecho)\b"
)
_NEGATED_BEFORE = re.compile(r"\b(?:no|nunca|jamas|aun\s+no|todavia\s+no)\s+(?:(?:lo|la|los|las|le|les|me|te|se)\s+)?$")


def tells_own_act_in_peninsular_perfect(text: object) -> bool:
    """«Ya he entrado en…», «Te he encontrado Spotify»: a just-done act told in the perfect, where BAXY's Chilean
    tuteo uses the preterite («entré», «encontré»). What BAXY has not done («No lo he encontrado») tells no act."""

    for sentence in _report_sentences(text):
        folded = fold(sentence)
        for found in _OWN_PERFECT.finditer(folded):
            if _NEGATED_BEFORE.search(found.group("before")) is None:
                return True
    return False
