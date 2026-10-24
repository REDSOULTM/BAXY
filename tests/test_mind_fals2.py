"""Holdout v4's false claims (w6-fals2): what the mind's outcome line says of a read that holds only part of what it
read."""
import json

from baxy_mind.mind import _outcome

READ = {"status": "completed", "verification": "output_only"}


def test_a_page_of_a_file_is_told_read_in_part_with_its_lines_of_the_whole() -> None:
    # The holdout's case: pages up to line ~1,904 of 3,000 and «revisé todo el archivo y no apareció».
    page = {**READ, "observed": {"characters": 300_000, "totalLines": 3_000, "offset": 180_000, "fromLine": 1_801,
                                 "toLine": 1_904, "returnedCharacters": 10_400, "hasMore": True, "endReached": False,
                                 "readInPart": True, "text": "…"}}
    told = _outcome(json.dumps(page), read=True)
    assert told.startswith("lectura: sólo miró")
    assert "; leído en parte: líneas 1801–1904 de 3000, no llegó al final;" in told
    assert told.endswith("un «no está» vale sólo para lo leído")


def test_a_whole_read_says_nothing_of_parts() -> None:
    whole = {**READ, "observed": {"characters": 40, "totalLines": 4, "offset": 0, "fromLine": 1, "toLine": 4,
                                  "hasMore": False, "endReached": True, "text": "…"}}
    assert "en parte" not in _outcome(json.dumps(whole), read=True)


def test_a_web_page_a_search_and_a_log_read_in_part_say_how_much() -> None:
    web = {**READ, "observed": {"totalCharacters": 9_000, "offset": 0, "hasMore": True, "nextOffset": 4_000,
                                "endReached": False, "readInPart": True}}
    search = {**READ, "observed": {"mode": "content", "count": 0, "readInPart": True,
                                   "searchScope": {"filesScanned": 2_000, "scanLimitReached": True, "skippedNotText": 3,
                                                   "skippedTooLarge": 0, "skippedUnreadable": 1,
                                                   "timeLimitReached": False}}}
    log = {**READ, "observed": {"hours": 24, "readCap": 80, "eventsSeen": 80, "eventsShown": 20, "endReached": False,
                                "readInPart": True, "events": []}}
    assert "leído en parte: caracteres 1–4000 de 9000, no llegó al final" in _outcome(json.dumps(web), read=True)
    assert "leído en parte: 2000 archivos recorridos, 4 de ellos sin leer su texto;" in _outcome(
        json.dumps(search), read=True)
    assert "leído en parte: sólo los 80 eventos más recientes del registro, no llegó al final" in _outcome(
        json.dumps(log), read=True)


def test_a_listing_of_a_folders_top_level_says_what_it_did_not_open() -> None:
    # The holdout's «Sí, porque no había .bak» with three .bak files present: a top-level listing whose subfolders,
    # hidden entries and entries past those shown were not looked at.
    listing = {**READ, "observed": {"mode": "list", "count": 50, "entriesShown": 20, "depth": "top_level",
                                    "subfoldersNotOpened": 3, "hiddenOrSystemSkipped": 1, "entriesNotListed": 0,
                                    "readInPart": True, "entries": []}}
    told = _outcome(json.dumps(listing), read=True)
    assert ("leído en parte: sólo lo que está directamente en la carpeta: sus 3 subcarpetas no se abrieron, "
            "1 entradas ocultas o de sistema sin mirar, 30 entradas sin listar;") in told
    assert told.endswith("un «no está» vale sólo para lo leído")
    flat = {**READ, "observed": {"mode": "list", "count": 4, "depth": "top_level", "subfoldersNotOpened": 0,
                                 "hiddenOrSystemSkipped": 0, "entries": []}}
    assert "en parte" not in _outcome(json.dumps(flat), read=True)


def test_a_listing_the_observation_cut_is_a_part_even_without_the_providers_flag() -> None:
    cut = {**READ, "observed": {"mode": "list", "count": 25, "entriesShown": 20, "subfoldersNotOpened": 0,
                                "hiddenOrSystemSkipped": 0, "entries": []}}
    assert "leído en parte: 5 entradas sin listar;" in _outcome(json.dumps(cut), read=True)
