"""Listings and reads the composer receives as projections (known folders, games, pages, PDFs, browser tabs,
YouTube playback), their last-resort finals and the checks of a reply that quotes them.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .semantic import answer_evidence as semantic_answer_evidence
from .semantic.request import fold as _reading_fold
from .device_facts import _KNOWN_FOLDER_LABELS, _LISTING_SHOWN_NAMES
from .search_report import _REPORT_COUNT, _REPORT_COUNT_WORDS, _REPORT_NUMBER


def _project_known_listing(observed: dict, language: str) -> dict:
    """FILES1425 «lista los archivos del escritorio»: the receipt carries up to a
    hundred entries with sizes and dates; the person needs the count and some
    names, exactly as listed. Folders come first, as the provider ordered them."""

    entries = observed.get("entries")
    names = [
        str(entry.get("name")).strip()
        for entry in (entries if isinstance(entries, list) else [])
        if isinstance(entry, dict) and isinstance(entry.get("name"), str) and entry.get("name").strip()
    ]
    shown = names[:_LISTING_SHOWN_NAMES]
    folder = observed.get("folder")
    labels = _KNOWN_FOLDER_LABELS.get(str(folder), (str(folder), str(folder)))
    count = observed.get("count") if type(observed.get("count")) is int else len(names)
    projected: dict = {
        "folder": labels[1 if language == "en" else 0],
        "count": count,
        "names": shown,
        "shownNames": len(shown),
        "moreNotShown": max(count - len(shown), 0),
    }
    for key in ("fileCount", "folderCount"):
        if type(observed.get(key)) is int:
            projected[key] = observed[key]
    if observed.get("order") == "recent":
        # FILES1433: the person asked for the newest entries; say so.
        projected["newestFirst"] = True
    return projected


def _project_game_listing(observed: dict, language: str) -> dict:
    """GAMES1531 «Ver la biblioteca de Steam»: the receipt carries app ids,
    manifest hashes and byte counts; the person needs how many games are
    installed and their names exactly as the manifests name them."""

    entries = observed.get("games")
    names = [
        str(entry.get("name")).strip()
        for entry in (entries if isinstance(entries, list) else [])
        if isinstance(entry, dict) and isinstance(entry.get("name"), str) and entry.get("name").strip()
    ]
    shown = names[:_LISTING_SHOWN_NAMES]
    count = observed.get("count") if type(observed.get("count")) is int else len(names)
    return {
        "library": "Steam",
        "count": count,
        "names": shown,
        "shownNames": len(shown),
        "moreNotShown": max(count - len(shown), 0),
    }


_PAGE_LEAD_CHARACTERS = 600
# Semilla fix2: a results page read for a listing («un top 3») lists its items below the engine's own menus.
_PAGE_LISTING_CHARACTERS = 2400


def _project_page_read(observed: dict, language: str, characters: int | None = None) -> dict:
    """WEB1539 «resumime esta página»: the receipt carries up to 12 000 characters
    of visible text; the composer receives the title, the site and the
    beginning of the text exactly as read, cut at a sentence end."""

    limit = characters or _PAGE_LEAD_CHARACTERS
    text = observed.get("text") if isinstance(observed.get("text"), str) else ""
    text = re.sub(r"[ \t]+", " ", text).strip()
    lead = text[:limit]
    if len(text) > limit:
        cut = max(lead.rfind(". "), lead.rfind(".\n"), lead.rfind("! "), lead.rfind("? "))
        if cut >= 120:
            lead = lead[: cut + 1]
    url = observed.get("url") if isinstance(observed.get("url"), str) else ""
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        host = ""
    projected: dict = {
        "title": (observed.get("title") if isinstance(observed.get("title"), str) else "").strip(),
        "site": host,
        "lead": lead.strip(),
        "moreNotShown": len(text) > len(lead) or observed.get("truncated") is True,
    }
    return projected


# 450 characters cut at a sentence end: the model quotes the whole lead, so
# the lead itself is kept to the opening of the text.
_PDF_LEAD_CHARACTERS = 450
_PDF_HEADINGS = 6


def _project_pdf_read(observed: dict, language: str) -> dict:
    """PDF1689 «resumime informe.pdf»: the receipt carries up to 12 000 characters
    of extracted text; the composer receives the document name, its page count,
    its heading-like lines and the beginning of its text exactly as read."""

    text = observed.get("text") if isinstance(observed.get("text"), str) else ""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    headings: list[str] = []
    for line in lines[1:]:
        # A heading: short, no sentence end, numbered or capitalised, with words.
        if (
            8 <= len(line) <= 72
            and not line.endswith((".", ",", ";", ":"))
            and ":" not in line
            and sum(ch.isalpha() for ch in line) >= 6
            and (re.match(r"^\d{1,2}[.)]?\s+\S", line) or line[:1].isupper())
            and len(line.split()) <= 9
        ):
            headings.append(line)
        if len(headings) >= _PDF_HEADINGS:
            break
    flat = re.sub(r"\s+", " ", text).strip()
    lead = flat[:_PDF_LEAD_CHARACTERS]
    if len(flat) > _PDF_LEAD_CHARACTERS:
        # A sentence end, never the dot of a numbered heading («2. Agua y riego»).
        ends = [m.end() - 1 for m in re.finditer(r"(?<!\d)[.!?] ", lead)]
        cut = ends[-1] if ends else -1
        if cut >= 120:
            lead = lead[: cut + 1]
    pages = observed.get("pages") if type(observed.get("pages")) is int else None
    lines_read = observed.get("lines") if type(observed.get("lines")) is int else None
    projected: dict = {
        "document": (observed.get("reviewLabel") if isinstance(observed.get("reviewLabel"), str) else "").strip(),
        "pages": pages,
        **({"lines": lines_read} if pages is None and lines_read is not None else {}),
        "hasText": bool(flat),
        "headings": headings,
        "lead": lead.strip(),
        "moreNotShown": len(flat) > len(lead) or observed.get("truncated") is True,
    }
    return projected


def _pdf_read_in_payload(payload: dict) -> dict | None:
    """The projected PDF («seen» with a lead) of a verified document.pdf.read."""

    if payload.get("operation") not in {"document.pdf.read", "document.text.read"}:
        return None
    seen = payload.get("seen")
    if isinstance(seen, dict) and isinstance(seen.get("lead"), str):
        return seen
    return None


def _pdf_read_quote_defect(text: str, seen: dict) -> str:
    """Every quoted passage must be in the lead, a heading or the name as read;
    a number in the prose must be in the lead, a heading or the page count."""

    lead = re.sub(r"\s+", " ", _reading_fold(str(seen.get("lead") or "")))
    headings = [re.sub(r"\s+", " ", _reading_fold(str(h))) for h in (seen.get("headings") or [])]
    name = re.sub(r"\s+", " ", _reading_fold(str(seen.get("document") or "")))
    pages = str(seen.get("pages")) if type(seen.get("pages")) is int else str(seen.get("lines")) if type(seen.get("lines")) is int else ""
    if not seen.get("hasText"):
        return ""
    quoted_any = False
    for quoted in re.findall(r'[«"“]([^»"”]{1,4096})[»"”]', text):
        candidate = re.sub(r"\s+", " ", _reading_fold(quoted.strip().rstrip(".,;:…"))).strip()
        if not candidate or candidate == name:
            continue
        if any(candidate == h or candidate in h for h in headings):
            continue
        quoted_any = quoted_any or candidate in lead
        if candidate not in lead:
            return "pdf_unquoted_passage"
    if not quoted_any:
        return "pdf_missing_quote"
    prose = re.sub(r'[«"“][^»"”]{1,4096}[»"”]', " ", text)
    for number in re.findall(r"(?<![\w.-])\d+(?![\w.-])", prose):
        if number != pages and number not in lead and not any(number in h for h in headings) and number not in name:
            return "pdf_unread_number"
    return ""


def _written_file_after_listing(payload: dict) -> str | None:
    """The name of a file written by a completed filesystem.write.text step that
    followed a system.process.list step (FILES1707), else None."""

    steps = payload.get("completedStepsInOrder")
    if not isinstance(steps, list) or len(steps) < 2:
        return None
    operations = [step.get("operation") for step in steps if isinstance(step, dict)]
    if "system.process.list" not in operations:
        return None
    for step in reversed(steps):
        if isinstance(step, dict) and step.get("operation") == "filesystem.write.text":
            result = step.get("resultAtThisStep")
            seen = result.get("seen") if isinstance(result, dict) else None
            name = seen.get("name") if isinstance(seen, dict) else None
            return name.strip() if isinstance(name, str) and name.strip() else None
    return None


# Owner's live check 2026-10-06 «cuántas pestañas tengo abiertas» (Opera GX): with five tabs, two of them YouTube
# videos, the reply said «tres videos de YouTube». A tab title names its site after its last dash or bar («Despacito -
# YouTube», «Inicio | BancoEstado», «Buscar • HBO Max»); a title that is only a site's name («YouTube») is that site's
# page too.
_TAB_TITLE_SITE = re.compile(r"\s[-–—|•·]\s+([^-–—|•·]{2,40})$")
# HBO Max writes «HBO\xa0Max» and wraps titles in bidi isolates (U+2068…U+2069): read as a person sees them.
_TAB_TITLE_INVISIBLE = re.compile("[‎‏⁦-⁩]")


def _tab_title(value: object) -> str:
    return " ".join(_TAB_TITLE_INVISIBLE.sub("", str(value or "")).replace("\xa0", " ").split())


def _tab_site(title: str) -> str:
    match = _TAB_TITLE_SITE.search(title.strip())
    site = match.group(1).strip() if match else ""
    return site if site and len(site.split()) <= 3 else ""


def _tab_site_counts(titles: list[str]) -> dict[str, int]:
    sites = {site for site in map(_tab_site, titles) if site}
    per_site: dict[str, int] = {}
    for title in titles:
        site = _tab_site(title) or (title if title in sites else "")
        if site:
            per_site[site] = per_site.get(site, 0) + 1
    return per_site


def _project_tab_listing(seen: dict) -> dict:
    """The person's tabs as the composer gets them: the count, the titles in order, the active one, and how many tabs
    each site holds when two or more share it — counted here from the tab strip, never left to the model."""

    tabs = [tab for tab in seen.get("tabs") or [] if isinstance(tab, dict)]
    titles = [_tab_title(tab.get("title")) for tab in tabs]
    count = seen.get("count") if type(seen.get("count")) is int else len(titles)
    per_site = _tab_site_counts(titles)
    projected: dict = {"tabCount": count, "titles": titles}
    active = next((title for tab, title in zip(tabs, titles) if tab.get("active") is True), "")
    if active:
        projected["activeTab"] = active
    shared = {site: number for site, number in per_site.items() if number >= 2}
    if shared:
        projected["tabsPerSite"] = shared
    if count > len(titles):
        projected["moreNotShown"] = count - len(titles)
    if isinstance(seen.get("browser"), str) and seen["browser"]:
        projected["browser"] = seen["browser"]
    return projected


def _tab_listing_fact_defect(text: str, payload: dict) -> str:
    """Every figure of a tab listing reply is one the listing gives: the tab count, a site's count, the rest after a
    site, or a number inside a title. «Tres videos de YouTube» over two is invented."""

    if payload.get("operation") != "browser.tabs.list":
        return ""
    seen = payload.get("seen")
    if not isinstance(seen, dict) or type(seen.get("tabCount")) is not int:
        return ""
    count = seen["tabCount"]
    titles = [title for title in seen.get("titles") or [] if isinstance(title, str)]
    per_site = seen.get("tabsPerSite") if isinstance(seen.get("tabsPerSite"), dict) else {}
    # One tab of a site, or none, is a count the titles show without a figure of their own.
    allowed = {0, 1, count, len(titles), *(n for n in per_site.values() if type(n) is int)}
    allowed |= {count - n for n in per_site.values() if type(n) is int}
    if type(seen.get("moreNotShown")) is int:
        allowed.add(seen["moreNotShown"])
    for title in titles:
        allowed |= {int(number) for number in re.findall(r"\d+", title) if len(number) <= 6}
        allowed |= {int(_REPORT_COUNT_WORDS[match["count"]]) for match in _REPORT_COUNT.finditer(_reading_fold(title))}
    without_titles = text
    for title in sorted(titles, key=len, reverse=True):
        if title:
            without_titles = without_titles.replace(title, " ")
    # A figure tied to a site («tres videos de YouTube», «2 pestañas de Gmail») is that site's own count.
    folded = _reading_fold(without_titles)
    for site, number in _tab_site_counts(titles).items():
        tied = re.compile(
            r"(?<![\w.,])(?P<n>\d+|" + "|".join(sorted(_REPORT_COUNT_WORDS, key=len, reverse=True))
            + r")\s+(?:[\w-]+\s+){0,3}?(?:de|del|en|of|on|from)\s+" + re.escape(_reading_fold(site)) + r"(?!\w)"
        )
        for match in tied.finditer(folded):
            said = match["n"]
            value = int(said) if said.isdigit() else int(_REPORT_COUNT_WORDS[said])
            if value != number:
                return "invented_number"
    for number in _REPORT_NUMBER.findall(without_titles):
        if number.isdigit() and int(number) not in allowed:
            return "invented_number"
    for match in _REPORT_COUNT.finditer(_reading_fold(without_titles)):
        if int(_REPORT_COUNT_WORDS[match["count"]]) not in allowed:
            return "invented_number"
    return ""


def _tab_listing_final(seen: dict, english: bool) -> str:
    """When every draft failed: the count and the titles, as read."""

    count = seen.get("tabCount")
    titles = [title for title in seen.get("titles") or [] if isinstance(title, str) and title]
    if type(count) is not int or not titles or any("«" in title or "»" in title for title in titles):
        return ""
    browser = seen.get("browser") if isinstance(seen.get("browser"), str) else ""
    shown = titles[:12]
    joiner = " and " if english else " y "
    listed = (", ".join(f"«{t}»" for t in shown[:-1]) + joiner + f"«{shown[-1]}»") if len(shown) > 1 else f"«{shown[0]}»"
    rest = count - len(shown)
    if english:
        where = f" in {browser}" if browser else ""
        noun = "tab" if count == 1 else "tabs"
        more = f", and {rest} more" if rest > 0 else ""
        return f"You have {count} {noun} open{where}: {listed}{more}."
    where = f" en {browser}" if browser else ""
    noun = "pestaña abierta" if count == 1 else "pestañas abiertas"
    more = f", y {rest} más" if rest > 0 else ""
    return f"Tienes {count} {noun}{where}: {listed}{more}."


def _closed_tabs_final(seen: dict, english: bool) -> str:
    """When every draft failed: how many tabs were closed and how many are left, as read back."""

    closed, left = seen.get("closedTabs"), seen.get("tabCount")
    if type(closed) is not int or type(left) is not int or closed < 1:
        return ""
    if english:
        return f"I closed {closed} {'tab' if closed == 1 else 'tabs'}; {left} {'is' if left == 1 else 'are'} left open."
    closed_noun = "pestaña" if closed == 1 else "pestañas"
    left_said = f"queda {left} abierta" if left == 1 else f"quedan {left} abiertas"
    return f"Cerré {closed} {closed_noun}; {left_said}."


def _page_read_final(seen: dict, english: bool) -> str:
    """Owner's live check 2026-10-06 «léeme lo que dice la página» (Opera GX): when every draft was vetoed the reply was
    only «Leí la página «GX Corner».». What the page says is told as read: its first real sentence, quoted."""

    title = str(seen.get("title") or "").strip()
    lead = str(seen.get("lead") or "")
    lines = [line.strip() for line in lead.splitlines() if "«" not in line and "»" not in line]
    # A sentence of the page (8 words or more, ended as a sentence), else its longest line of prose: menus and
    # section labels are short lines without an end.
    sentences = [line for line in lines if len(line.split()) >= 8 and line[-1:] in {".", "!", "?"}]
    prose = sorted((line for line in lines if len(line.split()) >= 6), key=len, reverse=True)
    sentence = sentences[0] if sentences else (prose[0] if prose else "")
    if not sentence:
        return ""
    if len(sentence) > 240:
        sentence = sentence[:240].rsplit(" ", 1)[0].rstrip(" ,;:")
    sentence = sentence.rstrip(".")
    named = f" «{title}»" if title and "«" not in title and "»" not in title and len(title) <= 120 else ""
    if english:
        return f"I read the page{named}. It says: «{sentence}»."
    return f"Leí la página{named}. Dice: «{sentence}»."


def _page_read_in_payload(payload: dict) -> dict | None:
    """The projected page («seen» with a lead) of a verified browser.page.read."""

    if payload.get("operation") != "browser.page.read":
        return None
    seen = payload.get("seen")
    if isinstance(seen, dict) and isinstance(seen.get("lead"), str):
        return seen
    return None


def _youtube_playback_in_payload(payload: dict) -> dict | None:
    """The projected «seen» of a verified media.play.youtube that is playing."""

    if payload.get("operation") != "media.play.youtube":
        return None
    if payload.get("verified") is not True or payload.get("succeeded") is not True:
        return None
    seen = payload.get("seen")
    if not isinstance(seen, dict) or seen.get("playbackStatus") != "playing":
        return None
    return seen


def _youtube_playback_defect(text: str, seen: dict) -> str:
    """MUSIC1553: every quoted passage must be the observed title (or the
    person's own query); a title the receipt did not observe is invented."""

    title = re.sub(r"\s+", " ", _reading_fold(str(seen.get("title") or "")))
    query = re.sub(r"\s+", " ", _reading_fold(str(seen.get("query") or "")))
    observed = bool(seen.get("titleObserved"))
    quoted_any = False
    for quoted in re.findall(r'[«"“]([^»"”]{1,512})[»"”]', text):
        quoted_any = True
        candidate = re.sub(r"\s+", " ", _reading_fold(quoted.strip().rstrip(".,;:…"))).strip()
        if candidate == query:
            continue
        if not observed or candidate != title:
            return "youtube_unobserved_title"
    if observed and not quoted_any:
        return "youtube_title_not_named"
    if "?" in text:
        return "youtube_question"
    return ""


def _page_read_quote_defect(text: str, seen: dict) -> str:
    """Every quoted passage must appear in the lead as read; a number must be in it too."""

    lead = _reading_fold(str(seen.get("lead") or ""))
    lead = re.sub(r"\s+", " ", lead)
    title = re.sub(r"\s+", " ", _reading_fold(str(seen.get("title") or "")))
    quoted_any = False
    for quoted in re.findall(r'[«"“]([^»"”]{1,4096})[»"”]', text):
        quoted_any = True
        candidate = re.sub(r"\s+", " ", _reading_fold(quoted.strip().rstrip(".,;:…"))).strip()
        if not candidate or candidate in lead or candidate == title:
            continue
        # Owner's live check 2026-10-06: a page's headline and its next line, quoted together and joined by a period
        # («…la serie Bayonetta. El presidente de PlatinumGames…»), are both on the page; each piece is checked.
        pieces = [
            re.sub(r"\s+", " ", piece.strip(" .,;:…")).strip()
            for piece in re.split(r"(?<=[.!?…])\s+|…", candidate)
        ]
        if not all(piece in lead for piece in pieces if piece):
            return "page_unquoted_passage"
    if not quoted_any:
        return "page_missing_quote"
    prose = re.sub(r'[«"“][^»"”]{1,4096}[»"”]', " ", text)
    for number in re.findall(r"(?<![\w.-])\d+(?![\w.-])", prose):
        if number not in lead and number not in title:
            return "page_unread_number"
    return ""


_LISTED_ITEM = re.compile(r"(?:^|(?<=\s))\d{1,2}[.)]\s+(?P<item>.+?)(?=\s+\d{1,2}[.)]\s|[.;:\n]|$)")


def _open_search_listing_defect(text: str, seen: dict, open_search: dict) -> str:
    """Review r10a finding 3 («Según Google, el top 3 es: 1. Sinners 2. Weapons 3. The Eyes» over a results page that
    named none of them): a reply over the search already open says only items the read page holds. Each numbered item,
    and each name the reply says outside quotes, must be in the lead as read, its title, the query or the site's name.
    "" when every one is; «page_unread_item» otherwise."""

    lead = re.sub(r"\s+", " ", _reading_fold(str(seen.get("lead") or "")))
    known = " ".join(
        re.sub(r"\s+", " ", _reading_fold(str(value or "")))
        for value in (seen.get("title"), open_search.get("query"), open_search.get("site"))
    )
    prose = re.sub(r'[«"“][^»"”]{1,4096}[»"”]', " ", text)

    def on_the_page(item: str) -> bool:
        folded = re.sub(r"\s+", " ", _reading_fold(item.strip(" .,;:…*_"))).strip()
        return not folded or folded in lead or folded in known

    for found in _LISTED_ITEM.finditer(prose):
        if not on_the_page(found.group("item")):
            return "page_unread_item"
    for name in semantic_answer_evidence.name_spans(prose, str(seen.get("lead") or "")):
        if not on_the_page(name):
            return "page_unread_item"
    return ""
