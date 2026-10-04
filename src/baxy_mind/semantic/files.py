"""Files: open, find, delete and list files and known folders, PDFs, downloads. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from typing import NamedTuple

from .grammar import _fold, _match, _has, _strip_request_envelope, _head_is, _is_negative_effect_clause, _OPEN, _SEARCH
from .intent import EffectIntent, _is_negated_match, _append
from .web import _KNOWN_FOLDER_WORDS, _KNOWN_FOLDER_ENUM, _literal_known_file_search


_FILE_CREATION_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:cre[aá]|crear|cre[aá]me|create|guard[aá]|guardar|escrib[eí]|escribir|write|save)(?:me)?\s+"
    r"(?:(?:un|una|a|the|el)\s+)?(?:archivo|fichero|file)(?:\s+(?:de\s+texto|txt|text))?"
    rf"(?:\s+(?:en|on|in|dentro\s+de|inside)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder_a>{_KNOWN_FOLDER_WORDS}))?"
    r"\s+(?:llamad[oa]|named|called|con\s+(?:el\s+)?nombre)\s+(?P<name>\"[^\"]+\"|'[^']+'|\S+)"
    rf"(?:\s+(?:en|on|in|dentro\s+de|inside)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder_b>{_KNOWN_FOLDER_WORDS}))?"
    r"\s+(?:que\s+diga|que\s+contenga|con\s+(?:el\s+)?(?:texto|contenido)|with\s+(?:the\s+)?(?:text|content)|containing|that\s+says|saying)\s+"
    r"(?P<content>.+?)\s*$",
    re.IGNORECASE,
)


# «borra el archivo hola.txt del escritorio», «borrá el archivo viejo.txt»,
# «delete old.txt from the desktop»: one named file, optionally in one known
# folder, goes to the product's recoverable private trash
# (filesystem.known.trash.named). A bare name must look like a file (an
# extension) unless the request says «archivo/file», so «borra el mensaje»
# and folders stay outside; a folder deletion has no operation.
_FILE_TRASH_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:borr[aá]|borrar|borr[aá]me|elimin[aá]|eliminar|elimin[aá]me|"
    r"delete|remove|"
    r"(?:mand[aá]|manda|envi[aá]|envia|tir[aá]|tira)(?:me)?\s+a\s+la\s+papelera)(?:me)?\s+"
    r"(?:(?:el|la|the)\s+)?(?P<noun>(?:archivo|fichero|file|carpeta|folder|directorio|directory)\s+)?"
    r"(?:(?:llamad[oa]|named|called)\s+)?"
    r"(?P<name>\"[^\"]+\"|'[^']+'|[^\s\"']+)"
    rf"(?:\s+(?:del|de\s+la|de|from|in|en|on)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder>{_KNOWN_FOLDER_WORDS}))?"
    r"(?:\s*,?\s+(?:por\s+favor|please|porfa))?[\s.!?]*$",
    re.IGNORECASE,
)


# PDF1689 H0666 «resumime informe.pdf», «hazme un resumen de informe.pdf»,
# «summarize report.pdf»: one named PDF in the known folders is read for its
# text (document.pdf.read) and the reply presents it; a bare name must be
# a .pdf file or the request must say «pdf».
_PDF_SUMMARY_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please|porfa)\s*[,;:]?\s*)?"
    r"(?:(?:hac[eé]|hace|hazme|haceme|hac[eé]me|arm[aá]|arm[aá]me|dame|make|give\s+me|write|escrib[ií])(?:me)?\s+"
    r"(?:(?:un|una|el|a|the)\s+)?(?:resumen|summary)\s+(?:de|del|of)(?:\s+(?:el|la|the))?"
    r"|(?:resum[ií]|resumime|resum[ií]me|resumeme|resumir|resume|summari[sz]e|sum\s+up)(?:me)?"
    r"(?:\s+(?:el|la|the))?)\s+"
    r"(?P<noun>(?:archivo|fichero|file|documento|document|pdf)\s+)?"
    r"(?:(?:llamad[oa]|named|called)\s+)?"
    r"(?P<name>\"[^\"]+\"|'[^']+'|[^\s\"']+)"
    rf"(?:\s+(?:del|de\s+la|de|from|in|en|on)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder>{_KNOWN_FOLDER_WORDS}))?"
    r"(?:\s*,?\s+(?:por\s+favor|please|porfa))?[\s.!?]*$",
    re.IGNORECASE,
)


def _pdf_summary_request(text: str) -> re.Match[str] | None:
    """Match one summary or reading request of a named PDF in the known folders."""

    found = _PDF_SUMMARY_REQUEST.match(text.strip())
    if found is None:
        return None
    name = found.group("name").strip("\"'").rstrip(".!?,")
    if not name or name.lower() in {"todo", "esto", "eso", "this", "that", "it", "pagina", "página", "page"}:
        return None
    if re.fullmatch(r"[^\\/:*?\"<>|]+\.pdf", name, re.IGNORECASE) is None:
        noun = found.group("noun")
        if noun is None or noun.strip().lower() != "pdf" or "." in name:
            return None
    return found


def _file_trash_request(text: str) -> re.Match[str] | None:
    """Match one literal deletion of a named file (or, FILES1603 H0327 «Borra la
    carpeta CarterTest del escritorio», a named folder) in the person's known folders."""

    found = _FILE_TRASH_REQUEST.match(text.strip())
    if found is None:
        return None
    name = found.group("name").strip("\"'").rstrip(".!?,")
    if not name or name.lower() in {"todo", "todos", "everything", "all", "eso", "esto", "it", "that", "this"}:
        return None
    looks_like_file = re.fullmatch(r"[^\\/:*?\"<>|]+\.[a-z0-9]{1,8}", name, re.IGNORECASE) is not None
    if not looks_like_file and found.group("noun") is None:
        return None
    return found


# FILES1705 H0334 «crea un archivo de texto con los 5 procesos que mas memoria
# usan»: a text file whose content is a process listing read from this
# machine — system.process.list (limit, sort) then filesystem.write.text
# with the listing projected deterministically from the verified result.
_PROCESS_REPORT_FILE_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:crea|crear|creame|genera|generame|generar|guarda|guardame|guardar|"
    r"escribe|escribime|escribir|arma|armame|make|create|save|write|generate)(?:me)?\s+"
    r"(?:(?:un|una|a|el|the)\s+)?(?:(?:text|txt)\s+)?(?:archivo|fichero|file)(?:\s+(?:de\s+texto|txt|text))?"
    r"(?:\s+(?:llamad[oa]|named|called)\s+(?P<name>[^\s\"']+))?\s+"
    r"(?:con|que\s+(?:tenga|liste|contenga|muestre)|with|listing|containing|of)\s+"
    r"(?P<desc>(?:(?:los|las|the|mis|my)\s+)?(?:(?P<n>\d{1,2})\s+)?(?:procesos|processes)\s+"
    r"(?:que\s+mas\s+(?P<res_a>memoria|cpu|procesador|ram)\s+(?:usan|consumen|ocupan|gastan)|"
    r"que\s+(?:usan|consumen|ocupan|gastan)\s+mas\s+(?P<res_b>memoria|cpu|procesador|ram)|"
    r"(?:that\s+)?(?:use|using|consume|consuming)\s+(?:the\s+)?most\s+(?P<res_c>memory|cpu|ram)|"
    r"with\s+(?:the\s+)?(?:highest|most)\s+(?P<res_d>memory|cpu|ram)(?:\s+usage)?))"
    r"(?:\s*,?\s+(?:por\s+favor|please))?[\s.!?]*$",
    re.IGNORECASE,
)


def process_report_file_request(folded: str) -> dict[str, object] | None:
    """Read one request for a text file listing the top processes by memory or CPU."""

    found = _PROCESS_REPORT_FILE_REQUEST.match(_strip_request_envelope(folded).strip())
    if found is None:
        return None
    resource = next(
        (found.group(key) for key in ("res_a", "res_b", "res_c", "res_d") if found.group(key)),
        "",
    ).lower()
    sort = "cpu" if resource in {"cpu", "procesador"} else "memory"
    report: dict[str, object] = {"sort": sort, "resource_word": resource}
    if found.group("n"):
        limit = int(found.group("n"))
        if not 1 <= limit <= 50:
            return None
        report["limit"] = limit
    if found.group("name"):
        report["name"] = found.group("name")
    # The file header repeats the request's own description of the listing
    # («los 5 procesos que mas memoria usan»), so every header token is evidence.
    report["description"] = " ".join(found.group("desc").split())
    return report


def _file_creation_request(text: str) -> re.Match[str] | None:
    """Match one literal file creation with a name and its content."""

    return _FILE_CREATION_REQUEST.match(text.strip())


_KNOWN_FOLDER_PATH = re.compile(
    r"^\s*(?:%USERPROFILE%|%HOMEPATH%|~|[A-Za-z]:[\\/]+Users[\\/]+[^\\/:*?\"<>|\r\n]+)?[\\/]*"
    r"(?P<folder>Desktop|Escritorio|Documents|Documentos|Downloads|Descargas)"
    r"(?P<rest>(?:[\\/][^\\/:*?\"<>|\r\n]+)+)\s*$",
    re.IGNORECASE,
)


_TEXT_FILE_EXTENSIONS = frozenset({
    ".txt", ".md", ".markdown", ".rst", ".py", ".json", ".jsonl", ".csv", ".tsv", ".log", ".ini", ".cfg", ".conf",
    ".toml", ".yaml", ".yml", ".xml", ".html", ".htm", ".css", ".js", ".ts", ".cs", ".ps1", ".bat", ".cmd", ".sh",
    ".sql", ".java", ".c", ".h", ".cpp", ".hpp", ".go", ".rs", ".rb", ".php", ".tex", ".bib", ".env", ".gitignore",
})


def known_folder_file_path(text: str) -> tuple[str, dict[str, object]] | None:
    """REOPEN1957 H0299 «%USERPROFILE%\\Desktop\\…\\ROADMAP.md»: a pasted path
    under a known folder names the file to read. Returns the reading
    operation and its arguments (a PDF goes to the PDF reader); a path
    outside the known folders, or a file that is not text, abstains and
    the pasted path keeps its honest question."""

    match = _KNOWN_FOLDER_PATH.match(text.strip())
    if match is None or len(text) > 512:
        return None
    folder = _KNOWN_FOLDER_ENUM.get(_fold(match.group("folder")))
    parts = [part for part in re.split(r"[\\/]+", match.group("rest")) if part]
    if folder is None or not parts or any(part in {".", ".."} for part in parts):
        return None
    name = parts[-1].strip()
    extension = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name.strip(".") else ""
    subdirectory = "\\".join(parts[:-1]) or None
    if extension == ".pdf":
        return "document.pdf.read", {"fileName": name, "folder": folder}
    if extension not in _TEXT_FILE_EXTENSIONS:
        return None
    arguments: dict[str, object] = {"fileName": name, "folder": folder}
    if subdirectory is not None:
        arguments["subdirectory"] = subdirectory
    return "document.text.read", arguments


# M151 (DEV-F v4s F-w18-t2 «Yeah, that's the one, give us the gist of it» after «Downloads is open; I can see
# «council_tax_2026-27.pdf»…» → file.open; F-w22-t3 «the signed one» after «There are two: lease_2026_signed.pdf and
# lease_2026_draft.pdf. Which one?» → file.open; F-w24-t3 «la de pisos»; DEV-G v4s G-w40-t2 «abre el segundo» after
# «Encontré dos: «cotizacion_mudanza.pdf» en Descargas y «cotizacion_mudanza_v2.pdf» en Documentos.» → the latest
# file; G-w40-t3 «resumemelo en corto», G-w44-t5 «qué dice»; DEV-H v4s H-w23-t3 «read it», H-w32-t2 «y de qué trata?
# resumímelo así nomás»): the file BAXY's last reply named by its file name is the one the person means — the only one
# it named, or the one of those it listed that the person picks by its place in the list or by a word of its name only.
# What is done with it is what the person asks: what it says (or, after the person asked for it, the pick alone) is
# read; «abre el segundo» opens it.
_NAMED_FILE_EXTENSIONS = frozenset({
    *(extension.lstrip(".") for extension in _TEXT_FILE_EXTENSIONS),
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp", "rtf", "zip", "rar", "7z",
    "jpg", "jpeg", "png", "gif", "bmp", "webp", "mp3", "mp4", "wav", "mkv", "avi", "mov", "exe", "msi",
})
_FILE_NAMED_IN_REPLY = re.compile(
    r"[«“\"](?P<quoted>[^«»“”\"\n]{1,200}?\.(?P<quoted_extension>[A-Za-z0-9]{1,5}))[»”\"]"
    r"|(?<![\w.\\/-])(?P<bare>\w[\w.()\-]{0,199}\.(?P<bare_extension>[A-Za-z0-9]{1,5}))(?!\w)",
)
# What the file says, asked: read it, summarize it, what it says or is about, its gist. Folded. Not «what's in there»
# nor «qué contiene»: after a folder opened those ask what the folder holds.
_ASKS_WHAT_IT_SAYS = (
    r"\b(?:lee(?:me|lo|la|melo|mela|r|rlo|rla|rmelo|rmela)?|resum\w*|que\s+(?:dice|pone|trae)|"
    r"de\s+que\s+(?:trata|va|se\s+trata|habla)|read|summar\w*|sum\s+(?:it\s+|that\s+|this\s+)?up|gist|"
    r"tl\s*;?\s*dr|rundown|what\s+(?:does|did)\s+(?:it|that|this)\s+say|what\s+(?:it|that|this)\s+says|"
    r"what(?:'s|s|\s+is)\s+(?:it|that|this)\s+about)\b"
)
_ASKS_TO_OPEN = r"\b(?:abr[ei](?:me|lo|la|melo|mela|los|las)?|abrir(?:lo|la)?|open)\b"
# A file of its own (a folder, the newest one, another one) is not the one BAXY named.
_ANOTHER_FILE_SAID = (
    rf"\b(?:{_KNOWN_FOLDER_WORDS}|ultim[oa]s?|latest|newest|last|recent\w*|mas\s+nuev[oa]|otr[oa]s?|other|another|"
    r"tod[oa]s|ambos|ambas|both|los\s+dos|las\s+dos)\b"
)
_PLACE_IN_THE_LIST = (
    (r"\b(?:primer[oa]?|first|1st)\b", 0),
    (r"\b(?:segund[oa]|second|2nd)\b", 1),
    (r"\b(?:tercer[oa]?|third|3rd)\b", 2),
    (r"\b(?:cuart[oa]|fourth|4th)\b", 3),
)
_NOT_A_DISTINCTIVE_WORD = frozenset({
    "the", "one", "that", "this", "file", "pdf", "doc", "please", "yeah", "yes", "and", "with",
    "que", "uno", "una", "ese", "esa", "este", "esta", "archivo", "fichero", "documento", "del", "las", "los", "por",
    "favor", "porfa", "pues", "con", "sin",
})


class NamedFileMeant(NamedTuple):
    """M151: what is done with the file BAXY named («read» or «open»), its name as written, and the person's words
    that ask it (this message, or the request a pick answers)."""

    act: str
    name: str
    request: str


def files_named_in_reply(reply: str) -> tuple[str, ...]:
    """The file names a reply of BAXY's wrote (with a file's extension), each once, in the order written."""

    names: list[str] = []
    for found in _FILE_NAMED_IN_REPLY.finditer(reply or ""):
        name = (found.group("quoted") or found.group("bare") or "").strip()
        extension = (found.group("quoted_extension") or found.group("bare_extension") or "").lower()
        if name and extension in _NAMED_FILE_EXTENSIONS and _fold(name) not in {_fold(seen) for seen in names}:
            names.append(name)
    return tuple(names)


def _picked_file(folded: str, names: tuple[str, ...]) -> str | None:
    """The one of ``names`` the message picks by its place in the list or by words only its name has, or None."""

    places = {index for pattern, index in _PLACE_IN_THE_LIST if _has(folded, pattern)}
    by_place = names[next(iter(places))] if len(places) == 1 and next(iter(places)) < len(names) else None
    if len(places) > 1 or (places and by_place is None):
        return None
    words = [
        word for word in re.findall(r"[a-z0-9]+", folded)
        if len(word) >= 3 and word not in _NOT_A_DISTINCTIVE_WORD
    ]
    pieces = {
        name: {piece for piece in re.split(r"[^a-z0-9]+", _fold(name.rsplit(".", 1)[0])) if piece}
        for name in names
    }

    def has(name: str, word: str) -> bool:
        return any(word in {piece, piece + "s", piece + "es"} or piece in {word + "s", word + "es"} for piece in pieces[name])

    by_word: set[str] = set()
    for word in words:
        holders = [name for name in names if has(name, word)]
        if len(holders) == 1:
            by_word.add(holders[0])
    if len(by_word) > 1 or (by_place is not None and by_word and by_word != {by_place}):
        return None
    return by_place or (next(iter(by_word)) if by_word else None)


def named_file_meant(message: str, last_reply: str, request_before: str = "") -> NamedFileMeant | None:
    """M151: the file BAXY's last reply named that ``message`` means, and what to do with it, or None.

    One name in the reply: the message asks what it says («read it», «qué dice», «give us the gist of it»). Several:
    the message picks one by its place («abre el segundo») or by a word only its name has («the signed one», «la de
    pisos»), and asks to open it, to read it, or nothing more after ``request_before`` (the person's message BAXY's
    reply answered) asked to read or summarize. None when the message names a file, a folder, the newest or another
    one, asks to open and to read at once, or picks none."""

    folded = _fold(message)
    names = files_named_in_reply(last_reply)
    if not names or files_named_in_reply(message) or _has(folded, _ANOTHER_FILE_SAID):
        return None
    reads, opens = _has(folded, _ASKS_WHAT_IT_SAYS), _has(folded, _ASKS_TO_OPEN)
    if reads and opens:
        return None
    if len(names) == 1:
        return NamedFileMeant("read", names[0], message.strip()) if reads else None
    picked = _picked_file(folded, names)
    if picked is None:
        return None
    if opens:
        return NamedFileMeant("open", picked, message.strip())
    if reads:
        return NamedFileMeant("read", picked, message.strip())
    before = _fold(request_before)
    if _has(before, _ASKS_WHAT_IT_SAYS) and not _has(before, _ASKS_TO_OPEN):
        return NamedFileMeant("read", picked, request_before.strip())
    return None


def named_file_operation(meant: NamedFileMeant) -> str | None:
    """M151: the operation that does what is asked with the file: its extension decides the reader (a PDF the PDF
    reader, a text file the text reader, as ``known_folder_file_path``); any file opens. None for a file no reader
    reads (an Office document, an image)."""

    if meant.act == "open":
        return "file.open"
    extension = "." + meant.name.rsplit(".", 1)[-1].lower() if "." in meant.name else ""
    if extension == ".pdf":
        return "document.pdf.read"
    return "document.text.read" if extension in _TEXT_FILE_EXTENSIONS else None


_FOLDER_SAID_AS = {
    "es": {"desktop": "Escritorio", "documents": "Documentos", "downloads": "Descargas"},
    "en": {"desktop": "Desktop", "documents": "Documents", "downloads": "Downloads"},
}


def named_file_request(meant: NamedFileMeant, folder: str, language: str) -> str:
    """M151: the request the arguments step reads. A reading keeps the person's words with the file named after them
    (the reader finds its folder in the conversation, M127); an opening says the file and its folder as
    ``open_named_file_request`` reads them."""

    if meant.act != "open":
        return f"{meant.request.rstrip()} («{meant.name}»)"
    said = _FOLDER_SAID_AS["en" if language == "en" else "es"][folder]
    return f"Open {meant.name} from {said}." if language == "en" else f"Abre {meant.name} de {said}."


def _current_directory_file_count(folded: str) -> bool:
    """FILES1437 «dime cuántos archivos .py hay en el directorio actual»: a
    file count over «the current directory», which BAXY does not have."""

    return (
        _has(folded, r"\b(?:cuantos|cuantas|how many|count|cuenta|conta|contame|cuentame)\b")
        and _has(folded, r"\b(?:archivos?|ficheros?|files?)\b")
        and _has(
            folded,
            r"\b(?:directorio|carpeta|folder|directory)\s+(?:actual|current|de trabajo|en (?:el|la) que estoy)\b"
            r"|\b(?:current|working|present)\s+(?:directory|folder)\b|\bcwd\b",
        )
        and not _has(folded, r"\b(?:escritorio|desktop|descargas|downloads|documentos|documents)\b")
    )


_DUPLICATE_FILES = r"\b(?:duplicad[oa]s?|repetid[oa]s?|duplicates?)\b"


_KNOWN_FOLDER_LISTING = (
    r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
    r"(?:(?:lista|listame|list|enumera|enumerame|mostrame|muestrame|muestra|show me|show|"
    r"decime|dime|contame|cuentame|tell me)\s+(?:me\s+)?(?:que\s+|what\s+)?(?:los|las|the|mis|my|todos los|all the|all)?\s*"
    r"(?:archivos|ficheros|files|documentos|cosas|things)\s+(?:(?:que\s+)?(?:hay|tengo|are|is)\s+)?"
    r"(?:de|del|en|in|on|of|from)\s+|"
    r"(?:que|what)\s+(?:(?:archivos?|ficheros?|files?|cosas?|things?)\s+)?"
    r"(?:hay|tengo|is|is there|are|are there|do i have|i have)\s+(?:en|in|on)\s+)"
    r"(?:mi|el|la|my|the)?\s*(?:carpeta\s+(?:de\s+)?|folder\s+)?"
    r"(?P<folder>escritorio|desktop|descargas|downloads|documentos|documents)"
    r"(?:\s+(?:folder|carpeta))?[\s?!.]*$"
)


_KNOWN_FOLDER_RECENT = (
    r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
    r"(?:(?:cuenta|conta|count)\s+(?:los\s+|the\s+)?(?:archivos|ficheros|files)\s+(?:de|del|en|in|on|of)\s+"
    r"(?:mi|el|la|my|the)?\s*(?P<folder_a>" + _KNOWN_FOLDER_WORDS + r")\s+(?:y|and)\s+)?"
    r"(?:lista|listame|list|mostrame|muestrame|muestra|show me|show|dame|give me|decime|dime|tell me)\s+(?:me\s+)?"
    r"(?:los|las|the)?\s*(?P<n>[1-9]|1[0-9]|20)\s+(?:(?:archivos|ficheros|files|entradas|entries)\s+)?"
    r"(?:mas|most)\s+(?:recientes?|nuevos?|recent|newest)(?:\s+(?:archivos|ficheros|files|entradas|entries))?"
    r"(?:\s+(?:de|del|en|in|on|of)\s+(?:mi|el|la|my|the)?\s*(?P<folder_b>" + _KNOWN_FOLDER_WORDS + r"))?[\s?!.]*$"
)


def _known_folder_recent_listing(text: str) -> tuple[str, int] | None:
    """FILES1433 «cuenta los archivos en el escritorio y lista los 5 mas recientes»,
    «listá los 5 archivos más recientes del escritorio»: (folder enum, count)."""

    folded = _fold(text)
    match = re.match(_KNOWN_FOLDER_RECENT, folded)
    if match is None:
        return None
    folder = match.group("folder_a") or match.group("folder_b")
    if folder is None or (match.group("folder_a") and match.group("folder_b")
                          and match.group("folder_a") != match.group("folder_b")):
        return None
    enum = _KNOWN_FOLDER_ENUM.get(folder)
    return (enum, int(match.group("n"))) if enum else None


def _known_folder_listing_request(text: str) -> str | None:
    """FILES1425 «lista los archivos del escritorio», «qué hay en Descargas»:
    the known-folder enum of a whole-folder listing request, else None."""

    folded = _fold(text)
    match = re.match(_KNOWN_FOLDER_LISTING, folded)
    if match is None:
        return None
    return _KNOWN_FOLDER_ENUM.get(match.group("folder"))


# M143 (DEV-H v4o H-s081 «abreme descargas y el ultimo archivo que baje» → only the latest file opened, where the
# isolated decider opened the folder and then the file): a known folder that is itself what is opened, joined by «y» /
# «and» to the latest file, is a second thing opened, not where the file is; the latest-file reader leaves the turn
# to the decider. «abre el último archivo de descargas» still names only where the file is. Folded.
_FOLDER_OPENED_BESIDE_THE_FILE = (
    rf"\b{_OPEN}\s+(?:(?:me|up)\s+)?(?:(?:la\s+)?carpeta\s+(?:de\s+)?|(?:mi|my|the|el|la)\s+)?{_KNOWN_FOLDER_WORDS}"
    r"(?:\s+(?:folder|carpeta))?\s*,?\s+(?:y|and)\s+(?:(?:luego|despues|then|tambien|also)\s+)?"
    r"(?:(?:el|la|the|my|mi)\s+)?(?:ultimo|ultima|latest|last|most\s+recent|mas\s+reciente|newest)\b"
)


def _review_file_and_game_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
) -> None:
    """Append closed file-discovery and explicitly Steam-scoped game effects."""

    if (
        _head_is(head, _OPEN)
        and not _has(folded, _FOLDER_OPENED_BESIDE_THE_FILE)
        and _has(folded, r"\b(?:archivo|file)\b")
        and _has(
            folded,
            r"\b(?:ultimo|ultima|mas reciente|latest|most recent|last)\b",
        )
        and _has(
            folded,
            r"\b(?:descargas|downloads?|escritorio|desktop|documentos?|"
            r"documents?|imagenes|pictures|descargue|downloaded)\b",
        )
    ):
        _append(
            matches,
            folded,
            "filesystem.file.open.latest",
            rf"\b{_OPEN}\b",
        )
    if _has(folded, r"\bhash\b") and _has(folded, r"\b(?:archivo|file)\b"):
        _append(matches, folded, "filesystem.hash", r"\bhash\b")
    if (
        _head_is(head, r"(?:que|cuales|what|which)")
        and _has(folded, r"\b(?:archivos?|files?)\b")
        and _has(folded, r"\b(?:carpeta|folder|directorio|directory)\b")
        and not _has(folded, r"\b(?:busca|buscar|search|find|hash)\b")
    ):
        _append(
            matches,
            folded,
            "filesystem.list",
            r"\b(?:archivos?|files?)\b",
        )
    if _literal_known_file_search(folded) is not None or (
        _head_is(head, _SEARCH)
        and _has(folded, r"\b(?:archivos?|files?)\b")
        and _has(
            folded,
            r"\b(?:contengan?|contiene|containing|contain|llamad[oa]s?|named)\b",
        )
        and not _has(
            folded,
            r"\b(?:google|bing|web|internet|online)\b",
        )
    ):
        _append(
            matches,
            folded,
            "filesystem.known.search",
            rf"\b{_SEARCH}\b",
        )
    if (
        _head_is(head, _OPEN)
        and _has(folded, r"\b(?:biblioteca|library)\b")
        and _has(folded, r"\bsteam\b")
    ):
        _append(
            matches,
            folded,
            "game.catalog.list",
            rf"\b{_OPEN}\b",
        )
    if (
        _head_is(head, rf"(?:{_OPEN}|lanza|launch|ejecuta|run)")
        and _has(folded, r"\b(?:desde|en|on|from)\s+steam\b")
        and _has(
            folded,
            rf"^[¿?¡!\s]*(?:{_OPEN}|lanza|launch|ejecuta|run)\b\s+\S.+",
        )
    ):
        _append(
            matches,
            folded,
            "game.launch",
            rf"\b(?:{_OPEN}|lanza|launch|ejecuta|run)\b",
        )


_ZIP_MISSION_FOLDER = "Nueva carpeta"


_ZIP_MISSION_FILE = "Nuevo documento de texto.txt"


def folder_txt_zip_open_mission(text: str) -> str | None:
    """REOPEN1957 H0542 «Crea una carpeta en el escritorio, mete un txt dentro,
    comprímela y luego abre el zip»: the known folder of a four-step mission
    (create the folder, put a text file in it, zip it, open the zip). The
    folder and the file are unnamed, so they take Windows' own default
    names («Nueva carpeta», «Nuevo documento de texto.txt»)."""

    folded = _strip_request_envelope(_fold(text)).strip()
    if _is_negative_effect_clause(folded):
        return None
    match = re.search(
        # ZIP (typed tandas): «armá una carpeta en el escritorio con un txt, comprimila y
        # abrí el zip», «make a folder on the desktop with a txt inside, zip it and open the zip».
        rf"\b(?:crea|crear|creame|create|make|haz|hace|arma|armar|armame)\s+(?:una\s+|a\s+)?(?:carpeta|folder|directorio|directory)"
        rf"(?:\s+(?:nueva|new))?\s+(?:en|on|in)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder>{_KNOWN_FOLDER_WORDS})\b",
        folded,
    )
    if match is None:
        return None
    if not _has(folded, r"\b(?:mete|meter|pone|pon|poner|crea|crear|guarda|put|add|create|con|with)\b.{0,20}\b(?:txt|archivo\s+de\s+texto|text\s+file|archivo\s+txt)\b"):
        return None
    if not _has(folded, r"\b(?:comprim\w+|zip\w*|compress\w*)\b"):
        return None
    if not _has(folded, r"\b(?:abre|abri|abrir|abrilo|abrila|open)\b.{0,12}\b(?:zip|comprimid[oa]|archive)\b") and not _has(
        folded, r"\b(?:comprim\w+|zip\w*|compress\w*)\b.{0,12}\b(?:y|and|,)?\s*(?:abrila|abrilo|abrela|abrelo|open\s+it)\s*$"
    ):
        return None
    return _KNOWN_FOLDER_ENUM.get(match.group("folder"))


def open_named_file_request(text: str) -> tuple[str, str] | None:
    """«abre el zip Nueva carpeta.zip del escritorio», «abrí informe.pdf de
    documentos» → (known folder, file name with extension)."""

    raw = _strip_request_envelope(str(text).strip()).rstrip(".!?")
    folded = _fold(raw)
    if _is_negative_effect_clause(folded) or folder_txt_zip_open_mission(text) is not None:
        return None
    match = re.match(
        rf"^[¿?¡!\s]*(?:[aá]br[eií](?:me|lo|la)?|abrir|open)\s+"
        rf"(?:(?:el|la|the|a)\s+)?(?:(?:archivo|file|fichero|zip|pdf|documento|document|imagen|image|foto|photo)\s+)?"
        rf"(?P<name>[^\s/\\:*?\"<>|]+(?:\s+[^\s/\\:*?\"<>|]+){{0,4}}?\.[a-z0-9]{{1,5}})\s+"
        # M111 (DEV-F v4d F-s025 «… presupuesto_finca.xlsx q esta en documentos»): where the file is, said as a clause.
        rf"(?:(?:q|que)\s+(?:est[aá]|tengo|guard[eé])\s+en|that'?s\s+in|which\s+is\s+in|"
        rf"del|de\s+la|de|from|in|en|on)\s+(?:(?:el|la|mis|mi|my|the)\s+)?(?P<folder>{_KNOWN_FOLDER_WORDS}|imagenes|pictures)\b",
        raw,
        re.IGNORECASE,
    )
    if match is None:
        return None
    folder = _KNOWN_FOLDER_ENUM.get(_fold(match.group("folder")), "pictures")
    return (folder, match.group("name").strip())


def _office_document_roundtrip_intent(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """Create one named Office document and read its verified identity."""

    if not {"office.document.create", "office.document.read"} <= available:
        return None
    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:crea|crear|create|make)\s+"
            r"(?:(?:un|una|a)\s+)?"
            r"(?:(?:documento|document)\s+)?"
            r"(?:word|excel|documento|document|hoja de calculo|spreadsheet)\b"
            r".{0,80}\b(?:llamad[oa]|named|called)\b\s+"
            r"[^,;.!?]{1,120}?\s+(?:y|and)\s+"
            r"(?:lee|leer|read)\s+"
            r"(?:(?:ese|este|el|that|this|the)\s+)?"
            r"(?:mismo|same)\s+(?:documento|document)\b"
            r"(?:\s+(?:que\s+acabas\s+de\s+crear|you\s+just\s+created))?"
            r"[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    evidence = request.group(0).strip(" ,;:-")[:240]
    return EffectIntent(
        ("office.document.create", "office.document.read"),
        (evidence, evidence),
    )
